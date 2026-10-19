"""Package reviewed owner helper files without credentials or local AWS configuration."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / '.local/deployment/step10b-access.zip'
files = ['operator-policy.json', 'bootstrap-access.json', 'apply-access-cloudshell.sh']
manifest = {}
with ZipFile(target, 'w', compression=ZIP_DEFLATED) as archive:
    for name in files:
        content = (ROOT / 'infra/database' / name).read_text(encoding='utf-8-sig').replace('\r\n', '\n').encode()
        archive.writestr(name, content)
        manifest[name] = hashlib.sha256(content).hexdigest()
report = {'status': 'PREPARED_NOT_UPLOADED', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
          'archive': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
          'files_sha256': manifest, 'contains_credentials': False}
(ROOT / 'docs/evidence/step10b-bundle.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
