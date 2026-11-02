void f(int *item) { (void)item; }
void caller(double *p) { f((int *)p); }
