"""Download only a successful main-branch manual release; verify GitHub's artifact digest."""
import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from github_client import REPOSITORY, request

ROOT = Path(__file__).resolve().parents[1]


def download(run_id):
    run = request(f'repos/{REPOSITORY}/actions/runs/{run_id}')
    if (run['conclusion'] != 'success' or run['head_branch'] != 'main'
            or run['event'] != 'workflow_dispatch' or run['path'] != '.github/workflows/release.yml'
            or run['head_repository']['full_name'] != REPOSITORY):
        raise ValueError('Only successful manual releases from this repository main are accepted')
    artifacts = request(f'repos/{REPOSITORY}/actions/runs/{run_id}/artifacts')['artifacts']
    name = f"mock-release-{run_id}-{run['run_attempt']}"
    found = [a for a in artifacts if a['name'] == name and not a['expired']]
    if len(found) != 1:
        raise ValueError('Expected exactly one unexpired release artifact')
    artifact = found[0]
    # The repository is public. Use the public archive endpoint with normal GitHub
    # authentication handled by the helper; the signed blob URL must never be logged.
    from github_client import artifact_bytes
    data = artifact_bytes(artifact['id'])
    digest = 'sha256:' + hashlib.sha256(data).hexdigest()
    if artifact.get('digest') != digest:
        raise ValueError('GitHub artifact checksum mismatch or digest unavailable')
    folder = ROOT / f'.local/releases/{run_id}-{run["run_attempt"]}'
    folder.mkdir(parents=True, exist_ok=False)
    archive_path = folder / 'release.zip'
    archive_path.write_bytes(data)
    with ZipFile(archive_path) as archive:
        if set(archive.namelist()) != {'manifest.json', 'frontend.zip'}:
            raise ValueError('Unexpected release artifact contents')
        for name in ['manifest.json', 'frontend.zip']:
            (folder / name).write_bytes(archive.read(name))
    manifest = json.loads((folder / 'manifest.json').read_text())
    if (manifest['commit'] != run['head_sha'] or str(manifest['run_id']) != str(run_id)
            or str(manifest['run_attempt']) != str(run['run_attempt'])):
        raise ValueError('Artifact source/run mismatch')
    receipt = {'status': 'DOWNLOADED', 'run_id': run_id, 'run_attempt': run['run_attempt'],
               'commit': run['head_sha'], 'artifact_id': artifact['id'], 'artifact_digest': digest,
               'url': run['html_url'], 'mode': 'MOCK'}
    (folder / 'github-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'release_folder': str(folder), **receipt}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', type=int)
    args = parser.parse_args()
    try:
        download(args.run_id)
    except urllib.error.URLError:
        raise SystemExit('Release download failed; sensitive signed URL suppressed') from None
