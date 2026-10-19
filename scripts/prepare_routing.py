"""Generate the exact public route allowlist and non-secret foundation inputs."""
import ast
import json
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
directory = ROOT / 'infra/terraform/routing'
routes = {}
sources = [
    ('catalog', 'services/catalog/app/api/routes.py', '/api/v1', True),
    ('catalog', 'services/catalog/app/api/identity.py', '/api/v1', False),
    ('catalog', 'services/catalog/app/api/admin.py', '/api/v1/admin', False),
    ('booking', 'services/booking/booking_app/main.py', '', False),
    ('booking', 'services/booking/booking_app/mock_checkout.py', '/api/v1/bookings', False),
    ('payment', 'services/payment/payment_app/main.py', '', False),
    ('admission', 'services/admission/admission_app/main.py', '', False),
]
excluded = []
for service, source, prefix, public in sources:
    for node in ast.walk(ast.parse((ROOT / source).read_text())):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute) or dec.func.attr not in {'get', 'post', 'put', 'patch', 'delete'} or not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            path = prefix + dec.args[0].value
            if not path.startswith('/api/v1/'):
                continue
            key = dec.func.attr.upper() + ' ' + path
            if path.endswith('/mock-payment') or '/admin/mock-tickets/' in path:
                excluded.append(key)
                continue
            routes[key] = {'service': service, 'public': public}
assert len(routes) == 29, len(routes)
assert sum(v['public'] for v in routes.values()) == 3
(directory / 'routes.json').write_text(json.dumps(dict(sorted(routes.items())), indent=2) + '\n')
outputs = json.loads((ROOT / '.local/deployment/foundation-outputs.json').read_text(encoding='utf-8-sig'))
session = boto3.Session(profile_name='wonderland-feasibility', region_name='ap-south-1')
cluster = session.client('eks').describe_cluster(name='wonderland-demo')['cluster']
assert session.client('sts').get_caller_identity()['Account'] == '708919751353'
config = {'vpc_id': outputs['vpc_id']['value'], 'subnet_ids': outputs['private_compute_subnets']['value'],
          'node_security_group_id': outputs['node_security_group_id']['value'],
          'control_security_group_id': cluster['resourcesVpcConfig']['securityGroupIds'][0]}
(directory / 'terraform.tfvars.json').write_text(json.dumps(config, indent=2) + '\n')
(directory / 'backend.hcl.example').write_text('bucket = "wonderland-tfstate-708919751353-ap-south-1"\nkey = "demo/routing/terraform.tfstate"\nregion = "ap-south-1"\nencrypt = true\nuse_lockfile = true\nprofile = "wonderland-feasibility"\n')
print(json.dumps({'public_routes': 3, 'protected_routes': 26, 'excluded_backend_routes': excluded}, indent=2))
