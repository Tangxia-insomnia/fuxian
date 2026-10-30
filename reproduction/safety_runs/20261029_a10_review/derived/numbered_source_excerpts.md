# Historical source excerpts

Automated extraction only. Numbers are original file line numbers.

## net/mac80211/tdls.c

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `ecb95e3e463fced7cf9cf79e88d9e7c7e3d140c3d52560c45bbf5b49b28f5d4d`

```text
  12: #include <linux/ieee80211.h>
  13: #include <linux/log2.h>
  14: #include <net/cfg80211.h>
  15: #include <linux/rtnetlink.h>
  16: #include "ieee80211_i.h"
  17: #include "driver-ops.h"
  18: #include "rate.h"
  19: #include "wme.h"

 591: static void
 592: ieee80211_tdls_add_setup_cfm_ies(struct ieee80211_link_data *link,
 593: 				 struct sk_buff *skb, const u8 *peer,
 594: 				 bool initiator, const u8 *extra_ies,
 595: 				 size_t extra_ies_len)
 596: {
 597: 	struct ieee80211_sub_if_data *sdata = link->sdata;
 598: 	struct ieee80211_local *local = sdata->local;
 599: 	size_t offset = 0, noffset;
 600: 	struct sta_info *sta, *ap_sta;
 601: 	struct ieee80211_supported_band *sband;
 602: 	u8 *pos;
 603: 
 604: 	sband = ieee80211_get_link_sband(link);
 605: 	if (WARN_ON_ONCE(!sband))
 606: 		return;
 607: 
 608: 	sta = sta_info_get(sdata, peer);
 609: 	ap_sta = sta_info_get(sdata, sdata->vif.cfg.ap_addr);
 610: 
 611: 	if (WARN_ON_ONCE(!sta || !ap_sta))
 612: 		return;
 613: 
 614: 	sta->tdls_chandef = link->conf->chanreq.oper;
 615: 
 616: 	/* add any custom IEs that go before the QoS IE */
 617: 	if (extra_ies_len) {
 618: 		static const u8 before_qos[] = {
 619: 			WLAN_EID_RSN,
 620: 		};
 621: 		noffset = ieee80211_ie_split(extra_ies, extra_ies_len,
 622: 					     before_qos,
 623: 					     ARRAY_SIZE(before_qos),
 624: 					     offset);
 625: 		skb_put_data(skb, extra_ies + offset, noffset - offset);
 626: 		offset = noffset;
 627: 	}
 628: 
 629: 	/* add the QoS param IE if both the peer and we support it */
 630: 	if (local->hw.queues >= IEEE80211_NUM_ACS && sta->sta.wme)
 631: 		ieee80211_tdls_add_wmm_param_ie(sdata, skb);
 632: 
 633: 	/* add any custom IEs that go before HT operation */
 634: 	if (extra_ies_len) {
 635: 		static const u8 before_ht_op[] = {
 636: 			WLAN_EID_RSN,
 637: 			WLAN_EID_QOS_CAPA,
 638: 			WLAN_EID_FAST_BSS_TRANSITION,
 639: 			WLAN_EID_TIMEOUT_INTERVAL,
 640: 		};
 641: 		noffset = ieee80211_ie_split(extra_ies, extra_ies_len,
 642: 					     before_ht_op,
 643: 					     ARRAY_SIZE(before_ht_op),
 644: 					     offset);
 645: 		skb_put_data(skb, extra_ies + offset, noffset - offset);
 646: 		offset = noffset;
 647: 	}
 648: 
 649: 	/*
 650: 	 * if HT support is only added in TDLS, we need an HT-operation IE.
 651: 	 * add the IE as required by IEEE802.11-2012 9.23.3.2.
 652: 	 */
 653: 	if (!ap_sta->sta.deflink.ht_cap.ht_supported && sta->sta.deflink.ht_cap.ht_supported) {
 654: 		u16 prot = IEEE80211_HT_OP_MODE_PROTECTION_NONHT_MIXED |
 655: 			   IEEE80211_HT_OP_MODE_NON_GF_STA_PRSNT |
 656: 			   IEEE80211_HT_OP_MODE_NON_HT_STA_PRSNT;
 657: 
 658: 		pos = skb_put(skb, 2 + sizeof(struct ieee80211_ht_operation));
 659: 		ieee80211_ie_build_ht_oper(pos, &sta->sta.deflink.ht_cap,
 660: 					   &link->conf->chanreq.oper, prot,
 661: 					   true);
 662: 	}
 663: 
 664: 	ieee80211_tdls_add_link_ie(link, skb, peer, initiator);
 665: 
 666: 	/* only include VHT-operation if not on the 2.4GHz band */
 667: 	if (sband->band != NL80211_BAND_2GHZ &&
 668: 	    sta->sta.deflink.vht_cap.vht_supported) {
 669: 		/*
 670: 		 * if both peers support WIDER_BW, we can expand the chandef to
 671: 		 * a wider compatible one, up to 80MHz
 672: 		 */
 673: 		if (test_sta_flag(sta, WLAN_STA_TDLS_WIDER_BW))
 674: 			ieee80211_tdls_chandef_vht_upgrade(sdata, sta);
 675: 
 676: 		pos = skb_put(skb, 2 + sizeof(struct ieee80211_vht_operation));
 677: 		ieee80211_ie_build_vht_oper(pos, &sta->sta.deflink.vht_cap,
 678: 					    &sta->tdls_chandef);
 679: 	}
 680: 
 681: 	/* add any remaining IEs */
 682: 	if (extra_ies_len) {
 683: 		noffset = extra_ies_len;
 684: 		skb_put_data(skb, extra_ies + offset, noffset - offset);
 685: 	}
 686: }

 740: 
 741: static void ieee80211_tdls_add_ies(struct ieee80211_link_data *link,
 742: 				   struct sk_buff *skb, const u8 *peer,
 743: 				   u8 action_code, u16 status_code,
 744: 				   bool initiator, const u8 *extra_ies,
 745: 				   size_t extra_ies_len, u8 oper_class,
 746: 				   struct cfg80211_chan_def *chandef)
 747: {
 748: 	switch (action_code) {
 749: 	case WLAN_TDLS_SETUP_REQUEST:
 750: 	case WLAN_TDLS_SETUP_RESPONSE:
 751: 	case WLAN_PUB_ACTION_TDLS_DISCOVER_RES:
 752: 		if (status_code == 0)
 753: 			ieee80211_tdls_add_setup_start_ies(link,
 754: 							   skb, peer,
 755: 							   action_code,
 756: 							   initiator,
 757: 							   extra_ies,
 758: 							   extra_ies_len);
 759: 		break;
 760: 	case WLAN_TDLS_SETUP_CONFIRM:
 761: 		if (status_code == 0)
 762: 			ieee80211_tdls_add_setup_cfm_ies(link, skb, peer,
 763: 							 initiator, extra_ies,
 764: 							 extra_ies_len);
 765: 		break;
 766: 	case WLAN_TDLS_TEARDOWN:
 767: 	case WLAN_TDLS_DISCOVERY_REQUEST:
 768: 		if (extra_ies_len)
 769: 			skb_put_data(skb, extra_ies, extra_ies_len);
 770: 		if (status_code == 0 || action_code == WLAN_TDLS_TEARDOWN)
 771: 			ieee80211_tdls_add_link_ie(link, skb,
 772: 						   peer, initiator);
 773: 		break;
 774: 	case WLAN_TDLS_CHANNEL_SWITCH_REQUEST:
 775: 		ieee80211_tdls_add_chan_switch_req_ies(link, skb, peer,
 776: 						       initiator, extra_ies,
 777: 						       extra_ies_len,
 778: 						       oper_class, chandef);
 779: 		break;
 780: 	case WLAN_TDLS_CHANNEL_SWITCH_RESPONSE:

```

## net/mac80211/sta_info.c

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `8e44a353a7815c2fd871c51a1528f4674d90aaaa7a7d139eeda73fb8e1ecc577`

```text
 203: /* protected by RCU */
 204: struct sta_info *sta_info_get(struct ieee80211_sub_if_data *sdata,
 205: 			      const u8 *addr)
 206: {
 207: 	struct ieee80211_local *local = sdata->local;
 208: 	struct rhlist_head *tmp;
 209: 	struct sta_info *sta;
 210: 
 211: 	rcu_read_lock();
 212: 	for_each_sta_info(local, addr, sta, tmp) {
 213: 		if (sta->sdata == sdata) {
 214: 			rcu_read_unlock();
 215: 			/* this is safe as the caller must already hold
 216: 			 * another rcu read section or the mutex
 217: 			 */
 218: 			return sta;
 219: 		}
 220: 	}
 221: 	rcu_read_unlock();
 222: 	return NULL;
 223: }

```

## net/mac80211/sta_info.h

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `95fe68f9d3d94197072ad3aad86992569b14457581054b18389ae28cf74d1345`

```text
 650: struct sta_info {
 651: 	/* General information, mostly static */
 652: 	struct list_head list, free_list;
 653: 	struct rcu_head rcu_head;
 654: 	struct rhlist_head hash_node;
 655: 	u8 addr[ETH_ALEN];
 656: 	struct ieee80211_local *local;
 657: 	struct ieee80211_sub_if_data *sdata;
 658: 	struct ieee80211_key __rcu *ptk[NUM_DEFAULT_KEYS];
 659: 	u8 ptk_idx;
 660: 	struct rate_control_ref *rate_ctrl;

 714: 
 715: 	u8 reserved_tid;
 716: 	s8 amsdu_mesh_control;
 717: 
 718: 	struct cfg80211_chan_def tdls_chandef;
 719: 
 720: 	struct ieee80211_fragment_cache frags;

 817: /*
 818:  * Get a STA info, must be under RCU read lock.
 819:  */
 820: struct sta_info *sta_info_get(struct ieee80211_sub_if_data *sdata,
 821: 			      const u8 *addr);
 822: 

```

## net/mac80211/ieee80211_i.h

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `c7b41a6974ceb4d761a262cac41286c81fea210325f6052dc0cb573818b28f23`

```text
1022: struct ieee80211_link_data {
1023: 	struct ieee80211_sub_if_data *sdata;
1024: 	unsigned int link_id;

1067: 	struct ieee80211_tx_queue_params tx_conf[IEEE80211_NUM_ACS];
1068: 
1069: 	struct ieee80211_bss_conf *conf;

```

## include/net/mac80211.h

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `3cd92649b7239941cd728913474bb64a0c5e983d6cf6a0813451eb8774a9a0bb`

```text
  12: 
  13: #ifndef MAC80211_H
  14: #define MAC80211_H
  15: 
  16: #include <linux/bug.h>
  17: #include <linux/kernel.h>
  18: #include <linux/if_ether.h>
  19: #include <linux/skbuff.h>
  20: #include <linux/ieee80211.h>
  21: #include <linux/lockdep.h>
  22: #include <net/cfg80211.h>

 232: /**
 233:  * struct ieee80211_chan_req - A channel "request"
 234:  * @oper: channel definition to use for operation
 235:  * @ap: the channel definition of the AP, if any
 236:  *	(otherwise the chan member is %NULL)
 237:  */
 238: struct ieee80211_chan_req {
 239: 	struct cfg80211_chan_def oper;
 240: 	struct cfg80211_chan_def ap;
 241: };
 242: 
 243: /**
 244:  * struct ieee80211_chanctx_conf - channel context that vifs may be tuned to

 705: struct ieee80211_bss_conf {
 706: 	struct ieee80211_vif *vif;

 737: 	u32 cqm_rssi_hyst;
 738: 	s32 cqm_rssi_low;
 739: 	s32 cqm_rssi_high;
 740: 	struct ieee80211_chan_req chanreq;
 741: 	struct ieee80211_mu_group_data mu_group;
 742: 	bool qos;

```

## include/net/cfg80211.h

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `0c67e4bb718abb055e2bdb1ea88c254a91e62a2140b95e770cd96bcdac743ca2`

```text
 815:  * @punctured: mask of the punctured 20 MHz subchannels, with
 816:  *	bits turned on being disabled (punctured); numbered
 817:  *	from lower to higher frequency (like in the spec)
 818:  */
 819: struct cfg80211_chan_def {
 820: 	struct ieee80211_channel *chan;
 821: 	enum nl80211_chan_width width;
 822: 	u32 center_freq1;
 823: 	u32 center_freq2;
 824: 	struct ieee80211_edmg edmg;
 825: 	u16 freq1_offset;
 826: 	u16 punctured;
 827: };
 828: 
 829: /*
 830:  * cfg80211_bitrate_mask - masks for bitrate control
 831:  */
 832: struct cfg80211_bitrate_mask {
 833: 	struct {
 834: 		u32 legacy;
 835: 		u8 ht_mcs[IEEE80211_HT_MCS_MASK_LEN];
 836: 		u16 vht_mcs[NL80211_VHT_NSS_MAX];
 837: 		u16 he_mcs[NL80211_HE_NSS_MAX];
 838: 		enum nl80211_txrate_gi gi;
 839: 		enum nl80211_he_gi he_gi;

```

## include/asm-generic/bug.h

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `b93635af28401ed276db4c322161fb2ff5b9f43b2f50284df87d0ec4e6ead0b9`

```text
   1: /* SPDX-License-Identifier: GPL-2.0 */
   2: #ifndef _ASM_GENERIC_BUG_H
   3: #define _ASM_GENERIC_BUG_H
   4: 
   5: #include <linux/compiler.h>
   6: #include <linux/instrumentation.h>
   7: #include <linux/once_lite.h>
   8: 

  95: #ifndef __WARN_FLAGS
  96: #define __WARN()		__WARN_printf(TAINT_WARN, NULL)
  97: #define __WARN_printf(taint, arg...) do {				\
  98: 		instrumentation_begin();				\
  99: 		warn_slowpath_fmt(__FILE__, __LINE__, taint, arg);	\
 100: 		instrumentation_end();					\
 101: 	} while (0)
 102: #else
 103: #define __WARN()		__WARN_FLAGS(BUGFLAG_TAINT(TAINT_WARN))
 104: #define __WARN_printf(taint, arg...) do {				\
 105: 		instrumentation_begin();				\
 106: 		__warn_printk(arg);					\
 107: 		__WARN_FLAGS(BUGFLAG_NO_CUT_HERE | BUGFLAG_TAINT(taint));\
 108: 		instrumentation_end();					\
 109: 	} while (0)
 110: #define WARN_ON_ONCE(condition) ({				\
 111: 	int __ret_warn_on = !!(condition);			\
 112: 	if (unlikely(__ret_warn_on))				\
 113: 		__WARN_FLAGS(BUGFLAG_ONCE |			\
 114: 			     BUGFLAG_TAINT(TAINT_WARN));	\
 115: 	unlikely(__ret_warn_on);				\
 116: })
 117: #endif
 118: 
 119: /* used internally by panic.c */
 120: 
 121: #ifndef WARN_ON
 122: #define WARN_ON(condition) ({						\
 123: 	int __ret_warn_on = !!(condition);				\
 124: 	if (unlikely(__ret_warn_on))					\
 125: 		__WARN();						\
 126: 	unlikely(__ret_warn_on);					\
 127: })
 128: #endif

 146: #ifndef WARN_ON_ONCE
 147: #define WARN_ON_ONCE(condition)					\
 148: 	DO_ONCE_LITE_IF(condition, WARN_ON, 1)
 149: #endif
 150: 
 151: #define WARN_ONCE(condition, format...)				\
 152: 	DO_ONCE_LITE_IF(condition, WARN, 1, format)
 153: 
 154: #define WARN_TAINT_ONCE(condition, taint, format...)		\
 155: 	DO_ONCE_LITE_IF(condition, WARN_TAINT, 1, taint, format)
 156: 
 157: #else /* !CONFIG_BUG */
 158: #ifndef HAVE_ARCH_BUG
 159: #define BUG() do {		\
 160: 	do {} while (1);	\
 161: 	unreachable();		\
 162: } while (0)
 163: #endif
 164: 
 165: #ifndef HAVE_ARCH_BUG_ON
 166: #define BUG_ON(condition) do { if (unlikely(condition)) BUG(); } while (0)
 167: #endif
 168: 
 169: #ifndef HAVE_ARCH_WARN_ON
 170: #define WARN_ON(condition) ({						\
 171: 	int __ret_warn_on = !!(condition);				\
 172: 	unlikely(__ret_warn_on);					\
 173: })
 174: #endif
 175: 
 176: #ifndef WARN
 177: #define WARN(condition, format...) ({					\
 178: 	int __ret_warn_on = !!(condition);				\
 179: 	no_printk(format);						\
 180: 	unlikely(__ret_warn_on);					\
 181: })
 182: #endif
 183: 
 184: #define WARN_ON_ONCE(condition) WARN_ON(condition)
 185: #define WARN_ONCE(condition, format...) WARN(condition, format)
 186: #define WARN_TAINT(condition, taint, format...) WARN(condition, format)
 187: #define WARN_TAINT_ONCE(condition, taint, format...) WARN(condition, format)

```

## include/linux/once_lite.h

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `d170b54b2ed415db7b23068388cb7503985bd32e25a7c150c5ba7c8aa7e6a28e`

```text
  13: #define __ONCE_LITE_IF(condition)					\
  14: 	({								\
  15: 		static bool __section(".data.once") __already_done;	\
  16: 		bool __ret_cond = !!(condition);			\
  17: 		bool __ret_once = false;				\
  18: 									\
  19: 		if (unlikely(__ret_cond && !__already_done)) {		\
  20: 			__already_done = true;				\
  21: 			__ret_once = true;				\
  22: 		}							\
  23: 		unlikely(__ret_once);					\
  24: 	})
  25: 
  26: #define DO_ONCE_LITE_IF(condition, func, ...)				\
  27: 	({								\
  28: 		bool __ret_do_once = !!(condition);			\
  29: 									\
  30: 		if (__ONCE_LITE_IF(__ret_do_once))			\
  31: 			func(__VA_ARGS__);				\
  32: 									\
  33: 		unlikely(__ret_do_once);				\
  34: 	})

```

## include/linux/compiler.h

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `fe2503c4bf43395aefac4f34bab81603dda4de2c6d0143614741e186e8b0e47a`

```text
  17: #if defined(CONFIG_TRACE_BRANCH_PROFILING) \
  18:     && !defined(DISABLE_BRANCH_PROFILING) && !defined(__CHECKER__)
  19: #define likely_notrace(x)	__builtin_expect(!!(x), 1)
  20: #define unlikely_notrace(x)	__builtin_expect(!!(x), 0)
  21: 
  22: #define __branch_check__(x, expect, is_constant) ({			\
  23: 			long ______r;					\
  24: 			static struct ftrace_likely_data		\
  25: 				__aligned(4)				\
  26: 				__section("_ftrace_annotated_branch")	\
  27: 				______f = {				\
  28: 				.data.func = __func__,			\
  29: 				.data.file = __FILE__,			\
  30: 				.data.line = __LINE__,			\
  31: 			};						\
  32: 			______r = __builtin_expect(!!(x), expect);	\
  33: 			ftrace_likely_update(&______f, ______r,		\
  34: 					     expect, is_constant);	\
  35: 			______r;					\
  36: 		})
  37: 
  38: /*
  39:  * Using __builtin_constant_p(x) to ignore cases where the return
  40:  * value is always the same.  This idea is taken from a similar patch
  41:  * written by Daniel Walker.
  42:  */
  43: # ifndef likely
  44: #  define likely(x)	(__branch_check__(x, 1, __builtin_constant_p(x)))
  45: # endif
  46: # ifndef unlikely
  47: #  define unlikely(x)	(__branch_check__(x, 0, __builtin_constant_p(x)))
  48: # endif
  49: 
  50: #ifdef CONFIG_PROFILE_ALL_BRANCHES
  51: /*
  52:  * "Define 'is'", Bill Clinton
  53:  * "Define 'if'", Steven Rostedt
  54:  */
  55: #define if(cond, ...) if ( __trace_if_var( !!(cond , ## __VA_ARGS__) ) )
  56: 
  57: #define __trace_if_var(cond) (__builtin_constant_p(cond) ? (cond) : __trace_if_value(cond))
  58: 
  59: #define __trace_if_value(cond) ({			\
  60: 	static struct ftrace_branch_data		\
  61: 		__aligned(4)				\
  62: 		__section("_ftrace_branch")		\
  63: 		__if_trace = {				\
  64: 			.func = __func__,		\
  65: 			.file = __FILE__,		\
  66: 			.line = __LINE__,		\
  67: 		};					\
  68: 	(cond) ?					\
  69: 		(__if_trace.miss_hit[1]++,1) :		\
  70: 		(__if_trace.miss_hit[0]++,0);		\
  71: })
  72: 
  73: #endif /* CONFIG_PROFILE_ALL_BRANCHES */
  74: 
  75: #else
  76: # define likely(x)	__builtin_expect(!!(x), 1)
  77: # define unlikely(x)	__builtin_expect(!!(x), 0)
  78: # define likely_notrace(x)	likely(x)

```

## include/linux/bug.h

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `3ea0aa87ccf827f7896d092d49346d3e78dce21f8deef3c790648eb24bb82602`

```text
   1: /* SPDX-License-Identifier: GPL-2.0 */
   2: #ifndef _LINUX_BUG_H
   3: #define _LINUX_BUG_H
   4: 
   5: #include <asm/bug.h>
   6: #include <linux/compiler.h>
   7: #include <linux/build_bug.h>

```

## include/asm-generic/Kbuild

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `c7e76ef918b60b82c8a789e475e3df2e122b08f597432dbea10b76af6c1c4ecd`

```text
   1: # SPDX-License-Identifier: GPL-2.0
   2: #
   3: # asm headers that all architectures except um should have
   4: # (This file is not included when SRCARCH=um since UML borrows several
   5: # asm headers from the host architecture.)
   6: 
   7: mandatory-y += atomic.h
   8: mandatory-y += archrandom.h
   9: mandatory-y += barrier.h
  10: mandatory-y += bitops.h
  11: mandatory-y += bug.h
  12: mandatory-y += bugs.h

```

## scripts/Makefile.asm-generic

Commit: `9c5a72fbc90d829ffb761da64a73c23cd4e0503f`
SHA-256: `a7565c82d39dd8aade86cec008ef8d8468e02f07d8ca709f8ba8850b5eeca427`

```text
  17: # $(generic)/Kbuild lists mandatory-y. Exclude um since it is a special case.
  18: ifneq ($(SRCARCH),um)
  19: include $(srctree)/$(generic)/Kbuild
  20: endif
  21: 
  22: redundant := $(filter $(mandatory-y) $(generated-y), $(generic-y))
  23: redundant += $(foreach f, $(generic-y), $(if $(wildcard $(srctree)/$(src)/$(f)),$(f)))
  24: redundant := $(sort $(redundant))
  25: $(if $(redundant),\
  26: 	$(warning redundant generic-y found in $(src)/Kbuild: $(redundant)))
  27: 
  28: # If arch does not implement mandatory headers, fallback to asm-generic ones.
  29: mandatory-y := $(filter-out $(generated-y), $(mandatory-y))
  30: generic-y   += $(foreach f, $(mandatory-y), $(if $(wildcard $(srctree)/$(src)/$(f)),,$(f)))
  31: 

  40:       cmd_wrap = echo "\#include <asm-generic/$*.h>" > $@
  41: 
  42: quiet_cmd_remove = REMOVE  $(unwanted)
  43:       cmd_remove = rm -f $(unwanted)

```
