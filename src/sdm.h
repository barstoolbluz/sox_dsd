/* Sigma-Delta modulator
 * Copyright (c) 2015 Mans Rullgard <mans@mansr.com>
 *
 * This library is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or (at
 * your option) any later version.
 *
 * This library is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser
 * General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this library; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

#ifndef SOX_SDM_H
#define SOX_SDM_H

#include "sox_i.h"

#define SDM_TRELLIS_MAX_ORDER 32
#define SDM_TRELLIS_MAX_NUM   32
#define SDM_TRELLIS_MAX_LAT   2048

typedef struct sdm sdm_t;

sdm_t *sdm_init(const char *filter_name,
                unsigned freq,
                unsigned trellis_order,
                unsigned trellis_num,
                unsigned trellis_latency);

int sdm_process(sdm_t *s, const sox_sample_t *ibuf, sox_sample_t *obuf,
                size_t *ilen, size_t *olen);

int sdm_drain(sdm_t *s, sox_sample_t *obuf, size_t *olen);

void sdm_close(sdm_t *s);
/* P09 allocation diagnostic: exact bytes in the existing legacy sdm_t. */
size_t sdm_legacy_allocation_bytes(void);


/* P09: strictly versioned, rate-specific entries. The legacy sdm_init() and
 * effect deliberately retain their historical <=-rate selection. No P09
 * entry is a mastering-qualification certificate. Coefficients live for the
 * lifetime of the process; callers may never modify or free them. */
typedef struct sdm_profile sdm_profile_t;
const sdm_profile_t *sdm_profile_find(const char *id, unsigned native_hz);
const char *sdm_profile_id(const sdm_profile_t *p);
const char *sdm_profile_filter_name(const sdm_profile_t *p);
unsigned sdm_profile_rate(const sdm_profile_t *p);
unsigned sdm_profile_working_rate(const sdm_profile_t *p);
int sdm_profile_coefficients(const sdm_profile_t *p, const double **a,
                             const double **g, unsigned *order);

typedef struct sdm_normal_monitor {
  uint64_t frames, windows28, excursions28, overloads, nonfinite;
  uint64_t first_bad_frame, first_overload_frame;
  uint64_t longest_run;
  uint32_t history28, ones28, run_length;
  unsigned history_bits, last_bit, min_ones28, max_ones28;
  unsigned counter_saturated;
  double max_abs_state[8];
} sdm_normal_monitor_t;

/* Stack-allocatable; no implicit allocation or trellis history. Only init
 * resets a normal state. Monitor attachment does not reset counters/state. */
typedef struct sdm_normal {
  const sdm_profile_t *profile;
  sdm_normal_monitor_t *monitor;
  double state[2][8];
  double previous_decision;
  unsigned bank;
  uint64_t frames;
} sdm_normal_t;

void sdm_normal_monitor_init(sdm_normal_monitor_t *m);
int sdm_normal_init(sdm_normal_t *s, const sdm_profile_t *profile);
void sdm_normal_attach_monitor(sdm_normal_t *s, sdm_normal_monitor_t *m);
/* Return 0 on success. Nonfinite arithmetic returns -1 without committing
 * the sample/state. The caller owns the output buffer and failure policy. */
int sdm_normal_step(sdm_normal_t *s, double x, int *bit);
/* P10: -2 denotes a finite state bound crossing; active state is uncommitted. */
int sdm_normal_step_guarded(sdm_normal_t *, double, int *,
    const double bounds[8], unsigned *coordinate);
/* Signbit wins ties: negative zero must return -1. */
int sdm_normal_decision(double accumulator);

#endif
