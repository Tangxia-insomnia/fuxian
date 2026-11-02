static struct dwarf_cie *dwarf_lookup_cie(unsigned long cie_ptr)
{
	struct rb_node **rb_node = &cie_root.rb_node;
	struct dwarf_cie *cie = NULL;
	unsigned long flags;

	spin_lock_irqsave(&dwarf_cie_lock, flags);

	/*
	 * We've cached the last CIE we looked up because chances are
	 * that the FDE wants this CIE.
	 */
	if (cached_cie && cached_cie->cie_pointer == cie_ptr) {
		cie = cached_cie;
		goto out;
	}

	while (*rb_node) {
		struct dwarf_cie *cie_tmp;

		cie_tmp = rb_entry(*rb_node, struct dwarf_cie, node);
		BUG_ON(!cie_tmp);

		if (cie_ptr == cie_tmp->cie_pointer) {
			cie = cie_tmp;
			cached_cie = cie_tmp;
			goto out;
		} else {
			if (cie_ptr < cie_tmp->cie_pointer)
				rb_node = &(*rb_node)->rb_left;
			else
				rb_node = &(*rb_node)->rb_right;
		}
	}

out:
	spin_unlock_irqrestore(&dwarf_cie_lock, flags);
	return cie;
}