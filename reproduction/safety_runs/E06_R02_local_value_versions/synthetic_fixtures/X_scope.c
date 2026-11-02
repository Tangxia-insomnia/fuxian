void test(int *p) { int *q = p; { int *q = 0; (void)q; } (void)q; }
