"""Pin the operator-IP repair and refresh workload-plan hashes before approval."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/deployment'
plan = json.loads((LOCAL / 'step10c-operator-ip-plan.json').read_text(encoding='utf-8-sig'))
changes = [r for r in plan['resource_changes'] if r['change']['actions'] != ['no-op']]
assert len(changes) == 1 and changes[0]['address'] == 'aws_eks_cluster.main'
change = changes[0]['change']
assert change['actions'] == ['update']
before, after = change['before'], change['after']
assert before['vpc_config'][0]['public_access_cidrs'] == ['112.134.222.147/32']
assert after['vpc_config'][0]['public_access_cidrs'] == ['112.134.219.72/32']
normalized = json.loads(json.dumps(after))
normalized['vpc_config'][0]['public_access_cidrs'] = before['vpc_config'][0]['public_access_cidrs']
# Provider-computed outputs may become unknown; all explicitly changed values are checked.
assert all(normalized.get(k) == value for k, value in before.items() if k in normalized and normalized[k] is not None), 'Unexpected additional cluster changes'
report = {'status': 'REVIEWED_NOT_APPLIED', 'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
          'resources_to_add': 0, 'resources_to_change': 1, 'resources_to_destroy': 0,
          'cluster': 'wonderland-demo', 'old_operator_cidr': before['vpc_config'][0]['public_access_cidrs'],
          'new_operator_cidr': after['vpc_config'][0]['public_access_cidrs'],
          'plan_sha256': hashlib.sha256((LOCAL / 'step10c-operator-ip.tfplan').read_bytes()).hexdigest(),
          'additional_capacity': 0, 'checkout': 'mock'}
(ROOT / 'docs/evidence/step10c-operator-ip-review.json').write_text(json.dumps(report, indent=2) + '\n')
workloads = json.loads((LOCAL / 'step10c-workloads-plan.json').read_text(encoding='utf-8-sig'))
managed = [r for r in workloads['resource_changes'] if r['mode'] == 'managed']
assert len(managed) == 45 and all(r['change']['actions'] == ['create'] for r in managed)
path = ROOT / 'docs/evidence/step10c-workloads-plan.json'
value = json.loads(path.read_text())
value['plan_sha256'] = hashlib.sha256((LOCAL / 'step10c-workloads.tfplan').read_bytes()).hexdigest()
value['terraform_sources_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted((ROOT / 'infra/terraform/workloads').glob('*.tf'))}
value['status'] = 'FRESH_PLAN_CAPACITY_REFRESH_PENDING_OPERATOR_IP_REPAIR'
value['plan_refreshed_at_utc'] = report['reviewed_at_utc']
value['capacity_snapshot_fresh'] = False
value['capacity_gate'] = 'Must refresh Kubernetes node/Pod data and pass review_workloads.py after the approved /32 repair, before workload apply.'
path.write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps(report, indent=2))
