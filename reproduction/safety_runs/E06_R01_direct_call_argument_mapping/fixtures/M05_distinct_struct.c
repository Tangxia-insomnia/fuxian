struct A { int x; };
struct B { int x; };
void f(struct A *item) { (void)item; }
void caller(struct B *p) { f(p); }
