void f(int *item) { (void)item; }
#define WRAP(x) f(x)
void caller(int *p) { WRAP(p); }
