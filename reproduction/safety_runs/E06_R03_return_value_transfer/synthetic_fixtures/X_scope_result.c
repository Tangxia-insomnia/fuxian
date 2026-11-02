int f(int x){return x;}void test(int a){int b=a;{int b=f(a);(void)b;}(void)b;}
