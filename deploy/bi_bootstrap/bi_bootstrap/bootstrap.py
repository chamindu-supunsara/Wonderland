"""Owner-approved one-shot initialization; never prints credentials or SQL exceptions."""
import base64
import json
import os
import re
import secrets
import ssl
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

import boto3
from psycopg import sql
from sqlalchemy import create_engine, text
from db_bootstrap.bootstrap import Config, connect, db_url, ensure_role, migrate
from analytics_app.worker import apply_booking
from wonderland_events.transport import Event

VIEWS=('mock_daily_arrivals','mock_popular_rides','mock_hourly_activity','mock_daily_hour_grid',
       'mock_pipeline_health','mock_worker_health','mock_daily_purchases','mock_purchase_totals','cloud_worker_health')


def credential(client, arn, host, kind):
    expected={'host':host,'dbname':'wonderland_metabase' if kind=='app' else 'wonderland',
              'username':'wl_metabase_app' if kind=='app' else 'wl_metabase_reader','mode':'MOCK'}
    if client.describe_secret(SecretId=arn).get('VersionIdsToStages'):
        value=json.loads(client.get_secret_value(SecretId=arn)['SecretString'])
        assert all(value.get(k)==v for k,v in expected.items()),'Existing BI credential mismatch'
        assert len(value['password'])>=32
    else:
        value={**expected,'password':secrets.token_urlsafe(48)}
        if kind=='app':value['encryption_key']=secrets.token_hex(32)
        client.put_secret_value(SecretId=arn,SecretString=json.dumps(value))
    return value


def publish_app_secret(app):
    params=urlencode({'user':app['username'],'password':app['password'],'sslmode':'verify-full',
                      'sslrootcert':'/certs/rds-global-bundle.pem','connectTimeout':'10'})
    uri=f"jdbc:postgresql://{app['host']}:5432/{app['dbname']}?{params}"
    data={'MB_DB_CONNECTION_URI':uri,'MB_ENCRYPTION_SECRET_KEY':app['encryption_key']}
    host=os.environ['KUBERNETES_SERVICE_HOST'];port=os.environ.get('KUBERNETES_SERVICE_PORT_HTTPS','443')
    path='/var/run/secrets/kubernetes.io/serviceaccount/'
    token=Path(path+'token').read_text().strip()
    request=urllib.request.Request(f'https://{host}:{port}/api/v1/namespaces/wonderland/secrets/wonderland-metabase-app',
        method='PATCH',headers={'Authorization':'Bearer '+token,'Content-Type':'application/merge-patch+json'},
        data=json.dumps({'data':{k:base64.b64encode(v.encode()).decode() for k,v in data.items()}}).encode())
    with urllib.request.urlopen(request,context=ssl.create_default_context(cafile=path+'ca.crt'),timeout=20) as response:
        assert response.status==200


def bootstrap():
    host=os.environ['DATABASE_HOST']
    assert re.fullmatch(r'wonderland-demo\.[a-z0-9]+\.ap-south-1\.rds\.amazonaws\.com',host)
    client=boto3.client('secretsmanager',region_name='ap-south-1')
    master=json.loads(client.get_secret_value(SecretId=os.environ['MASTER_SECRET_ARN'])['SecretString'])
    assert master.get('host',host)==host
    config=Config(host,os.environ['MASTER_SECRET_ARN'],{},'/app/certs/rds-global-bundle.pem',Path('/app/services'))
    app=credential(client,os.environ['APP_SECRET_ARN'],host,'app')
    reader=credential(client,os.environ['REPORTING_SECRET_ARN'],host,'reporting')
    checks={}
    with connect(config,master['username'],master['password'],autocommit=True) as admin:
        admin.execute("SELECT pg_advisory_lock(hashtextextended('wonderland:bi-bootstrap',0))")
        owner=admin.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='wonderland_metabase'").fetchone()
        assert owner==('wl_metabase_owner',),'Expected the 10B private metadata database'
        ensure_role(admin,app['username'],app['password'])
        ensure_role(admin,reader['username'],reader['password'])
        admin.execute('GRANT wl_metabase_owner TO wl_metabase_app')
        admin.execute('GRANT wl_reporting_reader TO wl_metabase_reader')
        admin.execute('GRANT CONNECT ON DATABASE wonderland_metabase TO wl_metabase_app')
        admin.execute('GRANT CONNECT ON DATABASE wonderland TO wl_metabase_reader')
        admin.execute('ALTER ROLE wl_metabase_reader SET default_transaction_read_only=on')
        admin.execute('ALTER ROLE wl_metabase_reader SET statement_timeout=30000')
        admin.execute('ALTER ROLE wl_metabase_app CONNECTION LIMIT 15')
        admin.execute('ALTER ROLE wl_metabase_reader CONNECTION LIMIT 8')
        heads=migrate(config,master,'analytics')
        assert heads==['analytics_0004']
        admin.execute('GRANT USAGE ON SCHEMA reporting TO wl_reporting_reader,wl_analytics')
        for view in VIEWS:
            admin.execute(sql.SQL('GRANT SELECT ON reporting.{} TO wl_reporting_reader,wl_analytics').format(sql.Identifier(view)))
        # Reuse real persisted confirmation events, never synthetic purchase seeds.
        rows=admin.execute("SELECT id,aggregate_id,aggregate_version,created_at,payload FROM booking.outbox_events WHERE event_type='MockBookingConfirmed' ORDER BY created_at,id").fetchall()
        engine=create_engine(db_url(config,master['username'],master['password']),hide_parameters=True)
        try:
            from sqlalchemy.orm import Session
            with engine.begin() as connection:
                connection.execute(text('SET LOCAL ROLE wl_analytics_owner'))
                with Session(bind=connection,join_transaction_mode='create_savepoint') as session, session.begin():
                    for event_id,aggregate,version,occurred,payload in rows:
                        apply_booking(session,Event(event_id=event_id,source='booking',event_type='MockBookingConfirmed',
                            aggregate_id=aggregate,aggregate_version=version,occurred_at=occurred,data=payload))
                    session.flush()
        finally:engine.dispose()
        checks['analytics_migration_head']=True
        checks['reporter_cannot_connect_metadata_db']=not admin.execute("SELECT has_database_privilege('wl_metabase_reader','wonderland_metabase','CONNECT')").fetchone()[0]
        checks['app_cannot_connect_operational_db']=not admin.execute("SELECT has_database_privilege('wl_metabase_app','wonderland','CONNECT')").fetchone()[0]
    meta_config=Config(host,'',{},config.ca_file,config.services_root,database='wonderland_metabase')
    with connect(meta_config,master['username'],master['password'],autocommit=True) as admin_meta:
        admin_meta.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
        admin_meta.execute('GRANT USAGE,CREATE ON SCHEMA public TO wl_metabase_app')
    with connect(meta_config,app['username'],app['password'],autocommit=True) as metadata:
        checks['metadata_tls_verified']=metadata.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()[0]
        checks['app_can_create_only_metadata_schema']=metadata.execute("SELECT has_schema_privilege(current_user,'public','CREATE')").fetchone()[0]
    with connect(config,reader['username'],reader['password'],autocommit=True) as reporting:
        checks['reporting_tls_verified']=reporting.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()[0]
        checks['reporter_default_read_only']=reporting.execute('SHOW default_transaction_read_only').fetchone()[0]=='on'
        checks['raw_schemas_denied']=all(not reporting.execute('SELECT has_schema_privilege(current_user,%s,\'USAGE\')',(s,)).fetchone()[0] for s in ['catalog','booking','payment','admission','analytics'])
        checks['named_reporting_views_readable']=all(reporting.execute(sql.SQL('SELECT * FROM reporting.{} LIMIT 0').format(sql.Identifier(v))).description for v in VIEWS)
        checks['reporter_view_writes_denied']=all(not reporting.execute('SELECT has_table_privilege(current_user,%s,\'INSERT\')',('reporting.'+v,)).fetchone()[0] for v in VIEWS)
        totals=reporting.execute('SELECT purchases,guest_tickets,simulated_revenue_minor FROM reporting.mock_purchase_totals').fetchone()
    assert all(checks.values()),'BI verification failed'
    publish_app_secret(app)
    return {'status':'VERIFIED','checks':checks,'analytics_head':heads,'backfilled_actual_confirmation_events':len(rows),
            'mock_purchase_totals':{'purchases':totals[0],'guest_tickets':totals[1],'simulated_revenue_minor':totals[2]},
            'credentials_logged':False,'checkout':'mock','reporting_views':list(VIEWS)}


if __name__=='__main__':
    try:print('BI_BOOTSTRAP_REPORT='+json.dumps(bootstrap()),flush=True)
    except Exception as error:
        print('BI_BOOTSTRAP_FAILED='+type(error).__name__+'; sensitive error messages suppressed',flush=True)
        sys.exit(1)
