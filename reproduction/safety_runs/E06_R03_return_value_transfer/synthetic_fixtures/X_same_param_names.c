int f(int x){return x;} int g(int x){x=0;return x;} void test(int a){int b=f(a);int c=g(a);(void)b;(void)c;}
