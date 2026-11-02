void modify(int *p){*p=10;} void first(void){int x=5;modify(&x);} void second(void){int x=5;modify(&x);}
