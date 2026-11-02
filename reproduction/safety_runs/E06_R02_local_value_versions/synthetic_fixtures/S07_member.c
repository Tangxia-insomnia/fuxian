struct sk_buff { int len; };
void test(struct sk_buff *skb) { int x = skb->len; (void)x; }
