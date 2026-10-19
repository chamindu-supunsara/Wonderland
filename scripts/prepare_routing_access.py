"""Prepare scoped owner setup inputs; does not change AWS access."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT / 'infra/terraform/routing'
base = json.loads((ROOT / '.local/deployment/database-merged-policy.json').read_text(encoding='utf-8-sig'))

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

role = 'arn:aws:iam::708919751353:role/wonderland-demo-target-controller'
app = 'arn:aws:amplify:ap-south-1:708919751353:apps/*'
statements = [
    dict(Sid='OneTargetRegistrationController', Effect='Allow', Action=['iam:CreateRole','iam:DeleteRole','iam:UpdateAssumeRolePolicy','iam:TagRole','iam:UntagRole','iam:PutRolePolicy','iam:DeleteRolePolicy'], Resource=role),
    dict(Sid='PassOnlyTargetController', Effect='Allow', Action='iam:PassRole', Resource=role, Condition={'StringEquals':{'iam:PassedToService':'pods.eks.amazonaws.com'}}),
    dict(Sid='OnlyDemoListenerRules', Effect='Allow', Action=['elasticloadbalancing:CreateRule','elasticloadbalancing:ModifyRule','elasticloadbalancing:DeleteRule','elasticloadbalancing:SetRulePriorities'], Resource=['arn:aws:elasticloadbalancing:ap-south-1:708919751353:listener/app/wonderland-demo-edge/*/*','arn:aws:elasticloadbalancing:ap-south-1:708919751353:listener-rule/app/wonderland-demo-edge/*/*/*']),
    dict(Sid='CreateTaggedFrontend', Effect='Allow', Action='amplify:CreateApp', Resource=app, Condition={'StringEquals':{'aws:RequestTag/Project':'Wonderland'}}),
    dict(Sid='MumbaiFrontendAppLifecycle', Effect='Allow', Action=['amplify:UpdateApp','amplify:DeleteApp','amplify:CreateBranch','amplify:TagResource','amplify:UntagResource'], Resource=app),
    dict(Sid='MainBranchDeployment', Effect='Allow', Action=['amplify:UpdateBranch','amplify:DeleteBranch','amplify:CreateDeployment','amplify:StartDeployment','amplify:StopJob'], Resource=[app+'/branches/main',app+'/branches/main/jobs/*','arn:aws:amplify:ap-south-1:708919751353:apps/d3vt08cs3xnlse/branches/main/deployments/*']),
    dict(Sid='GatewayLogsOnly', Effect='Allow', Action=['logs:CreateLogGroup','logs:DeleteLogGroup','logs:PutRetentionPolicy','logs:DeleteRetentionPolicy','logs:TagResource','logs:UntagResource'], Resource=['arn:aws:logs:ap-south-1:708919751353:log-group:/aws/apigateway/wonderland-demo-public','arn:aws:logs:ap-south-1:708919751353:log-group:/aws/apigateway/wonderland-demo-public:*']),
    dict(Sid='MumbaiGatewayLogDelivery', Effect='Allow', Action=['logs:CreateLogDelivery','logs:GetLogDelivery','logs:UpdateLogDelivery','logs:DeleteLogDelivery','logs:ListLogDeliveries','logs:PutResourcePolicy'], Resource='*',Condition={'StringEquals':{'aws:RequestedRegion':'ap-south-1'}}),
]
policy = dict(Version='2012-10-17', Statement=statements)
assert len(json.dumps(policy,separators=(',',':'))) < 6144
(directory / 'operator-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
guard = '''"""Immutable owner-side input guard; no AWS mutations."""
import hashlib,json,sys
from pathlib import Path
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def verify(directory,current):
    policy=json.loads((Path(directory)/'operator-policy.json').read_text())
    assert digest(policy)==%r,'Unreviewed routing policy'
    assert digest(json.loads(current['InlinePolicy']))==%r,'Existing inline policy drift'
    return policy
if __name__=='__main__':
    verify(sys.argv[1],json.loads(Path(sys.argv[2]).read_text()))
    print('Reviewed routing policy pinned; existing inline policy unchanged.')
''' % (digest(policy),digest(base))
(directory / 'verify_access.py').write_text(guard)
helper=(ROOT/'infra/terraform/workloads/apply-access-cloudshell.sh').read_text()
helper=helper.replace('WonderlandWorkloadsDeployment','WonderlandRoutingDeployment').replace('step10c','step10d').replace('Step10C','Step10D').replace('workload','routing')
(directory/'apply-access-cloudshell.sh').write_text(helper,newline='\n')
report={'status':'PREPARED_NOT_APPLIED','policy_name':'WonderlandRoutingDeployment','policy_canonical_sha256':digest(policy),'baseline_inline_sha256':digest(base),'managed_policy_bytes':len(json.dumps(policy,separators=(',',':'))),'amplify_scope':'App IDs are generated: lifecycle rights cover Mumbai account app ARNs and main branches, not only a pre-known app ID. Creation requires Project=Wonderland tag.','controller_scope':'One named IAM role; Pod role registers/deregisters only four Terraform target groups, no ELB/security-group creation.','log_delivery_scope':'Named Gateway log group plus regional log delivery/resource-policy operations.','password_read_access_added':False}
(ROOT/'docs/evidence/step10d-access-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
