void ieee80211_check_fast_rx(struct sta_info *sta)
{
	struct ieee80211_sub_if_data *sdata = sta->sdata;
	struct ieee80211_local *local = sdata->local;
	struct ieee80211_key *key;
	struct ieee80211_fast_rx fastrx = {
		.dev = sdata->dev,
		.vif_type = sdata->vif.type,
		.control_port_protocol = sdata->control_port_protocol,
	}, *old, *new = NULL;
	u32 offload_flags;
	bool set_offload = false;
	bool assign = false;
	bool offload;

	/* use sparse to check that we don't return without updating */
	__acquire(check_fast_rx);

	BUILD_BUG_ON(sizeof(fastrx.rfc1042_hdr) != sizeof(rfc1042_header));
	BUILD_BUG_ON(sizeof(fastrx.rfc1042_hdr) != ETH_ALEN);
	ether_addr_copy(fastrx.rfc1042_hdr, rfc1042_header);
	ether_addr_copy(fastrx.vif_addr, sdata->vif.addr);

	fastrx.uses_rss = ieee80211_hw_check(&local->hw, USES_RSS);

	/* fast-rx doesn't do reordering */
	if (ieee80211_hw_check(&local->hw, AMPDU_AGGREGATION) &&
	    !ieee80211_hw_check(&local->hw, SUPPORTS_REORDERING_BUFFER))
		goto clear;

	switch (sdata->vif.type) {
	case NL80211_IFTYPE_STATION:
		if (sta->sta.tdls) {
			fastrx.da_offs = offsetof(struct ieee80211_hdr, addr1);
			fastrx.sa_offs = offsetof(struct ieee80211_hdr, addr2);
			fastrx.expected_ds_bits = 0;
		} else {
			fastrx.da_offs = offsetof(struct ieee80211_hdr, addr1);
			fastrx.sa_offs = offsetof(struct ieee80211_hdr, addr3);
			fastrx.expected_ds_bits =
				cpu_to_le16(IEEE80211_FCTL_FROMDS);
		}

		if (sdata->u.mgd.use_4addr && !sta->sta.tdls) {
			fastrx.expected_ds_bits |=
				cpu_to_le16(IEEE80211_FCTL_TODS);
			fastrx.da_offs = offsetof(struct ieee80211_hdr, addr3);
			fastrx.sa_offs = offsetof(struct ieee80211_hdr, addr4);
		}

		if (!sdata->u.mgd.powersave)
			break;

		/* software powersave is a huge mess, avoid all of it */
		if (ieee80211_hw_check(&local->hw, PS_NULLFUNC_STACK))
			goto clear;
		if (ieee80211_hw_check(&local->hw, SUPPORTS_PS) &&
		    !ieee80211_hw_check(&local->hw, SUPPORTS_DYNAMIC_PS))
			goto clear;
		break;
	case NL80211_IFTYPE_AP_VLAN:
	case NL80211_IFTYPE_AP:
		/* parallel-rx requires this, at least with calls to
		 * ieee80211_sta_ps_transition()
		 */
		if (!ieee80211_hw_check(&local->hw, AP_LINK_PS))
			goto clear;
		fastrx.da_offs = offsetof(struct ieee80211_hdr, addr3);
		fastrx.sa_offs = offsetof(struct ieee80211_hdr, addr2);
		fastrx.expected_ds_bits = cpu_to_le16(IEEE80211_FCTL_TODS);

		fastrx.internal_forward =
			!(sdata->flags & IEEE80211_SDATA_DONT_BRIDGE_PACKETS) &&
			(sdata->vif.type != NL80211_IFTYPE_AP_VLAN ||
			 !sdata->u.vlan.sta);

		if (sdata->vif.type == NL80211_IFTYPE_AP_VLAN &&
		    sdata->u.vlan.sta) {
			fastrx.expected_ds_bits |=
				cpu_to_le16(IEEE80211_FCTL_FROMDS);
			fastrx.sa_offs = offsetof(struct ieee80211_hdr, addr4);
			fastrx.internal_forward = 0;
		}

		break;
	case NL80211_IFTYPE_MESH_POINT:
		fastrx.expected_ds_bits = cpu_to_le16(IEEE80211_FCTL_FROMDS |
						      IEEE80211_FCTL_TODS);
		fastrx.da_offs = offsetof(struct ieee80211_hdr, addr3);
		fastrx.sa_offs = offsetof(struct ieee80211_hdr, addr4);
		break;
	default:
		goto clear;
	}

	if (!test_sta_flag(sta, WLAN_STA_AUTHORIZED))
		goto clear;

	rcu_read_lock();
	key = rcu_dereference(sta->ptk[sta->ptk_idx]);
	if (!key)
		key = rcu_dereference(sdata->default_unicast_key);
	if (key) {
		switch (key->conf.cipher) {
		case WLAN_CIPHER_SUITE_TKIP:
			/* we don't want to deal with MMIC in fast-rx */
			goto clear_rcu;
		case WLAN_CIPHER_SUITE_CCMP:
		case WLAN_CIPHER_SUITE_CCMP_256:
		case WLAN_CIPHER_SUITE_GCMP:
		case WLAN_CIPHER_SUITE_GCMP_256:
			break;
		default:
			/* We also don't want to deal with
			 * WEP or cipher scheme.
			 */
			goto clear_rcu;
		}

		fastrx.key = true;
		fastrx.icv_len = key->conf.icv_len;
	}

	assign = true;
 clear_rcu:
	rcu_read_unlock();
 clear:
	__release(check_fast_rx);

	if (assign)
		new = kmemdup(&fastrx, sizeof(fastrx), GFP_KERNEL);

	offload_flags = get_bss_sdata(sdata)->vif.offload_flags;
	offload = offload_flags & IEEE80211_OFFLOAD_DECAP_ENABLED;

	if (assign && offload)
		set_offload = !test_and_set_sta_flag(sta, WLAN_STA_DECAP_OFFLOAD);
	else
		set_offload = test_and_clear_sta_flag(sta, WLAN_STA_DECAP_OFFLOAD);

	if (set_offload)
		drv_sta_set_decap_offload(local, sdata, &sta->sta, assign);

	spin_lock_bh(&sta->lock);
	old = rcu_dereference_protected(sta->fast_rx, true);
	rcu_assign_pointer(sta->fast_rx, new);
	spin_unlock_bh(&sta->lock);

	if (old)
		kfree_rcu(old, rcu_head);
}