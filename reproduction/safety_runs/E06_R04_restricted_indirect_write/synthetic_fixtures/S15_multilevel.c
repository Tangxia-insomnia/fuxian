void modify(int **p){*p=0;}void test(int *v){int *x=v;modify(&x);(void)x;}
