int f(int x){_Atomic int y=x;return y;} void test(int a){int b=f(a);(void)b;}
