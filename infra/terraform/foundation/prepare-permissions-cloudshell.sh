#!/usr/bin/env bash
# Owner/setup CloudShell only. Default is read/validate; --apply requires separate approval.
set -euo pipefail
account=708919751353
instance=arn:aws:sso:::instance/ssoins-65954bc9fbd03036
permission_set=arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026
region=ap-south-1
mode=${1:---prepare}
case "$mode" in --prepare|--apply) ;; *) echo 'Usage: bash prepare-permissions-cloudshell.sh [--prepare|--apply]' >&2; exit 1 ;; esac
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
test "$(aws sts get-caller-identity --query Account --output text)" = "$account"
caller=$(aws sts get-caller-identity --query Arn --output text)
case "$caller" in *AWSReservedSSO_WonderlandFeasibility*|*AWSReservedSSO_WonderlandReadOnly*) echo 'Use the owner/setup administrator session for this permission update.' >&2; exit 1 ;; esac
test "$(aws sso-admin describe-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --query PermissionSet.Name --output text)" = WonderlandFeasibility
task_dir=$(mktemp -d "$HOME/wonderland-foundation-permissions.XXXXXX")
chmod 700 "$task_dir"
echo "Keeping policy backup and validation evidence in: $task_dir"
aws sso-admin get-inline-policy-for-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --output json > "$task_dir/before.json"
python3 "$script_dir/merge_operator_policy.py" "$script_dir/operator-policy.json" "$task_dir/before.json" "$task_dir/merged.json"
aws accessanalyzer validate-policy --policy-type IDENTITY_POLICY --policy-document "file://$task_dir/merged.json" --region "$region" --output json > "$task_dir/validation.json"
python3 - "$task_dir/validation.json" <<'PY'
import json,sys
findings = json.load(open(sys.argv[1]))['findings']
if findings:
    print(json.dumps(findings, indent=2))
    raise SystemExit('Stop: policy findings need review before applying')
print('AWS Access Analyzer: zero findings.')
PY
if test "$mode" = --prepare; then
  echo 'PREPARED ONLY: no permissions changed and no infrastructure deployed.'
  exit 0
fi
# Recheck drift immediately before the mutation.
aws sso-admin get-inline-policy-for-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --output json > "$task_dir/recheck.json"
python3 - "$task_dir/before.json" "$task_dir/recheck.json" <<'PY'
import json,sys
policies = [json.loads(json.load(open(p))['InlinePolicy']) for p in sys.argv[1:]]
if policies[0] != policies[1]:
    raise SystemExit('Stop: inline policy changed during preparation')
PY
aws sso-admin put-inline-policy-to-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --inline-policy "file://$task_dir/merged.json" --region "$region"
request_id=$(aws sso-admin provision-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --target-type AWS_ACCOUNT --target-id "$account" --region "$region" --query PermissionSetProvisioningStatus.RequestId --output text)
echo "Provisioning request: $request_id"
for attempt in $(seq 1 20); do
  aws sso-admin describe-permission-set-provisioning-status --instance-arn "$instance" --provision-permission-set-request-id "$request_id" --region "$region" --output json > "$task_dir/provisioning.json"
  status=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["PermissionSetProvisioningStatus"]["Status"])' "$task_dir/provisioning.json")
  case "$status" in
    SUCCEEDED) echo 'SUCCEEDED: reviewed foundation permissions provisioned; no infrastructure deployed.'; exit 0 ;;
    FAILED) cat "$task_dir/provisioning.json" >&2; exit 1 ;;
  esac
  sleep 3
done
echo "Provisioning still pending; inspect request $request_id before retrying. Backup: $task_dir" >&2
exit 2
