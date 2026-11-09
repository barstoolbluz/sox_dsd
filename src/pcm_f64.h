/* Private, not installed: finite interleaved IEEE binary64 PCM primitives.
 * No DSD container, effects graph, public sox_sample_t, or hidden allocation.
 * All frame counts are frames, not interleaved scalar sample counts.
 * The coordinator owns its stream state and performs its own EOF transition.
 */
#ifndef SOX_DSD_PCM_F64_H
#define SOX_DSD_PCM_F64_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

typedef enum {
  PCM_F64_OK = 0,
  PCM_F64_NEED_INPUT,
  PCM_F64_NEED_OUTPUT,
  PCM_F64_DONE,
  PCM_F64_ARGUMENT,
  PCM_F64_UNSUPPORTED,
  PCM_F64_NUMERIC,
  PCM_F64_IO,
  PCM_F64_LIMIT,
  PCM_F64_STATE
} pcm_f64_status;

typedef struct {
  uint32_t rate_hz;
  uint32_t channels;             /* 1..64 for the initial native coordinator */
  uint64_t total_frames;
  bool length_known;             /* zero frames is different from unknown */
} pcm_f64_format;

typedef struct {
  const double *data;           /* borrowed for this call; immutable */
  size_t frames;
} pcm_f64_input;

typedef struct {
  double *data;                 /* caller-owned, capacity measured in frames */
  size_t capacity_frames;
} pcm_f64_output;

typedef struct {
  size_t consumed_frames;
  size_t produced_frames;
  pcm_f64_status status;        /* output may accompany NEED_INPUT/OUTPUT/DONE */
} pcm_f64_progress;

typedef struct {
  pcm_f64_status failed;        /* initialize to PCM_F64_OK; first failure sticks */
} pcm_f64_failure;

typedef enum {
  PCM_F64_WORD_FINITE,
  PCM_F64_WORD_INFINITY,
  PCM_F64_WORD_QNAN,
  PCM_F64_WORD_SNAN
} pcm_f64_word_class;

/* Context and checked, bounded views. Zero capacity permits a NULL pointer. */
pcm_f64_status pcm_f64_format_init(pcm_f64_format *format,
    uint32_t rate_hz, uint32_t channels, bool length_known,
    uint64_t total_frames);
pcm_f64_status pcm_f64_frame_storage(size_t frames, uint32_t channels,
    size_t *scalar_samples, size_t *bytes);
pcm_f64_status pcm_f64_validate_input(const pcm_f64_format *format,
    pcm_f64_input input);
pcm_f64_status pcm_f64_validate_output(const pcm_f64_format *format,
    pcm_f64_output output);
pcm_f64_status pcm_f64_advance(const pcm_f64_format *format,
    uint64_t already, size_t additional, uint64_t *next);
pcm_f64_status pcm_f64_count_samples(uint64_t frames,
    uint32_t channels, uint64_t *samples);

/* Stable errors and no retry after failure. Only a future coordinator implements
 * process/finish and latches EOF even on finish(capacity=0). */
bool pcm_f64_is_failure(pcm_f64_status code);
pcm_f64_status pcm_f64_latch(pcm_f64_failure *state, pcm_f64_status code);
const char *pcm_f64_status_name(pcm_f64_status status);

/* Native DSP capability is checked once at stream initialization and at each
 * processing/drain boundary, including on each active worker. It is NOT called
 * inside per-sample numerical primitives. No caller FP controls are changed.
 * Copy-only finite word transfer does not require compatible DSP controls. */
pcm_f64_status pcm_f64_check_dsp_env(void);
pcm_f64_status pcm_f64_check_ieee_storage(void);

/* Classification examines raw bits, including signaling NaNs, without FP ops.
 * The first invalid word is reported as an interleaved scalar index; caller
 * derives frame=index/channels and channel=index%channels. A copy rejects all
 * nonfinites before writing anything. Exact aliasing is supported; partial
 * source/destination overlap is not. */
pcm_f64_status pcm_f64_classify(const double *value,
    pcm_f64_word_class *kind);
pcm_f64_status pcm_f64_copy_finite(double *dst, const double *src,
    size_t scalar_count, size_t *bad_index);

/* Only widths 8,16,24,32. Signed samples are RIGHT-aligned, while aligned32
 * represents already left-aligned signed codec output (e.g., built-in FLAC).
 * Normalization is code * 2^-(bits-1), never code / INT_MAX. */
pcm_f64_status pcm_f64_normalize_signed(int32_t code, unsigned bits,
    double *result);
pcm_f64_status pcm_f64_normalize_u8(uint8_t code, double *result);
pcm_f64_status pcm_f64_normalize_aligned32(int32_t code,
    double *result);

/* Copy or scale finite scalar PCM. Identity (gain=1) preserves every bit.
 * Exact in-place alias is supported, partial overlap is not. On a failure,
 * a non-identity output buffer may contain a prefix; the future coordinator
 * must discard the entire block, never publish it to a sink, and latch error.
 * The caller checks the native DSP environment once per block, not per word. */
pcm_f64_status pcm_f64_fixed_gain(double *dst, const double *src,
    size_t scalar_count, double gain, size_t *bad_index);

/* One target-width conversion: nearest integer, exact ties away from zero;
 * saturated is true only if the rounded code lies outside target range.
 * nominal_excursion is independently (x >= +1 || x < -1), not saturation.
 * Return left-aligned signed 32-bit transport without signed-negative shifts. */
pcm_f64_status pcm_f64_quantize_int(double value, unsigned bits,
    int32_t *aligned32, bool *saturated);
pcm_f64_status pcm_f64_nominal_excursion(double value, bool *outside);

#endif
