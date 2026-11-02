void modify(int *p){return;*p=10;}void test(void){int x=5;modify(&x);(void)x;}
