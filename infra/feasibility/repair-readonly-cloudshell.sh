#!/usr/bin/env bash
# Run in AWS CloudShell from the owner/authorized Identity Center admin console.
# Repairs only this experiment permission set; does not deploy infrastructure.
set -euo pipefail
export AWS_PAGER=""
instance_arn='arn:aws:sso:::instance/ssoins-65954bc9fbd03036'
permission_set_arn='arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026'
target_account='708919751353'

actual_account=$(aws sts get-caller-identity --query Account --output text)
if [[ "$actual_account" != "$target_account" ]]; then
  echo 'Wrong account. No permissions changed.' >&2
  exit 1
fi
set_name=$(aws sso-admin describe-permission-set --region ap-south-1 \
  --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
  --query PermissionSet.Name --output text)
if [[ "$set_name" != 'WonderlandFeasibility' ]]; then
  echo 'Unexpected permission set. No permissions changed.' >&2
  exit 1
fi

# Attach the exact AWS-wide read policy first.
aws sso-admin attach-managed-policy-to-permission-set --region ap-south-1 \
  --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
  --managed-policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess

# Remove only the three unintended AI-specific policy attachments, when present.
attached=$(aws sso-admin list-managed-policies-in-permission-set --region ap-south-1 \
  --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
  --query 'AttachedManagedPolicies[].Arn' --output text)
for policy_name in AIDevOpsAgentReadOnlyAccess AIOpsReadOnlyAccess AgentRegistryReadOnlyAccess; do
  policy_arn="arn:aws:iam::aws:policy/$policy_name"
  if [[ " $attached " == *"$policy_arn"* ]]; then
    aws sso-admin detach-managed-policy-from-permission-set --region ap-south-1 \
      --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
      --managed-policy-arn "$policy_arn"
  fi
done

aws sso-admin list-managed-policies-in-permission-set --region ap-south-1 \
  --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
  --query 'AttachedManagedPolicies[].{Name:Name,Arn:Arn}' --output table
request_id=$(aws sso-admin provision-permission-set --region ap-south-1 \
  --instance-arn "$instance_arn" --permission-set-arn "$permission_set_arn" \
  --target-type AWS_ACCOUNT --target-id "$target_account" \
  --query PermissionSetProvisioningStatus.RequestId --output text)

echo "Provisioning requested: $request_id"
for attempt in {1..20}; do
  status=$(aws sso-admin describe-permission-set-provisioning-status --region ap-south-1 \
    --instance-arn "$instance_arn" --provision-permission-set-request-id "$request_id" \
    --query PermissionSetProvisioningStatus.Status --output text)
  if [[ "$status" == 'SUCCEEDED' ]]; then
    echo 'SUCCEEDED: exact ReadOnlyAccess policy applied to the experiment permission set.'
    exit 0
  elif [[ "$status" == 'FAILED' ]]; then
    aws sso-admin describe-permission-set-provisioning-status --region ap-south-1 \
      --instance-arn "$instance_arn" --provision-permission-set-request-id "$request_id"
    exit 1
  fi
  sleep 3
done
echo "Still $status. Wait for request $request_id to finish in Identity Center."
exit 2
