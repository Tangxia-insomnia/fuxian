void modify(int *p){*p=10;}void test(void){int x=5;int *q=&x;modify(q);}
