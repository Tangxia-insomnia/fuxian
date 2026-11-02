void modify(int *p){*p=10;}void test(void){int x=5;void(*f)(int*)=modify;f(&x);}
