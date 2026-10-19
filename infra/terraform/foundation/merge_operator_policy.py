"""Validate and merge the pinned permission proposal. No AWS calls or mutations."""

import copy
import hashlib
import json
import sys
from pathlib import Path

PROPOSAL_SHA256 = "c29b57377efc1dda853886eb9032bb945180df4b430bc98a4f4c6f080d8a29c9"
# Filled from the verified deployment role; an owner-side drift check, not a secret.
CURRENT_SHA256 = "e2d967695b947e6768d74916871cbf490c447135c2ae16ce18dca15622229f70"


def canonical(policy):
    return json.dumps(policy, sort_keys=True, separators=(",", ":"))


def digest(policy):
    return hashlib.sha256(canonical(policy).encode()).hexdigest()


def merge(proposal, current):
    if digest(proposal) != PROPOSAL_SHA256:
        raise ValueError("Proposal differs from the reviewed policy; review and repin it first")
    if current.get("Version") != "2012-10-17" or not isinstance(current.get("Statement"), list):
        raise ValueError("Existing inline policy is missing or malformed")
    proposal_sids = {s["Sid"] for s in proposal["Statement"]}
    if len(proposal_sids) != len(proposal["Statement"]):
        raise ValueError("Duplicate proposal statement IDs")
    # Accept only the reviewed baseline or the identical already-merged policy.
    baseline = {**current, "Statement": [s for s in current["Statement"] if s.get("Sid") not in proposal_sids]}
    if digest(baseline) != CURRENT_SHA256:
        raise ValueError("Existing policy changed since review; stop and prepare a fresh review")
    merged = {**baseline, "Statement": baseline["Statement"] + proposal["Statement"]}
    if digest(current) not in {CURRENT_SHA256, digest(merged)}:
        raise ValueError("Existing foundation statements differ from the reviewed proposal")
    size = len(json.dumps(merged, separators=(",", ":")).encode())
    if size > 10240:
        raise ValueError(f"Merged inline policy is {size} bytes; exceeds 10,240-byte limit")
    return copy.deepcopy(merged)


def main():
    proposal_path, current_path, output_path = map(Path, sys.argv[1:])
    proposal = json.loads(proposal_path.read_text(encoding="utf-8-sig"))
    envelope = json.loads(current_path.read_text(encoding="utf-8-sig"))
    current = json.loads(envelope.get("InlinePolicy") or "{}")
    merged = merge(proposal, current)
    output_path.write_text(json.dumps(merged, separators=(",", ":")), encoding="utf-8")
    print(f"Validated reviewed proposal; merged bytes: {output_path.stat().st_size}; SHA256: {digest(merged)}")


if __name__ == "__main__":
    main()
