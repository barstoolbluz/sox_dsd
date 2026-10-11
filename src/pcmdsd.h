/* P10 private composite PCM-to-DSD interface. Not an installed ABI.
 * A release create requires a qualified immutable profile. Only the named
 * test/qualification API admits candidate coefficients or calibration mode;
 * neither has a CLI switch or an experimental production alias. */
#ifndef LSX_PCMDSD_H
#define LSX_PCMDSD_H
#include "dsd.h"
#include "sdm.h"

typedef struct lsx_pcmdsd lsx_pcmdsd;
typedef struct {
  const char *id;
  uint32_t native_hz, working_hz;
  double pass_hz, stop_hz;
  const double *prefilter;
  size_t taps;
  const double *bounds;
  int qualified;
  const char *certificate_sha256;
} lsx_pcmdsd_profile;

typedef enum {
  LSX_PCMDSD_NO_ERROR, LSX_PCMDSD_INPUT_NONFINITE, LSX_PCMDSD_INTERPOLATION_OVERLOAD,
  LSX_PCMDSD_STATE_NONFINITE, LSX_PCMDSD_STATE_BOUND, LSX_PCMDSD_STREAM_ERROR
} lsx_pcmdsd_failure;
typedef struct {
  uint64_t input_frames, committed_frames, first_bad_frame;
  unsigned channel, coordinate;
  /* minimum_attenuation_db is a lower bound from the FIRST overloading
   * sample; fail-fast processing cannot know the maximum of the remainder.
   * A retry with exactly this attenuation is not guaranteed to succeed. */
  double peak, failure_value, minimum_attenuation_db, effective_pass_hz;
  lsx_pcmdsd_failure failure;
  sdm_normal_monitor_t monitor;
} lsx_pcmdsd_report;

/* Private diagnostic observer, optional and never enabled by production routing.
 * Observations are read-only and grouped by actual stream stage. A callback
 * must not call back into the encoder or alter samples. */
typedef enum {
  LSX_PCMDSD_STAGE_SOURCE, LSX_PCMDSD_STAGE_R,
  LSX_PCMDSD_STAGE_PREFILTER, LSX_PCMDSD_STAGE_NATIVE,
  LSX_PCMDSD_STAGE_SCALED, LSX_PCMDSD_STAGE_COUNT
} lsx_pcmdsd_stage;
typedef void (*lsx_pcmdsd_stage_observer)(void *opaque, lsx_pcmdsd_stage,
    const double *samples, size_t frames);
void lsx_pcmdsd_observe(lsx_pcmdsd *, lsx_pcmdsd_stage_observer, void *opaque);
/* Read-only per-context selection, used by P11 regression tests. */
const char *lsx_pcmdsd_kernel_name(const lsx_pcmdsd *);

const lsx_pcmdsd_profile *lsx_pcmdsd_profile_find(uint32_t);
int lsx_pcmdsd_qualified(uint32_t);
sox_dsd_status_t lsx_pcmdsd_create(uint32_t input_hz, uint32_t native_hz,
    double reference_scale, unsigned channel, lsx_pcmdsd **);
/* Calibration is explicit: NULL bounds means training WITHOUT finite guard
 * certification. Qualification passes frozen positive bounds. The optional
 * exact-rate SDM is a measurement control; it cannot alter the production ID. */
sox_dsd_status_t lsx_pcmdsd_candidate_create(uint32_t input_hz, uint32_t native_hz,
    double reference_scale, unsigned channel, const sdm_profile_t *control,
    const double bounds[8], lsx_pcmdsd **);
sox_dsd_status_t lsx_pcmdsd_process(lsx_pcmdsd *, const double *, size_t *,
    sox_sample_t *, size_t *);
sox_dsd_status_t lsx_pcmdsd_finish(lsx_pcmdsd *, sox_sample_t *, size_t *);
sox_dsd_status_t lsx_pcmdsd_report_get(const lsx_pcmdsd *, lsx_pcmdsd_report *);
/* Diagnostic continuation snapshot. Pointers are cleared; the test harness
 * reconstructs opaque SRC/FIR history by deterministic replay, not reset. */
sox_dsd_status_t lsx_pcmdsd_state_get(const lsx_pcmdsd *, sdm_normal_t *);
void lsx_pcmdsd_destroy(lsx_pcmdsd *);
/* Modulation primitive used by the pipeline and envelope/fault unit tests.
 * Failure latches. No output from the failed call is committed. */
sox_dsd_status_t lsx_pcmdsd_modulate(lsx_pcmdsd *, const double *,
    sox_sample_t *, size_t);

typedef struct {
  lsx_dsd_effect_options options; /* parser prefix; owns nothing */
  lsx_pcmdsd *encoder;           /* allocated after channel cloning */
  double resolved_reference;
} lsx_pcmdsd_private;
int lsx_pcmdsd_start(sox_effect_t *);
/* Test driver only: same wrapper, but explicit unqualified candidate create. */
int lsx_pcmdsd_candidate_start(sox_effect_t *);
int lsx_pcmdsd_flow(sox_effect_t *, const sox_sample_t *, sox_sample_t *, size_t *, size_t *);
int lsx_pcmdsd_drain(sox_effect_t *, sox_sample_t *, size_t *);
int lsx_pcmdsd_stop(sox_effect_t *);
void lsx_pcmdsd_set_reference(sox_effect_t *, double);
#endif
