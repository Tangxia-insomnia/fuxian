static void list_insert_sorted(QUIC_CFQ_ITEM_LIST *l, QUIC_CFQ_ITEM_EX *n,
                               int (*cmp)(const QUIC_CFQ_ITEM_EX *a,
                                          const QUIC_CFQ_ITEM_EX *b))
{
    QUIC_CFQ_ITEM_EX *p = l->head, *pprev = NULL;

    if (p == NULL) {
        l->head = l->tail = n;
        n->prev = n->next = NULL;
        return;
    }

    for (; p != NULL && cmp(p, n) < 0; pprev = p, p = p->next);

    if (p == NULL)
        list_insert_tail(l, n);
    else if (pprev == NULL)
        list_insert_head(l, n);
    else
        list_insert_after(l, pprev, n);
}