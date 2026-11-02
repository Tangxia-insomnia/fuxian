void callee(int *item) { (void)item; }
void caller(int *p) { callee(p); }
