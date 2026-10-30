"""Expand unchanged NPD completion over official groups; one shared 10-CNY ledger."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from completion.context import ContextRepository
from completion.engine import CompletedEngine
from completion.model import DeepSeekModel, save
from completion.metrics import evaluate
from scripts.run_completed import append_log, persist_rows, run_phase

GROUPS = {
    'codeql_linux': ('benchmark/NPD/codeql/codeql_kernel69_nullpointer.json', 'baseline/NPD-codeql-linux.json', 'NPD/codeql/kernel69'),
    'codeql_libav': ('benchmark/NPD/codeql/codeql_libav_nullpointer.json', 'baseline/NPD-codeql-libav.json', 'NPD/codeql/libav'),
    'codeql_openssl': ('benchmark/NPD/codeql/codeql_openssl_nullpointer.json', 'baseline/NPD-codeql-openssl.json', 'NPD/codeql/openssl'),
    'cppcheck_linux': ('benchmark/NPD/cppcheck/cppcheck_linux_nullpointer.json', 'baseline/NPD-cppcheck-linux.json', 'NPD/cppcheck/linux'),
    'cppcheck_libav': ('benchmark/NPD/cppcheck/cppcheck_libav_nullpointer.json', 'baseline/NPD-cppcheck-libav.json', 'NPD/cppcheck/libav'),
    'cppcheck_openssl': ('benchmark/NPD/cppcheck/cppcheck_openssl_nullpointer.json', 'baseline/NPD-cppcheck-openssl.json', 'NPD/cppcheck/openssl'),
    'infer_libav': ('benchmark/NPD/infer/infer_libav_nullpointer.json', 'baseline/NPD-infer-libav.json', 'NPD/infer/libav'),
    'infer_openssl': ('benchmark/NPD/infer/infer_openssl_nullpointer.json', 'baseline/NPD-infer-openssl.json', 'NPD/infer/openssl'),
}


def snapshot():
    destination = ROOT / 'results/archive/before_expanded_experiment'
    if destination.exists():
        return
    for name in ['README.md', 'results/final_report.md', 'configs/completed_run_identity.json',
                 'results/raw/completed/final_verification.json', 'results/metrics/completed_metrics.json',
                 'results/processed/stage_status.json']:
        source = ROOT / name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', choices=list(GROUPS), default='codeql_linux')
    parser.add_argument('--all-npd', action='store_true')
    parser.add_argument('--preflight', action='store_true', help='Offline context check only; no model service needed')
    args = parser.parse_args()
    snapshot()
    groups = list(GROUPS) if args.all_npd else [args.group]
    config = json.loads((ROOT/'configs/expanded_experiment.json').read_text(encoding='utf-8'))
    model = None if args.preflight else DeepSeekModel(config)
    if model:
        model.verify_service()
    for group in groups:
        dataset, historical, prefix = GROUPS[group]
        phase = 'expanded_' + group
        try:
            repo = ContextRepository(dataset, historical, prefix)
            engine = CompletedEngine(repo, model)
        except Exception as exc:
            save(ROOT/f'results/raw/completed/{phase}_setup_error.json', {'group':group,'error':f'{type(exc).__name__}: {exc}'})
            print(json.dumps({'group':group,'setup_error':str(exc)},ensure_ascii=True),flush=True)
            continue
        positions = [i for i, row in enumerate(repo.data) if type(row.get('result')) is int and row['result'] in {0,1}]
        preflight = []
        for position in positions:
            row = repo.data[position]
            try:
                context = engine.prepare(position)
                item = {'row':position,'label':row['result'],'status':'ready','frames':len(context['frames'])}
            except Exception as exc:
                item = {'row':position,'label':row['result'],'status':'blocked','error':f'{type(exc).__name__}: {exc}'}
            preflight.append(item)
        manifest = {'timestamp':datetime.now(timezone(timedelta(hours=8))).isoformat(), 'group':group,
                    'dataset':dataset,'dataset_sha256':hashlib.sha256((ROOT/'upstream'/dataset).read_bytes()).hexdigest(),
                    'historical_path':historical,'row_positions_zero_based':positions,
                    'source_records':len(repo.data),'eligible_records':len(positions),
                    'excluded_invalid_or_missing_label':len(repo.data)-len(positions),
                    'label_counts':{str(y):sum(repo.data[i]['result']==y for i in positions) for y in [0,1]},
                    'selection':'all rows with existing integer 0/1 labels; no filtering by outcome or preflight'}
        save(ROOT/f'configs/{phase}_manifest.json',manifest)
        save(ROOT/f'results/raw/completed/{phase}_preflight.json',preflight)
        print(json.dumps({'group':group,'eligible':len(positions),'ready':sum(r['status']=='ready' for r in preflight),'source':len(repo.data)},ensure_ascii=True),flush=True)
        append_log('stage_07_expanded.md',f"## {group} 预检查\n\n全部 {len(repo.data)} 条，现有 0/1 标签 {len(positions)} 条，预检查就绪 {sum(r['status']=='ready' for r in preflight)} 条。清单和阻塞原因已保存；预检查不作为结果筛选条件。")
        if args.preflight:
            continue
        result_path = ROOT/f'results/processed/completed_{phase}.json'
        if group == 'codeql_linux' and not result_path.exists():
            reused = []
            for prior in ['smoke','pilot']:
                for row in json.loads((ROOT/f'results/processed/completed_{prior}.json').read_text(encoding='utf-8')):
                    reused.append({**row,'phase':phase,'reused_from_phase':prior})
            persist_rows(phase,reused)
        rows = run_phase(phase,positions,repo,engine,model)
        metrics = evaluate(rows)
        save(ROOT/f'results/metrics/expanded_{group}_metrics.json', metrics)
        append_log('stage_07_expanded.md',f"### {group} 阶段保存完成\n\n已记录 {len(rows)} 条，成功执行 {metrics['successful']}、阻塞 {metrics['blocked']}、失败 {metrics['failed']}。分组 CSV/JSON、指标及原始输出均已保存后再进入下一组。")


if __name__ == '__main__':
    main()
