"""One-off A10 evidence extraction and saved-SMT replay; no network or LLM calls.

Writes only new files in derived/. Never executes saved model-generated Python.
This script checks artifact consistency, not complete C program semantics.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

import z3

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COMMIT = '9c5a72fbc90d829ffb761da64a73c23cd4e0503f'
SAMPLE = 'NPD/codeql/kernel69:row=65:index=95'
OUT = HERE / 'derived'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    path = OUT / name
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(value if isinstance(value, str) else
                json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    if OUT.exists():
        raise RuntimeError('Refusing overwrite of derived evidence')
    fetched = []
    for meta_path in sorted((HERE / 'fetched').rglob('*.metadata.json')):
        meta = load(meta_path)
        path = meta_path.with_name(meta_path.name.removesuffix('.metadata.json'))
        assert path.exists() and sha(path) == meta['sha256'], str(path)
        text = path.read_text(encoding='utf-8')
        fetched.append({
            'path': str(path), 'source_url': meta['url'],
            'retrieved_at': meta['retrieved_at'], 'http_status': meta['status'],
            'sha256': sha(path), 'metadata_path': str(meta_path),
            'metadata_sha256': sha(meta_path),
            'line_range': [1, len(text.splitlines())],
            'usable_evidence': meta['status'] == 200,
            'kind': 'historical_public_artifact' if meta['status'] == 200
                    else 'failed_download_response_not_source',
        })

    alert = load(HERE / 'original_a10/original_alert.json')
    original = load(HERE / 'original_a10/recorded_raw/solver_01.json')
    tag = load(HERE / 'fetched/v6.9.6_tag_object.json')
    ref = load(HERE / 'fetched/stable_v6.9.6_ref.json')
    commit = load(HERE / 'fetched/stable_commit.json')
    assert ref['object']['sha'] == tag['sha']
    assert tag['tag'] == 'v6.9.6' and tag['object']['sha'] == commit['sha'] == COMMIT
    pinned = HERE / 'fetched/pinned'
    tdls = pinned / 'net/mac80211/tdls.c'
    lines = tdls.read_text(encoding='utf-8').splitlines()
    body = '\n'.join(lines[590:686])
    assert body == alert['function_code']
    assert lines[613] == alert['location']['context']['snippet']['text']
    assert tdls.read_bytes() == (HERE / 'fetched/v6.9.6_tdls.c').read_bytes()
    dataset = ROOT / 'upstream/benchmark/NPD/codeql/codeql_kernel69_nullpointer.json'
    rows = load(dataset)
    assert rows[65] == alert
    query = original['queries'][0]['smt2']
    exported_query = (HERE / 'original_a10/solver_01_query_01.smt2').read_bytes()
    assert exported_query.replace(b'\r\n', b'\n') == query.encode()

    OUT.mkdir()
    save('historical_function.c', body)
    save('original_query.smt2', query)
    save('original_generated_solver.py', original['source'])
    save('smt_serialization_comparison.json', {
        'exported_file_sha256': sha(HERE / 'original_a10/solver_01_query_01.smt2'),
        'logged_payload_sha256': hashlib.sha256(query.encode()).hexdigest(),
        'byte_identical': exported_query == query.encode(),
        'equal_after_crlf_to_lf': True,
        'difference': 'audit export uses CRLF; logged payload uses LF; formula text unchanged',
        'replayed': 'exact logged UTF-8 payload with LF; original files left unchanged',
    })
    excerpts = {
        'net/mac80211/tdls.c': [(12, 19), (591, 686), (740, 780)],
        'net/mac80211/sta_info.c': [(203, 223)],
        'net/mac80211/sta_info.h': [(650, 660), (714, 720), (817, 822)],
        'net/mac80211/ieee80211_i.h': [(1022, 1024), (1067, 1069)],
        'include/net/mac80211.h': [(12, 22), (232, 244), (705, 706), (737, 742)],
        'include/net/cfg80211.h': [(815, 839)],
        'include/asm-generic/bug.h': [(1, 8), (95, 128), (146, 187)],
        'include/linux/once_lite.h': [(13, 34)],
        'include/linux/compiler.h': [(17, 78)],
        'include/linux/bug.h': [(1, 7)],
        'include/asm-generic/Kbuild': [(1, 12)],
        'scripts/Makefile.asm-generic': [(17, 31), (40, 43)],
    }
    text = ['# Historical source excerpts', '',
            'Automated extraction only. Numbers are original file line numbers.', '']
    for name, ranges in excerpts.items():
        path = pinned / name
        ls = path.read_text(encoding='utf-8').splitlines()
        text += [f'## {name}', '', f'Commit: `{COMMIT}`',
                 f'SHA-256: `{sha(path)}`', '', '```text']
        for start, end in ranges:
            text += [f'{i:4}: {ls[i-1]}' for i in range(start, end + 1)] + ['']
        text += ['```', '']
    save('numbered_source_excerpts.md', '\n'.join(text))

    arches = [x['name'] for x in load(HERE / 'fetched/arch_directories.json')
              if x['type'] == 'dir']
    routes = []
    for arch in arches:
        path = pinned / f'arch/{arch}/include/asm/bug.h'
        meta = load(path.with_name('bug.h.metadata.json'))
        ls = path.read_text(encoding='utf-8').splitlines() if meta['status'] == 200 else []
        routes.append({
            'architecture': arch, 'path': str(path), 'http_status': meta['status'],
            'sha256': sha(path),
            'direct_WARN_ON_ONCE_definition_lines': [i for i, s in enumerate(ls, 1)
                if re.match(r'\s*#\s*define\s+WARN_ON_ONCE\s*\(', s)],
            'direct_WARN_ON_definition_lines': [i for i, s in enumerate(ls, 1)
                if re.match(r'\s*#\s*define\s+WARN_ON\s*\(', s)],
            'generic_include_lines': [i for i, s in enumerate(ls, 1)
                if '#include <asm-generic/bug.h>' in s],
            'route_note': 'actual versioned header; include graph not fully preprocessed'
                if ls else '404 is not source; inspect saved arch Kbuild and generic mandatory-y rules; actual generated wrapper unavailable',
        })
    save('architecture_macro_inventory.json', routes)

    solver = z3.Solver()
    solver.from_string(query)
    solver.set(timeout=5000)
    started = time.perf_counter()
    result = str(solver.check())
    seconds = time.perf_counter() - started
    assert result == original['queries'][0]['result'] == 'unsat'
    assertions = [a.sexpr() for a in solver.assertions()]
    assert assertions == ['(= sta 0)', '(not (or (= sta 0) (= ap_sta 0)))']
    save('z3_replay.json', {
        'sample_id': SAMPLE, 'at': datetime.now(timezone.utc).isoformat(),
        'z3_version': z3.get_full_version(), 'query_sha256': sha(OUT / 'original_query.smt2'),
        'recorded_result': original['queries'][0]['result'], 'actual_result': result,
        'actual_assertions': assertions, 'timeout_ms': 5000, 'check_seconds': seconds,
        'saved_model_python_executed': False, 'check_count': 1,
        'scope': 'A10 original query only; no unsat core or additional solver queries',
        'limitation': 'Formula replay, not a proof of correspondence with original compiled C',
    })
    mapping = [
        {'assertion_index': 0, 'formula': assertions[0], 'role': 'bug_assumption',
         'source_path': str(tdls), 'source_lines': [614, 614], 'source_sha256': sha(tdls),
         'generated_python_lines': [13, 13], 'model_call': 59,
         'meaning': 'sta is null at the target dereference; NOT an unconditional source assignment',
         'original_pipeline_origin': {'path': str(ROOT / 'upstream/llm4pfa/feasibility_analysis_pipeline.py'),
                                      'line': 174},
         'assessment': 'appropriate local NPD hypothesis with null represented by Int zero'},
        {'assertion_index': 1, 'formula': assertions[1], 'role': 'reachability',
         'source_path': str(tdls), 'source_lines': [611, 612], 'source_sha256': sha(tdls),
         'generated_python_lines': [17, 17], 'model_calls': [60, 61, 62],
         'macro_refs': ['include/asm-generic/bug.h:110-116,146-148,170-184',
                        'include/linux/once_lite.h:26-34', 'include/linux/compiler.h:17-78'],
         'meaning': 'must negate the return guard to reach the next statement',
         'assessment': 'polarity/merge correct for saved historical macros; actual original build still unbound'},
    ]
    save('assertion_source_mapping.json', mapping)
    save('call_argument_mapping.json', {
        'provenance': 'new source inspection; NOT context supplied to original LLM run',
        'caller': 'ieee80211_tdls_add_ies', 'callee': alert['function_name'],
        'path': str(tdls), 'sha256': sha(tdls), 'call_lines': [762, 764],
        'formal_lines': [592, 595],
        'pairs': [{'position': i, 'actual': s, 'formal': s} for i, s in
                  enumerate(['link', 'skb', 'peer', 'initiator', 'extra_ies', 'extra_ies_len'], 1)],
        'sta': 'local pointer from sta_info_get; not a passed callee parameter',
        'original_runtime_frames': [alert['function_name']],
        'not_recovered': 'original complete SARIF Source/codeFlow and original scan build settings',
    })
    save('location_and_version_checks.json', {
        'sample_id': SAMPLE, 'tag': tag['tag'], 'tag_object': tag['sha'], 'commit': COMMIT,
        'github_reported_tag_signature': tag['verification']['reason'],
        'local_gpg_verification_performed': False,
        'function_range': [591, 686], 'function_exact_text_match': True,
        'tag_vs_commit_source_bytes_match': True, 'alert_target_line': 614,
        'target_exact_text_match': True,
        'target_text_occurrences_in_file': [i for i, s in enumerate(lines, 1)
                                             if s.strip() == lines[613].strip()],
        'target_text_occurrences_in_function': body.count(lines[613].strip()),
        'dataset_path': str(dataset), 'dataset_sha256': sha(dataset),
        'dataset_records': len(rows), 'row_position_zero_based': 65,
        'published_index': alert['index'], 'exact_dataset_row_match': True,
        'published_label': alert['result'], 'label_not_independently_validated': True,
        'original_scan_commit_or_translation_unit_attested': False,
    })

    original_files = []
    for path in sorted((HERE / 'original_a10').rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(HERE / 'original_a10')
        old = ROOT / 'audit/failure_audit_20261029/samples/A10' / relative
        assert old.exists() and sha(old) == sha(path), str(path)
        original_files.append({'path': str(path), 'source_path': str(old),
                               'sha256': sha(path), 'exact_copy': True,
                               'line_range': [1, len(path.read_text(encoding='utf-8').splitlines())]})
    paper = ROOT / 'results/raw/repository/paper_text.txt'
    paper_text = paper.read_text(encoding='utf-8')
    needle = 'Linux-kernel 6.9.6'
    paper_pos = paper_text.find(needle)
    assert paper_pos >= 0
    save('paper_version_excerpt.txt', paper_text[max(0, paper_pos-80):paper_pos+100] + '\n')
    save('evidence_inventory.json', {
        'fetched_artifacts': fetched, 'original_a10_exact_copies': original_files,
        'paper_version_reference': {'path': str(paper), 'sha256': sha(paper),
            'physical_line': 1, 'character_offset_zero_based': paper_pos,
            'text': needle, 'source_url': 'https://arxiv.org/html/2506.10322v1'},
        'note': '404 bodies are kept for provenance only; source line ranges apply to HTTP 200 text files.',
    })
    save('checkpoint_02_results.md',
         '# A10 inspection checkpoint\n\n'
         'Historical function and target match; original formula replayed UNSAT once.\n'
         'No generated Python execution, no other sample execution, no LLM calls.\n'
         'Original scan build/preprocessed translation unit remains unavailable.\n'
         'UNKNOWN retained; no human approval or trusted-analyzer attestation created.\n')
    print(json.dumps({'sample': SAMPLE, 'fetched_http200': sum(x['usable_evidence'] for x in fetched),
                      'fetched_http404': sum(x['http_status'] == 404 for x in fetched),
                      'original_copies': len(original_files), 'architectures': len(routes),
                      'actual_smt_result': result, 'verdict': 'UNKNOWN'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
