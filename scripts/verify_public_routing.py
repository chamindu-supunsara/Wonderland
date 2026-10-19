"""Verify public assets and routing boundaries without passwords or tokens."""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def request(url,method='GET',headers=None,data=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=data,method=method,headers=headers or {}),timeout=30) as r:
            return r.status,dict(r.headers),r.read()
    except urllib.error.HTTPError as r:return r.code,dict(r.headers),r.read()

def main():
    outputs=json.loads((ROOT/'.local/deployment/routing-outputs.json').read_text(encoding='utf-8-sig'))
    frontend=outputs['frontend_origin']['value'];api=outputs['api_endpoint']['value']
    checks={}
    for _ in range(18):
        status,headers,body=request(frontend+'/')
        if status==200 and b'<app-root' in body:break
        time.sleep(5)
    checks['frontend_https_html']=status==200 and b'<app-root' in body
    html_headers={k.lower():v for k,v in headers.items()}
    checks['frontend_security_headers']=all([
        html_headers.get('x-content-type-options')=='nosniff',
        html_headers.get('referrer-policy')=='strict-origin-when-cross-origin',
        'max-age=31536000' in html_headers.get('strict-transport-security',''),
        "frame-ancestors 'none'" in html_headers.get('content-security-policy',''),
        "script-src 'self'" in html_headers.get('content-security-policy',''),
    ])
    for path in ['/account','/bookings','/admin','/login']:
        code,_,html=request(frontend+path)
        checks['spa_reload_'+path.strip('/')]=code==200 and b'<app-root' in html
    status,headers,config_body=request(frontend+'/app-config.json')
    config=json.loads(config_body)
    checks['public_config_exact_api_and_cognito']=status==200 and config=={'apiBaseUrl':api+'/api/v1','cognito':{'region':'ap-south-1','userPoolId':'ap-south-1_aBuDlZ9RC','userPoolClientId':'202ssal4mlube43ttm0j5m3k4i'}}
    checks['runtime_config_not_cached']='no-store' in next((v for k,v in headers.items() if k.lower()=='cache-control'),'')
    static_files=re.findall(rb'(?:src|href)="([^" ]+\.(?:js|css))"',body)
    checks['compiled_assets_served']=bool(static_files) and all(request(frontend+'/'+f.decode().lstrip('/'))[0]==200 for f in static_files)
    status,headers,attractions=request(api+'/api/v1/attractions',headers={'Origin':frontend})
    attraction_rows=json.loads(attractions) if status==200 else []
    checks['public_attractions']=status==200 and len(attraction_rows)>=4
    allowed=next((v for k,v in headers.items() if k.lower()=='access-control-allow-origin'),None)
    checks['cors_exact_frontend']=allowed==frontend
    code,_,tiers=request(api+'/api/v1/ticket-tiers')
    checks['public_tiers']=code==200 and len(json.loads(tiers))>=4
    if attraction_rows:
        checks['public_attraction_detail']=request(api+'/api/v1/attractions/'+attraction_rows[0]['id'])[0]==200
    code,headers,_=request(api+'/api/v1/bookings',method='OPTIONS',headers={'Origin':frontend,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
    checks['authorized_header_preflight']=code in [200,204] and 'authorization' in next((v.lower() for k,v in headers.items() if k.lower()=='access-control-allow-headers'),'')
    _,headers,_=request(api+'/api/v1/attractions',headers={'Origin':'https://untrusted.example.invalid'})
    checks['untrusted_origin_not_allowed']=not any(k.lower()=='access-control-allow-origin' and v=='https://untrusted.example.invalid' for k,v in headers.items())
    route_results={}
    routes=json.loads((ROOT/'infra/terraform/routing/routes.json').read_text())
    for key,value in routes.items():
        if value['public']:continue
        method,path=key.split(' ',1)
        path=re.sub(r'\{[^}]+\}','00000000-0000-0000-0000-000000000000',path)
        code,_,_=request(api+path,method=method,headers={'Content-Type':'application/json'},data=b'{}' if method in ['POST','PUT','PATCH'] else None)
        route_results[key]=code
        time.sleep(.15)
    checks['all_26_protected_routes_deny_without_token']=len(route_results)==26 and all(c in [401,403] for c in route_results.values())
    checks['malformed_jwt_denied']=request(api+'/api/v1/users/me',headers={'Authorization':'Bearer invalid.test.token'})[0] in [401,403]
    for path in ['/health/live','/health/ready','/docs','/openapi.json','/api/v1/admin/mock-tickets/MOCK-TEST','/api/v1/bookings/00000000-0000-0000-0000-000000000000/mock-payment']:
        code,_,_=request(api+path,method='POST' if path.endswith('/mock-payment') else 'GET',data=b'{}' if path.endswith('/mock-payment') else None)
        checks['backend_path_blocked_'+path]=code==404
    report={'status':'VERIFIED' if all(checks.values()) else 'REVIEW_REQUIRED','verified_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'protected_route_statuses':route_results,'frontend_origin':frontend,'api_endpoint':api,'checkout':'mock','credentials_used':False,'limitations':['Authenticated administrator/visitor/ownership walkthrough requires real user sign-in.','Internal VPC API hops remain HTTP; HTTPS is verified at public endpoints.','Hosted Metabase remains Step10E.']}
    (ROOT/'docs/evidence/step10d-public-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    assert all(checks.values()),'Inspect failed public routing checks'
if __name__=='__main__':main()
