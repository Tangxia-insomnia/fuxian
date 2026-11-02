void ext(void);void modify(int *p){ext();*p=10;}void test(void){int x=5;modify(&x);(void)x;}
