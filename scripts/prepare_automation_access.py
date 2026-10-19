"""Prepare an owner-reviewed OIDC grant. This script never changes AWS access."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / 'infra/automation'
folder.mkdir(parents=True, exist_ok=True)
repos = ['arn:aws:ecr:ap-south-1:708919751353:repository/wonderland-demo/' + service
         for service in ['catalog', 'booking', 'payment', 'admission', 'analytics']]
policy = {'Version': '2012-10-17', 'Statement': [
    {'Sid': 'RegistryAuthentication', 'Effect': 'Allow',
     'Action': 'ecr:GetAuthorizationToken', 'Resource': '*'},
    {'Sid': 'PublishFiveExistingRepositories', 'Effect': 'Allow', 'Resource': repos,
     'Action': ['ecr:BatchCheckLayerAvailability', 'ecr:InitiateLayerUpload',
                'ecr:UploadLayerPart', 'ecr:CompleteLayerUpload', 'ecr:PutImage',
                'ecr:DescribeImages']} ]}
template = {'AWSTemplateFormatVersion': '2010-09-09',
    'Description': 'Wonderland main-branch GitHub OIDC image publishing only',
    'Resources': {
        'GitHubProvider': {'Type': 'AWS::IAM::OIDCProvider', 'Properties': {
            'Url': 'https://token.actions.githubusercontent.com',
            'ClientIdList': ['sts.amazonaws.com']}},
        'ReleaseRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'RoleName': 'wonderland-github-release', 'MaxSessionDuration': 3600,
            'AssumeRolePolicyDocument': {'Version': '2012-10-17', 'Statement': [{
                'Effect': 'Allow', 'Principal': {'Federated': {'Ref': 'GitHubProvider'}},
                'Action': 'sts:AssumeRoleWithWebIdentity', 'Condition': {'StringEquals': {
                    'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
                    'token.actions.githubusercontent.com:sub':
                    'repo:chamindu-supunsara@80322623/Wonderland@1425166882:ref:refs/heads/main'}}}]},
            'Policies': [{'PolicyName': 'PublishExistingWonderlandImages',
                          'PolicyDocument': policy}]}}},
    'Outputs': {'RoleArn': {'Value': {'Fn::GetAtt': ['ReleaseRole', 'Arn']}}}}
(folder / 'github-release-access.json').write_text(json.dumps(template, indent=2) + '\n')
(folder / 'release-policy.json').write_text(json.dumps(policy, indent=2) + '\n')
digest = hashlib.sha256((folder / 'github-release-access.json').read_bytes()).hexdigest()
helper = '''#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[[ "$(aws sts get-caller-identity --query Account --output text)" == 708919751353 ]] || exit 1
echo "EXPECTED_SHA  github-release-access.json" | sha256sum --check
case "${1:---prepare}" in
  --prepare)
    aws cloudformation validate-template --region ap-south-1 --template-body file://github-release-access.json >/dev/null
    aws accessanalyzer validate-policy --region ap-south-1 --policy-type IDENTITY_POLICY --policy-document file://release-policy.json --output json
    echo 'PREPARED: main branch only; five existing ECR repositories; no application deployment access.' ;;
  --apply)
    count=$(aws iam list-open-id-connect-providers --query 'length(OpenIDConnectProviderList)' --output text)
    if [[ "$count" != 0 ]]; then
      owned=$(aws cloudformation describe-stack-resource --region ap-south-1 --stack-name wonderland-github-release-access --logical-resource-id GitHubProvider --query StackResourceDetail.PhysicalResourceId --output text)
      [[ "$count" == 1 && "$owned" == arn:aws:iam::708919751353:oidc-provider/token.actions.githubusercontent.com ]] || { echo 'Provider ownership changed; stop for review.'; exit 1; }
    fi
    aws cloudformation deploy --region ap-south-1 --stack-name wonderland-github-release-access --template-file github-release-access.json --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset
    echo 'SUCCEEDED: main-branch GitHub release role created.' ;;
  *) echo 'Use --prepare or --apply'; exit 2 ;;
esac
'''.replace('EXPECTED_SHA', digest)
(folder / 'apply-access-cloudshell.sh').write_text(helper, newline='\n')
archive = ROOT / '.local/deployment/step11-automation-access.zip'
with ZipFile(archive, 'w') as zipped:
    for name in ['github-release-access.json', 'release-policy.json', 'apply-access-cloudshell.sh']:
        zipped.write(folder / name, name)
report = {'status': 'PREPARED_NOT_APPLIED', 'repository': 'chamindu-supunsara/Wonderland',
          'resources_to_create': 2, 'role': 'wonderland-github-release',
          'trust_subject': 'repo:chamindu-supunsara@80322623/Wonderland@1425166882:ref:refs/heads/main',
          'ecr_repositories': repos, 'secret_or_eks_access': False,
          'additional_compute_rds_nat_alb': 0, 'combined_planning_usd': 65.41,
          'allowance_usd': 75, 'new_image_storage_reserve_usd': 1,
          'cleanup_target': '2026-10-25T18:00:00+05:30',
          'template_sha256': digest,
          'bundle_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
(ROOT / 'docs/evidence/step11-access-review.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
