/* P06 private native-bit-to-intermediate-F64 reconstruction engine.
 * Unlike P07's public decoder, no arbitrary-ratio SRC or graph wiring exists. */
#ifndef LSX_DSD_DECODE_H
#define LSX_DSD_DECODE_H

#include "dsd.h"
#include "sox_dsd.h"
#include <stddef.h>
#include <stdint.h>

typedef struct lsx_dsd_reconstruction lsx_dsd_reconstruction;

typedef struct {
  uint32_t native_hz, intermediate_hz;
  unsigned channels, stages, factor;
  unsigned taps[8], phases[8];
  uint64_t delay_native_frames, discard_frames;
  size_t allocated_bytes; /* current owned heap storage, including alignment */
} lsx_dsd_reconstruction_info;

/* P06-P17 private mastering/wideband engine; P17 high-rate is experimental.
 * Input is interleaved canonical native bits: +/-SOX_SAMPLE_MAX.
 * Output is interleaved doubles in theoretical +/-1 native full-scale.
 * On entry frame counts are capacities; on return actual counts.
 * NEED_OUTPUT never consumes input if output capacity was zero.
 * BAD_ARGUMENT and NUMERIC_ERROR latch until destroy; repeated finish after
 * DONE returns DONE with zero frames.  Finish appends only numeric zeros.
 */
sox_dsd_status_t lsx_dsd_reconstruction_create(
    uint32_t native_hz, lsx_dsd_decode profile, unsigned channels,
    lsx_dsd_reconstruction **out);
/* Existing create is source/ABI stable. The internal variant carries the
 * caller's optional per-context override (ahead of environment selection). */
sox_dsd_status_t lsx_dsd_reconstruction_create_kernel(
    uint32_t native_hz, lsx_dsd_decode profile, unsigned channels,
    const char *kernel_fir, lsx_dsd_reconstruction **out);
/* Private read-only introspection for context-selection regression tests. */
const char *lsx_dsd_reconstruction_kernel_name(const lsx_dsd_reconstruction *);
const char *lsx_dsd_decoder_kernel_name(const sox_dsd_decoder_t *);
sox_dsd_status_t lsx_dsd_reconstruction_process(
    lsx_dsd_reconstruction *, const sox_sample_t *bits, size_t *input_frames,
    double *pcm, size_t *output_frames);
/* P16: same FIR state and phase clocks, packed-byte first-stage input. */
sox_dsd_status_t lsx_dsd_reconstruction_process_packed(
    lsx_dsd_reconstruction *, const sox_dsd_packed_block_t *, size_t start,
    size_t *input_frames, double *pcm, size_t *output_frames);
sox_dsd_status_t lsx_dsd_reconstruction_finish(
    lsx_dsd_reconstruction *, double *pcm, size_t *output_frames);
sox_dsd_status_t lsx_dsd_reconstruction_info_get(
    const lsx_dsd_reconstruction *, lsx_dsd_reconstruction_info *);
void lsx_dsd_reconstruction_destroy(lsx_dsd_reconstruction *);

#endif
