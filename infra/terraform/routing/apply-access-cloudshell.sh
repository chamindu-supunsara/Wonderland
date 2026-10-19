#!/usr/bin/env bash
# Owner/setup only. Creates no EKS/RDS/NAT resources; --apply requires reviewed approval.
set -euo pipefail
export AWS_PAGER=""
mode=${1:---prepare}
case "$mode" in --prepare|--apply) ;; *) exit 1 ;; esac
account=708919751353
region=ap-south-1
instance=arn:aws:sso:::instance/ssoins-65954bc9fbd03036
permission_set=arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026
policy_name=WonderlandRoutingDeployment
policy_arn="arn:aws:iam::$account:policy/$policy_name"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
test "$(aws sts get-caller-identity --query Account --output text)" = "$account"
caller=$(aws sts get-caller-identity --query Arn --output text)
case "$caller" in *AWSReservedSSO_WonderlandFeasibility*|*AWSReservedSSO_WonderlandReadOnly*) echo 'Use the owner/setup administrator session.' >&2; exit 1 ;; esac
test "$(aws sso-admin describe-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --query PermissionSet.Name --output text)" = WonderlandFeasibility
task_dir=$(mktemp -d "$HOME/wonderland-step10d-access.XXXXXX")
chmod 700 "$task_dir"
echo "Evidence directory: $task_dir"
aws sso-admin get-inline-policy-for-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" > "$task_dir/inline-before.json"
python3 "$script_dir/verify_access.py" "$script_dir" "$task_dir/inline-before.json"
aws accessanalyzer validate-policy --policy-type IDENTITY_POLICY --policy-document "file://$script_dir/operator-policy.json" --region "$region" > "$task_dir/validation.json"
python3 - "$task_dir/validation.json" <<'PY'
import json,sys
assert not json.load(open(sys.argv[1]))['findings'],'Policy findings require review'
print('Access Analyzer: zero findings.')
PY
exists=false
if aws iam get-policy --policy-arn "$policy_arn" > "$task_dir/existing-policy.json" 2> "$task_dir/policy-error.txt"; then
  exists=true
  version=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["Policy"]["DefaultVersionId"])' "$task_dir/existing-policy.json")
  aws iam get-policy-version --policy-arn "$policy_arn" --version-id "$version" > "$task_dir/existing-version.json"
  python3 - "$script_dir/operator-policy.json" "$task_dir/existing-version.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))==json.load(open(sys.argv[2]))['PolicyVersion']['Document'],'Policy name collision: stop; no version replacement allowed'
PY
elif ! grep -q NoSuchEntity "$task_dir/policy-error.txt"; then
  cat "$task_dir/policy-error.txt" >&2; exit 1
fi
if test "$mode" = --prepare; then
  echo 'PREPARED ONLY: no IAM/Identity Center changes; no infrastructure applied.'; exit 0
fi
aws sso-admin get-inline-policy-for-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" > "$task_dir/inline-recheck.json"
python3 "$script_dir/verify_access.py" "$script_dir" "$task_dir/inline-recheck.json"
if test "$exists" = false; then
  aws iam create-policy --policy-name "$policy_name" --policy-document "file://$script_dir/operator-policy.json" --tags Key=Project,Value=Wonderland Key=Purpose,Value=Step10D > "$task_dir/created-policy.json"
fi
aws sso-admin attach-customer-managed-policy-reference-to-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --customer-managed-policy-reference "Name=$policy_name,Path=/" --region "$region"
request=$(aws sso-admin provision-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --target-type AWS_ACCOUNT --target-id "$account" --region "$region" --query PermissionSetProvisioningStatus.RequestId --output text)
echo "Provisioning request: $request"
for attempt in $(seq 1 60); do
  status=$(aws sso-admin describe-permission-set-provisioning-status --instance-arn "$instance" --provision-permission-set-request-id "$request" --region "$region" --query PermissionSetProvisioningStatus.Status --output text)
  case "$status" in
    SUCCEEDED) echo 'SUCCEEDED: reviewed routing deployment policy provisioned; existing inline policy unchanged; no infrastructure applied.'; exit 0 ;;
    FAILED) echo 'Provisioning failed; inspect the request in owner console.' >&2; exit 1 ;;
  esac
  sleep 3
done
echo 'Provisioning timeout; inspect the request before retry.' >&2; exit 1
