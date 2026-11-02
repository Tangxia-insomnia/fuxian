int ext(int);int f(int x){if(x)return 2;int y=ext(x);return y;} void test(int a){int b=f(a);(void)b;}
