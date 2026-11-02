void f(int *a, double *b) { (void)a; (void)b; }
void caller(int *p, double *q) { f(p, q); }
