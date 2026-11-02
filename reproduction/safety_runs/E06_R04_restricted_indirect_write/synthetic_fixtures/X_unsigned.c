void modify(unsigned int *p){*p=10U;}void test(void){unsigned int x=5U;modify(&x);(void)x;}
