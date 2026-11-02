int f(int x){volatile int y=x;return y;} void test(int a){int b=f(a);(void)b;}
