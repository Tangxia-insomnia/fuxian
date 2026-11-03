"""Admit this exact source only; create immutable E11 evidence and contract.

This is a fixed-function source check, not a C parser, AST certificate, or
reconstruction of the original kernel translation unit/build configuration.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPRO = ROOT.parents[1]
COMMIT = '9c5a72fbc90d829ffb761da64a73c23cd4e0503f'
DATASET_SHA = '0275cd83a4c1cf617f0049d6dbb191dcc3d232e5545ca0139bab3aa45f747fd8'
BODY_SHA = '604a27c78dd3bd48933665f8253480eef56107e88e7e4039701dd4f397615ebb'
SOURCE_PATH = 'drivers/gpu/drm/omapdrm/dss/pll.c'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text('utf-8'))


def write_new(name, document):
    with (ROOT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    for name in ('source_manifest.json', 'source_evidence.json', 'semantic_contract.json'):
        if (ROOT / name).exists():
            raise FileExistsError(name)
    data = (REPRO / 'upstream/benchmark/DBZ/all_cwe369.json').read_bytes()
    if sha(data) != DATASET_SHA:
        raise ValueError('dataset SHA mismatch; UNKNOWN, stop')
    row = json.loads(data)[2]
    body = row['function_call'][0]
    if sha(body.encode('utf-8')) != BODY_SHA or row['index'] != 2:
        raise ValueError('body/identity mismatch; UNKNOWN, stop')
    if (ROOT / 'original_function.c').read_bytes() != body.encode('utf-8'):
        raise ValueError('saved original body differs; UNKNOWN, stop')
    tag = read('upstream_tag_verification.json')
    acquisition = read('source_acquisition.json')
    if (tag['status'] != 'MATCH' or tag['refs'].get('refs/tags/v6.9.6^{}') != COMMIT
            or acquisition['status'] != 'COMPLETE'):
        raise ValueError('incomplete upstream identity; UNKNOWN, stop')
    records = {record['path']: record for record in acquisition['files']}
    source_texts = {}
    for record in records.values():
        raw = (ROOT / record['local_path']).read_bytes()
        if sha(raw) != record['sha256'] or record['commit'] != COMMIT:
            raise ValueError('upstream source hash/commit mismatch; UNKNOWN, stop')
        source_texts[record['path']] = raw.decode('utf-8')
    source = source_texts[SOURCE_PATH]
    # Omit the one file-delimiting LF after the closing brace, and nothing else.
    extracted = ''.join(source.splitlines(keepends=True)[175:199]).removesuffix('\n')
    if extracted != body or sha(extracted.encode('utf-8')) != BODY_SHA:
        raise ValueError('upstream lines 176-199 differ from benchmark; UNKNOWN, stop')
    lines = source.splitlines()
    expected = {
        177: 'unsigned long out_min, unsigned long out_max,',
        184: 'out_min = out_min ? out_min : 1;',
        185: 'out_max = out_max ? out_max : ULONG_MAX;',
        186: '',
        187: 'm_start = max(DIV_ROUND_UP(clkdco, out_max), 1ul);',
        188: '',
        189: 'm_stop = min((unsigned)(clkdco / out_min), hw->mX_max);',
        192: 'out = clkdco / m;',
        194: 'if (func(m, out, data))',
    }
    for number, text in expected.items():
        if lines[number - 1].strip() != text:
            raise ValueError('source position or statement mismatch; UNKNOWN, stop')
    if 'out_min' in '\n'.join(lines[184:188]):
        raise ValueError('intervening out_min access; stop for source review')
    macro_checks = [
        ('include/linux/kernel.h', '#include <linux/math.h>'),
        ('include/linux/kernel.h', '#include <linux/minmax.h>'),
        ('include/linux/math.h', '#define DIV_ROUND_UP __KERNEL_DIV_ROUND_UP'),
        ('include/uapi/linux/const.h',
         '#define __KERNEL_DIV_ROUND_UP(n, d) (((n) + (d) - 1) / (d))'),
        ('include/linux/minmax.h', '#define min(x, y)\t__careful_cmp(min, x, y)'),
        ('include/linux/minmax.h', '#define max(x, y)\t__careful_cmp(max, x, y)'),
    ]
    for path, text in macro_checks:
        if text not in source_texts[path]:
            raise ValueError('reviewed macro definition differs; UNKNOWN, stop')
    evidence = {
        'method': 'exact whole-function hash plus fixed-line checks and scoped macro source review',
        'AST_or_original_build_verified': False,
        'source_path': SOURCE_PATH, 'source_sha256': records[SOURCE_PATH]['sha256'],
        'function_span': [176, 199], 'upstream_body_sha256': sha(extracted.encode()),
        'body_correspondence': 'byte-identical after omitting one delimiting LF after closing brace',
        'facts': [
            {'id': 'F_TYPE', 'line': 177, 'text': lines[176],
             'conclusion': 'out_min is a by-value unsigned long parameter; not volatile/atomic'},
            {'id': 'F_NORMALIZE', 'line': 184, 'text': lines[183],
             'conclusion': 'zero input selects int literal 1, converted to unsigned long; nonzero input copied'},
            {'id': 'F_PRESERVE', 'lines': [185, 188], 'text': '\n'.join(lines[184:188]),
             'conclusion': 'only out_max and m_start assignments; no out_min write/address escape/call using out_min'},
            {'id': 'F_USE', 'line': 189, 'text': lines[188],
             'conclusion': 'clkdco / out_min reads the normalized parameter; both operands unsigned long'},
        ],
        'macro_review': {
            'references': [
                {'path': 'include/linux/kernel.h', 'lines': [27, 28]},
                {'path': 'include/linux/math.h', 'lines': [37, 37]},
                {'path': 'include/uapi/linux/const.h', 'lines': [34, 34]},
                {'path': 'include/linux/minmax.h', 'lines': [43, 58]},
                {'path': 'include/linux/minmax.h', 'lines': [85, 92]},
            ],
            'conclusion': 'reviewed min/max helpers use expressions/temporary copies; DIV_ROUND_UP uses arithmetic only; no write to out_min in these expressions',
            'limitation': 'original preprocessing configuration and all transitive headers not reconstructed; no general macro or TU certification',
        },
        'control_flow_review': 'straight-line assignment dominates the target in this saved function; no branch/goto/callback between line 184 and line 189; callback first occurs at line 194',
        'alias_review': 'by-value automatic parameter; no address taken or escape in the saved function; no cross-frame/memory inference needed',
        'execution_scope': 'well-defined C executions reaching the line-189 division with the reviewed source semantics; earlier undefined behavior is not certified',
        'uncertified_expressions': [
            {'line': 187, 'text': lines[186], 'status': 'NOT_CERTIFIED'},
            {'line': 192, 'text': lines[191], 'status': 'NOT_CERTIFIED'},
        ],
    }
    write_new('source_evidence.json', evidence)
    manifest = {
        'repository': 'https://github.com/gregkh/linux', 'tag': 'v6.9.6',
        'commit': COMMIT, 'tag_association': tag['refs'], 'tag_signature_verified': False,
        'dataset_sha256': DATASET_SHA, 'function_body_sha256': BODY_SHA,
        'sample_id': 'DBZ/all_cwe369.json:row=2:index=2',
        'function': 'dss_pll_hsdiv_calc_a', 'source_span': [176, 199],
        'normalization_line': 184, 'target_division_line': 189,
        'files': acquisition['files'], 'upstream_body_match': True,
        'source_evidence_sha256': sha((ROOT / 'source_evidence.json').read_bytes()),
        'input_verification_sha256': sha((ROOT / 'input_verification.json').read_bytes()),
        'verified_at_UTC': datetime.now(timezone.utc).isoformat(),
        'original_TU_build_ABI': 'UNKNOWN',
    }
    write_new('source_manifest.json', manifest)
    contract = {
        'contract_version': 'e11-local-unsigned-normalization-v1',
        'sample_id': manifest['sample_id'], 'original_index': 2,
        'original_label': row['result'], 'label_used_as_constraint': False,
        'dataset_sha256': DATASET_SHA, 'function_body_sha256': BODY_SHA,
        'source_commit': COMMIT, 'function': manifest['function'],
        'source_manifest_sha256': sha((ROOT / 'source_manifest.json').read_bytes()),
        'source_evidence_sha256': manifest['source_evidence_sha256'],
        'c_type': 'unsigned long', 'unsigned_long_widths': [32, 64],
        'ABI_status': 'explicit scalar width contracts; original ABI UNKNOWN',
        'integer_literal': {'source_type': 'int', 'value': 1,
                            'conditional_conversion': 'usual arithmetic conversions to unsigned long',
                            'SMT': 'BitVecVal(1, width); representable at both widths'},
        'condition': 'C scalar truth: original out_min != 0; equality/inequality only, no signed comparison',
        'value_versions': [
            {'id': 'out_min_v0', 'role': 'parameter value before line 184',
             'scope': 'E11 local encoding for this sample/function and one width', 'source_line': 177},
            {'id': 'out_min_v1', 'role': 'new value after line 184 assignment',
             'definition': 'ITE(out_min_v0 == 0, unsigned_long(1), out_min_v0)',
             'source_line': 184, 'evidence': ['F_TYPE', 'F_NORMALIZE']},
            {'id': 'out_min_use', 'role': 'line 189 denominator read, not an additional assignment',
             'reaching_definition': 'out_min_v1', 'binding': 'out_min_use == out_min_v1',
             'source_line': 189, 'evidence': ['F_PRESERVE', 'F_USE']},
        ],
        'R02_value_versions_reused_or_modified': False,
        'numerator': 'clkdco is unsigned long, unconstrained; unnecessary to encode for zero-denominator property',
        'division_definedness': 'out_min_use != 0; no signed MIN/-1 overflow for unsigned division',
        'definedness_asserted_in_fault_query': False,
        'queries': {
            'A_unnormalized_control': 'out_min_v0 == 0 (counterfactual without assignment, not real source execution)',
            'B_normalized_core': 'out_min_v1 == ITE(out_min_v0 == 0, 1, out_min_v0) AND out_min_use == out_min_v1 AND out_min_use == 0',
        },
        'input_domain': 'all unsigned values 0..2**width-1; no caller constraint or E09/E10 assumption',
        'independent_proof': 'case v0=0 => v1=1; case v0!=0 => v1=v0!=0; use=v1',
        'certified_scope': 'nonzero denominator of clkdco / out_min at source line 189 only',
        'excluded_scope': ['line 187 division', 'line 192 division', 'whole function',
                           'loops/callbacks/hardware', 'cast to unsigned int and min result',
                           'original build/TU', 'cross-function, memory or concurrency semantics'],
        'original_alert_decision': None, 'filter_authority': False,
        'full_program_semantics': 'UNKNOWN',
    }
    write_new('semantic_contract.json', contract)
    print(json.dumps({'upstream_body_hash': BODY_SHA, 'source_checks': 'MATCH',
                      'type': 'unsigned long', 'normalization': 184, 'use': 189}))


if __name__ == '__main__':
    main()
