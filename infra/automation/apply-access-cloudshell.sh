#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[[ "$(aws sts get-caller-identity --query Account --output text)" == 708919751353 ]] || exit 1
echo "2073161f7de9337533cfad985040ab6483aef555faf87fb951c53e9c812407ab  github-release-access.json" | sha256sum --check
case "${1:---prepare}" in
  --prepare)
    aws cloudformation validate-template --region ap-south-1 --template-body file://github-release-access.json >/dev/null
    aws accessanalyzer validate-policy --region ap-south-1 --policy-type IDENTITY_POLICY --policy-document file://release-policy.json --output json
    echo 'PREPARED: main branch only; five existing ECR repositories; no application deployment access.' ;;
  --apply)
    [[ "$(aws iam list-open-id-connect-providers --query 'length(OpenIDConnectProviderList)' --output text)" == 0 ]] || { echo 'Provider inventory changed; review reuse before applying.'; exit 1; }
    aws cloudformation deploy --region ap-south-1 --stack-name wonderland-github-release-access --template-file github-release-access.json --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset
    echo 'SUCCEEDED: main-branch GitHub release role created.' ;;
  *) echo 'Use --prepare or --apply'; exit 2 ;;
esac
