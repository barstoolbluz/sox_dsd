/* Private fixed-shape PCM64 coordinator; no public libSoX effect ABI. */
#ifndef LSX_DSD_F64_H
#define LSX_DSD_F64_H
#include "sox_ng.h"
#include "pcm_f64.h"
#include "dsd_f64_decode.h"
#include "sox_dsd.h"
typedef enum {
  LSX_PRECISION_AUTO = 0, LSX_PRECISION_64, LSX_PRECISION_32
} lsx_precision_policy;

/* Query only getopts-populated state; never start the historical gain effect. */
int lsx_gain_plain_fixed(const sox_effect_t *effect, double *factor);

typedef struct {
  pcm_f64_format format;
  pcm_f64_failure failure;
  uint64_t input_frames, output_frames;
  double *gains;               /* one factor per operation, in source order */
  size_t gain_count;
  unsigned role_map[64];       /* output slot -> input slot */
  bool transformed, permuted, finished;
} lsx_dsd_f64_stream;

/* The first factor, when present, is the resolved input volume/replay gain.
 * The caller supplies all gain occurrences separately; identity factors are
 * retained for semantic accounting but do not multiply signed zero. */
pcm_f64_status lsx_dsd_f64_init(lsx_dsd_f64_stream *stream,
    const pcm_f64_format *format, const double *gains, size_t gain_count,
    const unsigned *role_map);
/* Borrowed, immutable input and caller-owned output: up to min(in,out) frames
 * per invocation. NEED_OUTPUT may accompany produced frames. No data is
 * buffered between calls; zero producer output is never interpreted as EOF. */
pcm_f64_progress lsx_dsd_f64_process(lsx_dsd_f64_stream *stream,
    pcm_f64_input input, pcm_f64_output output);
/* Explicit EOF, including when output capacity is zero. No tail in PCM-only
 * Phase 05A. Subsequent finish calls return DONE; process after finish fails. */
pcm_f64_progress lsx_dsd_f64_finish(lsx_dsd_f64_stream *stream,
    pcm_f64_output output);
void lsx_dsd_f64_destroy(lsx_dsd_f64_stream *stream);

/* Phase 06A: bounded, channel-synchronous, direct PCM64 -> composite DSD.
 * The caller owns finite, source-rate interleaved double frames. The output
 * consists solely of interleaved one-bit sign symbols for DSF/DFF writers.
 * No PCM sample traverses sox_sample_t, even transiently. */
typedef struct lsx_pcmdsd lsx_pcmdsd;
#define LSX_DSD_F64_ENCODE_INPUT 256u
#define LSX_DSD_F64_ENCODE_OUTPUT 512u
typedef struct {
  lsx_pcmdsd *channel[64];
  double *planar;
  sox_sample_t *bits;
  uint32_t source_hz, native_hz;
  unsigned channels;
  uint64_t source_frames, encoded_frames;
  bool finishing, done;
  sox_dsd_status_t error;
} lsx_dsd_f64_encoder;

sox_dsd_status_t lsx_dsd_f64_encode_init(lsx_dsd_f64_encoder *encoder,
    uint32_t source_hz, uint32_t native_hz, unsigned channels,
    double reference_scale, double attenuation, bool warn_and_clip);
sox_dsd_status_t lsx_dsd_f64_encode_process(lsx_dsd_f64_encoder *encoder,
    const double *interleaved_pcm, size_t *input_frames,
    sox_sample_t *interleaved_dsd, size_t *output_frames);
sox_dsd_status_t lsx_dsd_f64_encode_finish(lsx_dsd_f64_encoder *encoder,
    sox_sample_t *interleaved_dsd, size_t *output_frames);
const lsx_pcmdsd *lsx_dsd_f64_encode_channel(const lsx_dsd_f64_encoder *,
    unsigned channel);
/* Test-only admission instrumentation, never enabled in normal encoding. */
typedef void (*lsx_dsd_f64_admission_observer)(void *opaque,
    const double *words, size_t frames);
void lsx_dsd_f64_encode_observe_admitted(lsx_dsd_f64_encoder *,
    unsigned channel, lsx_dsd_f64_admission_observer, void *opaque);
void lsx_dsd_f64_encode_destroy(lsx_dsd_f64_encoder *encoder);

/* Phase 06B: one qualified decoder, bounded PCM64 staging FIFO, ordered
 * operations and one qualified encoder. FIFO capacity is an implementation
 * frame budget (1..256), not a native DSD-bit count. Input and output counts
 * are independently tracked by the unchanged public DSP adapters. */
#define LSX_DSD_F64_TRANSCODE_FIFO_MAX LSX_DSD_F64_ENCODE_INPUT
typedef struct {
  lsx_dsd_f64_decode decoder;
  lsx_dsd_f64_stream pcm;
  lsx_dsd_f64_encoder encoder;
  double *decoded, *fifo;
  size_t fifo_capacity, fifo_at, fifo_frames;
  /* Optional read-only test observation at the exact PCM64 encoder input.
   * Normal CLI conversions leave the callback NULL and incur no I/O. */
  void (*pcm_observer)(void *, const double *, size_t, unsigned);
  void *pcm_observer_opaque;
  double adapter_volume, decoder_peak;
  uint64_t decoder_nominal_clips;
  sox_dsd_status_t error;
  bool clip_error, finishing, decoder_done, pcm_done, done;
} lsx_dsd_f64_transcode;

sox_dsd_status_t lsx_dsd_f64_transcode_init(lsx_dsd_f64_transcode *,
    const sox_dsd_decode_options_t *decoder_options,
    bool native_length_known, uint64_t input_native_frames,
    const double *ordered_gains, size_t gain_count,
    const unsigned *output_to_input_map, uint32_t output_native_hz,
    double encoder_reference_scale, double encoder_attenuation,
    bool warn_and_clip, bool adapter_clip_error, size_t fifo_capacity);
/* The native source is either expanded interleaved signs or a packed block;
 * packed_start indexes the first native-bit frame of the packed block. A
 * zero-frame call is not EOF. Returned counts are frames, not scalar words. */
sox_dsd_status_t lsx_dsd_f64_transcode_process(lsx_dsd_f64_transcode *,
    const sox_sample_t *expanded, const sox_dsd_packed_block_t *packed,
    size_t packed_start, size_t *native_frames,
    sox_sample_t *interleaved_bits, size_t *bit_frames);
void lsx_dsd_f64_transcode_observe_pcm(lsx_dsd_f64_transcode *,
    void (*observer)(void *, const double *, size_t, unsigned), void *opaque);
sox_dsd_status_t lsx_dsd_f64_transcode_finish(lsx_dsd_f64_transcode *,
    sox_sample_t *interleaved_bits, size_t *bit_frames);
void lsx_dsd_f64_transcode_destroy(lsx_dsd_f64_transcode *);
#endif
