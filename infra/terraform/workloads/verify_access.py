"""Owner-side immutable input and baseline guards. No AWS calls or password access."""
import hashlib
import json
import sys
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def verify(directory, current):
    directory = Path(directory)
    policy = json.loads((directory / 'operator-policy.json').read_text())
    # Pin the reviewed policy independently of the supplied review document.
    assert digest(policy) == 'd2989a8dd67852c7c5c5d921d6ee1e1501aecc0e02a53984ac33355607b7bc96', 'Unreviewed workload policy'
    assert digest(json.loads(current['InlinePolicy'])) == 'df08dc3dca6cd21b3caba59204eea7d3e0307fe6501327ce8715603f53e84559', 'Existing inline policy drift'
    assert len(json.dumps(policy, separators=(',', ':')).encode()) < 6144
    return policy


if __name__ == '__main__':
    verify(sys.argv[1], json.loads(Path(sys.argv[2]).read_text()))
    print('Reviewed workload policy verified; existing inline policy remains unchanged.')
