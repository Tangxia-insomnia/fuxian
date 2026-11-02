int f(int *x){*x=0;return 1;} void test(int *a){int b=f(a);(void)b;}
