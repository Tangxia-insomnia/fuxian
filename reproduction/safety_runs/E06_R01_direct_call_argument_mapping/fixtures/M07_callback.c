void target(int *p) { (void)p; }
void f(void (*cb)(int *)) { (void)cb; }
void caller(void) { f(target); }
