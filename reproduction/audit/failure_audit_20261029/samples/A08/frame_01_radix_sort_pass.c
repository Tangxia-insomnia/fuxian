static void radix_sort_pass(RCCMPEntry *dst, const RCCMPEntry *data,
                            int size, int buckets[NBUCKETS], int pass)
{
    int shift = pass * BUCKET_BITS;
    int i;
    for (i = 0; i < size; i++) {
        int v   = get_bucket(data[i].value, shift);
        int pos = buckets[v]++;
        dst[pos] = data[i];
    }
}