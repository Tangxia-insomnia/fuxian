void ext(int*);void modify(int *p){ext(p);}void test(void){int x=5;modify(&x);(void)x;}
