int f(int x){static int s;s=x;return x;} void test(int a){int b=f(a);(void)b;}
