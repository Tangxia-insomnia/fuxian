void modify(int *p){goto out;out:*p=10;}void test(void){int x=5;modify(&x);}
