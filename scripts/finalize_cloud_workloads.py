"""Finalize the deployment record after live checks and Terraform drift checks pass."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/deployment'
EVIDENCE = ROOT / 'docs/evidence'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


live = load(EVIDENCE / 'step10c-live-verification.json')
assert live['status'] == 'VERIFIED' and all(live['checks'].values())
post = load(LOCAL / 'step10c-workloads-post.json')
assert all(r['change']['actions'] == ['no-op'] for r in post.get('resource_changes', []))
state = (LOCAL / 'step10c-state-list.txt').read_text(encoding='utf-8-sig').splitlines()
managed_state = [address for address in state if address and not address.startswith('data.')]
assert len(managed_state) == 45
assert 'no changes are needed' in (LOCAL / 'step10c-foundation-post.txt').read_text(encoding='utf-8-sig')
session = boto3.Session(profile_name='wonderland-feasibility', region_name='ap-south-1')
head = session.client('s3').head_object(Bucket='wonderland-tfstate-708919751353-ap-south-1', Key='demo/workloads/terraform.tfstate')
assert head.get('VersionId') and head.get('ServerSideEncryption')
sources = list((ROOT / 'infra/terraform/workloads').glob('*.tf')) + list((ROOT / 'deploy/helm/wonderland').rglob('*'))
sources += list((ROOT / 'services').glob('*/Dockerfile'))
report = {'status': 'APPLIED_AND_VERIFIED', 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
          'managed_workload_resources': 45, 'state_entries_including_data_sources': len(state), 'initial_apply_created': 42, 'repair_apply_created': 3,
          'repair': 'SNS resource policies require explicit topic actions; service-wide wildcard was rejected. Only three missing policies were applied.',
          'workload_post_apply_plan': 'NO_CHANGES', 'foundation_post_ip_repair_plan': 'NO_CHANGES',
          'state_bucket': 'wonderland-tfstate-708919751353-ap-south-1', 'state_key': 'demo/workloads/terraform.tfstate',
          'state_encryption': head['ServerSideEncryption'], 'state_version_id': head['VersionId'],
          'sources_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file()},
          'checkout': 'mock', 'planning_model_usd': 54.41, 'allowance_usd': 75,
          'actual_bill_verified': False, 'cleanup_target': '2026-10-25T18:00:00+05:30',
          'next_stage': '10D private routing/API Gateway/Angular hosting'}
(EVIDENCE / 'step10c-deployment.json').write_text(json.dumps(report, indent=2) + '\n')
for name, status in [('step10c-workloads-plan.json', 'APPLIED_WITH_REVIEWED_SNS_REPAIR_AND_VERIFIED'),
                     ('step10c-workloads-resume-plan.json', 'APPLIED_AND_VERIFIED'),
                     ('step10c-operator-ip-review.json', 'APPLIED_AND_VERIFIED'),
                     ('step10c-access-review.json', 'PROVISIONED_AND_CLI_VERIFIED'),
                     ('step10c-access-bundle.json', 'UPLOADED_CHECKSUM_VERIFIED_AND_APPLIED')]:
    path = EVIDENCE / name
    value = load(path)
    value.update(status=status, completed_at_utc=report['completed_at_utc'])
    path.write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'sources_sha256'}, indent=2))
