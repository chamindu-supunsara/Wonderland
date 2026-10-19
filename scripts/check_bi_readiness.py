"""Read-only capacity and delayed billing snapshot for the private BI rollout."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

root=Path(__file__).resolve().parents[1]
local=root/'.local/deployment'
base=[str(root/'.local/tools/kubectl.exe'),'--kubeconfig',str(local/'kubeconfig')]
def kube(*args): return json.loads(subprocess.check_output(base+list(args),text=True,timeout=45))
def cpu(v): return float(v[:-1]) if str(v).endswith('m') else float(v)*1000
def memory(v):
    for suffix,scale in [('Ki',1/1024),('Mi',1),('Gi',1024),('Ti',1048576),('K',1000/1048576),('M',1000000/1048576),('G',1000000000/1048576)]:
        if str(v).endswith(suffix): return float(v[:-len(suffix)])*scale
    return float(v)/1048576
session=boto3.Session(profile_name='wonderland-feasibility',region_name='ap-south-1')
identity=session.client('sts').get_caller_identity()
assert identity['Account']=='708919751353' and ':assumed-role/AWSReservedSSO_WonderlandFeasibility_' in identity['Arn']
nodes=kube('get','nodes','-o','json')['items']
pods=kube('get','pods','-A','-o','json')['items']
assert len(nodes)==2
capacity={}
for node in nodes:
    name=node['metadata']['name']; allocation=node['status']['allocatable']
    placed=[p for p in pods if p['spec'].get('nodeName')==name and p['status']['phase'] not in ['Succeeded','Failed']]
    total_cpu=total_memory=0
    for pod in placed:
        requests=[c.get('resources',{}).get('requests',{}) for c in pod['spec']['containers']]
        init=[c.get('resources',{}).get('requests',{}) for c in pod['spec'].get('initContainers',[])]
        total_cpu+=max(sum(cpu(r.get('cpu',0)) for r in requests),max([cpu(r.get('cpu',0)) for r in init] or [0]))
        total_memory+=max(sum(memory(r.get('memory',0)) for r in requests),max([memory(r.get('memory',0)) for r in init] or [0]))
    capacity[name]={'pods':len(placed),'max_pods':allocation['pods'],'free_cpu_m':cpu(allocation['cpu'])-total_cpu,'free_memory_mib':memory(allocation['memory'])-total_memory}
assert any(v['free_cpu_m']>=350 and v['free_memory_mib']>=1792 and v['pods']+3<=int(v['max_pods']) for v in capacity.values()),'No safe existing-node placement; do not add nodes automatically'
(local/'step10e-capacity.json').write_text(json.dumps(capacity,indent=2)+'\n')
report={'status':'READY','verified_at_utc':datetime.now(timezone.utc).isoformat(),'capacity':capacity,'additional_nodes':0,'checkout':'mock'}
try:
    result=session.client('ce',region_name='us-east-1').get_cost_and_usage(TimePeriod={'Start':'2026-10-18','End':'2026-10-19'},Granularity='DAILY',Metrics=['UnblendedCost'])
    report['delayed_account_billing']={'periods':result['ResultsByTime'],'scope':'Whole account, not a live bill or Wonderland-only attribution; excludes later/unreported usage.'}
except ClientError as error:
    report['delayed_account_billing']={'status':'UNAVAILABLE','code':error.response['Error']['Code'],'scope':'Actual current bill not verified; retain planning allowance and cleanup deadline.'}
(root/'docs/evidence/step10e-readiness.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
