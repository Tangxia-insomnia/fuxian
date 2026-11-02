int *f(int *x){int *y=x;x=0;return y;} void test(int *a){int *b=f(a);(void)a;(void)b;}
