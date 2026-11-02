static struct fib6_info *ip6_route_info_create(struct fib6_config *cfg,
					      gfp_t gfp_flags,
					      struct netlink_ext_ack *extack)
{
	struct net *net = cfg->fc_nlinfo.nl_net;
	struct fib6_info *rt = NULL;
	struct nexthop *nh = NULL;
	struct fib6_table *table;
	struct fib6_nh *fib6_nh;
	int err = -EINVAL;
	int addr_type;

	/* RTF_PCPU is an internal flag; can not be set by userspace */
	if (cfg->fc_flags & RTF_PCPU) {
		NL_SET_ERR_MSG(extack, "Userspace can not set RTF_PCPU");
		goto out;
	}

	/* RTF_CACHE is an internal flag; can not be set by userspace */
	if (cfg->fc_flags & RTF_CACHE) {
		NL_SET_ERR_MSG(extack, "Userspace can not set RTF_CACHE");
		goto out;
	}

	if (cfg->fc_type > RTN_MAX) {
		NL_SET_ERR_MSG(extack, "Invalid route type");
		goto out;
	}

	if (cfg->fc_dst_len > 128) {
		NL_SET_ERR_MSG(extack, "Invalid prefix length");
		goto out;
	}
	if (cfg->fc_src_len > 128) {
		NL_SET_ERR_MSG(extack, "Invalid source address length");
		goto out;
	}
#ifndef CONFIG_IPV6_SUBTREES
	if (cfg->fc_src_len) {
		NL_SET_ERR_MSG(extack,
			       "Specifying source address requires IPV6_SUBTREES to be enabled");
		goto out;
	}
#endif
	if (cfg->fc_nh_id) {
		nh = nexthop_find_by_id(net, cfg->fc_nh_id);
		if (!nh) {
			NL_SET_ERR_MSG(extack, "Nexthop id does not exist");
			goto out;
		}
		err = fib6_check_nexthop(nh, cfg, extack);
		if (err)
			goto out;
	}

	err = -ENOBUFS;
	if (cfg->fc_nlinfo.nlh &&
	    !(cfg->fc_nlinfo.nlh->nlmsg_flags & NLM_F_CREATE)) {
		table = fib6_get_table(net, cfg->fc_table);
		if (!table) {
			pr_warn("NLM_F_CREATE should be specified when creating new route\n");
			table = fib6_new_table(net, cfg->fc_table);
		}
	} else {
		table = fib6_new_table(net, cfg->fc_table);
	}

	if (!table)
		goto out;

	err = -ENOMEM;
	rt = fib6_info_alloc(gfp_flags, !nh);
	if (!rt)
		goto out;

	rt->fib6_metrics = ip_fib_metrics_init(net, cfg->fc_mx, cfg->fc_mx_len,
					       extack);
	if (IS_ERR(rt->fib6_metrics)) {
		err = PTR_ERR(rt->fib6_metrics);
		/* Do not leave garbage there. */
		rt->fib6_metrics = (struct dst_metrics *)&dst_default_metrics;
		goto out_free;
	}

	if (cfg->fc_flags & RTF_ADDRCONF)
		rt->dst_nocount = true;

	if (cfg->fc_flags & RTF_EXPIRES)
		fib6_set_expires(rt, jiffies +
				clock_t_to_jiffies(cfg->fc_expires));

	if (cfg->fc_protocol == RTPROT_UNSPEC)
		cfg->fc_protocol = RTPROT_BOOT;
	rt->fib6_protocol = cfg->fc_protocol;

	rt->fib6_table = table;
	rt->fib6_metric = cfg->fc_metric;
	rt->fib6_type = cfg->fc_type ? : RTN_UNICAST;
	rt->fib6_flags = cfg->fc_flags & ~RTF_GATEWAY;

	ipv6_addr_prefix(&rt->fib6_dst.addr, &cfg->fc_dst, cfg->fc_dst_len);
	rt->fib6_dst.plen = cfg->fc_dst_len;

#ifdef CONFIG_IPV6_SUBTREES
	ipv6_addr_prefix(&rt->fib6_src.addr, &cfg->fc_src, cfg->fc_src_len);
	rt->fib6_src.plen = cfg->fc_src_len;
#endif
	if (nh) {
		if (rt->fib6_src.plen) {
			NL_SET_ERR_MSG(extack, "Nexthops can not be used with source routing");
			goto out_free;
		}
		if (!nexthop_get(nh)) {
			NL_SET_ERR_MSG(extack, "Nexthop has been deleted");
			goto out_free;
		}
		rt->nh = nh;
		fib6_nh = nexthop_fib6_nh(rt->nh);
	} else {
		err = fib6_nh_init(net, rt->fib6_nh, cfg, gfp_flags, extack);
		if (err)
			goto out;

		fib6_nh = rt->fib6_nh;

		/* We cannot add true routes via loopback here, they would
		 * result in kernel looping; promote them to reject routes
		 */
		addr_type = ipv6_addr_type(&cfg->fc_dst);
		if (fib6_is_reject(cfg->fc_flags, rt->fib6_nh->fib_nh_dev,
				   addr_type))
			rt->fib6_flags = RTF_REJECT | RTF_NONEXTHOP;
	}

	if (!ipv6_addr_any(&cfg->fc_prefsrc)) {
		struct net_device *dev = fib6_nh->fib_nh_dev;

		if (!ipv6_chk_addr(net, &cfg->fc_prefsrc, dev, 0)) {
			NL_SET_ERR_MSG(extack, "Invalid source address");
			err = -EINVAL;
			goto out;
		}
		rt->fib6_prefsrc.addr = cfg->fc_prefsrc;
		rt->fib6_prefsrc.plen = 128;
	} else
		rt->fib6_prefsrc.plen = 0;

	return rt;
out:
	fib6_info_release(rt);
	return ERR_PTR(err);
out_free:
	ip_fib_metrics_put(rt->fib6_metrics);
	kfree(rt);
	return ERR_PTR(err);
}