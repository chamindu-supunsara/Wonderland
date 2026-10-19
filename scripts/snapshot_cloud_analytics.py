"""Read aggregate cloud analytics in its existing worker; no local credential reads."""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--label',choices=['before','after','persistence'],required=True)
args=parser.parse_args()
remote='''
import json,os,sys
from sqlalchemy import create_engine,text
try:
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,connect_args={'connect_timeout':10})
    queries={
      'purchases':'SELECT * FROM reporting.mock_purchase_totals',
      'pipeline':'SELECT * FROM reporting.mock_pipeline_health',
      'daily_arrivals':'SELECT * FROM reporting.mock_daily_arrivals ORDER BY visit_date,tier_code',
      'popular_rides':'SELECT * FROM reporting.mock_popular_rides ORDER BY visit_date,attraction_name',
      'hourly_activity':'SELECT * FROM reporting.mock_daily_hour_grid ORDER BY visit_date,hour_of_day',
      'daily_purchases':'SELECT * FROM reporting.mock_daily_purchases ORDER BY purchase_date,tier_code',
      'workers':'SELECT * FROM reporting.cloud_worker_health ORDER BY worker_name',
      'database_tls':'SELECT ssl,version,cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid()',
      'inbox':'SELECT consumer,count(*) AS processed_events FROM analytics.event_inbox GROUP BY consumer ORDER BY consumer'
    }
    with engine.connect() as connection:
        result={}
        for name,query in queries.items():
            try:result[name]=[dict(r) for r in connection.execute(text(query)).mappings()]
            except Exception as error:
                print('SNAPSHOT_QUERY_FAILED='+name+' SQLSTATE='+str(getattr(getattr(error,'orig',None),'sqlstate','unknown')))
                raise
    print(json.dumps(result,default=str))
except Exception as error:
    print('AGGREGATE_SNAPSHOT_FAILED='+type(error).__name__);sys.exit(1)
'''
command=[str(root/'.local/tools/kubectl.exe'),'--kubeconfig',str(root/'.local/deployment/kubeconfig'),'-n','wonderland','exec','-i','deployment/wonderland-analytics-admissions','--','python','-']
result=subprocess.run(command,input=remote,text=True,capture_output=True,timeout=60)
if result.returncode:
    print(result.stdout.strip());raise SystemExit('Aggregate check failed; credentials and SQL errors suppressed')
facts=json.loads(result.stdout)
assert facts['database_tls'][0]['ssl'] is True
bootstrap=json.loads((root/'docs/evidence/step10e-database-verification.json').read_text(encoding='utf-8-sig'))
assert bootstrap['status']=='VERIFIED' and bootstrap['analytics_head']==['analytics_0004']
report={'status':'SNAPSHOT','label':args.label,'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'mode':'MOCK','facts':facts,'passwords_or_tokens_read_locally':False}
path=root/f'docs/evidence/step10e-analytics-{args.label}.json'
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'label':args.label,'purchases':facts['purchases'],'pipeline':facts['pipeline'],'workers':facts['workers'],'inbox':facts['inbox']},indent=2))
