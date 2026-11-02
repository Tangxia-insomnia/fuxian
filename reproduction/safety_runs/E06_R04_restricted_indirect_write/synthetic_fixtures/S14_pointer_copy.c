void modify(int *p){int *q=p;*q=10;}void test(void){int x=5;modify(&x);(void)x;}
