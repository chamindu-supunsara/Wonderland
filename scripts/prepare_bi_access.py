"""Prepare a temporary owner-only BI bootstrap identity, not operator password-read access."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
directory=root/'infra/bi'
directory.mkdir(exist_ok=True)
outputs=json.loads((root/'.local/deployment/foundation-outputs.json').read_text(encoding='utf-8-sig'))
master=outputs['database_master_secret_arn']['value']
trust={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'pods.eks.amazonaws.com'},
    'Action':['sts:AssumeRole','sts:TagSession'],'Condition':{'StringEquals':{
    'aws:RequestTag/kubernetes-namespace':'wonderland-bootstrap','aws:RequestTag/kubernetes-service-account':'bi-bootstrap',
    'aws:RequestTag/eks-cluster-arn':'arn:aws:eks:ap-south-1:708919751353:cluster/wonderland-demo'}}}]}
policy={'Version':'2012-10-17','Statement':[
    {'Sid':'ReadOnlyExistingMaster','Effect':'Allow','Action':'secretsmanager:GetSecretValue','Resource':master},
    {'Sid':'OnlyTwoBICredentials','Effect':'Allow','Action':['secretsmanager:DescribeSecret','secretsmanager:GetSecretValue','secretsmanager:PutSecretValue'],
     'Resource':['arn:aws:secretsmanager:ap-south-1:708919751353:secret:wonderland-demo/'+name+'-??????' for name in ['metabase-app','metabase-reporting']]}]}
template={'AWSTemplateFormatVersion':'2010-09-09','Description':'Temporary Step10E BI bootstrap identity; no database or secret deletion resources.',
    'Resources':{
    'BootstrapRole':{'Type':'AWS::IAM::Role','Properties':{'RoleName':'wonderland-demo-bi-bootstrap','MaxSessionDuration':3600,
      'AssumeRolePolicyDocument':trust,'Policies':[{'PolicyName':'OnlyPrivateBIBootstrap','PolicyDocument':policy}],
      'Tags':[{'Key':'Project','Value':'Wonderland'},{'Key':'Purpose','Value':'temporary-bi-bootstrap'}]}},
    'PodIdentity':{'Type':'AWS::EKS::PodIdentityAssociation','Properties':{'ClusterName':'wonderland-demo','Namespace':'wonderland-bootstrap',
      'ServiceAccount':'bi-bootstrap','RoleArn':{'Fn::GetAtt':['BootstrapRole','Arn']}}}}}
(directory/'bootstrap-access.json').write_text(json.dumps(template,indent=2)+'\n')
(directory/'bootstrap-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
helper='''#!/usr/bin/env bash
set -euo pipefail
export AWS_PAGER=""
mode=${1:---prepare}
case "$mode" in --prepare|--apply|--cleanup) ;; *) exit 1 ;; esac
directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$directory"
printf '%%s  %%s\\n' '%s' bootstrap-access.json '%s' bootstrap-policy.json | sha256sum -c -
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
'''%(digest(directory/'bootstrap-access.json'),digest(directory/'bootstrap-policy.json'))
(directory/'apply-access-cloudshell.sh').write_text(helper,newline='\n')
bundle=root/'.local/deployment/step10e-bi-access.zip'
with ZipFile(bundle,'w',ZIP_DEFLATED) as archive:
    for name in ['bootstrap-access.json','bootstrap-policy.json','apply-access-cloudshell.sh']:archive.write(directory/name,name)
report={'status':'PREPARED_NOT_APPLIED','stack':'wonderland-bi-bootstrap-access','temporary_resources':2,
        'temporary_role':'wonderland-demo-bi-bootstrap','secret_scope':'Existing RDS master read; two named BI secrets read/write only',
        'operator_password_read_access_added':False,'persistent_infrastructure_plan':'Two BI secret containers; no secret values in Terraform',
        'additional_ec2_rds_nat_alb':0,'metabase_access':'Private ClusterIP and loopback-only authenticated kubectl port-forward',
        'metabase_replicas':1,'metabase_memory_request_mib':1536,'metabase_memory_limit_mib':2048,
        'prior_planning_model_usd':62.41,'bi_reserve_usd':2,'combined_planning_model_usd':64.41,'allowance_usd':75,
        'cleanup_target':'2026-10-25T18:00:00+05:30','bi_secret_retention':'Retain 14 days after teardown to preserve metadata recovery; then review seven-day recovery deletion. No automatic deletion.',
        'checkout':'mock','bundle_sha256':digest(bundle),'files_sha256':{p.name:digest(p) for p in directory.iterdir() if p.is_file()}}
(root/'docs/evidence/step10e-access-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
