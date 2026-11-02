int f(int x){int y=f(x);return y;} void test(int a){int b=f(a);(void)b;}
