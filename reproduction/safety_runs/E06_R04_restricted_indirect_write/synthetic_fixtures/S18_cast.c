void modify(int *p){*p=10;}void test(void){long x=5;modify((int*)&x);}
