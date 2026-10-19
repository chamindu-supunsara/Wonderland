"""Read-only, bounded CloudFormation monitoring with local experiment evidence."""

import argparse
import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime

import cloud_feasibility as cloud


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="wonderland-feasibility")
    parser.add_argument("--phase", default="attempt3")
    parser.add_argument("--seconds", type=int, default=0)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.phase) or not 0 <= args.seconds <= 45:
        parser.error("phase must be a simple label and seconds must be between 0 and 45")
    os.environ.update(
        AWS_CONFIG_FILE=str(cloud.ROOT / ".local/aws/config"),
        AWS_LOGIN_CACHE_DIRECTORY=str(cloud.ROOT / ".local/aws/login/cache"),
        AWS_EC2_METADATA_DISABLED="true",
    )
    cloud.identity(args.profile)
    seen_path = cloud.STATE / f"{args.phase}-seen.json"
    seen = set(json.loads(seen_path.read_text())) if seen_path.exists() else set()
    deadline = time.monotonic() + args.seconds
    while True:
        try:
            stack = cloud.aws(
                args.profile, "cloudformation", "describe-stacks", "--stack-name", cloud.STACK
            )["Stacks"][0]
        except RuntimeError as error:
            if "does not exist" not in str(error):
                raise
            cloud.save(
                f"{args.phase}-absence.json",
                {"checked_at": datetime.now(UTC).isoformat(), "stack": "ABSENT"},
            )
            print("Stack: ABSENT", flush=True)
            return
        events = cloud.aws(
            args.profile,
            "cloudformation",
            "describe-stack-events",
            "--stack-name",
            stack["StackId"],
        )["StackEvents"]
        cloud.save(f"{args.phase}-stack.json", stack)
        cloud.save(f"{args.phase}-events.json", events)
        latest = {}
        for event in events:
            latest.setdefault(event["LogicalResourceId"], event["ResourceStatus"])
        counts = dict(Counter(latest.values()))
        print(
            json.dumps(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "stack": stack["StackStatus"],
                    "resource_states": counts,
                }
            ),
            flush=True,
        )
        new = [event for event in events if event["EventId"] not in seen]
        important = [e for e in new if e["ResourceStatus"].endswith("FAILED")]
        for event in important or new[:5]:
            print(
                event["LogicalResourceId"],
                event["ResourceStatus"],
                event.get("ResourceStatusReason", ""),
                flush=True,
            )
        seen.update(event["EventId"] for event in events)
        cloud.save(f"{args.phase}-seen.json", sorted(seen))
        if (
            stack["StackStatus"]
            in {
                "CREATE_COMPLETE",
                "CREATE_FAILED",
                "ROLLBACK_COMPLETE",
                "ROLLBACK_FAILED",
                "DELETE_COMPLETE",
                "DELETE_FAILED",
            }
            or time.monotonic() >= deadline
        ):
            return
        time.sleep(min(15, max(0, deadline - time.monotonic())))


if __name__ == "__main__":
    main()
