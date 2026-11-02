static int epic_decode_from_cache(ePICContext *dc, uint32_t W, uint32_t *pPix)
{
    ePICPixListElem *list, *prev = NULL;
    ePICPixHashElem *hash_elem = epic_hash_find(&dc->hash, W);

    if (!hash_elem || !hash_elem->list)
        return 0;

    list = hash_elem->list;
    while (list) {
        if (!is_pixel_on_stack(dc, list->pixel)) {
            if (ff_els_decode_bit(&dc->els_ctx, &list->rung)) {
                *pPix = list->pixel;
                if (list != hash_elem->list) {
                    prev->next      = list->next;
                    list->next      = hash_elem->list;
                    hash_elem->list = list;
                }
                return 1;
            }
            dc->stack[dc->stack_pos++ & EPIC_PIX_STACK_MAX] = list->pixel;
        }
        prev = list;
        list = list->next;
    }

    return 0;
}