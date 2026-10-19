#!/usr/bin/env bash
set -euo pipefail
export AWS_PAGER=""
mode=${1:---prepare}
case "$mode" in --prepare|--apply|--cleanup) ;; *) exit 1 ;; esac
directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$directory"
printf '%s  %s\n' '26474e98c64ffa7c74b2808ac2dec9b6ba9c11573f94399054a136825bc10b6b' bootstrap-access.json 'e30d4fa50d3cf4596d8bc145c1e2b1c41480b458df9a2b307e3a8f0e8e96b535' bootstrap-policy.json | sha256sum -c -
test "$(aws sts get-caller-identity --query Account --output text)" = 708919751353
caller=$(aws sts get-caller-identity --query Arn --output text)
case "$caller" in *AWSReservedSSO_WonderlandFeasibility*|*AWSReservedSSO_WonderlandReadOnly*) echo 'Use owner/setup session'; exit 1 ;; esac
aws accessanalyzer validate-policy --region ap-south-1 --policy-type IDENTITY_POLICY --policy-document file://bootstrap-policy.json > validation.json
python3 -c 'import json;assert not json.load(open("validation.json"))["findings"];print("Access Analyzer: zero findings.")'
aws cloudformation validate-template --region ap-south-1 --template-body file://bootstrap-access.json > template-validation.json
if test "$mode" = --prepare; then echo 'PREPARED: two temporary identity resources; no changes applied.'; exit 0; fi
if test "$mode" = --cleanup; then
  aws cloudformation get-template --region ap-south-1 --stack-name wonderland-bi-bootstrap-access > existing-template.json
  python3 -c 'import json;a=json.load(open("existing-template.json"))["TemplateBody"];a=json.loads(a) if isinstance(a,str) else a;assert a==json.load(open("bootstrap-access.json")),"Unreviewed stack"'
  aws cloudformation delete-stack --region ap-south-1 --stack-name wonderland-bi-bootstrap-access
  aws cloudformation wait stack-delete-complete --region ap-south-1 --stack-name wonderland-bi-bootstrap-access
  echo 'SUCCEEDED: temporary BI IAM role and Pod Identity removed.'; exit 0
fi
aws cloudformation deploy --region ap-south-1 --stack-name wonderland-bi-bootstrap-access --template-file bootstrap-access.json --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset
echo 'SUCCEEDED: temporary BI bootstrap identity ready; CLI secret-read access unchanged.'
