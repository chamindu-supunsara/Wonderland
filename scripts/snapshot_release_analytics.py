"""Read aggregate-only facts through the existing worker; never retrieve credentials."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("stage", choices=["before", "deployed", "rollback", "final"])
stage = parser.parse_args().stage
remote = """
import json,os
from sqlalchemy import create_engine,text
engine=create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    result={name:[dict(r) for r in conn.execute(text(sql)).mappings()] for name,sql in {
        'purchases':'SELECT * FROM reporting.mock_purchase_totals',
        'pipeline':'SELECT total_guest_arrivals,total_ride_uses,rides_awaiting_arrival,mode FROM reporting.mock_pipeline_health',
        'workers':'SELECT worker_name,heartbeat_age_seconds,mode FROM reporting.cloud_worker_health ORDER BY worker_name',
        'tls':'SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()'
    }.items()}
    print(json.dumps(result,default=str))
"""
result = subprocess.run(
    [
        str(ROOT / ".local/tools/kubectl.exe"),
        "--kubeconfig",
        str(ROOT / ".local/deployment/kubeconfig"),
        "-n",
        "wonderland",
        "exec",
        "-i",
        "deployment/wonderland-analytics-admissions",
        "--",
        "python",
        "-",
    ],
    input=remote,
    text=True,
    capture_output=True,
    timeout=60,
)
if result.returncode:
    raise SystemExit("Aggregate snapshot failed; credential-bearing errors suppressed")
facts = json.loads(result.stdout)
assert facts["tls"] == [{"ssl": True}]
assert all(r["mode"] == "MOCK" for r in facts["pipeline"] + facts["workers"])
if stage != "before":
    baseline = json.loads((ROOT / "docs/evidence/step11-analytics-before.json").read_text())[
        "facts"
    ]
    assert facts["purchases"] == baseline["purchases"] and facts["pipeline"] == baseline["pipeline"]
assert all(float(r["heartbeat_age_seconds"]) < 90 for r in facts["workers"])
report = {
    "status": "VERIFIED",
    "stage": stage,
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "facts": facts,
    "credentials_read_locally": False,
}
(ROOT / f"docs/evidence/step11-analytics-{stage}.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(json.dumps(report, indent=2))
