void modify(int *p){int a=10;*p=a;}void test(void){int x=5;modify(&x);(void)x;}
