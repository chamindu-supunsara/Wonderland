"""Create and validate a mock release manifest. No credentials belong in artifacts."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ("catalog", "booking", "payment", "admission", "analytics")
REGISTRY = "708919751353.dkr.ecr.ap-south-1.amazonaws.com/wonderland-demo"
REPOSITORY = "chamindu-supunsara/Wonderland"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_sources():
    paths = list((ROOT / "deploy/helm/wonderland").rglob("*"))
    paths += list((ROOT / "deploy/helm/metabase").rglob("*"))
    for service in SERVICES:
        paths += list((ROOT / f"services/{service}/alembic").rglob("*.py"))
    return {p.relative_to(ROOT).as_posix():
            hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for p in sorted(paths) if p.is_file()}


def validate(manifest, folder):
    if manifest.get("schema") != 1 or manifest.get("mode") != "MOCK":
        raise ValueError("Only schema 1 MOCK releases are supported")
    if manifest.get("repository") != REPOSITORY or manifest.get("branch") != "main":
        raise ValueError("Unexpected release repository or branch")
    if not re.fullmatch(r"[a-f0-9]{40}", manifest.get("commit", "")):
        raise ValueError("A full source commit is required")
    if set(manifest.get("images", {})) != set(SERVICES):
        raise ValueError("Exactly five service images are required")
    for service, image in manifest["images"].items():
        if not re.fullmatch(re.escape(f"{REGISTRY}/{service}@sha256:") + r"[a-f0-9]{64}", image):
            raise ValueError("Unexpected repository or mutable image")
    if manifest.get("protected_sources") != protected_sources():
        raise ValueError("Local chart/migration source differs from release")
    baseline = json.loads((ROOT / "deploy/automation/contract.json").read_text())
    if manifest["protected_sources"] != baseline["protected_sources"]:
        raise ValueError("Chart/schema changes require a separate reviewed migration rollout")
    if sha(Path(folder) / "frontend.zip") != manifest.get("frontend_sha256"):
        raise ValueError("Frontend checksum mismatch")
    with ZipFile(Path(folder) / "frontend.zip") as archive:
        names = archive.namelist()
        if "index.html" not in names or "app-config.json" not in names:
            raise ValueError("Incomplete frontend artifact")
        if any(n.startswith(("/", "\\")) or ".." in Path(n).parts for n in names):
            raise ValueError("Unsafe frontend archive path")
        expected = json.loads((ROOT / "deploy/automation/public-app-config.json").read_text())
        if json.loads(archive.read("app-config.json")) != expected:
            raise ValueError("Unexpected frontend target or Cognito settings")
    return manifest


def package(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    dist = ROOT / "frontend/dist/wonderland/browser"
    config = (ROOT / "deploy/automation/public-app-config.json").read_bytes()
    with ZipFile(output / "frontend.zip", "w", ZIP_DEFLATED) as archive:
        for path in sorted(dist.rglob("*")):
            if path.is_file() and path.name != "app-config.json":
                archive.write(path, path.relative_to(dist).as_posix())
        archive.writestr("app-config.json", config)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    images = json.loads((output / "images.json").read_text())
    manifest = {"schema": 1, "mode": "MOCK", "repository": REPOSITORY, "branch": "main",
                "commit": commit, "run_id": os.environ["GITHUB_RUN_ID"],
                "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"], "images": images,
                "frontend_sha256": sha(output / "frontend.zip"),
                "protected_sources": protected_sources()}
    validate(manifest, output)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "images.json").unlink()
    print("MOCK release packaged for commit " + commit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    package(parser.parse_args().output)
