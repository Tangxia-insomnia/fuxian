void opaque(int **pp);
void test(int *p) { opaque(&p); (void)p; }
