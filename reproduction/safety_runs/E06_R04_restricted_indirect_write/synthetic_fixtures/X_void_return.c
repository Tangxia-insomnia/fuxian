void modify(int *p){*p=10;return;}void test(void){int x=5;modify(&x);(void)x;}
