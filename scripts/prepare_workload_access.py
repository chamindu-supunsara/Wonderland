"""Generate the dedicated Step10C operator policy; leave the existing inline policy unchanged."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'arn:aws:'
REGION = 'ap-south-1'
ACCOUNT = '708919751353'
WORKERS = ['catalog-publisher', 'booking-publisher', 'admission-publisher',
           'booking-prices', 'analytics-bookings', 'analytics-admissions']
ROUTES = ['booking-prices', 'analytics-bookings', 'analytics-admissions']


def main():
    roles = [f'arn:aws:iam::{ACCOUNT}:role/wonderland-demo-{name}' for name in WORKERS]
    topics = [f'arn:aws:sns:{REGION}:{ACCOUNT}:wonderland-demo-{s}' for s in ['catalog', 'booking', 'admission']]
    queues = [f'arn:aws:sqs:{REGION}:{ACCOUNT}:wonderland-demo-{r}{suffix}' for r in ROUTES for suffix in ['', '-dlq', '-delivery-dlq']]
    policy = {'Version': '2012-10-17', 'Statement': [
        {'Sid': 'FiveReleaseRepositories', 'Effect': 'Allow',
         'Action': ['ecr:BatchCheckLayerAvailability', 'ecr:InitiateLayerUpload', 'ecr:UploadLayerPart', 'ecr:CompleteLayerUpload', 'ecr:PutImage'],
         'Resource': [f'arn:aws:ecr:{REGION}:{ACCOUNT}:repository/wonderland-demo/{s}' for s in ['catalog', 'booking', 'payment', 'admission', 'analytics']]},
        {'Sid': 'OnlyEnvironmentTopics', 'Effect': 'Allow',
         'Action': ['sns:CreateTopic', 'sns:DeleteTopic', 'sns:SetTopicAttributes', 'sns:TagResource', 'sns:UntagResource', 'sns:Subscribe', 'sns:Unsubscribe', 'sns:SetSubscriptionAttributes'], 'Resource': topics},
        {'Sid': 'OnlyEnvironmentQueues', 'Effect': 'Allow',
         'Action': ['sqs:CreateQueue', 'sqs:DeleteQueue', 'sqs:SetQueueAttributes', 'sqs:TagQueue', 'sqs:UntagQueue'], 'Resource': queues},
        {'Sid': 'SixEventWorkerRoles', 'Effect': 'Allow',
         'Action': ['iam:CreateRole', 'iam:DeleteRole', 'iam:UpdateAssumeRolePolicy', 'iam:TagRole', 'iam:UntagRole', 'iam:PutRolePolicy', 'iam:DeleteRolePolicy'], 'Resource': roles},
        {'Sid': 'PassOnlyWorkerRolesToPodIdentity', 'Effect': 'Allow', 'Action': 'iam:PassRole', 'Resource': roles,
         'Condition': {'StringEquals': {'iam:PassedToService': 'pods.eks.amazonaws.com'}}},
        {'Sid': 'OnlyDemoPodIdentity', 'Effect': 'Allow',
         'Action': ['eks:CreatePodIdentityAssociation', 'eks:DeletePodIdentityAssociation', 'eks:UpdatePodIdentityAssociation', 'eks:TagResource', 'eks:UntagResource'],
         'Resource': [f'arn:aws:eks:{REGION}:{ACCOUNT}:cluster/wonderland-demo', f'arn:aws:eks:{REGION}:{ACCOUNT}:podidentityassociation/wonderland-demo/*']},
    ]}
    path = ROOT / 'infra/terraform/workloads/operator-policy.json'
    path.write_text(json.dumps(policy, indent=2) + '\n')
    compact = json.dumps(policy, sort_keys=True, separators=(',', ':')).encode()
    assert len(compact) < 6144
    baseline = json.loads((ROOT / '.local/deployment/database-merged-policy.json').read_text(encoding='utf-8-sig'))
    review = {'status': 'PREPARED_NOT_APPLIED', 'managed_policy_name': 'WonderlandWorkloadsDeployment',
              'managed_policy_bytes': len(compact), 'policy_canonical_sha256': hashlib.sha256(compact).hexdigest(),
              'existing_inline_canonical_sha256': hashlib.sha256(json.dumps(baseline, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
              'existing_inline_changed': False, 'password_read_permission_added': False,
              'worker_roles': roles, 'topics': topics, 'queues': queues, 'checkout': 'mock'}
    (ROOT / 'docs/evidence/step10c-access-review.json').write_text(json.dumps(review, indent=2) + '\n')
    print(json.dumps(review, indent=2))


if __name__ == '__main__':
    main()
