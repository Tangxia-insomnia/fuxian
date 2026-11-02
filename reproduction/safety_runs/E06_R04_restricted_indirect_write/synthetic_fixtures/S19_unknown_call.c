void ext(void);void modify(int *p){*p=10;ext();}void test(void){int x=5;modify(&x);(void)x;}
