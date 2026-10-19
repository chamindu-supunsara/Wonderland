"""Worker progress marker: updated only after a successful database/AWS poll."""

import os
import time
from pathlib import Path


def heartbeat():
    if os.environ.get("WORKER_HEARTBEAT_ENABLED") == "true":
        Path("/tmp/worker-heartbeat").touch()


def main():
    marker = Path("/tmp/worker-heartbeat")
    if not marker.exists() or time.time() - marker.stat().st_mtime > 120:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
