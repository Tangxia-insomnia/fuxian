"""Write self-contained C inputs, never compile or execute them."""
import json
from adapter import ROOT, r01

CASES = {
 'S01_param': ('PASS', 'int f(int x){return x;} void test(int a){int b=f(a);(void)b;}'),
 'S02_local': ('PASS', 'int f(int x){int y=x;return y;} void test(int a){int b=f(a);(void)b;}'),
 'S03_constant': ('PASS', 'int f(void){return 10;} void test(void){int b=f();(void)b;}'),
 'S04_two_returns': ('PASS', 'int f(int x){if(x)return 10;else return 20;} void test(int a){int b=f(a);(void)b;}'),
 'S05_early': ('PASS', 'int f(int x){if(x)return 10;return x;} void test(int a){int b=f(a);b=30;(void)b;}'),
 'S06_reassign_param': ('PASS', 'int f(int x){x=0;return x;} void test(int a){int b=f(a);(void)a;(void)b;}'),
 'S07_read': ('PASS', 'int f(int x){return x;} void use(int x){(void)x;} void test(int a){int b=f(a);use(b);}'),
 'S08_ignored': ('PASS', 'int f(int x){if(x)return 2;return 3;} void test(int a){f(a);int b=a;(void)b;}'),
 'S09_void': ('PASS', 'void f(int x){(void)x;return;} void test(int a){f(a);(void)a;}'),
 'S10_callsites': ('PASS', 'int f(int x){return x;} void test(int a,int b){int p=f(a);int q=f(b);(void)p;(void)q;}'),
 'S11_caller_paths': ('PASS', 'int f(int x){return x;} void test(int a,int b){int p=a;if(b)p=b;int q=f(p);(void)q;}'),
 'S12_nested_return': ('UNKNOWN', 'int g(int x){return x;} int f(int x){return g(x);} void test(int a){int b=f(a);(void)b;}'),
 'S13_global': ('UNKNOWN', 'int g; int f(int x){g=x;return x;} void test(int a){int b=f(a);(void)b;}'),
 'S13_indirect': ('UNKNOWN', 'int f(int *x){*x=0;return 1;} void test(int *a){int b=f(a);(void)b;}'),
 'S14_missing': ('UNKNOWN', 'int f(int); void test(int a){int b=f(a);(void)b;}'),
 'S15_recursive': ('UNKNOWN', 'int f(int x){int y=f(x);return y;} void test(int a){int b=f(a);(void)b;}'),
 'S15_loop': ('UNKNOWN', 'int f(int x){while(x){x=0;}return x;} void test(int a){int b=f(a);(void)b;}'),
 'S15_goto': ('UNKNOWN', 'int f(int x){goto out;out:return x;} void test(int a){int b=f(a);(void)b;}'),
 'S15_nested_if': ('UNKNOWN', 'int f(int x){if(x){if(x)return 2;}return 1;} void test(int a){int b=f(a);(void)b;}'),
 'S16_narrow_return': ('UNKNOWN', 'short f(int x){return x;} void test(int a){short b=f(a);(void)b;}'),
 'S16_narrow_receive': ('UNKNOWN', 'int f(int x){return x;} void test(int a){short b=f(a);(void)b;}'),
 'S17_fallthrough': ('UNKNOWN', 'int f(int x){if(x)return 1;} void test(int a){int b=f(a);(void)b;}'),
 'S18_member': ('UNKNOWN', 'struct T{int v;}; int f(int x){return x;} void test(int a){struct T s;s.v=f(a);}'),
 'S18_array': ('UNKNOWN', 'int f(int x){return x;} void test(int a){int s[2];s[0]=f(a);}'),
 'X_pointer_param': ('PASS', 'int *f(int *p){p=0;return p;} void test(int *a){int *b=f(a);(void)a;(void)b;}'),
 'X_pointer_constant': ('PASS', 'int *f(void){return 0;} void test(void){int *b=f();(void)b;}'),
 'X_pointer_copy': ('PASS', 'int *f(int *x){int *y=x;x=0;return y;} void test(int *a){int *b=f(a);(void)a;(void)b;}'),
 'X_repeated': ('PASS', 'int f(int x){return x;} void test(int a){int b=f(a);b=f(a);(void)b;}'),
 'X_same_param_names': ('PASS', 'int f(int x){return x;} int g(int x){x=0;return x;} void test(int a){int b=f(a);int c=g(a);(void)b;(void)c;}'),
 'X_multi_param': ('PASS', 'int f(int x,int y){return y;} void test(int a,int b){int c=f(a,b);(void)c;}'),
 'X_double_actual': ('PASS', 'int f(int x,int y){return y;} void test(int a){int c=f(a,a);(void)c;}'),
 'X_zero_void': ('PASS', 'void f(void){} void test(void){f();}'),
 'X_void_if': ('PASS', 'void f(int x){if(x)return;} void test(int a){f(a);(void)a;}'),
 'X_unsigned_literal': ('PASS', 'unsigned long long f(void){return 10ULL;} void test(void){unsigned long long b=f();(void)b;}'),
 'X_float_literal': ('PASS', 'double f(void){return 1.5;} void test(void){double b=f();(void)b;}'),
 'X_widen_return': ('PASS', 'long long f(int x){return x;} void test(int a){long long b=f(a);(void)b;}'),
 'X_widen_receive': ('PASS', 'int f(int x){return x;} void test(int a){long long b=f(a);(void)b;}'),
 'X_const_pointer': ('PASS', 'const int *f(int *x){return x;} void test(int *a){const int *b=f(a);(void)b;}'),
 'X_struct_pointer': ('PASS', 'struct T{int x;}; struct T *f(struct T *x){return x;} void test(struct T *a){struct T *b=f(a);(void)b;}'),
 'X_shadow': ('PASS', 'int f(int x){int y=x;{int y=1;(void)y;}return y;} void test(int a){int b=f(a);(void)b;}'),
 'X_no_call': ('N/A', 'void test(int a){(void)a;}'),
 'X_unknown_call': ('UNKNOWN', 'void ext(int); int f(int x){ext(x);return x;} void test(int a){int b=f(a);(void)b;}'),
 'X_unknown_after_early': ('UNKNOWN', 'int ext(int);int f(int x){if(x)return 2;int y=ext(x);return y;} void test(int a){int b=f(a);(void)b;}'),
 'X_arithmetic': ('UNKNOWN', 'int f(int x){return x+1;} void test(int a){int b=f(a);(void)b;}'),
 'X_cast': ('UNKNOWN', 'int f(int x){return (int)x;} void test(int a){int b=f(a);(void)b;}'),
 'X_negative': ('UNKNOWN', 'int f(void){return -1;} void test(void){int b=f();(void)b;}'),
 'X_macro': ('UNKNOWN', '#define V 2\nint f(void){return V;} void test(void){int b=f();(void)b;}'),
 'X_unknown_typedef': ('UNKNOWN', 'mystery f(mystery x){return x;} void test(void){f(0);}'),
 'X_static': ('UNKNOWN', 'int f(int x){static int s;s=x;return x;} void test(int a){int b=f(a);(void)b;}'),
 'X_member_write': ('UNKNOWN', 'struct T{int v;};int f(struct T *x){x->v=1;return 2;} void test(struct T *a){int b=f(a);(void)b;}'),
 'X_array_write': ('UNKNOWN', 'int f(int *x){x[0]=1;return 2;} void test(int *a){int b=f(a);(void)b;}'),
 'X_escape': ('UNKNOWN', 'void ext(int*);int f(int x){ext(&x);return x;} void test(int a){int b=f(a);(void)b;}'),
 'X_volatile': ('UNKNOWN', 'int f(int x){volatile int y=x;return y;} void test(int a){int b=f(a);(void)b;}'),
 'X_atomic': ('UNKNOWN', 'int f(int x){_Atomic int y=x;return y;} void test(int a){int b=f(a);(void)b;}'),
 'X_indirect_call': ('UNKNOWN', 'int f(int x){return x;} void test(int a){int (*p)(int)=f;int b=p(a);(void)b;}'),
 'X_union': ('UNKNOWN', 'union T{int x;};union T *f(union T *p){return p;}void test(union T *a){union T *b=f(a);(void)b;}'),
 'X_void_pointer': ('UNKNOWN', 'void *f(void *p){return p;}void test(void *a){void *b=f(a);(void)b;}'),
 'X_pointer_depth': ('UNKNOWN', 'int **f(int **p){return p;}void test(int **a){int **b=f(a);(void)b;}'),
 'X_argument_write': ('UNKNOWN', 'int f(int x,int y){return x;}void test(int a){int b=f(a,a=2);(void)b;}'),
 'X_explicit_discard_cast': ('UNKNOWN', 'int f(int x){return x;}void test(int a){(void)f(a);(void)a;}'),
 'X_two_definitions': ('UNKNOWN', 'int f(int x){return x;}void test(int a){int b=f(a);(void)b;}'),
 'X_incompatible_return': ('UNKNOWN', 'struct T{int x;};struct T f(int x){struct T s;return s;}void test(int a){struct T b=f(a);}'),
 'X_asm': ('UNKNOWN', 'int f(int x){__asm__("");return x;}void test(int a){int b=f(a);(void)b;}'),
 'X_unknown_caller_after': ('UNKNOWN', 'int ext(int);int f(int x){return x;}void test(int a){int b=f(a);ext(b);(void)b;}'),
 'X_scope_result': ('PASS', 'int f(int x){return x;}void test(int a){int b=a;{int b=f(a);(void)b;}(void)b;}'),
}


def main():
    directory = ROOT/'synthetic_fixtures'
    directory.mkdir(exist_ok=False)
    rows = []
    for name,(status,code) in CASES.items():
        blob = (code+'\n').encode('utf-8')
        path = directory/(name+'.c')
        path.write_bytes(blob)
        rows.append({'case': name, 'source': path.name, 'source_sha256': r01.digest(blob),
                     'expected_status': status, 'caller': 'test', 'original_C': code+'\n'})
    extra = directory/'extra_definition.c'
    extra.write_text('int f(int x){return x;}\n',encoding='utf-8')
    rows = [{**r, **({'candidate_source_paths': ['extra_definition.c']} if r['case']=='X_two_definitions' else {})} for r in rows]
    (directory/'cases.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'scenarios': len(rows)}))


if __name__=='__main__': main()
