"""Read official Git history/data and save stage 1 evidence. No model calls."""
import ast
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen
from datetime import timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / 'upstream'
RAW = ROOT / 'results/raw/repository'
RAW.mkdir(parents=True, exist_ok=True)
SELECTED = '4efb4b9bf7e845e180451b43ba29a25e3edaa0e3'
LATEST = '37a1fdc99d59a8af176ae8c93fa4bf0adbeed997'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO).decode('utf-8', errors='replace').strip()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


history = git('log', '--all', '--format=%H %aI %s')
(RAW / 'git_history.txt').write_text(history + '\n', encoding='utf-8')
all_names = sorted(set(git('log', '--all', '--name-only', '--format=').splitlines()) - {''})
(RAW / 'all_history_paths.txt').write_text('\n'.join(all_names) + '\n', encoding='utf-8')
tracked = git('ls-tree', '-r', '--name-only', SELECTED).splitlines()
(RAW / 'selected_tree.txt').write_text('\n'.join(tracked) + '\n', encoding='utf-8')
(RAW / 'latest_vs_selected.diff').write_text(git('diff', SELECTED, LATEST, '--', 'README.md', 'llm4pfa/feasibility_analysis_pipeline.py') + '\n', encoding='utf-8')
imports = []
for path in sorted((REPO / 'llm4pfa').glob('*.py')):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.append({'file': path.relative_to(REPO).as_posix(), 'line': node.lineno, 'module': node.module, 'names': [n.name for n in node.names]})
        elif isinstance(node, ast.Import):
            imports.extend({'file': path.relative_to(REPO).as_posix(), 'line': node.lineno, 'module': n.name} for n in node.names)
save(RAW / 'imports.json', imports)
missing_internal = sorted({x['module'] for x in imports if x['module'] and x['module'].split('.')[0] in {'util', 'LLM4Detection'}})
inventory, hashes = [], defaultdict(list)
for path in sorted((REPO / 'benchmark').rglob('*.json')):
    raw = path.read_bytes()
    data = json.loads(raw)
    rel = path.relative_to(REPO).as_posix()
    digest = sha256(raw).hexdigest()
    hashes[digest].append(rel)
    counts = Counter(str(r.get('result')) for r in data)
    inventory.append({'path': rel, 'sha256': digest, 'count': len(data), 'result_values': dict(counts), 'first_row_keys': list(data[0]) if data else []})
save(ROOT / 'results/processed/dataset_inventory.json', inventory)
duplicates = [p for p in hashes.values() if len(p) > 1]
save(RAW / 'duplicate_dataset_files.json', duplicates)
author_metrics = []
for path in sorted((REPO / 'results/llmpfa_result').glob('*_metrics.json')):
    author_metrics.append({'source': path.relative_to(REPO).as_posix(), 'origin': 'author_published_not_reexecuted', 'metrics': json.loads(path.read_text(encoding='utf-8'))})
save(ROOT / 'results/metrics/author_published_metrics_not_reexecuted.json', author_metrics)


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


paper_status = {}
try:
    raw = urlopen('https://arxiv.org/html/2506.10322v1', timeout=30).read()
    (RAW / 'paper_2506.10322v1.html').write_bytes(raw)
    parser = TextParser()
    parser.feed(raw.decode('utf-8'))
    text = ' '.join(' '.join(parser.parts).split())
    (RAW / 'paper_text.txt').write_text(text, encoding='utf-8')
    paper_status = {'downloaded': True, 'sha256': sha256(raw).hexdigest(), 'url': 'https://arxiv.org/html/2506.10322v1'}
except Exception as exc:
    paper_status = {'downloaded': False, 'error': f'{type(exc).__name__}: {exc}'}
summary = {'timestamp': datetime.now(timezone(timedelta(hours=8), 'Asia/Shanghai')).isoformat(), 'remote': git('remote', 'get-url', 'origin'), 'selected_commit': git('rev-parse', 'HEAD'), 'latest_observed_commit': LATEST, 'status': git('status', '--short', '--branch'), 'history_commit_count': len(history.splitlines()), 'missing_internal_modules': missing_internal, 'missing_modules_found_in_any_history_path': [p for p in all_names if p.startswith(('util/', 'LLM4Detection/'))], 'historical_cache_script_paths': [p for p in all_names if 'cache_dataflow_function' in p], 'source_blob_comparison': {ref: git('ls-tree', '-r', ref, '--', 'llm4pfa').splitlines() for ref in ['e72115ffb00d6825897b7ea1ba3ba1e40b0699b2', SELECTED]}, 'paper': paper_status, 'author_metrics_file_count': len(author_metrics)}
save(RAW / 'repository_summary.json', summary)
table = '\n'.join(f"| `{r['path']}` | {r['count']} | `{r['result_values']}` |" for r in inventory)
log = f'''# 阶段 1：仓库与论文核查

状态：已完成公开材料核查；未证明代码与论文实验完全一致，未运行模型实验。
核查时间：{summary['timestamp']}（Asia/Shanghai）。

## 版本证据

- 官方仓库：{summary['remote']}
- 当前远端 main：`{LATEST}`，2026-10-16 更新。
- 实际采用：`{SELECTED}`，detached HEAD，2025-07-21 的公开 LLM4PFA 版本。
- 选择理由：最新 README 改名 PATHAGENT，流水线清空 6 项路径并改变样本上限；历史版本仍描述 LLM4PFA，保留更多原始配置和作者结果。没有 tag 或 release 提供论文版本映射。
- 该版本 5 个 Python 源文件与 2025-03-29 提交相同；完整历史共 {summary['history_commit_count']} 个可达提交，内部缺失模块在历史路径中也未出现。
- 原论文：arXiv:2506.10322v1，2025-06-12。正文为三类缺陷 NPD/UAF/BOF、364 条告警、45 个真实缺陷；主模型 GPT-4o-mini、temperature=0，其他模型为 Claude Sonnet 3.5、Qwen2.5-Coder-32B-Instruct、DeepSeek-V2-Instruct；基线 LLM4SA、LLMDFA。
- README 扩展为五类、443 条、47 个真实缺陷，不能混同论文 v1。论文 HTML 下载状态：`{paper_status}`。

## 代码职责与运行入口

| 文件 | 功能与限制 |
|---|---|
| `llm4pfa/feasibility_analysis_pipeline.py` | `detect_pipeline()` 读取告警和约束缓存，调用条件提取、LLM、Z3、上下文递归；目前导入即被缺失内部模块阻断。示例默认面向 NPD、Linux，不能直接声称支持所有缺陷。 |
| `llm4pfa/extract_util_plus.py` | 条件、提前跳转、赋值等提取；导入缺失 `conditions_info` 并依赖 clang。 |
| `llm4pfa/prompt_templates.py` | 条件推理、Z3 脚本生成、合并和错误修复提示词。 |
| `llm4pfa/model.py` | 多模型封装；仍导入缺失工具定义，部分配置为非空字面量，禁止使用或记录其中可能的凭据。 |
| `llm4pfa/analyze_c_cpp_project.py` | lizard 项目函数索引，包含作者机器路径；本次不运行整项目扫描。 |

## 数据文件实际清点

下表仅记录 `result` 原始值，不将未核实的值擅自解释为标签。

| 数据文件 | 记录数 | result 分布 |
|---|---:|---|
{table}

- `UBI/all_cwe457.json` 与 `UUA/all_cwe457.json` SHA-256 相同，视为文件副本，不能累计两遍。
- Cppcheck/Linux 的 594 条包含 526 条无 result、3 条 -1；与论文对应分组 83 条/8 个真实缺陷不一致，不能任意补标签。
- CodeQL/OpenSSL NPD 含 1 条 -1，暂不纳入有监督指标。
- 原论文三类缺陷的文件在 2025-03-29 与采用版本中 Git blob 相同，因此简单退回 3 月不能修复已知数据不一致。
- 作者 LLM4PFA 聚合指标 {len(author_metrics)} 份；另有 LLMDFA 和 LLM4SA 输出。聚合结果不等于本次实验结果，已单独标记来源；未发现 LLM4PFA 完整逐样本预测、正式评测脚本或安装说明。

## 阻塞和后续边界

- 缺失模块：`{', '.join(missing_internal)}`。
- 缺少 `PathUtil`、`DataUtils`、函数检索、函数调用/参数识别、解引用定位、工具 schema、`ContextHelper/Conditions` 等公开实现，以及流水线所需函数调用链/解引用/缓存文件。
- 历史路径中出现过 `cache_dataflow_function.py`，需要进一步查看，不能仅依据文件名认定它能恢复缺失模块。
- 部分捕获异常会返回 `result=True`；上下文缺失不能当成成功分析。原代码不应直接用于可信评测。
- 用户指定 DeepSeek `deepseek-flash`、`https://api.deepseek.com/`、环境变量名 `DEEPSEEK_APIkey`、总费用上限 10 元；与原论文模型不同，必须独立报告。未读取或使用仓库中的任何凭据。
- 只允许必要接线、路径和依赖适配；若需要重写函数检索、跨过程分析等核心模块，停止端到端复现并记录阻塞。

证据：`results/raw/repository/`；数据清单：`results/processed/dataset_inventory.json`。原始仓库代码未修改。
'''
(ROOT / 'logs/stage_01_repository.md').write_text(log, encoding='utf-8')
print(json.dumps({'stage': 1, 'log_exists': (ROOT / 'logs/stage_01_repository.md').is_file(), 'dataset_files': len(inventory), 'missing_internal_modules': missing_internal, 'paper_downloaded': paper_status['downloaded']}, ensure_ascii=True))
