struct Node { int *p; };
void f(int *item) { (void)item; }
void caller(struct Node *n) { f(n->p); }
