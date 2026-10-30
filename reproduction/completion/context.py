"""Bounded C call/argument support over official benchmark and historical context.

This is lexical support, not a replacement for a whole-project C semantic parser.
Unsupported expressions, ambiguous definitions and missing sinks fail explicitly.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path
import lizard

ROOT = Path(__file__).resolve().parents[1]
HISTORY_REF = '29ca96e0d5f860d1f4ce07cd3e54e5e25732d1a1'
DATASET = 'benchmark/NPD/codeql/codeql_kernel69_nullpointer.json'


class ContextUnavailable(RuntimeError):
    pass


def clean(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]) if m[0].startswith(('/*', '//')) else m[0], text, flags=re.S)


def tokens(text):
    return [(m[0], m.start(), m.end()) for m in re.finditer(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|->|&&|\|\||==|!=|<=|>=|\S', clean(text))]


def compact(text):
    return ''.join(t[0] for t in tokens(text))


def calls(text):
    ts = tokens(text)
    out = []
    for i, (name, begin, _) in enumerate(ts[:-1]):
        if not re.fullmatch(r'[A-Za-z_]\w*', name) or ts[i+1][0] != '(' or name in {'if', 'for', 'while', 'switch', 'sizeof', 'return', 'typeof'}:
            continue
        if i and ts[i-1][0] in {'.', '->'}:
            continue  # indirect member call resolution is unsupported
        depth, start, args = 1, ts[i+1][2], []
        for j in range(i+2, len(ts)):
            v, a, b = ts[j]
            if v in {'(', '[', '{'}:
                depth += 1
            elif v in {')', ']', '}'}:
                depth -= 1
            if depth == 1 and v == ',':
                args.append(text[start:a].strip()); start = b
            if depth == 0:
                last = text[start:a].strip()
                if last or args:
                    args.append(last)
                out.append({'name': name, 'arguments': args, 'start': begin, 'end': b, 'text': text[begin:b]})
                break
    return out


def definitions(code):
    return lizard.analyze_file.analyze_source_code('context.c', code).function_list


def function_name(code):
    fs = definitions(code)
    if len(fs) != 1:
        raise ContextUnavailable('Expected one function definition, found ' + str(len(fs)))
    return fs[0].name


def containing_variable(expr, var):
    return re.search(r'(?<![\w])' + re.escape(var) + r'(?![\w])', expr) is not None


def called_function(var, text):
    found = [c for c in calls(text) if any(compact(a) == compact(var) for a in c['arguments'])]
    if len(found) > 1:
        raise ContextUnavailable('Multiple calls receive the tracked variable: ' + ','.join(c['name'] for c in found))
    if found:
        return found[0]['name']
    if any(containing_variable(a, var) for c in calls(text) for a in c['arguments']):
        raise ContextUnavailable('Tracked value passed via an unsupported compound argument')
    return None


def parameter_name(var, statement, body):
    fs = definitions(body)
    if len(fs) != 1:
        raise ContextUnavailable('Ambiguous callee definition')
    candidates = [c for c in calls(statement) if c['name'] == fs[0].name]
    if len(candidates) != 1:
        raise ContextUnavailable('Cannot uniquely match call to callee')
    positions = [i for i, arg in enumerate(candidates[0]['arguments']) if compact(arg) == compact(var)]
    params = fs[0].parameters
    if len(positions) != 1 or positions[0] >= len(params):
        raise ContextUnavailable('Cannot uniquely map argument to parameter')
    name = params[positions[0]]
    if not re.fullmatch(r'[A-Za-z_]\w*', name):
        raise ContextUnavailable('Unsupported parameter declaration: ' + name)
    return name


def direct_dereference(var, statement):
    ts = [t[0] for t in tokens(statement)]
    vs = [t[0] for t in tokens(var)]
    for i in range(len(ts)-len(vs)+1):
        if ts[i:i+len(vs)] != vs:
            continue
        end = i+len(vs)
        if end < len(ts) and ts[end] in {'->', '['}:
            return True
        if i and ts[i-1] == '*' and (i == 1 or ts[i-2] in {'(', '=', ',', 'return', '!', '{', ';', ':', '?'}):
            return True
    return False


class ContextRepository:
    def __init__(self, dataset=DATASET, historical_path='baseline/NPD-codeql-linux.json', sample_prefix='NPD/codeql/kernel69'):
        self.dataset, self.sample_prefix = dataset, sample_prefix
        self.data = json.loads((ROOT / 'upstream' / dataset).read_text(encoding='utf-8'))
        # Infer/Libav stores the same function-source field under func_info.
        for row in self.data:
            if 'function_code' not in row and isinstance(row.get('func_info'), str):
                row['function_code'] = row['func_info']
        self.historical = json.loads(subprocess.check_output(['git', 'show', HISTORY_REF + ':' + historical_path], cwd=ROOT / 'upstream'))
        self.bodies = {}
        for body in [r['function_code'] for r in self.data] + [b for r in self.historical for b in r['function_call']]:
            try:
                name = function_name(body)
                self.bodies.setdefault(name, {})[compact(body)] = body
            except ContextUnavailable:
                pass

    def lookup(self, name, local_chain=()):
        local = {compact(b): b for b in local_chain if function_name(b) == name}
        choices = local or self.bodies.get(name, {})
        if len(choices) != 1:
            raise ContextUnavailable(f'Function {name}: {len(choices)} distinct available definitions')
        return next(iter(choices.values()))

    def prepare(self, position):
        row = self.data[position]
        sink = row['location']['context']['snippet']['text']
        matches = [x for x in self.historical if x['prt'] == row['var_name'] and x['sink'].strip() == sink.strip() and compact(x['function_call'][0]) == compact(row['function_code'])]
        unique = {json.dumps([list(map(compact, x['function_call'])), x['final_sink'].strip()]): x for x in matches}
        if not unique and direct_dereference(row['var_name'], sink):
            context = {'function_call': [row['function_code']], 'final_sink': sink}
            origin = 'official_benchmark_direct_sink'
        elif len(unique) == 1:
            context = next(iter(unique.values())); origin = 'official_historical_baseline'
        else:
            raise ContextUnavailable(f'Historical context matches: {len(unique)}')
        chain = context['function_call']
        var, statement, frames = row['var_name'], sink, []
        for level, body in enumerate(chain):
            if statement.strip() not in body:
                raise ContextUnavailable('Target statement absent from recovered function')
            frame = {'level': level, 'function': function_name(body), 'var_name': var, 'target': statement, 'code': body, 'body_sha256': hashlib.sha256(body.encode()).hexdigest()}
            frames.append(frame)
            if level == len(chain)-1:
                # A historical macro sink is preserved as such; no claim of a visible
                # direct dereference. The analysis boundary is the author's final sink.
                frame['sink_kind'] = 'direct_dereference' if direct_dereference(var, statement) else 'author_historical_macro_or_call_sink'
                break
            next_body = chain[level+1]
            next_name = function_name(next_body)
            if called_function(var, statement) != next_name:
                raise ContextUnavailable('Call chain does not match the current call site')
            var = parameter_name(var, statement, next_body)
            if level+1 == len(chain)-1:
                statement = context['final_sink']
            else:
                following = function_name(chain[level+2])
                candidates = [c for c in calls(next_body) if c['name'] == following and any(compact(a) == compact(var) for a in c['arguments'])]
                if len(candidates) != 1:
                    raise ContextUnavailable('Cannot uniquely locate intermediate call site')
                # Original extractor requires a source line, including indentation.
                start = next_body.rfind('\n', 0, candidates[0]['start']) + 1
                end = next_body.find('\n', candidates[0]['end'])
                statement = next_body[start:end if end >= 0 else len(next_body)]
        return {'origin': origin, 'historical_ref': HISTORY_REF if matches else None, 'duplicate_equivalent_matches': len(matches), 'frames': frames, 'function_call': chain}
