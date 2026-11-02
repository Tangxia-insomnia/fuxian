void modify(int *p){*p=10;*p=20;}void test(void){int x=5;modify(&x);(void)x;}
