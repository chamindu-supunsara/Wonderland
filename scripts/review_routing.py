"""Review only additions, public route boundaries, capacity and the spending model."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from review_workloads import cpu, memory

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/deployment'
plan = json.loads((LOCAL/'step10d-routing-plan.json').read_text(encoding='utf-8-sig'))
changes = [r for r in plan['resource_changes'] if r['mode']=='managed']
assert all(r['change']['actions']==['create'] for r in changes)
counts = dict(Counter(r['type'] for r in changes))
assert counts.get('aws_apigatewayv2_route')==29 and counts.get('aws_lb')==1 and counts.get('aws_lb_target_group')==4
assert not any(t in counts for t in ['aws_instance','aws_db_instance','aws_nat_gateway','aws_eks_node_group'])
for r in changes:
    after=r['change']['after']
    if r['type']=='aws_lb': assert after['internal'] and after['load_balancer_type']=='application'
    if r['type']=='aws_lb_target_group': assert after['target_type']=='ip'
    if r['type']=='aws_apigatewayv2_route':
        assert after['route_key']!='$default' and '{proxy+' not in after['route_key']
        assert '/health' not in after['route_key'] and '/mock-payment' not in after['route_key'] and '/admin/mock-tickets/' not in after['route_key']
        if after['authorization_type']=='JWT': assert after['authorization_scopes']==['aws.cognito.signin.user.admin']
nodes=json.loads((LOCAL/'step10d-nodes.json').read_text(encoding='utf-8-sig'))['items']
pods=[p for p in json.loads((LOCAL/'step10d-pods.json').read_text(encoding='utf-8-sig'))['items'] if p['status']['phase'] not in ['Succeeded','Failed']]
available={'cpu_millicores':sum(cpu(n['status']['allocatable']['cpu']) for n in nodes),'memory_mib':sum(memory(n['status']['allocatable']['memory']) for n in nodes),'pod_slots':sum(int(n['status']['allocatable']['pods']) for n in nodes)}
used_cpu=used_memory=0
for p in pods:
    requests=[c.get('resources',{}).get('requests',{}) for c in p['spec']['containers']]
    init=[c.get('resources',{}).get('requests',{}) for c in p['spec'].get('initContainers',[])]
    used_cpu+=max(sum(cpu(r.get('cpu','0')) for r in requests),max([cpu(r.get('cpu','0')) for r in init] or [0]))
    used_memory+=max(sum(memory(r.get('memory','0')) for r in requests),max([memory(r.get('memory','0')) for r in init] or [0]))
peak={'cpu_millicores':used_cpu+3*100+4*100+100,'memory_mib':used_memory+(3+4+1)*128,'pod_slots':len(pods)+3+4+1}
assert len(nodes)==2 and all(peak[k]<available[k] for k in peak),(peak,available)
prices=json.loads((LOCAL/'step10d-elb-prices.json').read_text(encoding='utf-8-sig'))
rates={}
for sku,product in prices['products'].items():
    a=product['attributes']
    if a.get('operation')!='LoadBalancing:Application' or a.get('locationType')!='AWS Region':continue
    for term in prices['terms']['OnDemand'].get(sku,{}).values():
        for dim in term['priceDimensions'].values():rates[a['usagetype']]=float(dim['pricePerUnit']['USD'])
hourly=rates['APS3-LoadBalancerUsage']; lcu=rates['APS3-LCUUsage']
report={'status':'PLANNED_NOT_APPLIED','reviewed_at_utc':datetime.now(timezone.utc).isoformat(),'resources_to_add':len(changes),'resources_to_change':0,'resources_to_destroy':0,'resource_counts':counts,'public_read_routes':3,'jwt_routes':26,'existing_active_pods':len(pods),'cluster_allocatable':available,'conservative_peak_including_controller_and_surge':peak,'controller_chart_version':'3.6.0','additional_ec2_rds_nat_instances':0,'alb_hourly_usd':hourly,'alb_lcu_hour_usd':lcu,'conservative_168_hour_one_lcu_model_usd':round(168*(hourly+lcu),4),'prior_planning_model_usd':54.41,'step10d_reserve_usd':8,'combined_planning_model_usd':62.41,'allowance_usd':75,'budget_limitations':'Light demonstration traffic assumed; taxes, retention, transfer and usage vary. Not a live bill or enforced cap.','cleanup_target':'2026-10-25T18:00:00+05:30','tls_boundary':'HTTPS browser/frontend/Gateway; private VPC integration and API service hops remain HTTP. RDS uses verify-full TLS.','plan_sha256':hashlib.sha256((LOCAL/'step10d-routing.tfplan').read_bytes()).hexdigest(),'sources_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'infra/terraform/routing').glob('*.tf'))+[(ROOT/'infra/terraform/routing/routes.json')]},'checkout':'mock'}
report['public_read_routes'] = 3
report['jwt_routes'] = 26
(ROOT/'docs/evidence/step10d-routing-plan.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
