int *f(int *p){p=0;return p;} void test(int *a){int *b=f(a);(void)a;(void)b;}
