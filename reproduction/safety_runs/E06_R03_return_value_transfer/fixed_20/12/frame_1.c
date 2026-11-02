static void read_index(AVIOContext *pb, AVStream *st)
{
    uint64_t timestamp = 0;
    int i;
    for (i = 0; i < st->nb_frames; i++) {
        uint32_t pos  = avio_rb32(pb);
        uint32_t size = avio_rb32(pb);
        avio_skip(pb, 8);
        av_add_index_entry(st, pos, timestamp, size, 0, AVINDEX_KEYFRAME);
        if (st->codecpar->codec_type == AVMEDIA_TYPE_AUDIO) {
            timestamp += size / (st->codecpar->channels * 2);
        } else {
            timestamp++;
        }
    }
}