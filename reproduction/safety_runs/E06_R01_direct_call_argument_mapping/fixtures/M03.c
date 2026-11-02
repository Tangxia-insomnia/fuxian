void f(int *p) { (void)p; }
void first(int *p) { f(p); { int *p = 0; f(p); } }
void second(int *p) { f(p); }
