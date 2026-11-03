from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, hashlib, json, urllib.request, time
ROOT=Path(__file__).resolve().parent
COMMIT='9c5a72fbc90d829ffb761da64a73c23cd4e0503f'
BASE='https://raw.githubusercontent.com/gregkh/linux/'+COMMIT+'/'
def acquire(path):
    rel=PurePosixPath(path)
    if rel.is_absolute() or '..' in rel.parts or not path.endswith(('.c','.h')):
        raise ValueError('Only explicit relative C/header source paths are allowed')
    dst=ROOT/'sources'/COMMIT/Path(*rel.parts)
    if dst.exists(): raise FileExistsError(str(dst))
    url=BASE+path
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7890'}))
    start=time.perf_counter()
    with opener.open(urllib.request.Request(url,headers={'User-Agent':'E10-research-fixed-source-audit'}),timeout=40) as response:
        if response.status!=200: raise RuntimeError('Unexpected HTTP status')
        blob=response.read(2_000_001)
        if len(blob)>2_000_000: raise RuntimeError('Source size limit exceeded')
        metadata={'HTTP_status':response.status,'final_URL':response.url,'ETag':response.headers.get('ETag')}
    blob.decode('utf-8')
    dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open('xb') as stream: stream.write(blob)
    return {'repository':'gregkh/linux','commit':COMMIT,'path':path,'local_path':dst.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(blob).hexdigest(),'git_blob_sha1':hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest(),'bytes':len(blob),'retrieved_at_UTC':datetime.now(timezone.utc).isoformat(),'fetch_seconds':time.perf_counter()-start,**metadata}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--batch',required=True);parser.add_argument('paths',nargs='+');args=parser.parse_args()
    if not args.batch.replace('_','').isalnum(): raise ValueError('Invalid batch name')
    log=ROOT/('acquisition_'+args.batch+'.json')
    if log.exists(): raise FileExistsError(str(log))
    if len(set(args.paths))!=len(args.paths): raise ValueError('Duplicate source path')
    records=[];failures=[]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures={executor.submit(acquire,path):path for path in args.paths}
        for future in as_completed(futures):
            path=futures[future]
            try: records.append(future.result())
            except Exception as exc: failures.append({'path':path,'error_type':type(exc).__name__,'message':str(exc)})
    result={'status':'PASS_FETCH' if not failures else 'FETCH_INCOMPLETE','commit':COMMIT,'sources':sorted(records,key=lambda r:r['path']),'failures':failures,'version_association':'fixed commit URL over HTTPS; Git blob identities recorded; tag mapping separately recorded'}
    with log.open('x',encoding='utf-8',newline='\n') as stream: json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'batch':args.batch,'status':result['status'],'files':len(records),'bytes':sum(r['bytes'] for r in records),'failures':failures}))
    if failures: raise SystemExit(2)
if __name__=='__main__': main()
