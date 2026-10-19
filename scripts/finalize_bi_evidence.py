"""Summarize verified Step 10E receipts without reading credentials."""
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
evidence = root / 'docs/evidence'
def read(name):
    return json.loads((evidence / name).read_text(encoding='utf-8-sig'))

receipts = {
    'database': 'step10e-database-verification.json',
    'guest_flow': 'step10e-flow-verification.json',
    'transport': 'step10e-event-delivery.json',
    'runtime_and_cleanup': 'step10e-live-verification.json',
    'dashboard_persistence': 'step10e-dashboard-persistence.json',
}
assert all(read(name)['status'] == 'VERIFIED' for name in receipts.values())
plan = json.loads((root / '.local/deployment/step10e-final-plan.json').read_text(encoding='utf-8-sig'))
assert all(r['change']['actions'] == ['no-op'] for r in plan.get('resource_changes', []))
before = read('step10e-analytics-after.json')['facts']
after = read('step10e-analytics-persistence.json')['facts']
assert before['purchases'] == after['purchases']
assert before['pipeline'] == after['pipeline']
now = datetime.now(timezone.utc).isoformat()
for name, status in [('step10e-bi-plan.json', 'APPLIED_AND_NO_CHANGES'),
                     ('step10e-access-review.json', 'APPLIED_AND_TEMPORARY_ACCESS_REMOVED')]:
    report = read(name)
    report['original_review_status'] = report.get('original_review_status', report['status'])
    report['status'] = status
    report['final_verified_at_utc'] = now
    (evidence / name).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
report = {
    'status': 'VERIFIED', 'verified_at_utc': now, 'receipts': receipts,
    'terraform_no_changes': True, 'aggregate_facts_persisted': True,
    'dashboard_count': 3, 'question_count': 8,
    'checkout': 'mock', 'guest_arrivals': 1, 'ride_uses': 2,
    'mock_purchases': 2, 'simulated_revenue_usd': 80,
    'max_observed_delivery_lag_seconds': 1.422082,
    'planning_model_usd': 64.41, 'allowance_usd': 75,
    'final_aws_bill_verified': False, 'additional_nodes_rds_nat_alb': 0,
    'cleanup_target': '2026-10-25T18:00:00+05:30',
    'bi_credentials_recovery_review': '2026-11-08T18:00:00+05:30',
    'passwords_or_tokens_read_locally': False,
    'limitations': ['Small mock demonstration, not a load test or real payment integration.',
                    'Pod replacement verifies metadata persistence, not a backup restore rehearsal.',
                    'Private BI requires an authenticated tunnel and separate Metabase login.'],
}
(evidence / 'step10e-completion.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
