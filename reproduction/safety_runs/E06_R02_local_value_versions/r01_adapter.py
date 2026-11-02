"""Read-only adapter to accepted R01 evidence; no core globals are changed."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPRO = ROOT.parents[1]
R01 = ROOT.parent/'E06_R01_direct_call_argument_mapping'
sys.path.insert(0, str(R01))
import mapper as r01
import offline_boundary


def namespace(path, blob, dataset_id, position, build_status):
    # Same evidence namespace as R01, so role aliases can be verified exactly.
    return {'dataset_id': dataset_id, 'position': position, 'file': str(path),
            'source_sha256': r01.digest(blob),
            'build': {'status': build_status, 'args': r01.CONFIG['clang_args'],
                      'original_project_build_verified': False,
                      'controlled_synthetic_TU': build_status=='synthetic-self-contained'}}


def slot_evidence(decl, ns):
    d = r01.declaration(decl, ns)
    return {'slot_id': r01.stable_id('local-slot', [ns, d['declaration_id']]),
            'declaration': d, 'type': r01.type_info(decl.type, ns),
            'r01_caller_slot_id': r01.stable_id('caller-slot', [ns, d['declaration_id']]),
            'r01_callee_slot_id': r01.stable_id('callee-slot', [ns, d['declaration_id']])
            if decl.kind.name=='PARM_DECL' else None}


def link_call_reads(local_report, r01_report):
    """Link only pre-call argument reads; never equate caller/callee value versions."""
    if (local_report['source_sha256'] != r01_report['source_sha256'] or
        local_report['source'] != r01_report['source'] or
        local_report['dataset_id'] != r01_report['dataset_id'] or
        local_report['position'] != r01_report['position']):
        raise ValueError('R01/R02 source/data binding mismatch')
    aliases = {s['r01_caller_slot_id']:s['slot_id'] for f in local_report['functions'] for s in f['slots']}
    reads = [x for f in local_report['functions'] for x in f['reads']]
    links = []
    for call in r01_report['calls']:
        for m in call['mappings']:
            slot = aliases.get(m['actual_slot_id'])
            matches = [rd for rd in reads if rd['slot_id']==slot and
                       rd['source_range']==m['actual_source_range'] and rd['role']=='call_argument']
            for rd in matches:
                links.append({'r01_transfer_id':m['transfer_id'], 'r01_callsite_id':call['callsite_id'],
                              'caller_slot_id':m['actual_slot_id'], 'callee_slot_id':m['formal_slot_id'],
                              'local_slot_id':slot, 'read_id':rd['read_id'],
                              'value_version_id':rd['value_version_id'], 'path_id':rd['path_id'],
                              'status':'PASS' if call['status']==m['status']==rd['status']=='PASS' else 'UNKNOWN',
                              'scope':'pre_call_argument_read_only', 'whole_call_effect_status':'UNKNOWN',
                              'callee_state_propagated':False, 'slots_merged':False})
    return links


def rf_inputs():
    path = ROOT.parent/'E06_R01_runner_fix/run_regression.py'
    spec = importlib.util.spec_from_file_location('r01rf_input_reader', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Trusted accepted input adapter, not generated code.
    return module
