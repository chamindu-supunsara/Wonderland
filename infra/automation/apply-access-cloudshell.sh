#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[[ "$(aws sts get-caller-identity --query Account --output text)" == 708919751353 ]] || exit 1
echo "acbeb2bd1b45374dd788e885ce0b610dfc767d50a7cd73cd52c8d2627a82035a  github-release-access.json" | sha256sum --check
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
