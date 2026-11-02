static inline void neigh_confirm(struct neighbour *n)
{
	if (n) {
		unsigned long now = jiffies;

		/* avoid dirtying neighbour */
		if (READ_ONCE(n->confirmed) != now)
			WRITE_ONCE(n->confirmed, now);
	}
}