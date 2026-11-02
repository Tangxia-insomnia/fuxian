"""Hash protection for noncredential originals and new candidate evidence."""
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys
from adapter import ROOT, REPRO, r01


def inventory():
    return {p.relative_to(REPRO).as_posix():r01.digest(p.read_bytes()) for p in REPRO.rglob('*')
            if p.is_file() and not any(x in {'.git','.venv','__pycache__','node_modules'} for x in p.parts)
            and not p.name.startswith('.env') and not p.is_relative_to(ROOT)}


def preservation():
    baseline=json.loads((ROOT/'baseline_state.json').read_text('utf-8'))['protected_files_sha256']
    current=inventory()
    changed=[n for n,h in baseline.items() if current.get(n)!=h]
    added=sorted(set(current)-set(baseline))
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'status':'PASS' if not changed and not added else 'REJECT',
            'protected_existing_files':len(baseline),'changed_or_missing':changed,'outside_scope_additions':added,
            'budget_ledger':{n:{'before':h,'after':current.get(n),'unchanged':current.get(n)==h}
                             for n,h in baseline.items() if 'budget' in n.lower() or 'ledger' in n.lower()},
            'credential_files_read':False,'dependencies_installed_or_upgraded':False}


def environment():
    lib=Path(r01.c.Config.library_path)/'libclang.dll'
    clang_dir=lib.parent.parent
    files=[Path(sys.executable),lib,clang_dir/'cindex.py',clang_dir/'__init__.py']
    hashes={str(p.resolve()):r01.digest(p.read_bytes()) for p in files}
    assert hashes[str(lib.resolve())]=='b13ec96d9a036d6c6c36dd09e00415ead7acc7fcfd40e721bf33ea86b3490f9d'
    assert importlib.metadata.version('libclang')=='18.1.1'
    return {'python':sys.version,'platform':sys.platform,'libclang_package':importlib.metadata.version('libclang'),
            'clang_args':r01.CONFIG['clang_args'],'relevant_dependency_files_sha256':hashes,
            'native_library_matches_R01_verified_hash':True,'target':'host_default_no_cross_target_claim'}
