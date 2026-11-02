static int ipv6_route_native_seq_show(struct seq_file *seq, void *v)
{
	struct fib6_info *rt = v;
	struct ipv6_route_iter *iter = seq->private;
	struct fib6_nh *fib6_nh = rt->fib6_nh;
	unsigned int flags = rt->fib6_flags;
	const struct net_device *dev;

	if (rt->nh)
		fib6_nh = nexthop_fib6_nh(rt->nh);

	seq_printf(seq, "%pi6 %02x ", &rt->fib6_dst.addr, rt->fib6_dst.plen);

#ifdef CONFIG_IPV6_SUBTREES
	seq_printf(seq, "%pi6 %02x ", &rt->fib6_src.addr, rt->fib6_src.plen);
#else
	seq_puts(seq, "00000000000000000000000000000000 00 ");
#endif
	if (fib6_nh->fib_nh_gw_family) {
		flags |= RTF_GATEWAY;
		seq_printf(seq, "%pi6", &fib6_nh->fib_nh_gw6);
	} else {
		seq_puts(seq, "00000000000000000000000000000000");
	}

	dev = fib6_nh->fib_nh_dev;
	seq_printf(seq, " %08x %08x %08x %08x %8s\n",
		   rt->fib6_metric, refcount_read(&rt->fib6_ref), 0,
		   flags, dev ? dev->name : "");
	iter->w.leaf = NULL;
	return 0;
}