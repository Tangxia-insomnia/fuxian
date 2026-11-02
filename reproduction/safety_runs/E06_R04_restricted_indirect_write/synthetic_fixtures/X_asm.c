void modify(int *p){__asm__("");*p=10;}void test(void){int x=5;modify(&x);}
