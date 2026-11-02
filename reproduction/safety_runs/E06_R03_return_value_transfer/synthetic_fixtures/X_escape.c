void ext(int*);int f(int x){ext(&x);return x;} void test(int a){int b=f(a);(void)b;}
