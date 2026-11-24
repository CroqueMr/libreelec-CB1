/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include <libavcodec/avcodec.h>
#include <libavcodec/bsf.h>
#include <libavformat/avformat.h>

/* Use real software-decoded pixels for the test in place of VAAPI surfaces. */
static int receive_enhancement(AVCodecContext *decoder, AVFrame *frame)
{
    int status = avcodec_receive_frame(decoder, frame);
    if (status == 0) {
        assert(frame->format == AV_PIX_FMT_YUV420P);
        frame->format = AV_PIX_FMT_VAAPI;
    }
    return status;
}
#define avcodec_receive_frame receive_enhancement
#include "dvbridge_fel.c"
#undef avcodec_receive_frame

struct track {
    AVFormatContext *format;
    AVBSFContext *annexb;
    AVPacket *packet;
    int stream;
};

static void open_track(struct track *track, const char *path)
{
    assert(avformat_open_input(&track->format, path, NULL, NULL) == 0);
    assert(avformat_find_stream_info(track->format, NULL) >= 0);
    track->stream = av_find_best_stream(track->format, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    assert(track->stream >= 0);
    AVStream *stream = track->format->streams[track->stream];
    assert(av_bsf_alloc(av_bsf_get_by_name("hevc_mp4toannexb"), &track->annexb) == 0);
    assert(avcodec_parameters_copy(track->annexb->par_in, stream->codecpar) == 0);
    track->annexb->time_base_in = stream->time_base;
    assert(av_bsf_init(track->annexb) == 0);
    track->packet = av_packet_alloc();
    assert(track->packet);
}

static int next_packet(struct track *track)
{
    av_packet_unref(track->packet);
    int status;
    while ((status = av_read_frame(track->format, track->packet)) >= 0) {
        if (track->packet->stream_index == track->stream) {
            assert(av_bsf_send_packet(track->annexb, track->packet) == 0);
            assert(av_bsf_receive_packet(track->annexb, track->packet) == 0);
            assert(track->packet->pts != AV_NOPTS_VALUE);
            return 0;
        }
        av_packet_unref(track->packet);
    }
    assert(status == AVERROR_EOF);
    return status;
}

static void close_track(struct track *track)
{
    av_packet_free(&track->packet);
    av_bsf_free(&track->annexb);
    avformat_close_input(&track->format);
}

static int emit_pairs(struct dvbridge_fel *fel, AVFrame **pending, unsigned *count, AVRational time_base)
{
    while (*count) {
        AVFrame *base = pending[0];
        AVFrame *enhancement = NULL;
        int status = dvbridge_fel_take(fel, base->pts, &enhancement);
        if (status <= 0)
            return status;
        if (status == 1) {
            assert(enhancement && enhancement->pts == base->pts);
            printf("%lld %d %d\n", (long long)av_rescale_q(base->pts, time_base, (AVRational){1, 24}),
                   base->data[0][0] - 16, enhancement->data[0][0] - 16);
        } else {
            assert(status == 2 && !enhancement);
        }
        av_frame_free(&enhancement);
        av_frame_free(&base);
        --*count;
        memmove(pending, pending + 1, *count * sizeof(*pending));
    }
    return 0;
}

static bool submit_pair(struct dvbridge_fel *fel, struct track *base, struct track *enhancement)
{
    if (!enhancement->annexb)
        return dvbridge_fel_submit(fel, base->packet);
    assert(next_packet(enhancement) == 0);
    AVRational clock = base->annexb->time_base_out;
    int64_t pts = av_rescale_q(enhancement->packet->pts, enhancement->annexb->time_base_out, clock);
    /* The independently timed control removes EL44 while preserving the other timestamps. */
    bool drop = av_rescale_q(pts, clock, (AVRational){1, 24}) == 44;
    const struct dvbridge_fel_source source = {
        .base_pts = base->packet->pts,
        .enhancement_pts = drop ? AV_NOPTS_VALUE : pts,
        .time_base = clock,
        .epoch = 1,
        .presentable = true,
    };
    return dvbridge_fel_submit_layers(fel, drop ? NULL : enhancement->packet, &source);
}

static bool replay(struct track *base, struct track *enhancement, struct dvbridge_fel *fel,
                   AVCodecContext *decoder)
{
    enum { MAX_PENDING = 32 };
    AVFrame *pending[MAX_PENDING];
    unsigned count = 0;
    AVRational clock = base->annexb->time_base_out;
    bool ok = false, final_packet = false, draining = false;
    while (!final_packet) {
        final_packet = next_packet(base) == AVERROR_EOF;
        assert(avcodec_send_packet(decoder, final_packet ? NULL : base->packet) == 0);
        if (!final_packet && !submit_pair(fel, base, enhancement))
            break;
        if (final_packet && enhancement->annexb)
            assert(next_packet(enhancement) == AVERROR_EOF);
        for (;;) {
            if (emit_pairs(fel, pending, &count, clock) < 0)
                goto done;
            AVFrame *frame = av_frame_alloc();
            assert(frame);
            int status = avcodec_receive_frame(decoder, frame);
            if (status == 0) {
                assert(count < MAX_PENDING && frame->pts != AV_NOPTS_VALUE);
                assert(frame->format == AV_PIX_FMT_YUV420P);
                pending[count++] = frame;
                continue;
            }
            av_frame_free(&frame);
            if (status == AVERROR(EAGAIN)) {
                assert(!final_packet);
                break;
            }
            assert(status == AVERROR_EOF && final_packet);
            if (draining) {
                assert(count == 0);
                ok = true;
                goto done;
            }
            if (!dvbridge_fel_drain(fel, NULL))
                goto done;
            draining = true;
        }
    }
done:
    while (count)
        av_frame_free(&pending[--count]);
    return ok;
}

int main(int argc, char **argv)
{
    assert(argc == 2 || argc == 3);
    struct track base = {0}, enhancement = {0};
    open_track(&base, argv[1]);
    if (argc == 3)
        open_track(&enhancement, argv[2]);
    struct dvbridge_fel *fel = dvbridge_fel_create_layers(
        base.annexb->par_out, enhancement.annexb ? enhancement.annexb->par_out : NULL,
        base.annexb->time_base_out);
    assert(fel);
    fel->decoder->get_format = avcodec_default_get_format;
    assert(avcodec_open2(fel->decoder, fel->decoder->codec, NULL) == 0);
    fel->opened = true;
    const AVCodec *codec = avcodec_find_decoder(AV_CODEC_ID_HEVC);
    AVCodecContext *decoder = avcodec_alloc_context3(codec);
    assert(decoder && avcodec_parameters_to_context(decoder, base.annexb->par_out) == 0);
    decoder->thread_count = 1;
    decoder->pkt_timebase = base.annexb->time_base_out;
    assert(avcodec_open2(decoder, codec, NULL) == 0);
    bool ok = replay(&base, &enhancement, fel, decoder);
    avcodec_free_context(&decoder);
    dvbridge_fel_destroy(fel);
    close_track(&enhancement);
    close_track(&base);
    return ok ? 0 : 10;
}
