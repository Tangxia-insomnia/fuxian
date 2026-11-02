void test(int flag, int *p) { if (flag) { int *q = p; (void)q; } else { int *q = 0; (void)q; } (void)p; }
