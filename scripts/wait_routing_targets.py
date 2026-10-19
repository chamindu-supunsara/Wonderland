"""Wait for live IP target health, never manually register a Pod address."""
import json
import time
from pathlib import Path
import boto3

root=Path(__file__).resolve().parents[1]
outputs=json.loads((root/'.local/deployment/routing-outputs.json').read_text(encoding='utf-8-sig'))
client=boto3.Session(profile_name='wonderland-feasibility',region_name='ap-south-1').client('elbv2')
for attempt in range(60):
    health={service:client.describe_target_health(TargetGroupArn=arn)['TargetHealthDescriptions'] for service,arn in outputs['target_groups']['value'].items()}
    counts={s:sum(t['TargetHealth']['State']=='healthy' for t in targets) for s,targets in health.items()}
    if all(n==2 for n in counts.values()):
        print(json.dumps({'healthy_targets':counts,'registration':'controller-managed Pod IPs'}));break
    if attempt%6==0: print('Waiting for ALB target health: '+json.dumps(counts),flush=True)
    time.sleep(5)
else: raise SystemExit('Target health did not reach two healthy replicas per API; inspect controller logs without printing secrets')
