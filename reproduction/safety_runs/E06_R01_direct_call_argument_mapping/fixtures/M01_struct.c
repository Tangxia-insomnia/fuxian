struct Node { int n; };
void f(struct Node *item) { (void)item; }
void caller(struct Node *p) { f(p); }
