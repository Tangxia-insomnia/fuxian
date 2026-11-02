"""Read-only imports of the accepted local evidence layer; no core mutation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPRO = ROOT.parents[1]
R02_ROOT = ROOT.parent / 'E06_R02_local_value_versions'
sys.path.insert(0, str(R02_ROOT))
import value_version as r02
from r01_adapter import r01, namespace, offline_boundary, rf_inputs
from state_environment import StateEnvironment

STATUSES = ('PASS', 'REJECT', 'UNKNOWN', 'N/A')


def counts(values):
    values = list(values)
    return {s: sum(v == s for v in values) for s in STATUSES}


def typed(t, ns):
    evidence = r01.type_info(t, ns)
    evidence['bit_width'] = evidence['size_bytes'] * 8 if evidence['size_bytes'] > 0 else None
    k = evidence['kind']
    evidence['signedness'] = ('signed' if k in r01.SIGNED | {'CHAR_S'} else
                              'unsigned' if k in {'CHAR_U','UCHAR','USHORT','UINT','ULONG','ULONGLONG'} else
                              'boolean' if k == 'BOOL' else 'not_integer_or_unmodeled')
    return evidence


def preflight(fn):
    nodes = list(fn.walk_preorder())
    reasons = []
    if any(n.kind.name in r02.CONTROL_UNSUPPORTED for n in nodes):
        reasons.append('unsupported_control_flow')
    if sum(n.kind.name == 'IF_STMT' for n in nodes) > 1:
        reasons.append('if_budget_exceeded')
    if fn.type.is_function_variadic():
        reasons.append('variadic_function_unsupported')
    if any(n.kind.name.endswith('_ATTR') for n in nodes):
        reasons.append('function_or_declaration_attributes_unsupported')
    return reasons
