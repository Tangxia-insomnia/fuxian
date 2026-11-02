int *g;void modify(int *p){g=p;}void test(void){int x=5;modify(&x);(void)x;}
