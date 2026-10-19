#!/usr/bin/env bash
# Owner/setup session. --prepare does not mutate; --apply requires reviewed access approval.
set -euo pipefail
mode=${1:---prepare}
case "$mode" in --prepare|--apply|--remove-bootstrap) ;; *) exit 1 ;; esac
account=708919751353
region=ap-south-1
instance=arn:aws:sso:::instance/ssoins-65954bc9fbd03036
permission_set=arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026
stack=wonderland-db-bootstrap-access
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
test "$(aws sts get-caller-identity --query Account --output text)" = "$account"
caller=$(aws sts get-caller-identity --query Arn --output text)
case "$caller" in *AWSReservedSSO_WonderlandFeasibility*|*AWSReservedSSO_WonderlandReadOnly*) echo 'Use the owner/setup administrator session.' >&2; exit 1 ;; esac
test "$(aws sso-admin describe-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --query PermissionSet.Name --output text)" = WonderlandFeasibility
task_dir=$(mktemp -d "$HOME/wonderland-step10b-access.XXXXXX")
chmod 700 "$task_dir"
printf 'Evidence directory: %s\n' "$task_dir"
aws sso-admin get-inline-policy-for-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --output json > "$task_dir/before.json"
python3 - "$script_dir" "$task_dir" <<'PY'
import hashlib,json,sys
from pathlib import Path
source,output=map(Path,sys.argv[1:])
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
new=json.loads((source/'operator-policy.json').read_text())
template=json.loads((source/'bootstrap-access.json').read_text())
assert digest(new)=='3a2a3e9360b12b553a385c2fb61a30358d783372cfdbf92c00eada634fe70eba','Unreviewed operator policy'
assert digest(template)=='6cd7d80c746dc4ed09ea1da1d3c8dce1694d5b63cef89ff9641c1d2aa86e7b4e','Unreviewed bootstrap template'
old=json.loads(json.loads((output/'before.json').read_text())['InlinePolicy'])
base={**old,'Statement':[s for s in old['Statement'] if s.get('Sid')!='DatabaseBootstrapImagePush']}
assert digest(base)=='1cb5017593ad6b19334967a11b0f843c814578fc4ab5fd5ac480106c4c6e91c9','Existing policy drift; stop and review'
merged={**base,'Statement':base['Statement']+new['Statement']}
assert digest(old) in {digest(base),digest(merged)},'Unreviewed image-push permissions'
encoded=json.dumps(merged,separators=(',',':'))
assert len(encoded.encode())<=10240,'Inline size limit exceeded'
(output/'merged.json').write_text(encoded)
(output/'bootstrap-role-policy.json').write_text(json.dumps(template['Resources']['BootstrapRole']['Properties']['Policies'][0]['PolicyDocument']))
print('Reviewed ECR-only operator addition; merged bytes:',len(encoded.encode()))
PY
if test "$mode" = --remove-bootstrap; then
  aws cloudformation get-template --stack-name "$stack" --region "$region" --output json > "$task_dir/current-template.json"
  python3 - "$script_dir/bootstrap-access.json" "$task_dir/current-template.json" <<'PY'
import json,sys
expected=json.load(open(sys.argv[1])); actual=json.load(open(sys.argv[2]))['TemplateBody']
if isinstance(actual,str):actual=json.loads(actual)
assert expected==actual,'Unexpected stack contents; do not delete'
PY
  aws cloudformation delete-stack --stack-name "$stack" --region "$region"
  aws cloudformation wait stack-delete-complete --stack-name "$stack" --region "$region"
  echo 'SUCCEEDED: temporary bootstrap IAM role/Pod Identity removed; database and credentials preserved.'
  exit 0
fi
for document in merged bootstrap-role-policy; do
  aws accessanalyzer validate-policy --policy-type IDENTITY_POLICY --policy-document "file://$task_dir/$document.json" --region "$region" --output json > "$task_dir/$document-validation.json"
done
python3 - "$task_dir" <<'PY'
import json,sys
from pathlib import Path
for path in Path(sys.argv[1]).glob('*-validation.json'):
    findings=json.loads(path.read_text())['findings']
    if findings:raise SystemExit('Policy findings require review: '+json.dumps(findings))
print('AWS Access Analyzer: zero findings for both identity policies.')
PY
aws cloudformation validate-template --template-body "file://$script_dir/bootstrap-access.json" --region "$region" > "$task_dir/template-validation.json"
if test "$mode" = --prepare; then
  echo 'PREPARED ONLY: no access changed, no secret values read and no bootstrap workload run.'
  exit 0
fi
aws sso-admin get-inline-policy-for-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --output json > "$task_dir/recheck.json"
python3 - "$task_dir" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
assert json.loads(json.loads((p/'before.json').read_text())['InlinePolicy'])==json.loads(json.loads((p/'recheck.json').read_text())['InlinePolicy']),'Policy changed during validation'
PY
aws sso-admin put-inline-policy-to-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --inline-policy "file://$task_dir/merged.json" --region "$region"
request_id=$(aws sso-admin provision-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --target-type AWS_ACCOUNT --target-id "$account" --region "$region" --query PermissionSetProvisioningStatus.RequestId --output text)
printf 'Provisioning request: %s\n' "$request_id"
provisioned=false
for attempt in $(seq 1 20); do
  status=$(aws sso-admin describe-permission-set-provisioning-status --instance-arn "$instance" --provision-permission-set-request-id "$request_id" --region "$region" --query PermissionSetProvisioningStatus.Status --output text)
  case "$status" in SUCCEEDED) provisioned=true; break ;; FAILED) echo 'Account provisioning failed; inspect request.' >&2; exit 1 ;; esac
  sleep 3
done
test "$provisioned" = true
aws cloudformation deploy --template-file "$script_dir/bootstrap-access.json" --stack-name "$stack" --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset --region "$region" --tags Project=Wonderland Environment=demo Purpose=temporary-db-bootstrap
echo 'SUCCEEDED: Step10B ECR upload access and temporary scoped bootstrap identity ready; no database job run.'
