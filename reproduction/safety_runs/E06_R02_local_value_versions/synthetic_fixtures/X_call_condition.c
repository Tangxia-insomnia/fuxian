int opaque(void);
void test(int x) { if (opaque()) { x = 1; } (void)x; }
