int f(int n, int p[n++]) { return n; }
void test(int n, int *p) { int b = f(n, p); (void)b; }
