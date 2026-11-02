"""Generic source-text locators only. Never approve types, values or control flow."""
import re
from adapter import r01

LEX = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|\d+(?:[A-Za-z0-9_.]*)|\S')


def tokens(code):
    return [m for m in LEX.finditer(code) if not m.group().startswith(('//','/*'))]


def location(code, start, end):
    return {'start': {'line_1based':code.count('\n',0,start)+1,
                      'column_1based':start-code.rfind('\n',0,start),
                      'byte_offset':len(code[:start].encode('utf-8'))},
            'end_exclusive': {'line_1based':code.count('\n',0,end)+1,
                              'column_1based':end-code.rfind('\n',0,end),
                              'byte_offset':len(code[:end].encode('utf-8'))}}


def returns(code):
    ts=tokens(code); result=[]; lines=code.splitlines()
    for i,t in enumerate(ts):
        if t.group()!='return':continue
        depth=0;stop=None
        for j in range(i+1,len(ts)):
            tok=ts[j].group()
            if tok in {'(','['}:depth+=1
            elif tok in {')',']'}:depth-=1
            elif tok==';' and depth==0:stop=j;break
        if stop is None:continue
        expression=code[t.end():ts[stop].start()].strip()
        line=code.count('\n',0,t.start())+1
        result.append({'return_locator_id':r01.stable_id('source-return',[r01.digest(code.encode()),t.start(),ts[stop].end()]),
                       'return_source_range':location(code,t.start(),ts[stop].end()),
                       'raw_return_expression':expression,
                       'category_candidate':'constant' if re.fullmatch(r'\d+[uUlL]*',expression) else
                                            'void' if not expression else 'unsupported_or_unverified_expression',
                       'nearby_source_lines':{'first_line_1based':max(1,line-1),
                                             'text':'\n'.join(lines[max(0,line-2):line])},
                       'contains_call_candidate':bool(re.search(r'\b[A-Za-z_]\w*\s*\(',expression)),
                       'status':'UNKNOWN','type':None,'source_value_version_id':None,
                       'normal_return_verified':False,'guard_semantics_verified':False,
                       'method':'literal_source_locator_only'})
    return result


def calls_to(code,function):
    ts=tokens(code);out=[]
    for i,t in enumerate(ts[:-1]):
        if t.group()!=function or ts[i+1].group()!='(':continue
        depth=1;j=i+2
        while j<len(ts) and depth:
            if ts[j].group()=='(':depth+=1
            elif ts[j].group()==')':depth-=1
            j+=1
        if depth:continue
        isolated=(i>0 and ts[i-1].group() in {';','{','}'} and j<len(ts) and ts[j].group()==';')
        out.append({'raw_call':code[t.start():ts[j-1].end()],
                    'source_range':location(code,t.start(),ts[j-1].end()),
                    'result_disposition_candidate':'ignored' if isolated else 'unverified_expression_use',
                    'binding_status':'UNKNOWN','method':'literal_source_locator_only',
                    'caller_result_version_id':None,'guard_transferred_to_caller':False,
                    'callee_return_terminates_caller':False})
    return out
