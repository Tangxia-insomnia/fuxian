# 现有实现的只读代码证据

本文件只摘录代码，不导入或执行流水线。行号来自已冻结当前文件。

## upstream/llm4pfa/extract_util_plus.py

SHA-256: `c69bd09ef04bbf49fd1c6bc4e7609bdc59c795255b4863c770122b82de94f546`

```text
164:                         nested_conditions.append(extracted_condition)
165: 
166:     target_indent = len(lines[target_line_index]) - len(lines[target_line_index].lstrip('\t'))
167:     skip_if = False
168: 
169:     for i in range(target_line_index - 1, -1, -1):
170:         line = lines[i]
171:         stripped_line = line.strip()
172:         line_indent = len(line) - len(line.lstrip('\t'))
173: 
174:         if line_indent < target_indent:

1137:     lines = function_code.split('\n')
1138: 
1139:     target_line_index = -1
1140:     assignment_line_index = 0
1141: 
1142:     for i, line in enumerate(lines):
1143:         if var_assignment_statement and var_assignment_statement in line:
1144:             assignment_line_index = i
1145:         if target_statement in line:
1146:             # We also need to consider finding the true index of the complete target_line, for example, in the following case:
1147:             # pr_debug("omap_hwmod: %s %pOFn at %pR\n",
1148:             #         oh->name, np, res); //sink
1149:             if(line.count('(') < line.count(')')):
1150:                 target_line_index = find_complete_condition_start(lines,i)
1151:             else:
1152:                 target_line_index = i
1153: 
1154:     if assignment_line_index == -1 or target_line_index == -1 or assignment_line_index > target_line_index:
1155:         return json.dumps({
1156:             "target_statement": None,
1157:             "variable_assignments": [],
1158:             "variable_non_empty": [],
1159:             "return_goto_statements": [],
1160:             "filter_function_code":None
1161:         })
1162:     # target_conditions = extract_conditions_around_target_old(lines, target_line_index, True, var_name)
1163:     target_conditions = extract_conditions_around_target_with_lines(lines, target_line_index, True, var_name)
1164: 
1165:     variable_assignments_conditions = extract_conditions_around_target_old(lines, assignment_line_index, False, var_name)
1166:     
1167:     # variable_assignments_conditions_filter = filter_assignments_conditions(variable_assignments_conditions)
1168: 
1169:     # variable_non_empty = extract_var_non_empty_conditions(lines, assignment_line_index, target_line_index, var_name)
1170: 
1171:     return_goto_statements = extract_return_goto_conditions2(lines, target_line_index, var_name)
1172:     # return_goto_statements = extract_return_goto_conditions2(lines, assignment_line_index, target_line_index, var_name)
1173:     # result = {
1174:     #     "target_statement": {"text": target_statement, "condition": target_conditions},
1175:     #     "variable_assignments": {"text": var_assignment_statement, "condition": variable_assignments_conditions},
1176:     #     # "variable_non_empty": variable_non_empty,
1177:     #     "return_goto_statements": return_goto_statements,
1178:     #     "filter_function_code":function_code
1179:     # }
1180:     result = {
1181:         "bug_line_constraints": [{"text": target_statement, "condition": target_conditions}],
1182:         "target_conditions": target_conditions,
1183:         "variable_assignments": {"text": lines[assignment_line_index], "condition": variable_assignments_conditions},
1184:         "variable_non_empty": [],
1185:         "early_jump_constraints": return_goto_statements,
1186:         "filter_function_code": function_code
1187:     }

640: def extract_return_goto_conditions2(lines, target_line_index, var_name):
641:     """Extract conditions for return and goto statements"""
642:     statements = []
643:     
644:     def is_incomplete_condition(line):
645:         return line.count('(') != line.count(')')
646:         
647:     def get_indent_level(line):
648:         return len(line) - len(line.lstrip())
649:         
650:     def contains_var_name(condition, var_name):
651:         pattern = rf'(?<![a-zA-Z0-9_]){re.escape(var_name)}(?![a-zA-Z0-9_])'
652:         return re.search(pattern, condition) is not None
653:         
654:     def complete_condition(line, lines, index):
655:         """Complete a multi-line condition statement"""

748:     # Get target line indent level
749:     target_indent = get_indent_level(lines[target_line_index])
750:     
751:     # Scan upwards for return and goto statements
752:     i = target_line_index
753:     while i >= 0:
754:         line = lines[i].strip()
755:         if not line:
756:             i -= 1
757:             continue
758:             
759:         line_indent = get_indent_level(lines[i])
760:         if ('BUG_ON' in line or 'UNWINDER_BUG_ON' in line) and target_indent ==  line_indent:
761:             controlling_conditions = []
762:             controlling_conditions.insert(0,convert_bug_on_to_if(line))
763:         
764:             # controlling_conditions.append(get_controlling_conditions(lines, i-1, line_indent))
765:             statements.append({'text': 'return', 'condition': controlling_conditions})
766:         
767:         # Check return statement
768:         if line.startswith('return'):
769:             controlling_conditions = get_controlling_conditions(lines, i-1, line_indent)
770:             statement = {
771:                 'text': 'return',
772:                 'condition': controlling_conditions
773:             }
774:             statements.append(statement)
775:             
776:         # Check goto statement
777:         elif 'goto' in line:
778:             # Extract goto label
779:             try:
780:                 goto_label = line.split('goto')[1].strip().rstrip(';')
781:                 controlling_conditions = get_controlling_conditions(lines, i-1, line_indent)
782:                 statement = {
783:                     'text': goto_label,
784:                     'condition': controlling_conditions
785:                 }
786:                 statements.append(statement)
787:             except:
788:                 pass
789:                 
790:         # Check break statement
791:         elif line.startswith('break'):
792:             controlling_conditions = get_controlling_conditions(lines, i-1, line_indent)
793:             statement = {
794:                 'text': 'break',
795:                 'condition': controlling_conditions
796:             }
797:             statements.append(statement)
798:             
799:         i -= 1
800:         
801:     return statements

```

## upstream/llm4pfa/prompt_templates.py

SHA-256: `43fa105beb98fd40e7214dd321521ec1085ef8c9c557fa4863eaa9b502417a4c`

```text
136:     def get_z3_by_goto(self, condition, target_conditions, var_name):
137:         """Convert C code constraints to Z3 solver format with filtering"""
138:         return f"""
139:         As a C language expert, convert C code constraints to Z3 solver script.
140: 
141:         Input constraints: {condition}
142:         Relevant conditions/variables: {target_conditions}, {var_name}
143: 
144:         Guidelines:
145:         1. Convert only constraints affecting the specified conditions/variables
146:         2. Add comments explaining why each constraint is included
147:         3. Maintain original variable names
148:         4. Convert C-style expressions properly (e.g., !ptr to ptr!=0)
149: 
150:         Return only executable Z3 script with explanatory comments.
151:         """

171:     def get_z3_merged3(self, m1, m2, m3):
172:         """Merge multiple Z3 constraint sets into a single validation function"""
173:         return f"""
174:         As a Z3 constraint solver expert, merge the following constraint sets into a single function.
175: 
176:         Input:
177:         1. Base Z3 script: {m1}
178:         2. Constraint set 1: {m2}
179:         3. Constraint set 2: {m3}
180: 
181:         Requirements:
182:         1. Merge all constraints into a check_constraints() function
183:         2. Retain ALL original constraints from the base script
184:         3. Add any missing variable definitions from constraint sets
185:         4. Function must return boolean (True if constraints are satisfied)
186:         5. Return ONLY the function code without imports
187:         6. Ensure code is directly executable

```

## upstream/llm4pfa/feasibility_analysis_pipeline.py

SHA-256: `c903f6de291ad4dc0e29ffbfefa7c287d4b92c50d1a7b3febf2661e1a51fb8e3`

```text
116: def process_goto_conditions(early_jump_constraints, goto_label):
117:     early_jump_constraints_list = []
118:     for item_constraint in early_jump_constraints:
119:         if goto_label != item_constraint['text'] and item_constraint['condition'] != []:
120:             constraint_str = ""
121:             for item in item_constraint['condition']:
122:                 constraint_str += "!(" + item + ") || "
123:             constraint_str = constraint_str[:-4]
124:             early_jump_constraints_list.append(constraint_str)
125:     return early_jump_constraints_list

155: def data_flow_analysis_pipeline(var_name, loc_text, code_snippet, response_list, function_name_list, function_body_list,target_index, file_path, derefere_cache, target_conditions, early_jump_constraints,level, idx,original_index):
156: 
157:     # get conditional expressions
158: 
159:     extract_conditions_plus = json.loads(extract_util_plus.extract_conditions(var_name, None, loc_text, code_snippet))
160:     if extract_conditions_plus["bug_line_constraints"][0]["text"] == loc_text:
161:         target_conditions =  extract_conditions_plus["bug_line_constraints"][0]["condition"]
162:     early_jump_constraints = extract_conditions_plus["early_jump_constraints"]
163: 
164:     goto_label = ""               
165:     z3_constraints = ""
166: 
167:     for item_constraint in target_conditions:
168:         if "goto" in item_constraint["condition"] or "return" in item_constraint["condition"]:
169:             target_conditions.remove(item_constraint)
170:             goto_label = item_constraint
171: 
172:         
173:     # generate z3 template
174:     non_null_value = var_name + " == 0"
175:     target_conditions.append(non_null_value)
176:     target_conditions_prompt = prompt.get_z3_by_target_conditions(target_conditions)
177:     messages = [{"role": "user", "content": target_conditions_prompt}]
178:     response_message_target = get_answer_from_model_without_tool(messages, model_name)
179:     target_conditions.remove(non_null_value)
180:     response_list.append("step 1 z3 script: " + response_message_target)
181: 
182:     # symbolic range reasoning with LLM
183: 
184:     target_conditions = [item for item in target_conditions if "while" not in item]

276:     early_jump_constraints_list = process_goto_conditions(early_jump_constraints, goto_label)
277: 
278:     if early_jump_constraints_list != []:
279:         filter_goto_prompt = prompt.get_filter_goto(early_jump_constraints_list, target_conditions, var_name, code_snippet)
280:         messages = [{"role": "user", "content": filter_goto_prompt}]
281:         response_filter_goto = get_answer_from_model_without_tool(messages, model_name)
282:         early_jump_constraints_list = process_array_response(response_filter_goto)
283:         response_list.append("response_filter_goto: " + response_filter_goto)

420:     args = extract_function_arguments(new_function_name)
421:     if var_name in args:
422:         args.remove(var_name)
423:     new_target_condition = []
424:     new_early_jump_constraints = []
425:     for item in args:
426:         for con1 in target_conditions:
427:             if item in con1:
428:                 new_target_condition.append(con1)
429:         for con2 in early_jump_constraints_list:
430:             if item in con2:
431:                 new_early_jump_constraints.append(con2)
432: 
433:     return data_flow_analysis_pipeline(inner_var_name, deref_line, new_function_body, response_list,function_name_list, function_body_list,target_index,file_path,derefere_cache, new_target_condition, new_early_jump_constraints, level+1, idx,original_index)

```

## completion/engine.py

SHA-256: `c2b33783874a778717819a96943f4b646f4c09af7a1d032acc82106381005194`

```text
17: def load_extractor():
18:     path = ROOT / 'upstream/llm4pfa/extract_util_plus.py'
19:     tree = ast.parse(path.read_text(encoding='utf-8'))
20:     tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom) or n.module != 'LLM4Detection.m_agent.conditions_info']
21:     ns = {'__name__': '__completed_extractor__', '__file__': str(path)}
22:     exec(compile(tree, str(path), 'exec', flags=__future__.annotations.compiler_flag), ns)
23:     return ns

26: def completed_source():
27:     original = (ROOT / 'upstream/llm4pfa/feasibility_analysis_pipeline.py').read_text(encoding='utf-8')
28:     source = original[original.index('def get_context_function_body_with_tool'):original.index('def detect_pipeline():')]
29:     old = '''    for item_constraint in target_conditions:
30:         if "goto" in item_constraint["condition"] or "return" in item_constraint["condition"]:
31:             target_conditions.remove(item_constraint)
32:             goto_label = item_constraint'''
33:     new = '''    # Completion fix: do not remove items while iterating; label is text.
34:     for item_constraint in list(target_conditions):
35:         if "goto" in item_constraint["condition"] or "return" in item_constraint["condition"]:
36:             target_conditions.remove(item_constraint)
37:             goto_label = item_constraint["condition"].removeprefix("goto ").strip()'''
38:     assert old in source
39:     source = source.replace(old, new)
40:     source = source.replace('target_conditions = [item for item in target_conditions if "while" not in item]', 'target_conditions = [item for item in target_conditions if "while" not in item["condition"]]')
41:     source = re.sub(r'exec\(final_response, globals\(\)\)\n(?:\s*#.*\n)*\s*result = check_constraints\(\)', 'result = solve_z3(final_response)', source)
42:     assert 'exec(final_response' not in source

64:     source = source.replace('args = extract_function_arguments(new_function_name)', 'args = extract_function_arguments(loc_text)')
65:     source = source.replace('if item in con1:', 'if item in con1["condition"]:')
66:     save(ROOT / 'patches/completed_pipeline_changes.json', {'base_commit': '4efb4b9bf7e845e180451b43ba29a25e3edaa0e3', 'upstream_modified': False, 'loaded_range': 'author helper functions and data_flow_analysis_pipeline; original imports/config/batch entry replaced by adapter runner', 'changes': ['remove goto/return conditions without mutating iterator; pass goto label text', 'filter while in condition text instead of dict keys', 'replace exec in global namespace with bounded Z3 worker; record actual SMT queries', 'stop after solver repair exhaustion', 'execute base query when neither target nor jump constraints remain', 'use explicitly recovered chain end; never swallow missing context as True', 'extract call arguments from call text rather than bare function name', 'inspect propagated constraint text rather than dict keys', 'strict JSON/code response parsing and actual function/context helpers supplied by adapter'], 'method_changes': 'Prompts and main iterative analysis retained; error handling, data plumbing and base-solver omission repaired. This is a modified completion, not the authors exact executable.'})
67:     (ROOT / 'patches/completed_pipeline.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True), source.splitlines(True), fromfile='upstream/llm4pfa/feasibility_analysis_pipeline.py', tofile='completed_function_bodies.py')), encoding='utf-8')
68:     (ROOT / 'patches/completed_function_bodies.py').write_text(source, encoding='utf-8')
69:     return source

83:     def prepare(self, position):
84:         context = self.repository.prepare(position)
85:         for frame in context['frames']:
86:             extracted = json.loads(self.extractor['extract_conditions'](frame['var_name'], None, frame['target'], frame['code']))
87:             if not extracted.get('bug_line_constraints'):
88:                 raise ContextUnavailable('Author extractor cannot locate target')
89:             frame['extracted'] = extracted
90:             # Catch unavailable targeted contexts before spending on the sample.
91:             for cond in extracted['target_conditions']:
92:                 if any(x in cond['condition'] for x in ['goto', 'return', 'while']):
93:                     continue
94:                 name = called_function(frame['var_name'], cond['condition'])
95:                 if name:
96:                     self.repository.lookup(name, context['function_call'])
97:         return context
98: 
99:     def code_response(self, response, content=''):
100:         match = re.search(r'```(?:python)?\s*\n?(.*?)```', response, re.S)
101:         return (match[1] if match else response).replace('from z3 import *', '').strip()
102: 
103:     def array_response(self, response):
104:         match = re.search(r'```(?:json)?\s*(.*?)```', response, re.S)
105:         value = json.loads(match[1] if match else response)
106:         if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
107:             raise ValueError('Expected JSON array of condition strings')
108:         return value

158:         ns['process_final_response'] = self.code_response
159:         ns['process_array_response'] = self.array_response
160:         ns['get_function_body_by_name'] = lambda name: self.repository.lookup(name, self.context['function_call'])
161:         ns['get_next_frame'] = lambda original_index, level: (self.frames[level+1]['function'], self.frames[level+1]['code']) if level+1 < len(self.frames) else None
162: 
163:         def dereferenced_location(cache, function, var):
164:             frame = self.frames[self.level+1]
165:             if frame['function'] != function or frame['var_name'] != var:
166:                 raise ContextUnavailable('Recovered next sink does not match callee/parameter')
167:             return frame['target'], frame['code'][:frame['code'].index(frame['target'].strip())].count('\n')+1, 'official_context_snippet'
168: 
169:         ns['get_dereferenced_locations_plus'] = dereferenced_location
170:         original_pipeline = ns['data_flow_analysis_pipeline']

```

## completion/context.py

SHA-256: `ceef443e7de3c47579696fa8e67ec1b7efb495dac9c380f47138f48833c3c046`

```text
75: def called_function(var, text):
76:     found = [c for c in calls(text) if any(compact(a) == compact(var) for a in c['arguments'])]
77:     if len(found) > 1:
78:         raise ContextUnavailable('Multiple calls receive the tracked variable: ' + ','.join(c['name'] for c in found))
79:     if found:
80:         return found[0]['name']
81:     if any(containing_variable(a, var) for c in calls(text) for a in c['arguments']):
82:         raise ContextUnavailable('Tracked value passed via an unsupported compound argument')
83:     return None
84: 
85: 
86: def parameter_name(var, statement, body):
87:     fs = definitions(body)
88:     if len(fs) != 1:
89:         raise ContextUnavailable('Ambiguous callee definition')
90:     candidates = [c for c in calls(statement) if c['name'] == fs[0].name]
91:     if len(candidates) != 1:
92:         raise ContextUnavailable('Cannot uniquely match call to callee')
93:     positions = [i for i, arg in enumerate(candidates[0]['arguments']) if compact(arg) == compact(var)]
94:     params = fs[0].parameters
95:     if len(positions) != 1 or positions[0] >= len(params):
96:         raise ContextUnavailable('Cannot uniquely map argument to parameter')
97:     name = params[positions[0]]
98:     if not re.fullmatch(r'[A-Za-z_]\w*', name):
99:         raise ContextUnavailable('Unsupported parameter declaration: ' + name)
100:     return name

141:     def prepare(self, position):
142:         row = self.data[position]
143:         sink = row['location']['context']['snippet']['text']
144:         matches = [x for x in self.historical if x['prt'] == row['var_name'] and x['sink'].strip() == sink.strip() and compact(x['function_call'][0]) == compact(row['function_code'])]
145:         unique = {json.dumps([list(map(compact, x['function_call'])), x['final_sink'].strip()]): x for x in matches}
146:         if not unique and direct_dereference(row['var_name'], sink):
147:             context = {'function_call': [row['function_code']], 'final_sink': sink}
148:             origin = 'official_benchmark_direct_sink'
149:         elif len(unique) == 1:
150:             context = next(iter(unique.values())); origin = 'official_historical_baseline'
151:         else:
152:             raise ContextUnavailable(f'Historical context matches: {len(unique)}')
153:         chain = context['function_call']
154:         var, statement, frames = row['var_name'], sink, []
155:         for level, body in enumerate(chain):
156:             if statement.strip() not in body:
157:                 raise ContextUnavailable('Target statement absent from recovered function')
158:             frame = {'level': level, 'function': function_name(body), 'var_name': var, 'target': statement, 'code': body, 'body_sha256': hashlib.sha256(body.encode()).hexdigest()}
159:             frames.append(frame)
160:             if level == len(chain)-1:
161:                 # A historical macro sink is preserved as such; no claim of a visible

```

## completion/solver_worker.py

SHA-256: `cff88c483595615584c3a339d11edabd78e5f20ee3c950fc86793f74fd6cde62`

```text
35:     class TrackedSolver:
36:         def __init__(self, *args, **kwargs):
37:             self.s = z3.Solver(*args, **kwargs)
38:             self.s.set(timeout=5000)
39: 
40:         def add(self, *args):
41:             return self.s.add(*args)
42: 
43:         def check(self, *args):
44:             result = self.s.check(*args)
45:             queries.append({'result': str(result), 'smt2': self.s.to_smt2()})
46:             return result

63:         answer = namespace['check_constraints']()
64:     if type(answer) is not bool:
65:         raise ValueError('check_constraints must return a Python boolean')
66:     if not queries:
67:         raise ValueError('No actual Solver.check executed')
68:     if any(q['result'] == 'unknown' for q in queries):
69:         raise ValueError('Z3 returned unknown; cannot classify')
70:     if answer != (queries[-1]['result'] == 'sat'):
71:         raise ValueError('Returned boolean disagrees with last solver result')
72:     return {'ok': True, 'feasible': answer, 'queries': queries, 'stdout': output.getvalue()}

```

## safety/policy.py

SHA-256: `eadc92a551aa1f1844b9b0fa8316950c5823a21bab77c2f4a4979ac76811c946`

```text
38: def replay_last_query(bundle):
39:     """Independently check the decisive saved formula, not its C meaning."""
40:     events = bundle.get('solver_events', [])
41:     if not events:
42:         return {'valid': False, 'reason': 'no_saved_solver_event'}
43:     event = events[-1]
44:     queries = event.get('queries', [])
45:     if event.get('ok') is not True or type(event.get('feasible')) is not bool or not queries:
46:         return {'valid': False, 'reason': 'last_solver_event_incomplete'}
47:     if any(q.get('result') not in ('sat', 'unsat') for q in queries):
48:         return {'valid': False, 'reason': 'unknown_or_invalid_saved_query'}
49:     query = queries[-1]
50:     text = query.get('smt2')
51:     if not isinstance(text, str) or not text.strip() or len(text) > 512_000:
52:         return {'valid': False, 'reason': 'invalid_smt2_payload'}
53:     try:
54:         solver = z3.Solver()
55:         solver.from_string(text)
56:         solver.set(timeout=5000)
57:         assertions = [a.sexpr() for a in solver.assertions()]
58:         actual = str(solver.check())
59:     except z3.Z3Exception:
60:         return {'valid': False, 'reason': 'smt2_cannot_be_loaded_unambiguously'}
61:     if not assertions:
62:         return {'valid': False, 'reason': 'empty_constraint_set'}
63:     if actual not in ('sat', 'unsat') or actual != query['result']:
64:         return {'valid': False, 'reason': 'solver_replay_mismatch_or_unknown', 'actual': actual}
65:     if event['feasible'] != (actual == 'sat'):
66:         return {'valid': False, 'reason': 'saved_boolean_disagrees_with_solver'}
67:     return {'valid': True, 'result': actual, 'query_sha256': text_digest(text),
68:             'assertions': assertions, 'event_id': event.get('event_id'),
69:             'meaning': 'formula replay only; source semantics not established'}

117: def review_errors(bundle, review, replay):
118:     """Bind review to the exact evidence and every submitted assertion.
119: 
120:     This validates the review's identity, coverage and freshness. A reviewer
121:     must actually check the C semantics; matching hashes cannot establish that.
122:     """
123:     if not isinstance(review, dict):
124:         return ['missing_semantic_review']
125:     errors = []
126:     if review.get('evidence_sha256') != digest(bundle):
127:         errors.append('review_evidence_mismatch')
128:     if review.get('scope') != bundle.get('scope'):
129:         errors.append('review_scope_mismatch')
130:     allowed = {'manual_source_review', 'trusted_analyzer'}
131:     if bundle.get('scope') == 'synthetic_fixture':
132:         allowed.add('synthetic_fixture_review')
133:     if review.get('verification_mode') not in allowed:
134:         errors.append('untrusted_review_mode')
135:     if not str(review.get('reviewer') or '').strip() or not str(review.get('reviewed_at') or '').strip():
136:         errors.append('review_identity_missing')
137:     if review.get('unresolved_issues') != []:
138:         errors.append('review_has_unresolved_or_unspecified_issues')
139:     if review.get('query_sha256') != replay.get('query_sha256'):

157:     checks = review.get('conditions')
158:     if not isinstance(checks, dict) or set(checks) != set(CONDITIONS):
159:         errors.append('six_review_conditions_required')
160:         checks = {}
161:     for name in CONDITIONS:
162:         item = checks.get(name)
163:         if (not isinstance(item, dict) or item.get('status') != 'verified' or
164:                 not str(item.get('rationale') or '').strip() or not valid_refs(item.get('source_refs'))):
165:             errors.append('review_condition_incomplete:' + name)
166:     trace = review.get('assertion_provenance')
167:     assertions = replay.get('assertions', [])
168:     if not isinstance(trace, list) or len(trace) != len(assertions) or not assertions:
169:         errors.append('incomplete_assertion_provenance')
170:     else:
171:         for i, (item, formula) in enumerate(zip(trace, assertions)):
172:             if (not isinstance(item, dict) or type(item.get('index')) is not int or
173:                     item['index'] != i or item.get('formula') != formula or
174:                     item.get('role') not in ('bug_assumption', 'reachability') or
175:                     not str(item.get('rationale') or '').strip() or not valid_refs(item.get('source_refs'))):
176:                 errors.append('invalid_assertion_provenance:' + str(i))
177:     return errors

198:     if not blockers:
199:         predicted = candidate.get('prediction')
200:         expected = 'sat' if predicted == 'keep' else 'unsat' if predicted == 'filter' else None
201:         if replay.get('result') != expected or expected is None:
202:             reasons.append('candidate_solver_decision_mismatch')
203:         elif predicted == 'keep':
204:             verdict = 'KEEP'
205:             reasons.append('consistent_sat_candidate; alert_retained_not_bug_proved')
206:         else:
207:             review_validation = review_errors(bundle, review, replay)
208:             reasons.extend(review_validation)
209:             if not review_validation:
210:                 complete = True
211:                 verdict = 'FILTER'
212:                 for name in CONDITIONS:
213:                     if name != 'solver_validity':
214:                         checks[name] = _check('verified', 'bound_source_review_attestation')
215:                 reasons.append('six_checks_verified_and_bound_unsat_replayed')

```

## safety/metrics.py

SHA-256: `9507e2e411c14e280b1565e8cbe21bd6f4a01acb180874bfbce9775c741668e8`

```text
18:     for row in rows:
19:         verdict = row['verdict']
20:         if verdict not in ('FILTER', 'KEEP', 'UNKNOWN'):
21:             raise ValueError('Unknown verdict')
22:         expected = 'FILTER' if verdict == 'FILTER' else 'KEEP'
23:         if row.get('action') != expected:
24:             raise ValueError('UNKNOWN/KEEP must retain alert')
25:         label = row.get('dataset_label')
26:         if type(label) is int and label in (0, 1):
27:             counts[str(label)][verdict] += 1
28:             if label == 1 and verdict == 'FILTER':
29:                 deleted.append(row['sample_id'])
30:         else:
31:             unlabeled[verdict] += 1
32:         if verdict == 'FILTER':
33:             if row.get('filter_evidence_complete') is not True:
34:                 raise ValueError('Filtered record without complete evidence')
35:             evidence.append({'sample_id': row['sample_id'], 'evidence_complete': True,
36:                              'evidence_sha256': row.get('evidence_sha256'),
37:                              'review_sha256': row.get('review_sha256')})
38:     fp, bug = counts['0'], counts['1']
39:     n_fp, n_bug = sum(fp.values()), sum(bug.values())
40:     precision = ratio(fp['FILTER'], fp['FILTER'] + bug['FILTER'])
41:     recall = ratio(fp['FILTER'], n_fp)
42:     f1 = (None if precision is None or recall is None else
43:           (2*precision*recall/(precision+recall) if precision+recall else 0.0))

45:         'sample_count': len(rows), 'dataset_label_status': 'published_labels_not_independently_verified',
46:         'confusion_matrix': {'rows': ['published_false_alarm', 'published_real_bug'],
47:                              'columns': ['FILTER', 'KEEP', 'UNKNOWN'],
48:                              'values': [[counts[str(y)][v] for v in ('FILTER', 'KEEP', 'UNKNOWN')] for y in (0, 1)]},
49:         'unverified_or_missing_label_count': sum(unlabeled.values()),
50:         'unverified_or_missing_label_verdicts': dict(unlabeled),
51:         'false_alarm_count': n_fp, 'real_bug_count': n_bug,
52:         'operational_real_bug_retention_rate': ratio(bug['KEEP'] + bug['UNKNOWN'], n_bug),
53:         'explicit_keep_real_bug_rate': ratio(bug['KEEP'], n_bug),
54:         'unknown_real_bug_rate': ratio(bug['UNKNOWN'], n_bug),
55:         'real_bug_deletion_rate': ratio(bug['FILTER'], n_bug),
56:         'real_bug_deletion_cases': deleted,
57:         'false_positive_filter_rate': ratio(fp['FILTER'], n_fp),
58:         'unknown_count': sum(r['verdict'] == 'UNKNOWN' for r in rows),
59:         'unknown_rate': ratio(sum(r['verdict'] == 'UNKNOWN' for r in rows), len(rows)),
60:         'auto_filter_count': len(evidence), 'auto_filter_evidence': evidence,
61:         'positive_class': 'published_false_alarm_to_filter',
62:         'precision': precision, 'recall': recall, 'f1': f1,
63:         'undefined_metric_policy': 'precision/F1 null when no positive prediction; not perfect performance',

```
