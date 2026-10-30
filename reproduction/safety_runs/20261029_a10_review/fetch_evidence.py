"""GET historical public source evidence only; never overwrites or uses API keys."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent


def fetch(name, url):
    target = HERE/'fetched'/name
    meta_path = target.with_name(target.name+'.metadata.json')
    if target.exists() or meta_path.exists():
        raise ValueError('Refusing overwrite: ' + name)
    target.parent.mkdir(parents=True, exist_ok=True)
    meta = {'url': url, 'retrieved_at': datetime.now(timezone(timedelta(hours=8))).isoformat()}
    try:
        response = requests.get(url, headers={'User-Agent': 'LLM4PFA-A10-source-review'}, timeout=(8, 25))
        meta.update(status=response.status_code, final_url=response.url,
                    sha256=hashlib.sha256(response.content).hexdigest(), bytes=len(response.content),
                    headers={k: v for k, v in response.headers.items()
                             if k.lower() in ['etag', 'last-modified', 'content-type']})
        with target.open('xb') as handle:
            handle.write(response.content)
    except requests.RequestException as exc:
        meta['error'] = type(exc).__name__ + ': ' + str(exc)
    with meta_path.open('x', encoding='utf-8') as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'file': name, **meta}, ensure_ascii=True), flush=True)
    return meta


if __name__ == '__main__':
    # Annotated Linux stable tag; inspect the saved object before fetching by SHA.
    fetch('v6.9.6_tag_object.json',
          'https://api.github.com/repos/gregkh/linux/git/tags/185c18dcbe7edb086251c0a4fadb752f0b42aaaa')
