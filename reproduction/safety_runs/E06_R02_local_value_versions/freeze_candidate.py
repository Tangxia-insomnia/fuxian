"""Freeze only after synthetic, accepted R01 and historical prerequisites pass."""
from datetime import datetime, timezone
import json
import importlib.metadata
import sys

from r01_adapter import ROOT, REPRO, R01, offline_boundary, r01
from run_r02 import RF, save, verify_baseline


def main():
    offline_boundary.install()
    baseline=verify_baseline()
    if (ROOT/'fixed_20').exists() or (ROOT/'fixed_20_results.json').exists():
        raise RuntimeError('Fixed candidate already attempted; no freeze/retry permitted')
    synth_path=ROOT/'synthetic_runs/final_candidate_01/synthetic_test_results.json'
    synth=json.loads(synth_path.read_text('utf-8'))
    r1=json.loads((ROOT/'r01_core_recheck/test_results.json').read_text('utf-8'))
    hist=json.loads((ROOT/'historical_results.json').read_text('utf-8'))
    if not (synth['all_passed'] and synth['total']==synth['passed']==110 and synth['fixture_count']==43):
        raise RuntimeError('Synthetic acceptance incomplete')
    if not (r1['all_passed'] and r1['total']==r1['passed']==41):
        raise RuntimeError('R01 original regression failed')
    if len(hist['rows'])!=3 or hist['metrics']['runtime_errors'] or any(r['status']!='UNKNOWN' for r in hist['rows']):
        raise RuntimeError('Historical risks not conservatively preserved')
    if any(x.get('external_operations') for x in [synth,r1,hist['metrics']]):
        raise RuntimeError('Forbidden external operation recorded')
    # Byte-identical published summary of the final synthetic run, not another run.
    with (ROOT/'synthetic_test_results.json').open('xb') as f:f.write(synth_path.read_bytes())
    selected={RF.FIXED,RF.AUDIT,RF.INVENTORY}
    selected.update(str(p.relative_to(REPRO).as_posix()) for p in R01.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    selected.add('safety_runs/E06_R01_runner_fix/run_regression.py')
    selected.update(n for n in baseline['protected_files_sha256'] if n.startswith('upstream/benchmark/'))
    selected.update(n for n in baseline['protected_files_sha256'] if n.endswith('/bundle.json') and
                    ('/audit_10_frozen_candidate/' in n or '/fixed_20_frozen_candidate/' in n))
    history=json.loads((ROOT/'historical_cases.json').read_text('utf-8'))
    for spec in history['cases']:
        selected.update(spec.get('prior_diagnoses',[]))
        selected.update(spec[k] for k in ['manifest','source','bundle'] if k in spec)
    selected.update(p.relative_to(REPRO).as_posix() for p in ROOT.rglob('*')
                    if p.is_file() and '__pycache__' not in p.parts and p.name!='execution_log.md')
    hashes={n:r01.digest((REPRO/n).read_bytes()) for n in sorted(selected)}
    manifest={'candidate':'E06-R02-local-value-versions-01',
              'frozen_at':datetime.now(timezone.utc).isoformat(),
              'publication_baseline':baseline['publication_head'],
              'upstream_frozen_commit':'4efb4b9bf7e845e180451b43ba29a25e3edaa0e3',
              'fixed20_is_blind':False,'fixed20_attempts_before_freeze':0,
              'fixed20_allowed_attempts':1,'fixed20_order_and_labels_unchanged':True,
              'frozen_files_sha256':hashes,'protected_existing_file_count':len(baseline['protected_files_sha256']),
              'environment':{'python':sys.version,'platform':sys.platform,
                             'libclang_package':importlib.metadata.version('libclang'),
                             'library_file':str(r01.c.Config.library_file or ''),
                             'clang_args':r01.CONFIG['clang_args']},
              'preconditions':{'synthetic':{'passed':110,'total':110,'fixture_count':43},
                               'R01':{'passed':41,'total':41},'historical_unknown':3,
                               'protected_all_unchanged':True,'external_operations':[]},
              'no_production_integration':True,'no_safety_decisions':True}
    save(ROOT/'candidate_manifest.json',manifest)
    print(json.dumps({'frozen_file_count':len(hashes),'protected':manifest['protected_existing_file_count'],
                      'fixed20_attempts':0,'candidate_manifest_sha256':r01.digest((ROOT/'candidate_manifest.json').read_bytes())}))


if __name__=='__main__':main()
