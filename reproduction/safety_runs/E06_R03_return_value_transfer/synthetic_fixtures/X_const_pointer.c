const int *f(int *x){return x;} void test(int *a){const int *b=f(a);(void)b;}
