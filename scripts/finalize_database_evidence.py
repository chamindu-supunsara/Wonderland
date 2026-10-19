"""Record completed Step 10B statuses only after both live reports pass."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'docs/evidence'
database = json.loads((root / 'step10b-database-verification.json').read_text(encoding='utf-8-sig'))
cleanup = json.loads((root / 'step10b-cleanup-verification.json').read_text(encoding='utf-8-sig'))
assert database['status'] == cleanup['status'] == 'VERIFIED'
assert database['temporary_access_removed'] and all(cleanup['checks'].values())
for name, status, extra in [
    ('step10b-access-review.json', 'APPLIED_VERIFIED_TEMPORARY_ACCESS_REMOVED',
     {'operator_ecr_upload_grant_retained': True, 'temporary_resources_remaining': 0}),
    ('step10b-bundle.json', 'UPLOADED_CHECKSUM_VERIFIED_EXECUTED_AND_TEMPORARY_ACCESS_REMOVED', {}),
]:
    path = root / name
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    value.update(status=status, completed_at_utc=cleanup['verified_at_utc'], **extra)
    path.write_text(json.dumps(value, indent=2) + '\n')
print('Step10B evidence finalized: live database verified, temporary access removed, checkout mock.')
