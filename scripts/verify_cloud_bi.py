"""Verify private BI runtime and removal of its temporary privilege, without credentials."""
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

root=Path(__file__).resolve().parents[1]
local=root/'.local/deployment'
base=[str(root/'.local/tools/kubectl.exe'),'--kubeconfig',str(local/'kubeconfig')]
def kube(*args): return json.loads(subprocess.check_output(base+list(args),text=True,encoding='utf-8',timeout=45))
def absent(namespace,kind,name):
    result=subprocess.run(base+['-n',namespace,'get',kind,name,'-o','name','--ignore-not-found'],capture_output=True,text=True,timeout=40)
    assert result.returncode==0,'Unable to verify Kubernetes absence'
    return not result.stdout.strip()
def http_status(path):
    try:
        with urllib.request.urlopen('http://127.0.0.1:3001'+path,timeout=30) as response:return response.status
    except urllib.error.HTTPError as error:return error.code
session=boto3.Session(profile_name='wonderland-feasibility',region_name='ap-south-1')
identity=session.client('sts').get_caller_identity()
assert identity['Account']=='708919751353' and ':assumed-role/AWSReservedSSO_WonderlandFeasibility_' in identity['Arn']
checks={}
deployment=kube('-n','wonderland','get','deployment','wonderland-metabase','-o','json')
pod=deployment['spec']['template']['spec'];container=pod['containers'][0]
checks['single_metabase_replica_ready']=deployment['spec']['replicas']==deployment['status'].get('readyReplicas')==deployment['status'].get('updatedReplicas')==1
checks['recreate_strategy']=deployment['spec']['strategy']['type']=='Recreate'
checks['image_pinned_current_patch']=container['image']=='metabase/metabase@sha256:3b968d64944840ec0ed452a94fb58301a0a8d8e4fe6d632a5956014a91a2b635'
checks['nonroot_readonly_no_escalation']=pod['securityContext']['runAsNonRoot'] and container['securityContext']['readOnlyRootFilesystem'] and not container['securityContext']['allowPrivilegeEscalation']
checks['no_kubernetes_token']=pod['automountServiceAccountToken'] is False
checks['only_metadata_runtime_secret']=container['envFrom']==[{'secretRef':{'name':'wonderland-metabase-app'}}]
env={v['name']:v.get('value') for v in container['env']}
checks['postgres_metadata_and_timezone']=env['MB_DB_TYPE']=='postgres' and env['MB_REPORT_TIMEZONE']==env['JAVA_TIMEZONE']=='Asia/Colombo'
checks['public_sharing_embedding_tracking_disabled']=all(env[k]=='false' for k in ['MB_ENABLE_PUBLIC_SHARING','MB_ENABLE_EMBEDDING','MB_ANON_TRACKING_ENABLED'])
checks['bounded_resources']=container['resources']['requests']=={'cpu':'250m','memory':'1536Mi','ephemeral-storage':'1Gi'} and container['resources']['limits']['memory']=='2Gi'
checks['jvm_startup_repair_persisted']='-Xmx768m' in env['JAVA_OPTS'] and 'MaxMetaspaceSize=256m' not in env['JAVA_OPTS']
service=kube('-n','wonderland','get','service','wonderland-metabase','-o','json')
checks['private_clusterip_only']=service['spec']['type']=='ClusterIP' and not service['spec'].get('externalIPs') and not service['spec'].get('loadBalancerIP')
checks['no_ingress']=not kube('-n','wonderland','get','ingress','-o','json')['items']
bindings=kube('-n','wonderland','get','targetgroupbindings','-o','json')['items']
checks['no_metabase_public_target_binding']=len(bindings)==4 and all(b['spec']['serviceRef']['name']!='wonderland-metabase' for b in bindings)
checks['original_two_nodes_only']=len(kube('get','nodes','-o','json')['items'])==2
runtime=kube('-n','wonderland','get','configmap','wonderland-runtime','-o','json')['data']
checks['all_mock_flags_and_pricing_unchanged']=all(runtime[k]=='true' for k in ['MOCK_PAYMENTS_ENABLED','MOCK_ADMISSION_ENABLED','MOCK_ANALYTICS_ENABLED']) and runtime['PRICING_MODE']=='projection'
images=json.loads((local/'bi-images.json').read_text(encoding='utf-8-sig'))
for name in ['analytics-admissions','analytics-bookings']:
    worker=kube('-n','wonderland','get','deployment','wonderland-'+name,'-o','json')
    checks[name+'_updated_and_ready']=worker['status'].get('readyReplicas')==1 and worker['spec']['template']['spec']['containers'][0]['image']==images['analytics']
checks['bootstrap_job_removed']=absent('wonderland-bootstrap','job','wonderland-bi-bootstrap')
checks['bootstrap_service_account_removed']=absent('wonderland-bootstrap','serviceaccount','bi-bootstrap')
checks['bootstrap_secret_writer_role_removed']=absent('wonderland','role','bi-bootstrap-secret-writer')
checks['bootstrap_secret_writer_binding_removed']=absent('wonderland','rolebinding','bi-bootstrap-secret-writer')
try:
    session.client('iam').get_role(RoleName='wonderland-demo-bi-bootstrap')
    checks['temporary_iam_role_removed']=False
except ClientError as error:
    assert error.response['Error']['Code']=='NoSuchEntity'
    checks['temporary_iam_role_removed']=True
associations=session.client('eks').list_pod_identity_associations(clusterName='wonderland-demo',namespace='wonderland-bootstrap',serviceAccount='bi-bootstrap')['associations']
checks['temporary_pod_identity_removed']=not associations
bi=json.loads((local/'bi-outputs.json').read_text(encoding='utf-8-sig'))['secret_arns']['value']
secret_metadata={name:session.client('secretsmanager').describe_secret(SecretId=arn) for name,arn in bi.items()}
checks['both_retained_bi_credentials_initialized']=len(secret_metadata)==2 and all(any('AWSCURRENT' in stages for stages in v.get('VersionIdsToStages',{}).values()) and not v.get('DeletedDate') for v in secret_metadata.values())
workloads=json.loads((local/'workload-outputs.json').read_text(encoding='utf-8-sig'))
queue_counts={}
for category in ['queues','processing_dlqs','delivery_dlqs']:
    for name,url in workloads[category]['value'].items():
        attributes=session.client('sqs').get_queue_attributes(QueueUrl=url,AttributeNames=['ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed'])['Attributes']
        queue_counts[category+'/'+name]={k:int(v) for k,v in attributes.items()}
checks['observed_queues_and_dlqs_drained']=all(all(value==0 for value in attributes.values()) for attributes in queue_counts.values())
checks['private_tunnel_health']=http_status('/api/health')==200
checks['metabase_cards_require_login']=http_status('/api/card')==401
checks['metabase_dashboards_require_login']=http_status('/api/dashboard')==401
database=json.loads((root/'docs/evidence/step10e-database-verification.json').read_text(encoding='utf-8-sig'))
checks['database_privilege_and_tls_checks_passed']=database['status']=='VERIFIED' and all(database['checks'].values())
report={'status':'VERIFIED' if all(checks.values()) else 'REVIEW_REQUIRED','verified_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'queue_counts':queue_counts,'checkout':'mock','passwords_or_tokens_read_locally':False,'planning_model_usd':64.41,'allowance_usd':75,'access':'Private loopback kubectl tunnel and separate Metabase login; not Cognito SSO'}
(root/'docs/evidence/step10e-live-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert all(checks.values()),'Inspect failed checks before completing Step10E'
