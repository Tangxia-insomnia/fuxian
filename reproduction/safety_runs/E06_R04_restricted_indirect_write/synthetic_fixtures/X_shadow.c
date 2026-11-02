void modify(int *p){*p=10;}void test(void){int x=1;{int x=2;modify(&x);(void)x;}modify(&x);(void)x;}
