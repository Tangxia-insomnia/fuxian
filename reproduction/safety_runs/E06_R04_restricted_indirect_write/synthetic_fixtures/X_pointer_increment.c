void modify(int *p){p++;*p=10;}void test(void){int x=5;modify(&x);(void)x;}
