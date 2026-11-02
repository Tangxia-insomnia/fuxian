void f(int *a, int *b) { (void)a; (void)b; }
void caller(int *p) { f(p, p); }
