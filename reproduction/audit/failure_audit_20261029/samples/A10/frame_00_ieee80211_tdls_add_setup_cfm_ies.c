static void
ieee80211_tdls_add_setup_cfm_ies(struct ieee80211_link_data *link,
				 struct sk_buff *skb, const u8 *peer,
				 bool initiator, const u8 *extra_ies,
				 size_t extra_ies_len)
{
	struct ieee80211_sub_if_data *sdata = link->sdata;
	struct ieee80211_local *local = sdata->local;
	size_t offset = 0, noffset;
	struct sta_info *sta, *ap_sta;
	struct ieee80211_supported_band *sband;
	u8 *pos;

	sband = ieee80211_get_link_sband(link);
	if (WARN_ON_ONCE(!sband))
		return;

	sta = sta_info_get(sdata, peer);
	ap_sta = sta_info_get(sdata, sdata->vif.cfg.ap_addr);

	if (WARN_ON_ONCE(!sta || !ap_sta))
		return;

	sta->tdls_chandef = link->conf->chanreq.oper;

	/* add any custom IEs that go before the QoS IE */
	if (extra_ies_len) {
		static const u8 before_qos[] = {
			WLAN_EID_RSN,
		};
		noffset = ieee80211_ie_split(extra_ies, extra_ies_len,
					     before_qos,
					     ARRAY_SIZE(before_qos),
					     offset);
		skb_put_data(skb, extra_ies + offset, noffset - offset);
		offset = noffset;
	}

	/* add the QoS param IE if both the peer and we support it */
	if (local->hw.queues >= IEEE80211_NUM_ACS && sta->sta.wme)
		ieee80211_tdls_add_wmm_param_ie(sdata, skb);

	/* add any custom IEs that go before HT operation */
	if (extra_ies_len) {
		static const u8 before_ht_op[] = {
			WLAN_EID_RSN,
			WLAN_EID_QOS_CAPA,
			WLAN_EID_FAST_BSS_TRANSITION,
			WLAN_EID_TIMEOUT_INTERVAL,
		};
		noffset = ieee80211_ie_split(extra_ies, extra_ies_len,
					     before_ht_op,
					     ARRAY_SIZE(before_ht_op),
					     offset);
		skb_put_data(skb, extra_ies + offset, noffset - offset);
		offset = noffset;
	}

	/*
	 * if HT support is only added in TDLS, we need an HT-operation IE.
	 * add the IE as required by IEEE802.11-2012 9.23.3.2.
	 */
	if (!ap_sta->sta.deflink.ht_cap.ht_supported && sta->sta.deflink.ht_cap.ht_supported) {
		u16 prot = IEEE80211_HT_OP_MODE_PROTECTION_NONHT_MIXED |
			   IEEE80211_HT_OP_MODE_NON_GF_STA_PRSNT |
			   IEEE80211_HT_OP_MODE_NON_HT_STA_PRSNT;

		pos = skb_put(skb, 2 + sizeof(struct ieee80211_ht_operation));
		ieee80211_ie_build_ht_oper(pos, &sta->sta.deflink.ht_cap,
					   &link->conf->chanreq.oper, prot,
					   true);
	}

	ieee80211_tdls_add_link_ie(link, skb, peer, initiator);

	/* only include VHT-operation if not on the 2.4GHz band */
	if (sband->band != NL80211_BAND_2GHZ &&
	    sta->sta.deflink.vht_cap.vht_supported) {
		/*
		 * if both peers support WIDER_BW, we can expand the chandef to
		 * a wider compatible one, up to 80MHz
		 */
		if (test_sta_flag(sta, WLAN_STA_TDLS_WIDER_BW))
			ieee80211_tdls_chandef_vht_upgrade(sdata, sta);

		pos = skb_put(skb, 2 + sizeof(struct ieee80211_vht_operation));
		ieee80211_ie_build_vht_oper(pos, &sta->sta.deflink.vht_cap,
					    &sta->tdls_chandef);
	}

	/* add any remaining IEs */
	if (extra_ies_len) {
		noffset = extra_ies_len;
		skb_put_data(skb, extra_ies + offset, noffset - offset);
	}
}