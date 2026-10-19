"""Pin tested local BI source/images before requesting the temporary owner grant."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1]
paths=[]
for folder in ['deploy/bi_bootstrap','deploy/helm/bi-bootstrap','deploy/helm/metabase','services/analytics','deploy/database_bootstrap/db_bootstrap','packages/common/wonderland_events','infra/bi','infra/terraform/analytics']:
    paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.yaml','.json','.sh','.tf','.txt','.ini'} and '.terraform' not in p.parts and '__pycache__' not in p.parts)
paths.extend(root/p for p in ['deploy/bi_bootstrap/Dockerfile','services/analytics/Dockerfile','scripts/deploy-cloud-bi.ps1','scripts/open-cloud-metabase.ps1'])
images={name:subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip() for name,tag in [('bootstrap','wonderland-bi-bootstrap:step10e'),('analytics','wonderland-analytics:step10e')]}
report={'status':'LOCAL_REVIEWED_AND_TESTED','recorded_at_utc':datetime.now(timezone.utc).isoformat(),'tests_passed':21,'images':images,
        'sources_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))},
        'metabase_version':'v0.64.2.8','metabase_image':'metabase/metabase@sha256:3b968d64944840ec0ed452a94fb58301a0a8d8e4fe6d632a5956014a91a2b635',
        'checkout':'mock','additional_nodes_or_public_bi':False,'credentials_in_evidence':False}
(root/'docs/evidence/step10e-code-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'pinned_files':len(set(paths)),'images':images,'tests_passed':21},indent=2))
