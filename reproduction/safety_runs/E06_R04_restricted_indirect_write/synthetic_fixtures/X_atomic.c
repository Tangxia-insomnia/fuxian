void modify(_Atomic int *p){*p=10;}void test(void){_Atomic int x=5;modify(&x);}
