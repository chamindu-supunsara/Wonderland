"""Read-only post-bootstrap checks; never retrieve secret values."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]


def main():
    session = boto3.Session(profile_name='wonderland-feasibility', region_name='ap-south-1')
    identity = session.client('sts').get_caller_identity()
    assert identity['Account'] == '708919751353' and ':assumed-role/AWSReservedSSO_WonderlandFeasibility_' in identity['Arn']
    outputs = json.loads((ROOT / '.local/deployment/foundation-outputs.json').read_text(encoding='utf-8-sig'))
    kubectl = str(ROOT / '.local/tools/kubectl.exe')
    base = [kubectl, '--kubeconfig', str(ROOT / '.local/deployment/kubeconfig')]

    def kube(*args):
        return subprocess.check_output(base + list(args), text=True)

    # Output keys and lengths only; do not return credential values to this process.
    keys = kube('-n', 'wonderland', 'get', 'secrets', '-o',
                'go-template={{range .items}}{{.metadata.name}}:{{range $k,$v := .data}}{{$k}}={{len $v}},{{end}}{{"\\n"}}{{end}}')
    lines = dict(line.split(':', 1) for line in keys.strip().splitlines())
    services = ('catalog', 'booking', 'payment', 'admission', 'analytics')
    runtime_secrets = {}
    for service in services:
        fields = lines.get('wonderland-' + service, '').rstrip(',').split('=')
        runtime_secrets[service] = len(fields) == 2 and fields[0] == 'DATABASE_URL' and int(fields[1]) > 0
    metadata = [session.client('secretsmanager').describe_secret(SecretId=arn)
                for arn in outputs['service_secret_arns']['value'].values()]
    current = all(any('AWSCURRENT' in stages for stages in value.get('VersionIdsToStages', {}).values()) for value in metadata)
    associations = session.client('eks').list_pod_identity_associations(clusterName='wonderland-demo')['associations']
    bootstrap_associations = [a for a in associations if a.get('namespace') == 'wonderland-bootstrap' and a.get('serviceAccount') == 'db-bootstrap']
    role_absent = False
    try:
        session.client('iam').get_role(RoleName='wonderland-demo-db-bootstrap')
    except ClientError as error:
        if error.response['Error']['Code'] != 'NoSuchEntity':
            raise
        role_absent = True
    stack_absent = False
    try:
        stack = session.client('cloudformation').describe_stacks(StackName='wonderland-db-bootstrap-access')['Stacks'][0]
        stack_absent = stack['StackStatus'] == 'DELETE_COMPLETE'
    except ClientError as error:
        if error.response['Error']['Code'] != 'ValidationError' or 'does not exist' not in error.response['Error']['Message']:
            raise
        stack_absent = True
    checks = {'five_runtime_secret_urls_present': all(runtime_secrets.values()),
              'five_service_secrets_have_current_versions': len(metadata) == 5 and current,
              'temporary_role_removed': role_absent,
              'temporary_pod_identity_removed': not bootstrap_associations,
              'temporary_stack_removed': stack_absent}
    resources = [('bootstrap_jobs_removed', 'wonderland-bootstrap', 'jobs'),
                 ('bootstrap_pods_removed', 'wonderland-bootstrap', 'pods'),
                 ('bootstrap_service_account_removed', 'wonderland-bootstrap', 'serviceaccounts'),
                 ('bootstrap_role_removed', 'wonderland', 'roles'),
                 ('bootstrap_rolebinding_removed', 'wonderland', 'rolebindings')]
    for name, namespace, kind in resources:
        items = json.loads(kube('-n', namespace, 'get', kind, '-o', 'json'))['items']
        checks[name] = not any(i['metadata']['name'].startswith(('wonderland-db-bootstrap', 'db-bootstrap')) for i in items)
    db = session.client('rds').describe_db_instances(DBInstanceIdentifier='wonderland-demo')['DBInstances'][0]
    checks['database_available_and_private'] = db['DBInstanceStatus'] == 'available' and not db['PubliclyAccessible']
    result = {'status': 'VERIFIED' if all(checks.values()) else 'REVIEW_REQUIRED', 'checks': checks,
              'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'checkout': 'mock',
              'secret_values_read_by_verifier': False, 'runtime_secret_fields_verified': runtime_secrets}
    (ROOT / 'docs/evidence/step10b-cleanup-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    assert all(checks.values()), 'Review the failed cleanup verification checks'
    path = ROOT / 'docs/evidence/step10b-database-verification.json'
    report = json.loads(path.read_text(encoding='utf-8-sig'))
    report['temporary_access_removed'] = True
    report['cloud_bootstrap_runs'] = 1
    report['retry_test_scope'] = 'Two complete local PostgreSQL integration runs; one live RDS run'
    path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
