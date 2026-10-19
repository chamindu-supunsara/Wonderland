"""Prepare an exact-app correction to the already approved main-branch deployment grant."""
import hashlib
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
directory = root / 'infra/terraform/routing'
policy_path = directory / 'operator-policy.json'
old = json.loads(policy_path.read_text())
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
old_hash = digest(old)
assert old_hash == '7f5e7c4b2fc27482848212a0fea3dd4e28c219813c99c8c880e7f62ec76dc7b1'
policy = json.loads(json.dumps(old))
statement = next(s for s in policy['Statement'] if s['Sid'] == 'MainBranchDeployment')
statement['Resource'].append('arn:aws:amplify:ap-south-1:708919751353:apps/d3vt08cs3xnlse/branches/main/deployments/*')
new_hash = digest(policy)
policy_path.write_text(json.dumps(policy, indent=2) + '\n')
guard = directory / 'verify_access.py'
guard.write_text(guard.read_text().replace(old_hash, new_hash))
helper = '''"""Owner-only, hash-pinned repair of the approved frontend deployment grant."""
import hashlib,json,sys,time
from pathlib import Path
import boto3
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
session=boto3.Session(region_name='ap-south-1')
identity=session.client('sts').get_caller_identity()
assert identity['Account']=='708919751353'
assert 'AWSReservedSSO_WonderlandFeasibility' not in identity['Arn']
assert 'AWSReservedSSO_WonderlandReadOnly' not in identity['Arn']
iam=session.client('iam'); sso=session.client('sso-admin')
arn='arn:aws:iam::708919751353:policy/WonderlandRoutingDeployment'
instance='arn:aws:sso:::instance/ssoins-65954bc9fbd03036'
permission_set='arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026'
version=iam.get_policy(PolicyArn=arn)['Policy']['DefaultVersionId']
before=iam.get_policy_version(PolicyArn=arn,VersionId=version)['PolicyVersion']['Document']
after=json.loads(Path(__file__).with_name('operator-policy.json').read_text())
assert digest(before)==%r,'Live policy changed; stop'
assert digest(after)==%r,'Repair file changed; stop'
baseline=json.loads(sso.get_inline_policy_for_permission_set(InstanceArn=instance,PermissionSetArn=permission_set)['InlinePolicy'])
assert digest(baseline)=='df08dc3dca6cd21b3caba59204eea7d3e0307fe6501327ce8715603f53e84559'
findings=session.client('accessanalyzer').validate_policy(policyDocument=json.dumps(after),policyType='IDENTITY_POLICY')['findings']
assert not findings,findings
print('Validated: only exact app main/deployments ARN added; inline baseline unchanged; zero findings.',flush=True)
if '--apply' not in sys.argv: sys.exit(0)
result=iam.create_policy_version(PolicyArn=arn,PolicyDocument=json.dumps(after),SetAsDefault=True)
print('Policy version:',result['PolicyVersion']['VersionId'],flush=True)
request=sso.provision_permission_set(InstanceArn=instance,PermissionSetArn=permission_set,TargetType='AWS_ACCOUNT',TargetId='708919751353')['PermissionSetProvisioningStatus']['RequestId']
for _ in range(60):
    status=sso.describe_permission_set_provisioning_status(InstanceArn=instance,ProvisionPermissionSetRequestId=request)['PermissionSetProvisioningStatus']
    if status['Status']=='SUCCEEDED':
        print('SUCCEEDED: exact-app frontend deployment correction provisioned.',flush=True);break
    assert status['Status']!='FAILED',status
    time.sleep(3)
else: raise RuntimeError('Provisioning timeout; inspect request '+request)
'''
(directory / 'repair-deployment-access.py').write_text(helper % (old_hash, new_hash))
bundle = root / '.local/deployment/step10d-deployment-repair.zip'
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
    for name in ['operator-policy.json', 'repair-deployment-access.py']:
        archive.write(directory / name, name)
report = {'old_policy_sha256': old_hash, 'new_policy_sha256': new_hash,
          'bundle_sha256': hashlib.sha256(bundle.read_bytes()).hexdigest(),
          'change': 'Add deployment-specific ARN for existing Amplify app d3vt08cs3xnlse main branch only',
          'status': 'PREPARED'}
(root / 'docs/evidence/step10d-deployment-access-repair.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
