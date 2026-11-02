struct T{int x;}; struct T *f(struct T *x){return x;} void test(struct T *a){struct T *b=f(a);(void)b;}
