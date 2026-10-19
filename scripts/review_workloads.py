"""Review the saved workload plan and measured cluster capacity without applying it."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/deployment'


def read(name):
    return json.loads((LOCAL / name).read_text(encoding='utf-8-sig'))


def memory(value):
    for suffix, factor in [('Ki', 1 / 1024), ('Mi', 1), ('Gi', 1024)]:
        if value.endswith(suffix):
            return float(value[:-len(suffix)]) * factor
    return float(value) / 1048576


def cpu(value):
    return float(value[:-1]) if value.endswith('m') else float(value) * 1000


def main():
    plan = read('step10c-workloads-plan.json')
    changes = [r for r in plan.get('resource_changes', []) if r['mode'] == 'managed']
    assert all(r['change']['actions'] == ['create'] for r in changes), 'Plan must add only new workload resources'
    counts = dict(Counter(r['type'] for r in changes))
    assert counts == {'aws_sns_topic': 3, 'aws_sns_topic_policy': 3, 'aws_sqs_queue': 9, 'aws_sqs_queue_policy': 9,
                      'aws_sns_topic_subscription': 3, 'aws_iam_role': 6, 'aws_iam_role_policy': 6,
                      'aws_eks_pod_identity_association': 6}, counts
    nodes = read('step10c-nodes.json')['items']
    pods = [p for p in read('step10c-pods.json')['items'] if p['status']['phase'] not in ['Succeeded', 'Failed']]
    assert len(nodes) == 2
    available = {'cpu_millicores': sum(cpu(n['status']['allocatable']['cpu']) for n in nodes),
                 'memory_mib': sum(memory(n['status']['allocatable']['memory']) for n in nodes),
                 'pod_slots': sum(int(n['status']['allocatable']['pods']) for n in nodes)}
    existing_cpu, existing_memory = 0, 0
    for pod in pods:
        requests = [c.get('resources', {}).get('requests', {}) for c in pod['spec']['containers']]
        init_requests = [c.get('resources', {}).get('requests', {}) for c in pod['spec'].get('initContainers', [])]
        existing_cpu += max(sum(cpu(r.get('cpu', '0')) for r in requests), max([cpu(r.get('cpu', '0')) for r in init_requests] or [0]))
        existing_memory += max(sum(memory(r.get('memory', '0')) for r in requests), max([memory(r.get('memory', '0')) for r in init_requests] or [0]))
    # Eight API Pods, seven workers; four simultaneous API surge Pods and one verification Job.
    peak = {'cpu_millicores': existing_cpu + 8 * 100 + 7 * 50 + 4 * 100 + 100,
            'memory_mib': existing_memory + (8 + 7 + 4 + 1) * 128,
            'pod_slots': len(pods) + 8 + 7 + 4 + 1}
    assert all(peak[k] < available[k] for k in peak), (peak, available)
    sources = sorted((ROOT / 'infra/terraform/workloads').glob('*.tf'))
    report = {'status': 'PLANNED_NOT_APPLIED', 'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
              'resources_to_add': len(changes), 'resources_to_change': 0, 'resources_to_destroy': 0,
              'resource_counts': counts, 'additional_ec2_rds_nat_loadbalancers': 0,
              'cluster_allocatable': available, 'existing_active_pods': len(pods),
              'estimated_peak_requests_including_surge_and_probe': peak,
              'capacity_limitations': 'Aggregate requests fit; actual scheduling, memory and delivery are verified during rollout. No node autoscaler enabled.',
              'plan_sha256': hashlib.sha256((LOCAL / 'step10c-workloads.tfplan').read_bytes()).hexdigest(),
              'terraform_sources_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              'spending_allowance_usd': 75, 'foundation_model_usd': 52.41,
              'step10c_incremental_planning_reserve_usd': 2, 'combined_planning_model_usd': 54.41,
              'budget_limitations': 'Reserve is a planning assumption for light demonstration traffic, not an AWS quote or enforced cap. Usage, tax and retained artifacts vary; later hosting needs another estimate.',
              'cleanup_target': '2026-10-25T18:00:00+05:30', 'checkout': 'mock'}
    (ROOT / 'docs/evidence/step10c-workloads-plan.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
