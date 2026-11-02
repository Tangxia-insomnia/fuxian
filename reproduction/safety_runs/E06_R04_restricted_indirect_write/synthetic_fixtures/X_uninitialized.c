void modify(int *p){*p=10;}void test(void){int x;modify(&x);(void)x;}
