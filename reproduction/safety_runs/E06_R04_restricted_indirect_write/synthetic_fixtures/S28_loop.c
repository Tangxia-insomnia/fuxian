void modify(int *p){while(p){*p=10;break;}}void test(void){int x=5;modify(&x);(void)x;}
