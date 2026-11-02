struct T{int v;};struct T *g;void modify(int *p){*p=10;g->v=1;}void test(void){int x=5;modify(&x);}
