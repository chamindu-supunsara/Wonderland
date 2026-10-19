"""Fail closed before a small private BI rollout; no secret values read."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1]
local=root/'.local/deployment'
plan=json.loads((local/'step10e-analytics-plan.json').read_text(encoding='utf-8-sig'))
changes=[r for r in plan['resource_changes'] if r['change']['actions']!=['no-op']]
assert len(changes)==2
assert all(r['type']=='aws_secretsmanager_secret' and r['change']['actions']==['create'] for r in changes)
assert {r['change']['after']['name'] for r in changes}=={'wonderland-demo/metabase-app','wonderland-demo/metabase-reporting'}
assert all(r['change']['after']['recovery_window_in_days']==7 for r in changes)
capacity=json.loads((local/'step10e-capacity.json').read_text())
assert len(capacity)==2 and all(v['pods']+3<=int(v['max_pods']) for v in capacity.values())
assert any(v['free_cpu_m']>=350 and v['free_memory_mib']>=1792 for v in capacity.values())
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report={'status':'PLANNED_NOT_APPLIED','reviewed_at_utc':datetime.now(timezone.utc).isoformat(),
        'resources_to_add':2,'resources_to_change':0,'resources_to_destroy':0,'secret_values_in_plan':False,
        'additional_ec2_rds_nat_alb':0,'existing_nodes':capacity,'metabase_request':{'cpu_m':250,'memory_mib':1536},
        'prior_planning_usd':62.41,'bi_reserve_usd':2,'combined_planning_usd':64.41,'allowance_usd':75,
        'billing_limitations':'Cost Explorer is delayed and estimated; not a live spending cap. Light demo traffic assumed; taxes, CPU credits, usage and retained artifacts vary.',
        'cleanup_target':'2026-10-25T18:00:00+05:30','bi_credential_retention_review':'2026-11-08T18:00:00+05:30',
        'plan_sha256':digest(local/'step10e-analytics.tfplan'),
        'source_sha256':{str(p.relative_to(root)):digest(p) for p in sorted((root/'infra/terraform/analytics').glob('*.tf'))},
        'checkout':'mock'}
(root/'docs/evidence/step10e-bi-plan.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
