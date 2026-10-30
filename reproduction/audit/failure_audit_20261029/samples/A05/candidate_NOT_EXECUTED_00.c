static void ieee80211_mgd_probe_ap_send(struct ieee80211_sub_if_data *sdata)
{
	struct ieee80211_if_managed *ifmgd = &sdata->u.mgd;
	u8 *dst = sdata->vif.cfg.ap_addr;
	u8 unicast_limit = max(1, max_probe_tries - 3);
	struct sta_info *sta;

	lockdep_assert_wiphy(sdata->local->hw.wiphy);

	if (WARN_ON(ieee80211_vif_is_mld(&sdata->vif)))
		return;

	/*
	 * Try sending broadcast probe requests for the last three
	 * probe requests after the first ones failed since some
	 * buggy APs only support broadcast probe requests.
	 */
	if (ifmgd->probe_send_count >= unicast_limit)
		dst = NULL;

	/*
	 * When the hardware reports an accurate Tx ACK status, it's
	 * better to send a nullfunc frame instead of a probe request,
	 * as it will kick us off the AP quickly if we aren't associated
	 * anymore. The timeout will be reset if the frame is ACKed by
	 * the AP.
	 */
	ifmgd->probe_send_count++;

	if (dst) {
		sta = sta_info_get(sdata, dst);
		if (!WARN_ON(!sta))
			ieee80211_check_fast_rx(sta);
	}

	if (ieee80211_hw_check(&sdata->local->hw, REPORTS_TX_ACK_STATUS)) {
		ifmgd->nullfunc_failed = false;
		ieee80211_send_nullfunc(sdata->local, sdata, false);
	} else {
		ieee80211_mlme_send_probe_req(sdata, sdata->vif.addr, dst,
					      sdata->vif.cfg.ssid,
					      sdata->vif.cfg.ssid_len,
					      sdata->deflink.conf->bss->channel);
	}

	ifmgd->probe_timeout = jiffies + msecs_to_jiffies(probe_wait_ms);
	run_again(sdata, ifmgd->probe_timeout);
}