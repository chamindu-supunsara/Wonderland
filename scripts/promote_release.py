"""Review and promote verified mock artifacts using the existing operator SSO session."""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import boto3
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manifest', ROOT / 'scripts/ci/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
CONTRACT = json.loads((ROOT / 'deploy/automation/contract.json').read_text())
AUTHENTICATION_PROBES = ('/api/v1/bookings/me', '/api/v1/users/me')


def tool(name):
    bundled = {'helm': '.local/tools/helm/windows-amd64/helm.exe',
               'kubectl': '.local/tools/kubectl.exe'}[name]
    path = ROOT / bundled
    return str(path) if path.exists() else shutil.which(name) or name


def run(args, timeout=90):
    return subprocess.check_output([str(a) for a in args], cwd=ROOT, text=True,
                                   encoding='utf-8', timeout=timeout)


def kube(*args):
    return json.loads(run([tool('kubectl'), '--kubeconfig', ROOT / '.local/deployment/kubeconfig',
                           *args, '-o', 'json']))


def helm(*args):
    return run([tool('helm'), *args, '--kubeconfig', ROOT / '.local/deployment/kubeconfig'], 660)


def dump(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def session():
    current = boto3.Session(profile_name='wonderland-feasibility', region_name='ap-south-1')
    identity = current.client('sts').get_caller_identity()
    if (identity['Account'] != CONTRACT['account']
            or ':assumed-role/AWSReservedSSO_WonderlandFeasibility_' not in identity['Arn']):
        raise ValueError('Unexpected AWS operator')
    return current


def validate(folder):
    manifest = release.validate(json.loads((folder / 'manifest.json').read_text()), folder)
    receipt = json.loads((folder / 'github-receipt.json').read_text())
    if manifest['commit'] != receipt['commit']:
        raise ValueError('GitHub run and artifact source differ')
    if run(['git', 'rev-parse', 'HEAD']).strip() != manifest['commit']:
        raise ValueError('Review and check out the exact release commit before promotion')
    if run(['git', 'status', '--porcelain', '--untracked-files=no']).strip():
        raise ValueError('Commit or restore tracked edits before reviewing a deployment')
    return manifest


def read_values():
    values = json.loads(helm('get', 'values', 'wonderland', '-n', 'wonderland', '-o', 'json'))
    baseline = json.loads((ROOT / 'deploy/automation/workload-values.json').read_text())
    if {k: v for k, v in values.items() if k != 'images'} != {
            k: v for k, v in baseline.items() if k != 'images'}:
        raise ValueError('Live Helm configuration differs from approved mock baseline')
    config = kube('-n', 'wonderland', 'get', 'configmap', 'wonderland-runtime')['data']
    if not all(config[k] == 'true' for k in
               ['MOCK_PAYMENTS_ENABLED', 'MOCK_ADMISSION_ENABLED', 'MOCK_ANALYTICS_ENABLED']):
        raise ValueError('Live environment is not fully mock')
    if config['PRICING_MODE'] != 'projection':
        raise ValueError('Pricing projection must remain enabled')
    return values


def prepare(folder):
    manifest = validate(folder)
    aws = session()
    values = read_values()
    ecr = aws.client('ecr')
    for name, image in manifest['images'].items():
        ecr.describe_images(repositoryName='wonderland-demo/' + name,
                            imageIds=[{'imageDigest': image.split('@')[1]}])
    nodes = kube('get', 'nodes')['items']
    if len(nodes) != 2 or not all(any(c['type'] == 'Ready' and c['status'] == 'True'
                                     for c in n['status']['conditions']) for n in nodes):
        raise ValueError('Exactly two healthy existing nodes are required')
    pods = kube('get', 'pods', '-A')['items']
    active = [p for p in pods if p['status']['phase'] not in ['Succeeded', 'Failed']]
    if len(active) + 4 > sum(int(n['status']['allocatable']['pods']) for n in nodes):
        raise ValueError('Insufficient existing Pod slots for bounded API surge')
    previous = ROOT / '.local/deployment/frontend-release.zip'
    if not previous.is_file():
        raise ValueError('Preserve the current known-good frontend archive before promotion')
    shutil.copyfile(previous, folder / 'previous-frontend.zip')
    dump(folder / 'previous-values.json', values)
    values['images'] = manifest['images']
    dump(folder / 'values.json', values)
    rendered = helm('template', 'wonderland', 'deploy/helm/wonderland', '-n', 'wonderland',
                    '-f', folder / 'values.json', '--kube-version', '1.35.0')
    docs = [d for d in yaml.safe_load_all(rendered) if d]
    deployments = [d for d in docs if d['kind'] == 'Deployment']
    if len(deployments) != 11 or any(d['kind'] in ['Secret', 'Ingress', 'Job'] for d in docs):
        raise ValueError('Unexpected chart resources')
    live = {d['metadata']['name']: d for d in kube('-n', 'wonderland', 'get', 'deployments')['items']}
    for d in deployments:
        old = live[d['metadata']['name']]['spec']
        if (d['spec']['replicas'] != old['replicas'] or
                d['spec']['template']['spec']['containers'][0]['resources'] !=
                old['template']['spec']['containers'][0]['resources']):
            raise ValueError('Resource/replica change requires separate review')
    history = json.loads(helm('history', 'wonderland', '-n', 'wonderland', '-o', 'json'))
    review = {'status': 'PREPARED_NOT_APPLIED', 'commit': manifest['commit'],
              'run_id': manifest['run_id'], 'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
              'previous_revision': max(h['revision'] for h in history),
              'manifest_sha256': release.sha(folder / 'manifest.json'),
              'values_sha256': release.sha(folder / 'values.json'),
              'previous_values_sha256': release.sha(folder / 'previous-values.json'),
              'previous_frontend_sha256': release.sha(folder / 'previous-frontend.zip'),
              'mode': 'MOCK', 'existing_nodes': 2, 'additional_infrastructure': 0,
              'planning_usd': 65.41, 'allowance_usd': 75}
    dump(folder / 'review.json', review)
    print(json.dumps(review, indent=2))


def publish(aws, archive):
    client = aws.client('amplify')
    args = {'appId': CONTRACT['amplify_app_id'], 'branchName': 'main'}
    deployment = client.create_deployment(**args)
    try:
        req = urllib.request.Request(deployment['zipUploadUrl'], data=archive.read_bytes(),
                                     method='PUT', headers={'Content-Type': 'application/zip'})
        with urllib.request.urlopen(req, timeout=120) as response:
            if response.status not in [200, 201]:
                raise RuntimeError('Upload failed')
    except urllib.error.URLError:
        raise RuntimeError('Amplify upload failed; signed URL suppressed') from None
    client.start_deployment(**args, jobId=deployment['jobId'])
    for _ in range(120):
        status = client.get_job(**args, jobId=deployment['jobId'])['job']['summary']['status']
        if status == 'SUCCEED':
            return deployment['jobId']
        if status in ['FAILED', 'CANCELLED']:
            raise RuntimeError('Amplify deployment did not succeed')
        time.sleep(5)
    client.stop_job(**args, jobId=deployment['jobId'])
    raise TimeoutError('Amplify deployment timed out and was stopped')


def verify(images, archive):
    checks = {}
    read_values()
    live = {d['metadata']['name']: d for d in kube('-n', 'wonderland', 'get', 'deployments')['items']}
    baseline = json.loads((ROOT / 'deploy/automation/workload-values.json').read_text())
    names = {f'wonderland-{s}': s for s in ['catalog', 'booking', 'payment', 'admission']}
    for name, worker in baseline['workers'].items():
        service = {'analytics-bookings': 'analytics', 'analytics-admissions': 'analytics',
                   'booking-maintenance': 'booking', 'booking-prices': 'booking'}.get(name)
        names['wonderland-' + name] = service or name.removesuffix('-publisher')
    for name, service in names.items():
        d = live[name]
        checks[name] = (d['spec']['template']['spec']['containers'][0]['image'] == images[service]
                       and d['status'].get('updatedReplicas') == d['spec']['replicas']
                       and d['status'].get('readyReplicas') == d['spec']['replicas'])
    for service in ['catalog', 'booking', 'payment', 'admission']:
        code = "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=10).status)"
        status = run([tool('kubectl'), '--kubeconfig', ROOT / '.local/deployment/kubeconfig',
                      '-n', 'wonderland', 'exec', 'deployment/wonderland-' + service,
                      '--', 'python', '-c', code]).strip()
        checks[service + '_private_readiness'] = status == '200'
    with release.ZipFile(archive) as zipped:
        expected_index = zipped.read('index.html')
    for _ in range(12):
        with urllib.request.urlopen(CONTRACT['frontend_origin'] + '/', timeout=30) as response:
            actual = response.read()
        if actual == expected_index:
            break
        time.sleep(5)
    checks['exact_frontend_release_served'] = actual == expected_index
    with urllib.request.urlopen(CONTRACT['frontend_origin'] + '/app-config.json', timeout=30) as response:
        checks['frontend_runtime_config'] = json.load(response) == json.loads(
            (ROOT / 'deploy/automation/public-app-config.json').read_text())
    for path in ['/api/v1/attractions', '/api/v1/ticket-tiers']:
        with urllib.request.urlopen(CONTRACT['api_endpoint'] + path, timeout=30) as response:
            checks[path] = response.status == 200 and bool(json.load(response))
    for path in AUTHENTICATION_PROBES:
        try:
            urllib.request.urlopen(CONTRACT['api_endpoint'] + path, timeout=30)
            checks[path + '_requires_login'] = False
        except urllib.error.HTTPError as error:
            checks[path + '_requires_login'] = error.code in [401, 403]
    service = kube('-n', 'wonderland', 'get', 'service', 'wonderland-metabase')
    checks['metabase_stays_private'] = service['spec']['type'] == 'ClusterIP'
    checks['two_existing_nodes'] = len(kube('get', 'nodes')['items']) == 2
    if not all(checks.values()):
        raise ValueError('Post-deployment verification failed: ' + ','.join(k for k,v in checks.items() if not v))
    return checks


def apply(folder, rollback=False):
    manifest = validate(folder)
    aws = session()
    review = json.loads((folder / 'review.json').read_text())
    if not rollback:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(review['prepared_at_utc'])
        if age.total_seconds() > 1800:
            raise ValueError('Preparation is older than 30 minutes; prepare and review again')
    if datetime.now(timezone.utc) >= datetime.fromisoformat('2026-10-25T18:00:00+05:30'):
        raise ValueError('Trial cleanup deadline reached; do not deploy without a renewed plan')
    for name, key in [('manifest.json', 'manifest_sha256'), ('values.json', 'values_sha256'),
                      ('previous-values.json', 'previous_values_sha256'),
                      ('previous-frontend.zip', 'previous_frontend_sha256')]:
        if release.sha(folder / name) != review[key]:
            raise ValueError('Reviewed artifact changed: ' + name)
    current = read_values()
    expected = manifest['images'] if rollback else json.loads((folder / 'previous-values.json').read_text())['images']
    if current['images'] != expected:
        raise ValueError('Live release changed since preparation; review again')
    history = json.loads(helm('history', 'wonderland', '-n', 'wonderland', '-o', 'json'))
    if not rollback and max(h['revision'] for h in history) != review['previous_revision']:
        raise ValueError('Helm revision changed since preparation')
    values = folder / ('previous-values.json' if rollback else 'values.json')
    archive = folder / ('previous-frontend.zip' if rollback else 'frontend.zip')
    print(helm('upgrade', 'wonderland', 'deploy/helm/wonderland', '-n', 'wonderland', '-f', values,
               '--rollback-on-failure', '--wait', '--timeout', '600s'))
    job = publish(aws, archive)
    checks = verify(json.loads(values.read_text())['images'], archive)
    shutil.copyfile(archive, ROOT / '.local/deployment/frontend-release.zip')
    shutil.copyfile(values, ROOT / '.local/deployment/workload-values.json')
    result = {'status': 'ROLLED_BACK' if rollback else 'DEPLOYED', 'mode': 'MOCK',
              'commit': manifest['commit'], 'run_id': manifest['run_id'], 'amplify_job_id': job,
              'completed_at_utc': datetime.now(timezone.utc).isoformat(),
              'images': json.loads(values.read_text())['images'], 'post_deploy_checks': checks}
    dump(folder / ('rollback.json' if rollback else 'deployment.json'), result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('phase', choices=['prepare', 'apply', 'rollback'])
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare(args.folder.resolve())
    else:
        apply(args.folder.resolve(), args.phase == 'rollback')
