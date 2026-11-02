"""E03 deterministic B/delta transfer, guarded by the unchanged E02 checker.

This module never imports Z3, evaluates generated code, or makes model calls.
Structural admission does not establish C semantics, polarity, or safety.
"""
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / 'safety_runs/E02_base_constraint_preservation_static/checker.py'
CHECKER_SHA256 = '5a0d6532e73af8485113541fd3982f491ddeef0b6b44c7f856ad61d649a1916a'
VERSION = 'e03-base-delta-explicit-transfer-v1'


class ConstraintTransferRejected(RuntimeError):
    def __init__(self, audit):
        self.audit = audit
        super().__init__('E03 structural transfer rejected: ' + ','.join(audit['rejection_reasons']))


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _checker():
    """Explicit read-only file loading; pin bytes before every use, no pycache."""
    if not CHECKER_PATH.is_file() or hashlib.sha256(CHECKER_PATH.read_bytes()).hexdigest() != CHECKER_SHA256:
        raise RuntimeError('E03 STOP: E02 checker missing or SHA-256 mismatch')
    module_name = '_llm4pfa_e02_checker_' + CHECKER_SHA256
    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, CHECKER_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError('E03 STOP: cannot load pinned E02 checker')
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # dataclass module identity
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise
        finally:
            sys.dont_write_bytecode = previous
    return sys.modules[module_name]


def _evidence(script, source, role):
    return {'stage': role, 'reference': source or 'caller_supplied_' + role + '_raw_output',
            'raw_text': script, 'raw_sha256': text_sha(script) if isinstance(script, str) else None,
            'provenance_scope': 'caller-bound response; hash is not an independent semantic attestation'}


def validate_base_delta(base_script, delta_script, final_script, *, base_source=None,
                        delta_source=None, final_source=None):
    """Return admission record. UNKNOWN is rejected; never changes any input."""
    checker = _checker()
    missing = []
    if not isinstance(base_script, str) or not base_script.strip():
        missing.append('missing_U02_raw_evidence')
    if not isinstance(delta_script, str):
        missing.append('missing_U06_raw_evidence')
    if not isinstance(final_script, str):
        missing.append('missing_final_evidence')
    sources = (base_source or 'U02/raw', delta_source or 'U06/raw', final_source or 'Final/code')
    if missing:
        result = checker.check_contract(None, None, None, formats=('python',)*3, refs=sources)
    else:
        result = checker.check_contract(base_script, delta_script, final_script,
                                        formats=('python',)*3, refs=sources)
    counts = result.get('counts', {})
    rejected = missing + ([] if result['contract_status'] == 'PASS' else ['contract_not_PASS'])
    for key in ('duplicate_declarations', 'type_conflicts', 'symbol_identity_conflicts'):
        if counts.get(key, 0):
            rejected.append(key)
    if result.get('parse_errors'):
        rejected.append('unsupported_syntax')
    base_ir = result.get('ir', {}).get('B')
    if base_ir is not None and (not base_ir['declarations'] or not base_ir['assertions']):
        rejected.append('base_has_no_declared_asserted_constraint')
    # A duplicated assertion is kept verbatim, not removed. E02 totals count each
    # role; also expose Final-only multiplicity to avoid ambiguous audit counts.
    summary = {k: counts.get(k) for k in ('missing_declarations', 'missing_base_assertions',
               'missing_delta_assertions', 'type_conflicts', 'symbol_identity_conflicts',
               'duplicate_declarations', 'duplicate_assertions')}
    summary['final_duplicate_assertions'] = result.get('duplicate_assertions_by_role', {}).get('Final')
    summary['final_duplicate_declarations'] = result.get('duplicate_declarations_by_role', {}).get('Final')
    return {'adapter_version': VERSION, 'checker_sha256': CHECKER_SHA256,
            'base_sha256': text_sha(base_script) if isinstance(base_script, str) else None,
            'delta_sha256': text_sha(delta_script) if isinstance(delta_script, str) else None,
            'final_sha256': text_sha(final_script) if isinstance(final_script, str) else None,
            'contract_status': result['contract_status'], 'accepted': not rejected,
            'rejection_reasons': sorted(set(rejected)), 'counts': summary, 'check_contract': result,
            'semantic_correctness': 'NOT_ASSESSED', 'polarity_correctness': 'NOT_ASSESSED',
            'alert_safety_decision': None, 'solver_executed': False,
            'sources': {'base': _evidence(base_script, base_source, 'U02'),
                        'delta': _evidence(delta_script, delta_source, 'U06'),
                        'final': _evidence(final_script, final_source, 'Final')}}


def assemble_base_delta(base_script, delta_script, *, base_source=None, delta_source=None):
    """Concatenate original code bodies, retaining raw responses and exact spans.

    Removing a single Markdown code fence is transport decoding only. No code
    line, declaration, assertion, contradiction, or duplicate is rewritten.
    """
    checker = _checker()
    base = _evidence(base_script, base_source, 'U02')
    delta = _evidence(delta_script, delta_source, 'U06')
    invalid = (not isinstance(base_script, str) or not base_script.strip()
               or not isinstance(delta_script, str))
    try:
        if invalid:
            raise ValueError('missing_original_evidence')
        base_code = checker.code_block(base_script)
        delta_code = checker.code_block(delta_script)
    except (checker.Unsupported, ValueError, TypeError) as exc:
        audit = validate_base_delta(base_script, delta_script, None,
                                    base_source=base_source, delta_source=delta_source)
        audit['rejection_reasons'].append('cannot_decode_original_code:' + str(exc))
        audit['stage'] = 'before_U10'
        raise ConstraintTransferRejected(audit) from exc
    header = '# E03 BEGIN U02 BASE raw_sha256=' + base['raw_sha256'] + '\n'
    separator = '\n# E03 END U02 BASE\n# E03 BEGIN U06 DELTA raw_sha256=' + delta['raw_sha256'] + '\n'
    footer = '\n# E03 END U06 DELTA\n'
    merged = header + base_code + separator + delta_code + footer
    base.update(code_text=base_code, code_sha256=text_sha(base_code),
                merged_span={'start':len(header), 'end':len(header)+len(base_code), 'unit':'Python character offset, half-open'})
    delta_start = len(header)+len(base_code)+len(separator)
    delta.update(code_text=delta_code, code_sha256=text_sha(delta_code),
                 merged_span={'start':delta_start, 'end':delta_start+len(delta_code), 'unit':'Python character offset, half-open'})
    audit = validate_base_delta(base_script, delta_script, merged, base_source=base_source,
                                delta_source=delta_source, final_source='deterministic_U02_code_plus_U06_code')
    bundle = {'adapter_version': VERSION, 'base':base, 'delta':delta, 'merged_script':merged,
              'base_sha256':base['raw_sha256'], 'delta_sha256':delta['raw_sha256'],
              'merged_sha256':text_sha(merged), 'assembly_audit':audit}
    audit.update(stage='before_U10', merged_sha256=bundle['merged_sha256'])
    if not audit['accepted']:
        # Copy the envelope: bundle already references its assembly_audit.
        # Mutating that audit to reference bundle would create a JSON cycle.
        raise ConstraintTransferRejected(dict(audit, bundle=bundle))
    return bundle


def replace_once(source, old, new):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f'E03 STOP: expected exactly one patch target; found {count}')
    return source.replace(old, new, 1)
