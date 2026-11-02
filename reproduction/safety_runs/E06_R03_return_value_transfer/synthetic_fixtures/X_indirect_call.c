int f(int x){return x;} void test(int a){int (*p)(int)=f;int b=p(a);(void)b;}
