#!/usr/bin/env bash
# Owner/authorized Identity Center admin CloudShell only. No infrastructure deployment.
set -euo pipefail
export AWS_PAGER=""
instance_arn='arn:aws:sso:::instance/ssoins-65954bc9fbd03036'
permission_set_arn='arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026'
policy_file="${1:-operator-policy.json}"
[[ $(aws sts get-caller-identity --query Account --output text) == '708919751353' ]] || {
  echo 'Wrong account. No permissions changed.' >&2; exit 1;
}
[[ $(aws sso-admin describe-permission-set --region ap-south-1 \
  --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
  --query PermissionSet.Name --output text) == 'WonderlandFeasibility' ]] || {
  echo 'Wrong permission set. No permissions changed.' >&2; exit 1;
}
python3 - "$policy_file" <<'PY'
import json, sys
with open(sys.argv[1]) as source:
    policy = json.load(source)
gateway = next(s for s in policy['Statement'] if s['Sid'] == 'RegionalHttpApiLifecycle')
assert gateway['Action'] == 'apigateway:*', 'Upload the updated operator-policy.json'
assert gateway['Resource'] == [
    'arn:aws:apigateway:ap-south-1::/apis*',
    'arn:aws:apigateway:ap-south-1::/vpclinks*',
    'arn:aws:apigateway:ap-south-1::/tags/*'
], 'Unexpected API Gateway resource scope'
PY
aws sso-admin put-inline-policy-to-permission-set --region ap-south-1 \
  --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
  --inline-policy "file://$policy_file"
request_id=$(aws sso-admin provision-permission-set --region ap-south-1 \
  --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
  --target-type AWS_ACCOUNT --target-id 708919751353 \
  --query PermissionSetProvisioningStatus.RequestId --output text)
for attempt in {1..20}; do
  status=$(aws sso-admin describe-permission-set-provisioning-status --region ap-south-1 \
    --instance-arn "$instance_arn" --provision-permission-set-request-id "$request_id" \
    --query PermissionSetProvisioningStatus.Status --output text)
  if [[ "$status" == 'SUCCEEDED' ]]; then
    echo 'SUCCEEDED: updated experiment inline policy applied.'; exit 0
  elif [[ "$status" == 'FAILED' ]]; then
    aws sso-admin describe-permission-set-provisioning-status --region ap-south-1 \
      --instance-arn "$instance_arn" --provision-permission-set-request-id "$request_id"
    exit 1
  fi
  sleep 3
done
echo "Still $status. Check provisioning request $request_id in Identity Center."
exit 2
