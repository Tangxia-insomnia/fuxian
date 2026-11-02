void f(int *p){*p=10;}void g(int *p){*p=20;}void test(void){int x=5;int y=6;f(&x);g(&y);(void)x;(void)y;}
