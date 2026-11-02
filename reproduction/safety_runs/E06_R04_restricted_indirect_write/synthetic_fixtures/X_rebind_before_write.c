void modify(int *p){p=0;*p=10;}void test(void){int x=5;modify(&x);(void)x;}
