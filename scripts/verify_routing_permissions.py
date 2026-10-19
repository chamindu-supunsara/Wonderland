"""Verify the owner-provisioned managed policy and unchanged inline baseline."""
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import boto3

root = Path(__file__).resolve().parents[1]
session = boto3.Session(profile_name='wonderland-feasibility', region_name='ap-south-1')
identity = session.client('sts').get_caller_identity()
assert identity['Account'] == '708919751353' and ':assumed-role/AWSReservedSSO_WonderlandFeasibility_' in identity['Arn']
iam = session.client('iam')
role = identity['Arn'].split('/')[1]
arn = 'arn:aws:iam::708919751353:policy/WonderlandRoutingDeployment'
attached = iam.list_attached_role_policies(RoleName=role)['AttachedPolicies']
assert arn in [p['PolicyArn'] for p in attached], 'Workload deployment policy has not been provisioned'
policy = iam.get_policy(PolicyArn=arn)['Policy']
actual = iam.get_policy_version(PolicyArn=arn, VersionId=policy['DefaultVersionId'])['PolicyVersion']['Document']
expected = json.loads((root / 'infra/terraform/routing/operator-policy.json').read_text())
assert expected == actual, 'Unreviewed deployment policy contents'
baseline = session.client('sso-admin').get_inline_policy_for_permission_set(
    InstanceArn='arn:aws:sso:::instance/ssoins-65954bc9fbd03036',
    PermissionSetArn='arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026')
spec = importlib.util.spec_from_file_location('guard', root / 'infra/terraform/routing/verify_access.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
guard.verify(root / 'infra/terraform/routing', baseline)
report = {'status': 'VERIFIED', 'account': identity['Account'], 'operator_role': role, 'managed_policy_arn': arn,
          'reviewed_policy_attached': True, 'policy_contents_match': True, 'existing_inline_unchanged': True,
          'password_read_access_added': False, 'verified_at_utc': datetime.now(timezone.utc).isoformat()}
(root / 'docs/evidence/step10d-live-permissions.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
