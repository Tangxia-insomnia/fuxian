void modify(volatile int *p){*p=10;}void test(void){volatile int x=5;modify(&x);}
