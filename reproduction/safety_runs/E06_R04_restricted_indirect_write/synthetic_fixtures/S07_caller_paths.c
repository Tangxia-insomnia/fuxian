void modify(int *p){*p=10;} void test(int c){int x=1;if(c)x=2;modify(&x);(void)x;}
