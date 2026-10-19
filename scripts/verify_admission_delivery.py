"""Match three actual Admission outbox/SNS receipts to committed Analytics inbox facts."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1]
base=[str(root/'.local/tools/kubectl.exe'),'--kubeconfig',str(root/'.local/deployment/kubeconfig'),'-n','wonderland','exec','-i']
def query(deployment,sql,parameters):
    payload=json.dumps({'query':sql,'parameters':parameters})
    remote='''import os,json,sys
from sqlalchemy import create_engine,text
try:
    request=json.loads(%r)
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True,connect_args={'connect_timeout':10})
    with engine.connect() as connection:
        rows=[dict(r) for r in connection.execute(text(request['query']),request['parameters']).mappings()]
    print(json.dumps(rows,default=str))
except Exception as error:
    print('DELIVERY_CHECK_FAILED='+type(error).__name__);sys.exit(1)
''' % payload
    result=subprocess.run(base+['deployment/'+deployment,'--','python','-'],input=remote,text=True,capture_output=True,timeout=60)
    if result.returncode:raise RuntimeError('Private delivery metadata query failed; sensitive details suppressed')
    return json.loads(result.stdout)
source=query('wonderland-admission',
    '''SELECT e.id,e.aggregate_id,e.aggregate_version,e.event_type,e.published_at,e.sns_message_id,e.failed_at
       FROM admission.outbox_events e JOIN admission.check_ins a ON a.id=e.aggregate_id
       JOIN admission.ticket_projection t ON t.id=a.ticket_id WHERE t.booking_id=:booking ORDER BY e.aggregate_version''',
    {'booking':'2680caeb-3b95-4214-b671-8931bd7086e2'})
assert len(source)==3
destination=query('wonderland-analytics-admissions',
    '''SELECT e.event_id,e.admission_id,e.aggregate_version,e.event_type,i.consumer
       FROM analytics.mock_events e JOIN analytics.event_inbox i ON i.event_id=e.event_id
       WHERE e.admission_id=:admission AND i.consumer='analytics-admissions-v1' ORDER BY e.aggregate_version''',
    {'admission':source[0]['aggregate_id']})
checks={'three_source_events_published_to_sns':len(source)==3 and all(e['published_at'] and e['sns_message_id'] and e['failed_at'] is None for e in source),
        'source_versions_one_two_three':[e['aggregate_version'] for e in source]==[1,2,3],
        'one_checkin_two_ride_event_types':[e['event_type'] for e in source]==['MockGuestCheckedIn','MockRideUsed','MockRideUsed'],
        'exact_source_ids_in_committed_analytics_inbox':{e['id'] for e in source}=={e['event_id'] for e in destination} and len(destination)==3,
        'versions_and_types_preserved':[(e['aggregate_version'],e['event_type']) for e in source]==[(e['aggregate_version'],e['event_type']) for e in destination]}
report={'status':'VERIFIED' if all(checks.values()) else 'REVIEW_REQUIRED','verified_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'source_events':source,'destination_events':destination,'mode':'MOCK','passwords_or_tokens_read_locally':False}
(root/'docs/evidence/step10e-event-delivery.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert all(checks.values())
