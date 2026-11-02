void modify(int *p){static int g;g=1;*p=10;}void test(void){int x=5;modify(&x);}
