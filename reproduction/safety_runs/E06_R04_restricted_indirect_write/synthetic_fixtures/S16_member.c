struct T{int v;};void modify(int *p){*p=10;}void test(void){struct T x;modify(&x.v);}
