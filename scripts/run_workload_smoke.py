"""Run and remove the private smoke Job; never retrieve Secret values."""
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/deployment'
BASE = [str(ROOT / '.local/tools/kubectl.exe'), '--kubeconfig', str(LOCAL / 'kubeconfig'), '-n', 'wonderland']
NAME = 'wonderland-step10c-smoke'


def kubectl(*args, check=True):
    return subprocess.run(BASE + list(args), text=True, capture_output=True, check=check, timeout=30)


def main():
    values = json.loads((LOCAL / 'workload-values.json').read_text(encoding='utf-8-sig'))
    outputs = json.loads((LOCAL / 'workload-outputs.json').read_text(encoding='utf-8-sig'))
    job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': NAME},
           'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 180, 'ttlSecondsAfterFinished': 300,
                    'template': {'spec': {'serviceAccountName': 'wonderland-catalog-publisher',
                     'automountServiceAccountToken': False, 'restartPolicy': 'Never',
                     'securityContext': {'runAsNonRoot': True, 'runAsUser': 10001, 'runAsGroup': 10001, 'seccompProfile': {'type': 'RuntimeDefault'}},
                     'containers': [{'name': 'verify', 'image': values['images']['catalog'],
                       'command': ['python', '/verification/workloads.py'],
                       'env': [
                         {'name': 'PYTHONPATH', 'value': '/app'},
                         {'name': 'CATALOG_DATABASE_URL', 'valueFrom': {'secretKeyRef': {'name': 'wonderland-catalog', 'key': 'DATABASE_URL'}}},
                         {'name': 'BOOKING_DATABASE_URL', 'valueFrom': {'secretKeyRef': {'name': 'wonderland-booking', 'key': 'DATABASE_URL'}}},
                         {'name': 'CATALOG_TOPIC_ARN', 'value': outputs['topics']['value']['catalog']},
                         {'name': 'AWS_REGION', 'value': 'ap-south-1'}, {'name': 'AWS_EC2_METADATA_DISABLED', 'value': 'true'}],
                       'securityContext': {'readOnlyRootFilesystem': True, 'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                       'resources': {'requests': {'cpu': '100m', 'memory': '128Mi'}, 'limits': {'cpu': '250m', 'memory': '256Mi'}},
                       'volumeMounts': [{'name': 'script', 'mountPath': '/verification', 'readOnly': True}]}],
                     'volumes': [{'name': 'script', 'configMap': {'name': NAME}}]}}}}
    config = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': NAME},
              'data': {'workloads.py': (ROOT / 'deploy/verification/workloads.py').read_text()}}
    manifest = LOCAL / 'workload-smoke.yaml'
    manifest.write_text(yaml.safe_dump_all([config, job]))
    # This named disposable verification Job is never a persistent application workload.
    kubectl('delete', 'job', NAME, '--ignore-not-found=true', '--wait=true')
    logs = ''
    try:
        kubectl('apply', '-f', str(manifest))
        for _ in range(42):
            state = json.loads(kubectl('get', 'job', NAME, '-o', 'json').stdout)['status']
            if state.get('succeeded') or state.get('failed'):
                break
            time.sleep(5)
        response = kubectl('logs', f'job/{NAME}', check=False)
        logs = response.stdout
        (LOCAL / 'workload-smoke.log').write_text(logs)
        assert state.get('succeeded'), 'Smoke Job failed; inspect sanitized workload-smoke.log and scheduling'
        reports = [line.split('=', 1)[1] for line in logs.splitlines() if line.startswith('WORKLOAD_REPORT=')]
        assert len(reports) == 1
        report = json.loads(reports[0])
        event_id = report['duplicate_event_id']
        for _ in range(10):
            consumer_logs = kubectl('logs', 'deployment/wonderland-booking-prices', '--since=120s').stdout
            duplicate_observed = any(event_id in line and 'duplicate=True' in line for line in consumer_logs.splitlines())
            if duplicate_observed:
                break
            time.sleep(2)
        assert duplicate_observed, 'No consumer duplicate acknowledgement observed yet'
        report['checks']['live_duplicate_acknowledgement_observed'] = True
        report['pricing_mode'] = values['pricingMode']
        report['verified_at_utc'] = datetime.now(timezone.utc).isoformat()
        (ROOT / 'docs/evidence/step10c-smoke-verification.json').write_text(json.dumps(report, indent=2) + '\n')
        (ROOT / f"docs/evidence/step10c-{values['pricingMode']}-smoke-verification.json").write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        kubectl('delete', 'job', NAME, '--ignore-not-found=true', '--wait=true', check=False)
        kubectl('delete', 'configmap', NAME, '--ignore-not-found=true', check=False)


if __name__ == '__main__':
    main()
