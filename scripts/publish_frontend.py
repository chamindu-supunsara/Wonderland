"""Upload the built Angular bundle; never print Amplify's signed upload URL."""
import hashlib
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import boto3

ROOT=Path(__file__).resolve().parents[1]
def main():
    outputs=json.loads((ROOT/'.local/deployment/routing-outputs.json').read_text(encoding='utf-8-sig'))
    dist=ROOT/'frontend/dist/wonderland/browser'
    assert (dist/'index.html').is_file()
    config={'apiBaseUrl':outputs['api_endpoint']['value']+'/api/v1','cognito':{'region':'ap-south-1','userPoolId':'ap-south-1_aBuDlZ9RC','userPoolClientId':'202ssal4mlube43ttm0j5m3k4i'}}
    (dist/'app-config.json').write_text(json.dumps(config,indent=2)+'\n')
    archive=ROOT/'.local/deployment/frontend-release.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED) as zipped:
        for path in sorted(dist.rglob('*')):
            if path.is_file():zipped.write(path,str(path.relative_to(dist)).replace('\\','/'))
    client=boto3.Session(profile_name='wonderland-feasibility',region_name='ap-south-1').client('amplify')
    app=outputs['amplify_app_id']['value']
    deployment=client.create_deployment(appId=app,branchName='main')
    request=urllib.request.Request(deployment['zipUploadUrl'],data=archive.read_bytes(),method='PUT',headers={'Content-Type':'application/zip'})
    with urllib.request.urlopen(request,timeout=90) as response:assert response.status in [200,201]
    client.start_deployment(appId=app,branchName='main',jobId=deployment['jobId'])
    previous=None
    for _ in range(120):
        job=client.get_job(appId=app,branchName='main',jobId=deployment['jobId'])['job']['summary']
        status=job['status']
        if status!=previous:print('Amplify deployment: '+status,flush=True);previous=status
        if status=='SUCCEED':break
        if status in ['FAILED','CANCELLED']:raise RuntimeError('Amplify deployment did not succeed')
        time.sleep(3)
    else:raise TimeoutError('Amplify deployment timeout')
    report={'status':'DEPLOYED','completed_at_utc':datetime.now(timezone.utc).isoformat(),'app_id':app,'branch':'main','job_id':deployment['jobId'],'frontend_origin':outputs['frontend_origin']['value'],'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_bytes':archive.stat().st_size,'public_runtime_config':config,'checkout':'mock','upload_url_logged':False}
    (ROOT/'docs/evidence/step10d-frontend-deployment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':
    try:main()
    except Exception as error:
        # HTTP errors can include signed upload URLs. Keep messages/tracebacks private.
        print('FRONTEND_DEPLOYMENT_FAILED='+type(error).__name__)
        if hasattr(error,'operation_name') and hasattr(error,'response'):
            print('AWS_OPERATION='+error.operation_name+' ERROR_CODE='+error.response.get('Error',{}).get('Code','unknown'))
        sys.exit(1)
