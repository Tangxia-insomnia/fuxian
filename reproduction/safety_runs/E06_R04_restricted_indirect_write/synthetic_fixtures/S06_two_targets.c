void modify(int *p){*p=10;} void test(void){int x=1;int y=2;modify(&x);modify(&y);(void)x;(void)y;}
