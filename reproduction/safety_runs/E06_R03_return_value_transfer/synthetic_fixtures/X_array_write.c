int f(int *x){x[0]=1;return 2;} void test(int *a){int b=f(a);(void)b;}
