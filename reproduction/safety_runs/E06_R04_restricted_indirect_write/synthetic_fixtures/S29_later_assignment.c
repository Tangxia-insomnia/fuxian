void modify(int *p){*p=10;}void test(void){int x=5;modify(&x);x=20;(void)x;}
