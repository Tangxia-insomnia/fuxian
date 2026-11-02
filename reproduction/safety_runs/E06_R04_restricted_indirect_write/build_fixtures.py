"""Controlled C fixtures; never compile or execute C."""
import json
from r03_adapter import ROOT,r01

CASES={
 'S01_write':('PASS','void modify(int *p){*p=10;} void test(void){int x=5;modify(&x);}'),
 'S02_read':('PASS','void modify(int *p){*p=10;} void test(void){int x=5;modify(&x);(void)x;}'),
 'S03_old':('PASS','void modify(int *p){*p=10;} void test(void){int x=5;int y=x;modify(&x);(void)y;(void)x;}'),
 'S04_rebind':('PASS','void modify(int *p){p=0;} void test(void){int x=5;modify(&x);(void)x;}'),
 'S05_write_rebind':('PASS','void modify(int *p){*p=10;p=0;} void test(void){int x=5;modify(&x);(void)x;}'),
 'S06_two_targets':('PASS','void modify(int *p){*p=10;} void test(void){int x=1;int y=2;modify(&x);modify(&y);(void)x;(void)y;}'),
 'S07_caller_paths':('PASS','void modify(int *p){*p=10;} void test(int c){int x=1;if(c)x=2;modify(&x);(void)x;}'),
 'S10_global_escape':('UNKNOWN','int *g;void modify(int *p){g=p;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S11_return_escape':('UNKNOWN','int *modify(int *p){return p;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S12_transfer_escape':('UNKNOWN','void ext(int*);void modify(int *p){ext(p);}void test(void){int x=5;modify(&x);(void)x;}'),
 'S13_arithmetic':('UNKNOWN','void modify(int *p){p=p+1;*p=10;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S14_pointer_copy':('UNKNOWN','void modify(int *p){int *q=p;*q=10;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S15_multilevel':('UNKNOWN','void modify(int **p){*p=0;}void test(int *v){int *x=v;modify(&x);(void)x;}'),
 'S16_member':('UNKNOWN','struct T{int v;};void modify(int *p){*p=10;}void test(void){struct T x;modify(&x.v);}'),
 'S17_array':('UNKNOWN','void modify(int *p){*p=10;}void test(void){int x[2];modify(&x[0]);}'),
 'S18_cast':('UNKNOWN','void modify(int *p){*p=10;}void test(void){long x=5;modify((int*)&x);}'),
 'S19_unknown_call':('UNKNOWN','void ext(void);void modify(int *p){*p=10;ext();}void test(void){int x=5;modify(&x);(void)x;}'),
 'S20_global_write':('UNKNOWN','int g;void modify(int *p){*p=10;g=2;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S21_multiple_definitions':('UNKNOWN','void modify(int *p){*p=10;}void test(void){int x=5;modify(&x);}'),
 'S22_missing':('UNKNOWN','void modify(int *p);void test(void){int x=5;modify(&x);(void)x;}'),
 'S23_multiple_targets':('UNKNOWN','void modify(int *p,int *q){*p=10;}void test(void){int x=5;int y=6;modify(&x,&y);}'),
 'S24_two_writes':('UNKNOWN','void modify(int *p){*p=10;*p=20;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S25_compound':('UNKNOWN','void modify(int *p){*p+=1;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S26_increment':('UNKNOWN','void modify(int *p){(*p)++;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S27_read_modify':('UNKNOWN','void modify(int *p){*p=*p+1;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S28_branch':('UNKNOWN','void modify(int *p){if(p)*p=10;}void test(void){int x=5;modify(&x);(void)x;}'),
 'S28_loop':('UNKNOWN','void modify(int *p){while(p){*p=10;break;}}void test(void){int x=5;modify(&x);(void)x;}'),
 'S29_later_assignment':('PASS','void modify(int *p){*p=10;}void test(void){int x=5;modify(&x);x=20;(void)x;}'),
 'S32_narrow_write':('UNKNOWN','void modify(short *p){*p=10;}void test(short v){short x=v;modify(&x);}'),
 'X_same_object_twice':('PASS','void modify(int *p){*p=10;}void test(void){int x=5;modify(&x);modify(&x);(void)x;}'),
 'X_shadow':('PASS','void modify(int *p){*p=10;}void test(void){int x=1;{int x=2;modify(&x);(void)x;}modify(&x);(void)x;}'),
 'X_unsigned':('PASS','void modify(unsigned int *p){*p=10U;}void test(void){unsigned int x=5U;modify(&x);(void)x;}'),
 'X_double':('PASS','void modify(double *p){*p=1.5;}void test(void){double x=5.0;modify(&x);(void)x;}'),
 'X_widen_write':('PASS','void modify(long long *p){*p=10;}void test(void){long long x=5;modify(&x);(void)x;}'),
 'X_void_return':('PASS','void modify(int *p){*p=10;return;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_parentheses':('PASS','void modify(int *p){*(p)=10;}void test(void){int x=5;modify(&(x));(void)x;}'),
 'X_no_write':('PASS','void modify(int *p){(void)p;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_no_call':('N/A','void test(void){int x=5;(void)x;}'),
 'X_rebind_before_write':('UNKNOWN','void modify(int *p){p=0;*p=10;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_call_before_write':('UNKNOWN','void ext(void);void modify(int *p){ext();*p=10;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_pointer_increment':('UNKNOWN','void modify(int *p){p++;*p=10;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_pointer_integer':('UNKNOWN','void modify(int *p){long long a=(long long)p;(void)a;}void test(void){int x=5;modify(&x);}'),
 'X_local_RHS':('UNKNOWN','void modify(int *p){int a=10;*p=a;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_negative_literal':('UNKNOWN','void modify(int *p){*p=-1;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_arithmetic_literal':('UNKNOWN','void modify(int *p){*p=1+1;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_macro':('UNKNOWN','#define V 10\nvoid modify(int *p){*p=V;}void test(void){int x=5;modify(&x);}'),
 'X_volatile':('UNKNOWN','void modify(volatile int *p){*p=10;}void test(void){volatile int x=5;modify(&x);}'),
 'X_atomic':('UNKNOWN','void modify(_Atomic int *p){*p=10;}void test(void){_Atomic int x=5;modify(&x);}'),
 'X_static_target':('UNKNOWN','void modify(int *p){*p=10;}void test(void){static int x=5;modify(&x);}'),
 'X_global_target':('UNKNOWN','int x=5;void modify(int *p){*p=10;}void test(void){modify(&x);}'),
 'X_const_target':('UNKNOWN','void modify(const int *p){p=0;}void test(void){const int x=5;modify(&x);}'),
 'X_uninitialized':('UNKNOWN','void modify(int *p){*p=10;}void test(void){int x;modify(&x);(void)x;}'),
 'X_parameter_object':('UNKNOWN','void modify(int *p){*p=10;}void test(int x){modify(&x);(void)x;}'),
 'X_address_alias':('UNKNOWN','void modify(int *p){*p=10;}void test(void){int x=5;int *q=&x;modify(q);}'),
 'X_function_pointer':('UNKNOWN','void modify(int *p){*p=10;}void test(void){int x=5;void(*f)(int*)=modify;f(&x);}'),
 'X_unknown_caller_after':('UNKNOWN','void use(int);void modify(int *p){*p=10;}void test(void){int x=5;modify(&x);use(x);(void)x;}'),
 'X_other_indirect':('UNKNOWN','int *g;void modify(int *p){*p=10;*g=20;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_static_write':('UNKNOWN','void modify(int *p){static int g;g=1;*p=10;}void test(void){int x=5;modify(&x);}'),
 'X_member_write':('UNKNOWN','struct T{int v;};struct T *g;void modify(int *p){*p=10;g->v=1;}void test(void){int x=5;modify(&x);}'),
 'X_goto':('UNKNOWN','void modify(int *p){goto out;out:*p=10;}void test(void){int x=5;modify(&x);}'),
 'X_recursion':('UNKNOWN','void modify(int *p){modify(p);}void test(void){int x=5;modify(&x);}'),
 'X_asm':('UNKNOWN','void modify(int *p){__asm__("");*p=10;}void test(void){int x=5;modify(&x);}'),
 'X_missing_typedef':('UNKNOWN','void modify(missing *p){*p=10;}void test(void){int x=5;modify(&x);}'),
 'X_unknown_named_alloc':('UNKNOWN','void alloc(int *p);void test(void){int x=5;alloc(&x);}'),
 'X_two_functions_same_parameter':('PASS','void f(int *p){*p=10;}void g(int *p){*p=20;}void test(void){int x=5;int y=6;f(&x);g(&y);(void)x;(void)y;}'),
 'X_early_return':('PASS','void modify(int *p){return;*p=10;}void test(void){int x=5;modify(&x);(void)x;}'),
 'X_context_budget':('UNKNOWN','void modify(int *p){*p=10;}void test(void){int x=5;'+('modify(&x);'*17)+'(void)x;}'),
}


def main():
    out=ROOT/'synthetic_fixtures';out.mkdir(exist_ok=False);rows=[]
    for name,(expected,code) in CASES.items():
        blob=(code+'\n').encode();(out/(name+'.c')).write_bytes(blob)
        rows.append({'case':name,'source':name+'.c','original_C':code+'\n','source_sha256':r01.digest(blob),
            'expected_status':expected,'caller':'test',**({'candidate_source_paths':['extra_definition.c']} if name=='S21_multiple_definitions' else {})})
    (out/'extra_definition.c').write_bytes(b'void modify(int *p){*p=10;}\n')
    (out/'different_callers.c').write_bytes(b'void modify(int *p){*p=10;} void first(void){int x=5;modify(&x);} void second(void){int x=5;modify(&x);}\n')
    with (out/'cases.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(rows,f,indent=2);f.write('\n')
    print(json.dumps({'primary_scenarios':len(rows),'additional_different_callers':1}))


if __name__=='__main__':main()
