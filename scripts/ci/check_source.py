"""Reject credential artifacts before publishing; print only offending file paths."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    )
    blocked = set()
    for raw in output.decode().split("\0"):
        if not raw:
            continue
        path = Path(raw)
        if (raw.startswith((".local/", "docs/evidence/", ".aws/", ".terraform/"))
                or path.name in {".env", "terraform.tfstate", "terraform.tfvars"}
                or path.suffix in {".tfplan", ".key"}
                or (path.suffix == ".pem" and raw != "deploy/certs/rds-global-bundle.pem")):
            blocked.add(raw)
            continue
        data = (ROOT / path).read_bytes()
        patterns = [rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
                    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                    rb"gh[pousr]_[A-Za-z0-9]{30,}"]
        if any(re.search(pattern, data) for pattern in patterns):
            blocked.add(raw)
    if blocked:
        print("SOURCE_REVIEW_REQUIRED: " + ", ".join(sorted(blocked)))
        return 1
    print("Source publication checks passed; local credentials/state/raw evidence excluded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
