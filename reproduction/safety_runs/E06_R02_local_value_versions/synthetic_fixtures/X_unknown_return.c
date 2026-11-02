int *opaque(void);
void test(int *p) { p = opaque(); (void)p; }
