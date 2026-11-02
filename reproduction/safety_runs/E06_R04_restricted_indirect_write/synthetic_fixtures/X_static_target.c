void modify(int *p){*p=10;}void test(void){static int x=5;modify(&x);}
