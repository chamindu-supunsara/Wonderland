"""Read-only checks for routing ownership, JWT, private networking and controller health."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import boto3

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local/deployment'
BASE=[str(ROOT/'.local/tools/kubectl.exe'),'--kubeconfig',str(LOCAL/'kubeconfig')]
def kube(*args):return json.loads(subprocess.check_output(BASE+list(args),text=True,timeout=40))
def main():
    outputs=json.loads((LOCAL/'routing-outputs.json').read_text(encoding='utf-8-sig'))
    session=boto3.Session(profile_name='wonderland-feasibility',region_name='ap-south-1')
    assert session.client('sts').get_caller_identity()['Account']=='708919751353'
    elb=session.client('elbv2');gateway=session.client('apigatewayv2')
    lb=elb.describe_load_balancers(LoadBalancerArns=[outputs['alb_arn']['value']])['LoadBalancers'][0]
    link=gateway.get_vpc_link(VpcLinkId=outputs['vpc_link_id']['value'])
    api_id=outputs['api_id']['value']
    routes=[]
    route_args={'ApiId':api_id,'MaxResults':'100'}
    while True:
        page=gateway.get_routes(**route_args)
        routes.extend(page.get('Items',[]))
        if not page.get('NextToken'):break
        route_args['NextToken']=page['NextToken']
    expected=json.loads((ROOT/'infra/terraform/routing/routes.json').read_text())
    auth=gateway.get_authorizers(ApiId=api_id)['Items']
    api=gateway.get_api(ApiId=api_id)
    checks={'one_internal_alb':lb['Scheme']=='internal' and lb['Type']=='application' and lb['State']['Code']=='active',
            'vpc_link_available':link['VpcLinkStatus']=='AVAILABLE',
            'exact_29_gateway_routes':{r['RouteKey'] for r in routes}==set(expected),
            'gateway_jwt_issuer_and_client':len(auth)==1 and auth[0]['JwtConfiguration']=={'Audience':['202ssal4mlube43ttm0j5m3k4i'],'Issuer':'https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_aBuDlZ9RC'},
            'gateway_cors_exact_origin':api['CorsConfiguration']['AllowOrigins']==[outputs['frontend_origin']['value']]}
    checks['public_and_protected_routes_match_python']=all((r.get('AuthorizationType')=='NONE' if expected[r['RouteKey']]['public'] else r.get('AuthorizationType')=='JWT' and r.get('AuthorizerId')==auth[0]['AuthorizerId'] and r.get('AuthorizationScopes')==['aws.cognito.signin.user.admin']) for r in routes)
    stage=gateway.get_stage(ApiId=api_id,StageName='$default')
    checks['gateway_throttle_bounded']=stage['DefaultRouteSettings']['ThrottlingRateLimit']==5 and stage['DefaultRouteSettings']['ThrottlingBurstLimit']==20
    bindings=kube('-n','wonderland','get','targetgroupbindings','-o','json')['items']
    checks['four_ip_target_bindings']=len(bindings)==4 and {b['spec']['targetGroupARN'] for b in bindings}==set(outputs['target_groups']['value'].values()) and all(b['spec']['targetType']=='ip' and not b['spec'].get('networking') for b in bindings)
    pods=kube('-n','wonderland','get','pods','-o','json')['items']
    healthy_targets={}
    for service,arn in outputs['target_groups']['value'].items():
        targets=elb.describe_target_health(TargetGroupArn=arn)['TargetHealthDescriptions']
        ips={t['Target']['Id'] for t in targets if t['TargetHealth']['State']=='healthy'}
        pod_ips={p['status']['podIP'] for p in pods if p['metadata'].get('labels',{}).get('app')=='wonderland-'+service and not p['metadata'].get('deletionTimestamp') and all(c['ready'] for c in p['status'].get('containerStatuses',[]))}
        healthy_targets[service]=len(ips)
        checks[service+'_healthy_targets_match_live_pods']=len(ips)==2 and ips==pod_ips
    controller=kube('-n','kube-system','get','deployment','aws-load-balancer-controller','-o','json')
    checks['two_controller_replicas_ready']=controller['status'].get('readyReplicas')==2 and controller['status'].get('updatedReplicas')==2
    args=controller['spec']['template']['spec']['containers'][0]['args']
    checks['controller_restricted_to_namespace_and_no_backend_sg']=all(a in args for a in ['--watch-namespace=wonderland','--enable-backend-security-group=false'])
    role='wonderland-demo-target-controller'
    iam=session.client('iam')
    policy=iam.get_role_policy(RoleName=role,PolicyName='OnlyExistingTargetRegistration')['PolicyDocument']
    mutation=[s for s in policy['Statement'] if 'elasticloadbalancing:RegisterTargets' in s['Action']]
    checks['controller_write_access_only_four_target_groups']=len(mutation)==1 and set(mutation[0]['Action'])=={'elasticloadbalancing:RegisterTargets','elasticloadbalancing:DeregisterTargets'} and set(mutation[0]['Resource'])==set(outputs['target_groups']['value'].values())
    associations=session.client('eks').list_pod_identity_associations(clusterName='wonderland-demo',namespace='kube-system',serviceAccount='aws-load-balancer-controller')['associations']
    checks['one_controller_pod_identity']=len(associations)==1
    sg=session.client('ec2')
    alb_sg=sg.describe_security_groups(GroupIds=lb['SecurityGroups'])['SecurityGroups'][0]
    ingress=alb_sg['IpPermissions']
    checks['alb_ingress_only_vpc_link']=len(ingress)==1 and ingress[0]['FromPort']==ingress[0]['ToPort']==80 and not ingress[0].get('IpRanges') and {g['GroupId'] for g in ingress[0]['UserIdGroupPairs']}==set(link['SecurityGroupIds'])
    runtime=kube('-n','wonderland','get','configmap','wonderland-runtime','-o','json')['data']
    checks['backend_cors_and_mock_flags']=json.loads(runtime['CORS_ORIGINS'])==[outputs['frontend_origin']['value']] and all(runtime[k]=='true' for k in ['MOCK_PAYMENTS_ENABLED','MOCK_ADMISSION_ENABLED','MOCK_ANALYTICS_ENABLED']) and runtime['PRICING_MODE']=='projection'
    nodes=kube('get','nodes','-o','json')['items']
    checks['original_two_nodes_only']=len(nodes)==2
    app=session.client('amplify').get_app(appId=outputs['amplify_app_id']['value'])['app']
    checks['amplify_static_manual_hosting']=app['platform']=='WEB' and not app.get('repository')
    attributes={v['Key']:v['Value'] for v in elb.describe_load_balancer_attributes(LoadBalancerArn=lb['LoadBalancerArn'])['Attributes']}
    checks['desync_protection_enabled_compatible_mode']=attributes['routing.http.desync_mitigation_mode']=='defensive'
    frontend=json.loads((ROOT/'docs/evidence/step10d-public-verification.json').read_text())
    checks['public_verification_passed']=frontend['status']=='VERIFIED' and all(frontend['checks'].values())
    browser_path=ROOT/'docs/evidence/step10d-browser-verification.json'
    browser_status=json.loads(browser_path.read_text())['status'] if browser_path.exists() else 'Pending real hosted user sign-in'
    report={'status':'VERIFIED' if all(checks.values()) else 'REVIEW_REQUIRED','verified_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'healthy_targets':healthy_targets,'frontend_origin':outputs['frontend_origin']['value'],'api_endpoint':outputs['api_endpoint']['value'],'checkout':'mock','passwords_or_tokens_read':False,'tls_boundary':'Public HTTPS and verified database TLS; private VPC/service API hops remain HTTP','authenticated_walkthrough':browser_status}
    (ROOT/'docs/evidence/step10d-live-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    assert all(checks.values()),'Review failed routing checks'
if __name__=='__main__':main()
