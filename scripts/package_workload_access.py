import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'infra/terraform/workloads'
archive = ROOT / '.local/deployment/step10c-access.zip'
files = ['operator-policy.json', 'verify_access.py', 'apply-access-cloudshell.sh']
manifest = {}
with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as target:
    for name in files:
        content = (source / name).read_text(encoding='utf-8-sig').replace('\r\n', '\n').encode()
        target.writestr(name, content)
        manifest[name] = hashlib.sha256(content).hexdigest()
report = {'status': 'PREPARED_NOT_UPLOADED', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
          'archive': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
          'files_sha256': manifest, 'contains_credentials': False}
(ROOT / 'docs/evidence/step10c-access-bundle.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
