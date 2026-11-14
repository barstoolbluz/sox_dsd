/* Private Phase 05B binary64 decoder boundary, not part of the public ABI.
 * The qualified public decoder owns all FIR/SRC/delay/tail arithmetic. */
#ifndef LSX_DSD_F64_DECODE_H
#define LSX_DSD_F64_DECODE_H
#include "sox_dsd.h"
#include <stdint.h>

typedef struct {
  sox_dsd_decoder_t *api;
  uint64_t native_seen, pcm_seen;
  uint64_t native_expected, pcm_expected;
  sox_dsd_status_t error;
  int length_known, finishing, finished;
} lsx_dsd_f64_decode;

sox_dsd_status_t lsx_dsd_f64_decode_init(lsx_dsd_f64_decode *d,
    const sox_dsd_decode_options_t *options, int length_known,
    uint64_t native_frames);
/* The input/output counts are in interleaved *frames*, not sample words.
 * Successful output stays binary64; no signed-32 conversion exists here. */
sox_dsd_status_t lsx_dsd_f64_decode_process(lsx_dsd_f64_decode *d,
    const sox_sample_t *in, size_t *native_frames, double *pcm,
    size_t *pcm_frames);
sox_dsd_status_t lsx_dsd_f64_decode_process_packed(lsx_dsd_f64_decode *d,
    const sox_dsd_packed_block_t *in, size_t start,
    size_t *native_frames, double *pcm, size_t *pcm_frames);
sox_dsd_status_t lsx_dsd_f64_decode_finish(lsx_dsd_f64_decode *d,
    double *pcm, size_t *pcm_frames);
void lsx_dsd_f64_decode_destroy(lsx_dsd_f64_decode *d);
#endif
