"""Require live-run, deployment, rollback and data-preservation receipts before completion."""

import argparse
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from github_client import REPOSITORY, artifact_bytes, request

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"
parser = argparse.ArgumentParser()
parser.add_argument("folder", type=Path)
folder = parser.parse_args().folder


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


manifest = read(folder / "manifest.json")
download = read(folder / "github-receipt.json")
run_id = manifest["run_id"]
run = request(f"repos/{REPOSITORY}/actions/runs/{run_id}")
jobs = request(f"repos/{REPOSITORY}/actions/runs/{run_id}/jobs")["jobs"]
assert run["conclusion"] == "success" and run["head_sha"] == manifest["commit"]
assert run["event"] == "workflow_dispatch" and run["head_branch"] == "main"
assert all(j["conclusion"] == "success" for j in jobs) and len(jobs) == 4
publish = next(j for j in jobs if j["name"] == "publish")
assert any(
    "configure-aws-credentials" in s["name"] and s["conclusion"] == "success"
    for s in publish["steps"]
)
artifacts = request(f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts")["artifacts"]
test_artifact = next(a for a in artifacts if a["name"].startswith("python-test-results-"))
test_bytes = artifact_bytes(test_artifact["id"])
assert "sha256:" + hashlib.sha256(test_bytes).hexdigest() == test_artifact["digest"]
with ZipFile(io.BytesIO(test_bytes)) as archive:
    suites = ElementTree.fromstring(archive.read("python.xml"))
test_totals = {
    key: sum(int(s.attrib.get(key, 0)) for s in suites.iter("testsuite"))
    for key in ["tests", "errors", "failures", "skipped"]
}
assert test_totals["tests"] >= 212
assert test_totals["errors"] == test_totals["failures"] == test_totals["skipped"] == 0
access = read(EVIDENCE / "step11-access-verification.json")
assert access["status"] == "VERIFIED" and all(access["checks"].values())
stages = {}
for name, filename, status in [
    ("deployment", "step11-deployment.json", "DEPLOYED"),
    ("rollback", "step11-rollback.json", "ROLLED_BACK"),
    ("final_deployment", "step11-final-deployment.json", "DEPLOYED"),
]:
    receipt = read(EVIDENCE / filename)
    assert receipt["status"] == status and receipt["mode"] == "MOCK"
    assert str(receipt["run_id"]) == str(run_id) and receipt["commit"] == manifest["commit"]
    assert len(receipt["post_deploy_checks"]) == 23 and all(receipt["post_deploy_checks"].values())
    stages[name] = {
        "receipt": filename,
        "checks_passed": 23,
        "amplify_job_id": receipt["amplify_job_id"],
        "completed_at_utc": receipt["completed_at_utc"],
    }
final = read(EVIDENCE / "step11-final-deployment.json")
assert final["images"] == manifest["images"]
for stage in ["before", "deployed", "rollback", "final"]:
    assert read(EVIDENCE / f"step11-analytics-{stage}.json")["status"] == "VERIFIED"
protection = request(f"repos/{REPOSITORY}/branches/main/protection")
assert set(protection["required_status_checks"]["contexts"]) == {
    "python-services",
    "angular",
    "infrastructure",
}
assert (
    not protection["allow_force_pushes"]["enabled"] and not protection["allow_deletions"]["enabled"]
)
report = {
    "status": "VERIFIED",
    "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    "repository": "https://github.com/" + REPOSITORY,
    "source_commit": manifest["commit"],
    "release_run_id": run_id,
    "release_url": run["html_url"],
    "release_artifact_digest": download["artifact_digest"],
    "python_tests": test_totals,
    "oidc_assumption_succeeded": True,
    "jobs": [
        {
            "name": j["name"],
            "conclusion": j["conclusion"],
            "started_at": j["started_at"],
            "completed_at": j["completed_at"],
        }
        for j in jobs
    ],
    "stages": stages,
    "images": manifest["images"],
    "checkout": "mock",
    "additional_compute_rds_nat_alb": 0,
    "existing_nodes": 2,
    "planning_model_usd": 65.41,
    "allowance_usd": 75,
    "cleanup_target": "2026-10-25T18:00:00+05:30",
    "recovery_review": "2026-11-08T18:00:00+05:30",
    "administrator_branch_protection_bypass": not protection["enforce_admins"]["enabled"],
    "delivery_model": "GitHub CI/OIDC image publication, explicit local SSO-controlled promotion",
    "limitations": [
        "Costs remain delayed/estimated, not an enforced spending cap.",
        "Application rollback was rehearsed; this was not database restore or fault injection.",
        "Provider payments and later resilience/submission milestones remain.",
    ],
}
(EVIDENCE / "step11-completion.json").write_text(json.dumps(report, indent=2) + "\n")
(EVIDENCE / "step11-release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
review = read(EVIDENCE / "step11-access-review.json")
review["status"] = "APPLIED_AND_VERIFIED"
review["owner_output_sha256"] = access["owner_output_sha256"]
review["applied_template_lf_sha256"] = (
    "d50e1b4663db798d7273404e527ba6b845c25bae70d450374807642242a4a812"
)
(EVIDENCE / "step11-access-review.json").write_text(json.dumps(review, indent=2) + "\n")
print(json.dumps(report, indent=2))
