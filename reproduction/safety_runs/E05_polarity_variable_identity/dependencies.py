"""Load only hash-pinned, side-effect-free historical static readers."""
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    'e01': ('safety_runs/E01_predicate_polarity_consistency/predicate_check.py',
            '0d41c1142adee9a3047ce2014daad1ef6e6ea85eee674d9d4534e15cf63880e4'),
    'e02': ('safety_runs/E02_base_constraint_preservation_static/checker.py',
            '5a0d6532e73af8485113541fd3982f491ddeef0b6b44c7f856ad61d649a1916a'),
    'e03': ('completion/constraint_bundle.py',
            '7718ae636dd19d88aa51f44d96e0fb5c1d303f0d849804598181a6a9bc28a483'),
}


def load(name):
    relative, expected = PINS[name]
    path = ROOT / relative
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('STOP: dependency hash mismatch: ' + relative)
    key = '_e05_pinned_' + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]
