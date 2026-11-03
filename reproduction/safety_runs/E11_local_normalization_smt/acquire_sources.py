"""Fetch only explicit E11 evidence at the requested commit; never overwrite.

No kernel checkout or build is created. HTTP and Git identity checks are
provenance evidence, not a claim that the original translation unit was built.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parent
COMMIT = '9c5a72fbc90d829ffb761da64a73c23cd4e0503f'
PATHS = (
    'drivers/gpu/drm/omapdrm/dss/pll.c',
    'include/linux/kernel.h',
    'include/linux/math.h',
    'include/linux/minmax.h',
    'include/uapi/linux/const.h',
)


def write_new(name, document):
    with (ROOT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def acquire(path):
    destination = ROOT / 'sources' / COMMIT / path
    if destination.exists():
        raise FileExistsError(path)
    url = 'https://raw.githubusercontent.com/gregkh/linux/' + COMMIT + '/' + path
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(
        {'https': 'http://127.0.0.1:7890'}))
    with opener.open(urllib.request.Request(url, headers={
            'User-Agent': 'E11-fixed-commit-source-audit'}), timeout=40) as response:
        data = response.read(2_000_001)
        if response.status != 200 or len(data) > 2_000_000:
            raise RuntimeError('HTTP failure or source-size bound exceeded')
        data.decode('utf-8')
        metadata = {'HTTP_status': response.status, 'final_URL': response.url,
                    'ETag': response.headers.get('ETag')}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(data)
    return {'repository': 'gregkh/linux', 'commit': COMMIT, 'path': path,
            'local_path': destination.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
            'git_blob_sha1': hashlib.sha1(
                b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(),
            'retrieved_at_UTC': datetime.now(timezone.utc).isoformat(), **metadata}


def main():
    for name in ('source_acquisition.json', 'upstream_tag_verification.json'):
        if (ROOT / name).exists():
            raise FileExistsError(name)
    command = ['git', '-c', 'http.proxy=http://127.0.0.1:7890', '-c',
               'http.version=HTTP/1.1', 'ls-remote',
               'https://github.com/gregkh/linux.git',
               'refs/tags/v6.9.6', 'refs/tags/v6.9.6^{}']
    process = subprocess.run(command, capture_output=True, text=True, timeout=50)
    refs = {}
    if process.returncode == 0:
        refs = {line.split()[1]: line.split()[0]
                for line in process.stdout.splitlines()}
    verified = refs.get('refs/tags/v6.9.6^{}') == COMMIT
    write_new('upstream_tag_verification.json', {
        'command': command, 'returncode': process.returncode,
        'refs': refs, 'requested_commit': COMMIT,
        'status': 'MATCH' if verified else 'UNKNOWN',
        'stderr': process.stderr, 'GPG_signature_verified': False})
    if not verified:
        raise RuntimeError('tag/commit identity unavailable or inconsistent; stop')
    successes, failures = [], []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [(path, executor.submit(acquire, path)) for path in PATHS]
        for path, future in futures:
            try:
                successes.append(future.result())
            except Exception as error:
                failures.append({'path': path, 'type': type(error).__name__,
                                 'message': str(error)})
    write_new('source_acquisition.json', {
        'status': 'COMPLETE' if not failures else 'UNKNOWN',
        'files': successes, 'failures': failures,
        'provenance_scope': 'fixed commit HTTPS bytes and remote Git tag refs'})
    print(json.dumps({'files': len(successes), 'failures': failures}))
    if failures:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
