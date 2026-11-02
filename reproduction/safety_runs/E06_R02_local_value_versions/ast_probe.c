void probe(int *p, int *other, int flag) {
    int *q = p;
    p = 0;
    if (flag) { p = other; } else { p = q; }
    (void)p;
}
