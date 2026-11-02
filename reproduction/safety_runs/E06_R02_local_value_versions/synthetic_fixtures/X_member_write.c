struct N { int x; };
void test(struct N *p) { p->x = 1; (void)p; }
