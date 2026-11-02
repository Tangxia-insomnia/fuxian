static inline void sock_confirm_neigh(struct sk_buff *skb, struct neighbour *n)
{
	if (skb_get_dst_pending_confirm(skb)) {
		struct sock *sk = skb->sk;

		if (sk && READ_ONCE(sk->sk_dst_pending_confirm))
			WRITE_ONCE(sk->sk_dst_pending_confirm, 0);
		neigh_confirm(n);
	}
}