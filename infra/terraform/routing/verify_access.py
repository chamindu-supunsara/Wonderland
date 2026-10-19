"""Immutable owner-side input guard; no AWS mutations."""
import hashlib,json,sys
from pathlib import Path
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def verify(directory,current):
    policy=json.loads((Path(directory)/'operator-policy.json').read_text())
    assert digest(policy)=='f6a93712cd8ab6ba338393f20d2f81d9a9300abd2162a368c77625594be8d970','Unreviewed routing policy'
    assert digest(json.loads(current['InlinePolicy']))=='df08dc3dca6cd21b3caba59204eea7d3e0307fe6501327ce8715603f53e84559','Existing inline policy drift'
    return policy
if __name__=='__main__':
    verify(sys.argv[1],json.loads(Path(sys.argv[2]).read_text()))
    print('Reviewed routing policy pinned; existing inline policy unchanged.')
