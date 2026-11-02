static int ip6_finish_output2(struct net *net, struct sock *sk, struct sk_buff *skb)
{
	struct dst_entry *dst = skb_dst(skb);
	struct net_device *dev = dst->dev;
	struct inet6_dev *idev = ip6_dst_idev(dst);
	unsigned int hh_len = LL_RESERVED_SPACE(dev);
	const struct in6_addr *daddr, *nexthop;
	struct ipv6hdr *hdr;
	struct neighbour *neigh;
	int ret;

	/* Be paranoid, rather than too clever. */
	if (unlikely(hh_len > skb_headroom(skb)) && dev->header_ops) {
		skb = skb_expand_head(skb, hh_len);
		if (!skb) {
			IP6_INC_STATS(net, idev, IPSTATS_MIB_OUTDISCARDS);
			return -ENOMEM;
		}
	}

	hdr = ipv6_hdr(skb);
	daddr = &hdr->daddr;
	if (ipv6_addr_is_multicast(daddr)) {
		if (!(dev->flags & IFF_LOOPBACK) && sk_mc_loop(sk) &&
		    ((mroute6_is_socket(net, skb) &&
		     !(IP6CB(skb)->flags & IP6SKB_FORWARDED)) ||
		     ipv6_chk_mcast_addr(dev, daddr, &hdr->saddr))) {
			struct sk_buff *newskb = skb_clone(skb, GFP_ATOMIC);

			/* Do not check for IFF_ALLMULTI; multicast routing
			   is not supported in any case.
			 */
			if (newskb)
				NF_HOOK(NFPROTO_IPV6, NF_INET_POST_ROUTING,
					net, sk, newskb, NULL, newskb->dev,
					dev_loopback_xmit);

			if (hdr->hop_limit == 0) {
				IP6_INC_STATS(net, idev,
					      IPSTATS_MIB_OUTDISCARDS);
				kfree_skb(skb);
				return 0;
			}
		}

		IP6_UPD_PO_STATS(net, idev, IPSTATS_MIB_OUTMCAST, skb->len);
		if (IPV6_ADDR_MC_SCOPE(daddr) <= IPV6_ADDR_SCOPE_NODELOCAL &&
		    !(dev->flags & IFF_LOOPBACK)) {
			kfree_skb(skb);
			return 0;
		}
	}

	if (lwtunnel_xmit_redirect(dst->lwtstate)) {
		int res = lwtunnel_xmit(skb);

		if (res != LWTUNNEL_XMIT_CONTINUE)
			return res;
	}

	IP6_UPD_PO_STATS(net, idev, IPSTATS_MIB_OUT, skb->len);

	rcu_read_lock();
	nexthop = rt6_nexthop(dst_rt6_info(dst), daddr);
	neigh = __ipv6_neigh_lookup_noref(dev, nexthop);

	if (unlikely(IS_ERR_OR_NULL(neigh))) {
		if (unlikely(!neigh))
			neigh = __neigh_create(&nd_tbl, nexthop, dev, false);
		if (IS_ERR(neigh)) {
			rcu_read_unlock();
			IP6_INC_STATS(net, idev, IPSTATS_MIB_OUTNOROUTES);
			kfree_skb_reason(skb, SKB_DROP_REASON_NEIGH_CREATEFAIL);
			return -EINVAL;
		}
	}
	sock_confirm_neigh(skb, neigh);
	ret = neigh_output(neigh, skb, false);
	rcu_read_unlock();
	return ret;
}