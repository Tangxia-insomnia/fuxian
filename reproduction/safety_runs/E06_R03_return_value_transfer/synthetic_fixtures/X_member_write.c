struct T{int v;};int f(struct T *x){x->v=1;return 2;} void test(struct T *a){int b=f(a);(void)b;}
