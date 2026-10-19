"""Inspect deployed private workloads and event metadata without retrieving secrets."""
import ast
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/deployment'
BASE = [str(ROOT / '.local/tools/kubectl.exe'), '--kubeconfig', str(LOCAL / 'kubeconfig')]


def kube(*args):
    return subprocess.check_output(BASE + list(args), text=True, timeout=40)


def main():
    session = boto3.Session(profile_name='wonderland-feasibility', region_name='ap-south-1')
    identity = session.client('sts').get_caller_identity()
    assert identity['Account'] == '708919751353'
    values = json.loads((LOCAL / 'workload-values.json').read_text(encoding='utf-8-sig'))
    outputs = json.loads((LOCAL / 'workload-outputs.json').read_text(encoding='utf-8-sig'))
    smoke = json.loads((ROOT / 'docs/evidence/step10c-smoke-verification.json').read_text())
    deployments = json.loads(kube('-n', 'wonderland', 'get', 'deployments', '-o', 'json'))['items']
    deployments = [d for d in deployments if d['metadata']['name'].startswith('wonderland-')]
    pods = json.loads(kube('-n', 'wonderland', 'get', 'pods', '-o', 'json'))['items']
    pods = [p for p in pods if p['metadata']['name'].startswith('wonderland-') and p['status']['phase'] not in ['Succeeded', 'Failed']]
    services = json.loads(kube('-n', 'wonderland', 'get', 'services', '-o', 'json'))['items']
    nodes = json.loads(kube('get', 'nodes', '-o', 'json'))['items']
    config = json.loads(kube('-n', 'wonderland', 'get', 'configmap', 'wonderland-runtime', '-o', 'json'))['data']
    checks = {
        'eleven_deployments_ready': len(deployments) == 11 and all(d['status'].get('readyReplicas') == d['spec']['replicas'] and d['status'].get('updatedReplicas') == d['spec']['replicas'] and d['status'].get('observedGeneration') == d['metadata']['generation'] for d in deployments),
        'fifteen_application_pods_ready': len(pods) == 15 and all(p['status']['phase'] == 'Running' and all(c['ready'] for c in p['status'].get('containerStatuses', [])) for p in pods),
        'two_existing_workers_ready': len(nodes) == 2 and all(any(c['type'] == 'Ready' and c['status'] == 'True' for c in n['status']['conditions']) for n in nodes),
        'four_private_clusterip_services': len(services) == 4 and all(s['spec']['type'] == 'ClusterIP' for s in services),
        'mock_modes_enabled': all(config[key] == 'true' for key in ['MOCK_PAYMENTS_ENABLED', 'MOCK_ADMISSION_ENABLED', 'MOCK_ANALYTICS_ENABLED']),
        'verified_projection_pricing': config['PRICING_MODE'] == values['pricingMode'] == smoke['pricing_mode'] == 'projection' and smoke['status'] == 'VERIFIED' and all(smoke['checks'].values()),
        'browser_cors_matches_current_stage': json.loads(config['CORS_ORIGINS']) == ([values['frontendOrigin']] if values.get('frontendOrigin') else []),
        'all_five_images_digest_pinned': len(values['images']) == 5 and all('@sha256:' in image for image in values['images'].values()),
        'pods_hardened': all(p['spec'].get('automountServiceAccountToken') is False and p['spec']['securityContext']['runAsNonRoot'] and all(c['securityContext']['readOnlyRootFilesystem'] and not c['securityContext']['allowPrivilegeEscalation'] for c in p['spec']['containers']) for p in pods),
        'database_credentials_from_own_secret_only': True,
    }
    # Values file relies on chart defaults for secret references and worker service mappings.
    service_for_worker = {'booking-maintenance': 'booking', 'catalog-publisher': 'catalog', 'booking-publisher': 'booking', 'admission-publisher': 'admission', 'booking-prices': 'booking', 'analytics-bookings': 'analytics', 'analytics-admissions': 'analytics'}
    for d in deployments:
        name = d['metadata']['name'].removeprefix('wonderland-')
        service = service_for_worker.get(name, name)
        refs = [e['secretRef']['name'] for e in d['spec']['template']['spec']['containers'][0]['envFrom'] if 'secretRef' in e]
        checks['database_credentials_from_own_secret_only'] &= refs == ['wonderland-' + service]
    associations = session.client('eks').list_pod_identity_associations(clusterName='wonderland-demo')['associations']
    expected_roles = outputs['worker_roles']['value']
    actual = {}
    for a in associations:
        if a['namespace'] == 'wonderland':
            detail = session.client('eks').describe_pod_identity_association(clusterName='wonderland-demo', associationId=a['associationId'])['association']
            actual[a['serviceAccount'].removeprefix('wonderland-')] = detail['roleArn']
    checks['six_exact_worker_identity_associations'] = actual == expected_roles
    iam = session.client('iam')
    for name, arn in expected_roles.items():
        role_name = arn.split('/')[-1]
        trust = iam.get_role(RoleName=role_name)['Role']['AssumeRolePolicyDocument']['Statement'][0]
        tags = trust['Condition']['StringEquals']
        checks[name + '_trust_scoped'] = trust['Principal'] == {'Service': 'pods.eks.amazonaws.com'} and tags['aws:RequestTag/kubernetes-namespace'] == 'wonderland' and tags['aws:RequestTag/kubernetes-service-account'] == 'wonderland-' + name and tags['aws:RequestTag/eks-cluster-arn'].endswith(':cluster/wonderland-demo')
    sqs = session.client('sqs')
    queue_counts = {}
    for name, url in outputs['queues']['value'].items():
        attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['All'])['Attributes']
        checks[name + '_queue_encrypted_and_redrive'] = attrs.get('SqsManagedSseEnabled') == 'true' and json.loads(attrs['RedrivePolicy'])['maxReceiveCount'] == 5 and attrs['VisibilityTimeout'] == '60'
        queue_counts[name] = {k: int(attrs.get(k, 0)) for k in ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']}
        for suffix in ['-dlq', '-delivery-dlq']:
            dlq = sqs.get_queue_url(QueueName='wonderland-demo-' + name + suffix)['QueueUrl']
            count = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=['ApproximateNumberOfMessages'])['Attributes']
            queue_counts[name + suffix] = {'ApproximateNumberOfMessages': int(count['ApproximateNumberOfMessages'])}
    checks['six_dead_letter_queues_empty_at_check'] = all(c['ApproximateNumberOfMessages'] == 0 for n, c in queue_counts.items() if n.endswith('-dlq'))
    sns = session.client('sns')
    for name, arn in outputs['topics']['value'].items():
        attrs = sns.get_topic_attributes(TopicArn=arn)['Attributes']
        checks[name + '_topic_encrypted'] = attrs['KmsMasterKeyId'] == 'alias/aws/sns'
        subscriptions = sns.list_subscriptions_by_topic(TopicArn=arn)['Subscriptions']
        checks[name + '_one_sqs_subscription'] = len(subscriptions) == 1 and subscriptions[0]['Protocol'] == 'sqs'
        sub = sns.get_subscription_attributes(SubscriptionArn=subscriptions[0]['SubscriptionArn'])['Attributes']
        checks[name + '_raw_delivery_and_delivery_dlq'] = sub['RawMessageDelivery'] == 'true' and 'deadLetterTargetArn' in json.loads(sub['RedrivePolicy'])
    outboxes = {}
    for service, module in [('catalog', 'app.event_worker'), ('booking', 'booking_app.event_worker'), ('admission', 'admission_app.event_worker')]:
        outboxes[service] = ast.literal_eval(kube('-n', 'wonderland', 'exec', 'deployment/wonderland-' + service + '-publisher', '--', 'python', '-m', module, 'status').strip())
    checks['outboxes_have_no_pending_or_failed_events'] = all(c['pending'] == c['failed'] == 0 for c in outboxes.values())
    for kind in ['jobs', 'configmaps', 'pods']:
        items = json.loads(kube('-n', 'wonderland', 'get', kind, '-o', 'json'))['items']
        checks['verification_' + kind + '_removed'] = not any(i['metadata']['name'].startswith('wonderland-step10c-smoke') for i in items)
    report = {'status': 'VERIFIED' if all(checks.values()) else 'REVIEW_REQUIRED', 'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'checks': checks, 'deployments': {d['metadata']['name']: d['status'].get('readyReplicas', 0) for d in deployments},
              'image_digests': values['images'], 'queue_counts_approximate': queue_counts, 'outboxes': outboxes,
              'application_pod_restarts': sum(c['restartCount'] for p in pods for c in p['status'].get('containerStatuses', [])),
              'checkout': 'mock', 'secret_values_retrieved': False, 'public_application_hosted': False,
              'limitations': ['Queue counts are approximate; empty DLQs do not prove a poison-message redrive test.', 'Authenticated booking/payment/admission and hosted analytics are later stages.', 'Internal API HTTP is private; service-hop TLS remains a later routing task.', 'Budget is a planning allowance; actual delayed charges are not verified.']}
    (ROOT / 'docs/evidence/step10c-live-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    assert all(checks.values()), 'Inspect failed workload verification checks'


if __name__ == '__main__':
    main()
