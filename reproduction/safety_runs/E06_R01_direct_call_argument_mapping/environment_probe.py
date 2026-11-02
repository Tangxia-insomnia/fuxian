"""R01 gate: load existing libclang and parse only synthetic C, never execute C."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time
import traceback


ROOT = Path(__file__).resolve().parent


def main():
    dest = ROOT / 'environment'
    dest.mkdir(exist_ok=False)
    source = ('void callee(int *item) { (void)item; }\n'
              'void caller(int *p) { callee(p); }\n')
    path = dest / 'probe.c'
    path.write_bytes(source.encode())
    broken = dest / 'diagnostic_probe.c'
    broken.write_bytes(b'void invalid(void) { int x = ; }\n')
    result = {'status': 'FAIL', 'python': platform.python_version(),
              'platform': platform.platform(), 'libclang_package':
              importlib.metadata.version('libclang'), 'C_execution': 0}
    started = time.perf_counter()
    try:
        from clang import cindex as c
        idx = c.Index.create()
        libpath = Path(c.Config.library_path) / 'libclang.dll'
        result['library'] = str(libpath)
        result['library_sha256'] = hashlib.sha256(libpath.read_bytes()).hexdigest()
        args = ['-x', 'c', '-std=c11', '-nostdinc', '-Werror=implicit-function-declaration']
        result['args'] = args
        snapshots = []
        for _ in range(2):
            tu = idx.parse(str(path), args=args,
                           options=c.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
            diagnostics = [{'severity': d.severity, 'spelling': d.spelling,
                            'line': d.location.line, 'column': d.location.column}
                           for d in tu.diagnostics]
            nodes = [{'kind': n.kind.name, 'spelling': n.spelling,
                      'usr': n.get_usr(), 'type': n.type.spelling,
                      'line': n.location.line, 'column': n.location.column,
                      'offset': n.location.offset,
                      'referenced_usr': n.referenced.get_usr() if n.referenced else None}
                     for n in tu.cursor.walk_preorder()
                     if n.location.file and Path(n.location.file.name) == path]
            snapshots.append({'diagnostics': diagnostics, 'nodes': nodes})
        result['parses'] = snapshots
        kinds = {n['kind'] for n in snapshots[0]['nodes']}
        required = {'CALL_EXPR', 'FUNCTION_DECL', 'PARM_DECL', 'DECL_REF_EXPR'}
        assert required <= kinds, kinds
        assert not snapshots[0]['diagnostics'], snapshots[0]['diagnostics']
        assert snapshots[0] == snapshots[1], 'non-deterministic semantic output'
        bad_tu = idx.parse(str(broken), args=args)
        bad_diagnostics = [{'severity': d.severity, 'spelling': d.spelling,
                            'line': d.location.line, 'column': d.location.column}
                           for d in bad_tu.diagnostics]
        assert any(d['severity'] >= c.Diagnostic.Error for d in bad_diagnostics)
        result.update(status='PASS', required_node_kinds=sorted(required),
                      repeat_semantic_output_identical=True,
                      diagnostic_probe=bad_diagnostics,
                      recovery_nodes_trusted=False)
    except Exception:
        result['error'] = traceback.format_exc()
    result['source_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['diagnostic_source_sha256'] = hashlib.sha256(broken.read_bytes()).hexdigest()
    result['elapsed_seconds'] = time.perf_counter() - started
    (dest / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in {'parses'}}, ensure_ascii=True))
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
