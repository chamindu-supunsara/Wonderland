"""Exercise release boundaries without GitHub, AWS credentials or a cluster."""

import copy
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_manifest", ROOT / "scripts/ci/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def manifest(tmp_path):
    with ZipFile(tmp_path / "frontend.zip", "w") as archive:
        archive.writestr("index.html", "<html>Mock release</html>")
        archive.writestr(
            "app-config.json", (ROOT / "deploy/automation/public-app-config.json").read_bytes()
        )
    return {
        "schema": 1,
        "mode": "MOCK",
        "repository": release.REPOSITORY,
        "branch": "main",
        "commit": "a" * 40,
        "images": {
            service: f"{release.REGISTRY}/{service}@sha256:{'b' * 64}"
            for service in release.SERVICES
        },
        "protected_sources": release.protected_sources(),
        "frontend_sha256": release.sha(tmp_path / "frontend.zip"),
    }


def test_complete_mock_release_is_accepted(manifest, tmp_path):
    assert release.validate(manifest, tmp_path) == manifest


@pytest.mark.parametrize(
    "change", ["live", "branch", "foreign_repo", "mutable", "missing", "chart"]
)
def test_rejects_release_boundary_changes(manifest, tmp_path, change):
    bad = copy.deepcopy(manifest)
    if change == "live":
        bad["mode"] = "LIVE"
    elif change == "branch":
        bad["branch"] = "feature"
    elif change == "foreign_repo":
        bad["images"]["catalog"] = f"evil.invalid/catalog@sha256:{'b' * 64}"
    elif change == "mutable":
        bad["images"]["catalog"] = f"{release.REGISTRY}/catalog:latest"
    elif change == "missing":
        del bad["images"]["analytics"]
    else:
        bad["protected_sources"]["deploy/helm/wonderland/values.yaml"] = "0" * 64
    with pytest.raises(ValueError):
        release.validate(bad, tmp_path)


def test_frontend_tampering_and_traversal_are_rejected(manifest, tmp_path):
    with ZipFile(tmp_path / "frontend.zip", "a") as archive:
        archive.writestr("../outside", "unsafe")
    with pytest.raises(ValueError, match="checksum"):
        release.validate(manifest, tmp_path)
    manifest["frontend_sha256"] = release.sha(tmp_path / "frontend.zip")
    with pytest.raises(ValueError, match="Unsafe"):
        release.validate(manifest, tmp_path)


def test_oidc_grant_has_exact_main_subject_and_existing_registry_scope():
    template = json.loads((ROOT / "infra/automation/github-release-access.json").read_text())
    role = template["Resources"]["ReleaseRole"]["Properties"]
    trust = role["AssumeRolePolicyDocument"]["Statement"][0]
    assert trust["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert trust["Condition"] == {
        "StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": (
                "repo:chamindu-supunsara/Wonderland:ref:refs/heads/main"
            ),
        }
    }
    statements = role["Policies"][0]["PolicyDocument"]["Statement"]
    assert statements[0]["Action"] == "ecr:GetAuthorizationToken"
    assert len(statements[1]["Resource"]) == 5
    assert all(action.startswith("ecr:") for action in statements[1]["Action"])
    assert not any("*" in resource for resource in statements[1]["Resource"])
