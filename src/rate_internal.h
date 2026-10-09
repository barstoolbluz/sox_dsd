/* Private binary64 interface to rate.c's existing FIR backend (P07).
 * This is not a public SoX effect.  A context owns its own coefficients and
 * FIFO state.  Finite-stream final count is specified by the caller. */
#ifndef LSX_RATE_INTERNAL_H
#define LSX_RATE_INTERNAL_H
#include "sox_dsd.h"
#include <stddef.h>
#include <stdint.h>
typedef struct lsx_rate_f64 lsx_rate_f64_t;
typedef struct {
  uint32_t input_hz, output_hz;
  double rejection_db;
  double bandwidth_0db_pct;
  unsigned phase_percent;
} lsx_rate_f64_config;
sox_dsd_status_t lsx_rate_f64_create(const lsx_rate_f64_config *, lsx_rate_f64_t **);
sox_dsd_status_t lsx_rate_f64_process(lsx_rate_f64_t *, const double *,
    size_t *input_frames, double *, size_t *output_frames);
sox_dsd_status_t lsx_rate_f64_finish(lsx_rate_f64_t *, uint64_t final_frames,
    double *, size_t *output_frames);
void lsx_rate_f64_destroy(lsx_rate_f64_t *);
#endif
