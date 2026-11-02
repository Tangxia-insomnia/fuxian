static int __ip6_append_data(struct sock *sk,
			     struct sk_buff_head *queue,
			     struct inet_cork_full *cork_full,
			     struct inet6_cork *v6_cork,
			     struct page_frag *pfrag,
			     int getfrag(void *from, char *to, int offset,
					 int len, int odd, struct sk_buff *skb),
			     void *from, size_t length, int transhdrlen,
			     unsigned int flags, struct ipcm6_cookie *ipc6)
{
	struct sk_buff *skb, *skb_prev = NULL;
	struct inet_cork *cork = &cork_full->base;
	struct flowi6 *fl6 = &cork_full->fl.u.ip6;
	unsigned int maxfraglen, fragheaderlen, mtu, orig_mtu, pmtu;
	struct ubuf_info *uarg = NULL;
	int exthdrlen = 0;
	int dst_exthdrlen = 0;
	int hh_len;
	int copy;
	int err;
	int offset = 0;
	bool zc = false;
	u32 tskey = 0;
	struct rt6_info *rt = dst_rt6_info(cork->dst);
	bool paged, hold_tskey, extra_uref = false;
	struct ipv6_txoptions *opt = v6_cork->opt;
	int csummode = CHECKSUM_NONE;
	unsigned int maxnonfragsize, headersize;
	unsigned int wmem_alloc_delta = 0;

	skb = skb_peek_tail(queue);
	if (!skb) {
		exthdrlen = opt ? opt->opt_flen : 0;
		dst_exthdrlen = rt->dst.header_len - rt->rt6i_nfheader_len;
	}

	paged = !!cork->gso_size;
	mtu = cork->gso_size ? IP6_MAX_MTU : cork->fragsize;
	orig_mtu = mtu;

	hh_len = LL_RESERVED_SPACE(rt->dst.dev);

	fragheaderlen = sizeof(struct ipv6hdr) + rt->rt6i_nfheader_len +
			(opt ? opt->opt_nflen : 0);

	headersize = sizeof(struct ipv6hdr) +
		     (opt ? opt->opt_flen + opt->opt_nflen : 0) +
		     rt->rt6i_nfheader_len;

	if (mtu <= fragheaderlen ||
	    ((mtu - fragheaderlen) & ~7) + fragheaderlen <= sizeof(struct frag_hdr))
		goto emsgsize;

	maxfraglen = ((mtu - fragheaderlen) & ~7) + fragheaderlen -
		     sizeof(struct frag_hdr);

	/* as per RFC 7112 section 5, the entire IPv6 Header Chain must fit
	 * the first fragment
	 */
	if (headersize + transhdrlen > mtu)
		goto emsgsize;

	if (cork->length + length > mtu - headersize && ipc6->dontfrag &&
	    (sk->sk_protocol == IPPROTO_UDP ||
	     sk->sk_protocol == IPPROTO_ICMPV6 ||
	     sk->sk_protocol == IPPROTO_RAW)) {
		ipv6_local_rxpmtu(sk, fl6, mtu - headersize +
				sizeof(struct ipv6hdr));
		goto emsgsize;
	}

	if (ip6_sk_ignore_df(sk))
		maxnonfragsize = sizeof(struct ipv6hdr) + IPV6_MAXPLEN;
	else
		maxnonfragsize = mtu;

	if (cork->length + length > maxnonfragsize - headersize) {
emsgsize:
		pmtu = max_t(int, mtu - headersize + sizeof(struct ipv6hdr), 0);
		ipv6_local_error(sk, EMSGSIZE, fl6, pmtu);
		return -EMSGSIZE;
	}

	/* CHECKSUM_PARTIAL only with no extension headers and when
	 * we are not going to fragment
	 */
	if (transhdrlen && sk->sk_protocol == IPPROTO_UDP &&
	    headersize == sizeof(struct ipv6hdr) &&
	    length <= mtu - headersize &&
	    (!(flags & MSG_MORE) || cork->gso_size) &&
	    rt->dst.dev->features & (NETIF_F_IPV6_CSUM | NETIF_F_HW_CSUM))
		csummode = CHECKSUM_PARTIAL;

	if ((flags & MSG_ZEROCOPY) && length) {
		struct msghdr *msg = from;

		if (getfrag == ip_generic_getfrag && msg->msg_ubuf) {
			if (skb_zcopy(skb) && msg->msg_ubuf != skb_zcopy(skb))
				return -EINVAL;

			/* Leave uarg NULL if can't zerocopy, callers should
			 * be able to handle it.
			 */
			if ((rt->dst.dev->features & NETIF_F_SG) &&
			    csummode == CHECKSUM_PARTIAL) {
				paged = true;
				zc = true;
				uarg = msg->msg_ubuf;
			}
		} else if (sock_flag(sk, SOCK_ZEROCOPY)) {
			uarg = msg_zerocopy_realloc(sk, length, skb_zcopy(skb));
			if (!uarg)
				return -ENOBUFS;
			extra_uref = !skb_zcopy(skb);	/* only ref on new uarg */
			if (rt->dst.dev->features & NETIF_F_SG &&
			    csummode == CHECKSUM_PARTIAL) {
				paged = true;
				zc = true;
			} else {
				uarg_to_msgzc(uarg)->zerocopy = 0;
				skb_zcopy_set(skb, uarg, &extra_uref);
			}
		}
	} else if ((flags & MSG_SPLICE_PAGES) && length) {
		if (inet_test_bit(HDRINCL, sk))
			return -EPERM;
		if (rt->dst.dev->features & NETIF_F_SG &&
		    getfrag == ip_generic_getfrag)
			/* We need an empty buffer to attach stuff to */
			paged = true;
		else
			flags &= ~MSG_SPLICE_PAGES;
	}

	hold_tskey = cork->tx_flags & SKBTX_ANY_TSTAMP &&
		     READ_ONCE(sk->sk_tsflags) & SOF_TIMESTAMPING_OPT_ID;
	if (hold_tskey)
		tskey = atomic_inc_return(&sk->sk_tskey) - 1;

	/*
	 * Let's try using as much space as possible.
	 * Use MTU if total length of the message fits into the MTU.
	 * Otherwise, we need to reserve fragment header and
	 * fragment alignment (= 8-15 octects, in total).
	 *
	 * Note that we may need to "move" the data from the tail
	 * of the buffer to the new fragment when we split
	 * the message.
	 *
	 * FIXME: It may be fragmented into multiple chunks
	 *        at once if non-fragmentable extension headers
	 *        are too large.
	 * --yoshfuji
	 */

	cork->length += length;
	if (!skb)
		goto alloc_new_skb;

	while (length > 0) {
		/* Check if the remaining data fits into current packet. */
		copy = (cork->length <= mtu ? mtu : maxfraglen) - skb->len;
		if (copy < length)
			copy = maxfraglen - skb->len;

		if (copy <= 0) {
			char *data;
			unsigned int datalen;
			unsigned int fraglen;
			unsigned int fraggap;
			unsigned int alloclen, alloc_extra;
			unsigned int pagedlen;
alloc_new_skb:
			/* There's no room in the current skb */
			if (skb)
				fraggap = skb->len - maxfraglen;
			else
				fraggap = 0;
			/* update mtu and maxfraglen if necessary */
			if (!skb || !skb_prev)
				ip6_append_data_mtu(&mtu, &maxfraglen,
						    fragheaderlen, skb, rt,
						    orig_mtu);

			skb_prev = skb;

			/*
			 * If remaining data exceeds the mtu,
			 * we know we need more fragment(s).
			 */
			datalen = length + fraggap;

			if (datalen > (cork->length <= mtu ? mtu : maxfraglen) - fragheaderlen)
				datalen = maxfraglen - fragheaderlen - rt->dst.trailer_len;
			fraglen = datalen + fragheaderlen;
			pagedlen = 0;

			alloc_extra = hh_len;
			alloc_extra += dst_exthdrlen;
			alloc_extra += rt->dst.trailer_len;

			/* We just reserve space for fragment header.
			 * Note: this may be overallocation if the message
			 * (without MSG_MORE) fits into the MTU.
			 */
			alloc_extra += sizeof(struct frag_hdr);

			if ((flags & MSG_MORE) &&
			    !(rt->dst.dev->features&NETIF_F_SG))
				alloclen = mtu;
			else if (!paged &&
				 (fraglen + alloc_extra < SKB_MAX_ALLOC ||
				  !(rt->dst.dev->features & NETIF_F_SG)))
				alloclen = fraglen;
			else {
				alloclen = fragheaderlen + transhdrlen;
				pagedlen = datalen - transhdrlen;
			}
			alloclen += alloc_extra;

			if (datalen != length + fraggap) {
				/*
				 * this is not the last fragment, the trailer
				 * space is regarded as data space.
				 */
				datalen += rt->dst.trailer_len;
			}

			fraglen = datalen + fragheaderlen;

			copy = datalen - transhdrlen - fraggap - pagedlen;
			/* [!] NOTE: copy may be negative if pagedlen>0
			 * because then the equation may reduces to -fraggap.
			 */
			if (copy < 0 && !(flags & MSG_SPLICE_PAGES)) {
				err = -EINVAL;
				goto error;
			}
			if (transhdrlen) {
				skb = sock_alloc_send_skb(sk, alloclen,
						(flags & MSG_DONTWAIT), &err);
			} else {
				skb = NULL;
				if (refcount_read(&sk->sk_wmem_alloc) + wmem_alloc_delta <=
				    2 * sk->sk_sndbuf)
					skb = alloc_skb(alloclen,
							sk->sk_allocation);
				if (unlikely(!skb))
					err = -ENOBUFS;
			}
			if (!skb)
				goto error;
			/*
			 *	Fill in the control structures
			 */
			skb->protocol = htons(ETH_P_IPV6);
			skb->ip_summed = csummode;
			skb->csum = 0;
			/* reserve for fragmentation and ipsec header */
			skb_reserve(skb, hh_len + sizeof(struct frag_hdr) +
				    dst_exthdrlen);

			/*
			 *	Find where to start putting bytes
			 */
			data = skb_put(skb, fraglen - pagedlen);
			skb_set_network_header(skb, exthdrlen);
			data += fragheaderlen;
			skb->transport_header = (skb->network_header +
						 fragheaderlen);
			if (fraggap) {
				skb->csum = skb_copy_and_csum_bits(
					skb_prev, maxfraglen,
					data + transhdrlen, fraggap);
				skb_prev->csum = csum_sub(skb_prev->csum,
							  skb->csum);
				data += fraggap;
				pskb_trim_unique(skb_prev, maxfraglen);
			}
			if (copy > 0 &&
			    getfrag(from, data + transhdrlen, offset,
				    copy, fraggap, skb) < 0) {
				err = -EFAULT;
				kfree_skb(skb);
				goto error;
			} else if (flags & MSG_SPLICE_PAGES) {
				copy = 0;
			}

			offset += copy;
			length -= copy + transhdrlen;
			transhdrlen = 0;
			exthdrlen = 0;
			dst_exthdrlen = 0;

			/* Only the initial fragment is time stamped */
			skb_shinfo(skb)->tx_flags = cork->tx_flags;
			cork->tx_flags = 0;
			skb_shinfo(skb)->tskey = tskey;
			tskey = 0;
			skb_zcopy_set(skb, uarg, &extra_uref);

			if ((flags & MSG_CONFIRM) && !skb_prev)
				skb_set_dst_pending_confirm(skb, 1);

			/*
			 * Put the packet on the pending queue
			 */
			if (!skb->destructor) {
				skb->destructor = sock_wfree;
				skb->sk = sk;
				wmem_alloc_delta += skb->truesize;
			}
			__skb_queue_tail(queue, skb);
			continue;
		}

		if (copy > length)
			copy = length;

		if (!(rt->dst.dev->features&NETIF_F_SG) &&
		    skb_tailroom(skb) >= copy) {
			unsigned int off;

			off = skb->len;
			if (getfrag(from, skb_put(skb, copy),
						offset, copy, off, skb) < 0) {
				__skb_trim(skb, off);
				err = -EFAULT;
				goto error;
			}
		} else if (flags & MSG_SPLICE_PAGES) {
			struct msghdr *msg = from;

			err = -EIO;
			if (WARN_ON_ONCE(copy > msg->msg_iter.count))
				goto error;

			err = skb_splice_from_iter(skb, &msg->msg_iter, copy,
						   sk->sk_allocation);
			if (err < 0)
				goto error;
			copy = err;
			wmem_alloc_delta += copy;
		} else if (!zc) {
			int i = skb_shinfo(skb)->nr_frags;

			err = -ENOMEM;
			if (!sk_page_frag_refill(sk, pfrag))
				goto error;

			skb_zcopy_downgrade_managed(skb);
			if (!skb_can_coalesce(skb, i, pfrag->page,
					      pfrag->offset)) {
				err = -EMSGSIZE;
				if (i == MAX_SKB_FRAGS)
					goto error;

				__skb_fill_page_desc(skb, i, pfrag->page,
						     pfrag->offset, 0);
				skb_shinfo(skb)->nr_frags = ++i;
				get_page(pfrag->page);
			}
			copy = min_t(int, copy, pfrag->size - pfrag->offset);
			if (getfrag(from,
				    page_address(pfrag->page) + pfrag->offset,
				    offset, copy, skb->len, skb) < 0)
				goto error_efault;

			pfrag->offset += copy;
			skb_frag_size_add(&skb_shinfo(skb)->frags[i - 1], copy);
			skb->len += copy;
			skb->data_len += copy;
			skb->truesize += copy;
			wmem_alloc_delta += copy;
		} else {
			err = skb_zerocopy_iter_dgram(skb, from, copy);
			if (err < 0)
				goto error;
		}
		offset += copy;
		length -= copy;
	}

	if (wmem_alloc_delta)
		refcount_add(wmem_alloc_delta, &sk->sk_wmem_alloc);
	return 0;

error_efault:
	err = -EFAULT;
error:
	net_zcopy_put_abort(uarg, extra_uref);
	cork->length -= length;
	IP6_INC_STATS(sock_net(sk), rt->rt6i_idev, IPSTATS_MIB_OUTDISCARDS);
	refcount_add(wmem_alloc_delta, &sk->sk_wmem_alloc);
	if (hold_tskey)
		atomic_dec(&sk->sk_tskey);
	return err;
}