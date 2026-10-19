#!/usr/bin/env bash
# Owner/setup session only. Merges the reviewed state-bucket grants into the existing permission set.
set -euo pipefail
account=708919751353
instance=arn:aws:sso:::instance/ssoins-65954bc9fbd03036
permission_set=arn:aws:sso:::permissionSet/ssoins-65954bc9fbd03036/ps-659523c3e5c38026
region=ap-south-1
policy_file=${1:-operator-policy.json}
test "$(aws sts get-caller-identity --query Account --output text)" = "$account"
test "$(aws sso-admin describe-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --query PermissionSet.Name --output text)" = WonderlandFeasibility
task_tmp=$(mktemp -d)
trap 'rm -rf -- "$task_tmp"' EXIT
aws sso-admin get-inline-policy-for-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --region "$region" --output json > "$task_tmp/current.json"
python3 - "$policy_file" "$task_tmp/current.json" "$task_tmp/merged.json" <<'PY'
import json, sys
new = json.load(open(sys.argv[1]))
bucket = 'arn:aws:s3:::wonderland-tfstate-708919751353-ap-south-1'
expected = {
    'ManageOnlyWonderlandStateBucket': (bucket, {'s3:CreateBucket', 's3:PutBucketVersioning', 's3:PutEncryptionConfiguration', 's3:PutBucketPublicAccessBlock', 's3:PutBucketPolicy', 's3:PutBucketTagging'}),
    'StateVersionsAndLocks': (bucket + '/demo/*', {'s3:GetObject', 's3:PutObject'}),
    'DeleteOnlyReleasedStateLocks': (bucket + '/demo/*.tflock', {'s3:DeleteObject'}),
}
assert new['Version'] == '2012-10-17' and len(new['Statement']) == 3
for statement in new['Statement']:
    resource, actions = expected[statement['Sid']]
    assert statement['Effect'] == 'Allow' and statement['Resource'] == resource
    actual_actions = statement['Action'] if isinstance(statement['Action'], list) else [statement['Action']]
    assert set(actual_actions) == actions
    assert set(statement) == {'Sid', 'Effect', 'Action', 'Resource'}
old = json.load(open(sys.argv[2])).get('InlinePolicy') or '{"Version":"2012-10-17","Statement":[]}'
merged = json.loads(old)
merged['Statement'] = [s for s in merged['Statement'] if s.get('Sid') not in expected] + new['Statement']
with open(sys.argv[3], 'w') as output:
    json.dump(merged, output, separators=(',', ':'))
print('Validated exact bucket-only grants; preserving all other inline statements.')
PY
aws accessanalyzer validate-policy --policy-type IDENTITY_POLICY --policy-document "file://$task_tmp/merged.json" --region "$region" --output json > "$task_tmp/validation.json"
python3 - "$task_tmp/validation.json" <<'PY'
import json,sys
assert not json.load(open(sys.argv[1]))['findings'], 'Policy findings require review before applying'
PY
aws sso-admin put-inline-policy-to-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --inline-policy "file://$task_tmp/merged.json" --region "$region"
request_id=$(aws sso-admin provision-permission-set --instance-arn "$instance" --permission-set-arn "$permission_set" --target-type AWS_ACCOUNT --target-id "$account" --region "$region" --query PermissionSetProvisioningStatus.RequestId --output text)
for attempt in $(seq 1 20); do
  status=$(aws sso-admin describe-permission-set-provisioning-status --instance-arn "$instance" --provision-permission-set-request-id "$request_id" --region "$region" --query PermissionSetProvisioningStatus.Status --output text)
  case "$status" in
    SUCCEEDED) echo 'SUCCEEDED: Terraform state-bucket permissions applied; no infrastructure deployed.'; exit 0 ;;
    FAILED) aws sso-admin describe-permission-set-provisioning-status --instance-arn "$instance" --provision-permission-set-request-id "$request_id" --region "$region"; exit 1 ;;
  esac
  sleep 3
done
echo "Provisioning still pending. Request ID: $request_id" >&2
exit 2
