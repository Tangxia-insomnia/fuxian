union T{int x;};union T *f(union T *p){return p;}void test(union T *a){union T *b=f(a);(void)b;}
