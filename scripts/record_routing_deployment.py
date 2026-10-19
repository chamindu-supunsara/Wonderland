"""Record completed routing evidence; never reads Terraform secret contents."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import boto3

root=Path(__file__).resolve().parents[1]
local=root/'.local/deployment'
evidence=root/'docs/evidence'
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
public=read(evidence/'step10d-public-verification.json')
live=read(evidence/'step10d-live-verification.json')
frontend=read(evidence/'step10d-frontend-deployment.json')
permissions=read(evidence/'step10d-live-permissions.json')
plan=read(local/'step10d-routing-final.json')
assert public['status']==live['status']==permissions['status']=='VERIFIED'
assert all(public['checks'].values()) and all(live['checks'].values())
assert frontend['status']=='DEPLOYED'
assert all(r['change']['actions']==['no-op'] for r in plan.get('resource_changes',[]))
session=boto3.Session(profile_name='wonderland-feasibility',region_name='ap-south-1')
head=session.client('s3').head_object(Bucket='wonderland-tfstate-708919751353-ap-south-1',Key='demo/routing/terraform.tfstate')
assert head.get('ServerSideEncryption') in ['AES256','aws:kms'] and head.get('VersionId')
resources=plan['planned_values']['root_module']['resources']
assert len(resources)==57
report={'status':'PUBLIC_DEPLOYMENT_VERIFIED','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'resources_created':57,'resource_replacements':0,'post_apply_compatibility_updates':1,
        'routing_terraform_changes':0,'public_checks_passed':len(public['checks']),
        'live_checks_passed':len(live['checks']),'frontend_origin':frontend['frontend_origin'],
        'api_endpoint':live['api_endpoint'],'amplify_job_id':frontend['job_id'],
        'state_encryption':head['ServerSideEncryption'],'state_version_id':head['VersionId'],
        'checkout':'mock','planning_model_usd':62.41,'allowance_usd':75,
        'actual_bill_verified':False,'cleanup_target':'2026-10-25T18:00:00+05:30',
        'authenticated_walkthrough_evidence':'step10d-browser-verification.json (record separately after real UI checks)',
        'final_source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'infra/terraform/routing').glob('*.tf'))}}
browser_path=evidence/'step10d-browser-verification.json'
if browser_path.exists():
    browser=read(browser_path)
    if browser['status']=='VERIFIED' and all(browser['checks'].values()):
        report['status']='DEPLOYED_AND_VERIFIED'
        report['authenticated_walkthrough_evidence']='step10d-browser-verification.json'
        live['authenticated_walkthrough']='VERIFIED (step10d-browser-verification.json)'
        (evidence/'step10d-live-verification.json').write_text(json.dumps(live,indent=2)+'\n')
(evidence/'step10d-deployment-execution.json').write_text(json.dumps(report,indent=2)+'\n')
review=read(evidence/'step10d-routing-plan.json')
review['status']='APPLIED'
review['execution_evidence']='step10d-deployment-execution.json'
(evidence/'step10d-routing-plan.json').write_text(json.dumps(review,indent=2)+'\n')
repair=read(evidence/'step10d-deployment-access-repair.json')
repair['status']='APPLIED_AND_VERIFIED'
repair['live_policy_verified']=True
(evidence/'step10d-deployment-access-repair.json').write_text(json.dumps(repair,indent=2)+'\n')
print(json.dumps(report,indent=2))
