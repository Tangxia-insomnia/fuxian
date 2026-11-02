int f(int x){goto out;out:return x;} void test(int a){int b=f(a);(void)b;}
