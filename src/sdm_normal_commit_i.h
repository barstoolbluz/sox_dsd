/* P11: identical scalar acceptance/monitor bookkeeping shared by the
 * original scalar step and the separate ISA arithmetic TUs. Never commit the
 * inactive bank on failure. Purely per-context state. */
#ifndef LSX_SDM_NORMAL_COMMIT_I_H
#define LSX_SDM_NORMAL_COMMIT_I_H
#include "sdm.h"
#include <math.h>
#include <stdint.h>

static inline void sdm_monitor_increment(uint64_t *value, unsigned *saturated)
{
  if (*value == UINT64_MAX) *saturated = 1;
  else ++*value;
}

static inline int lsx_sdm_normal_reject_nonfinite(sdm_normal_t *s)
{
  sdm_normal_monitor_t *m = s->monitor;
  if (m) {
    if (m->nonfinite == 0) m->first_bad_frame = s->frames;
    sdm_monitor_increment(&m->nonfinite, &m->counter_saturated);
  }
  return -1;
}

static inline int lsx_sdm_normal_accept(sdm_normal_t *s, double x, double v,
    unsigned order, int *bit, const double *bounds, unsigned *coordinate)
{
  sdm_normal_monitor_t *m = s->monitor;
  double *next = s->state[s->bank ^ 1];
  unsigned i;
  int y;
  if (!isfinite(v)) goto nonfinite;
  for (i = 0; i < order; ++i) {
    if (!isfinite(next[i])) {
      if (coordinate) *coordinate=i;
      goto nonfinite;
    }
    if (bounds && fabs(next[i])>bounds[i]) {
      if (coordinate) *coordinate=i;
      return -2; /* no decision or active-bank commit on finite runaway */
    }
  }

  y = sdm_normal_decision(v);
  *bit = y;
  s->bank ^= 1;
  s->previous_decision = (double)y;
  if (m) {
    unsigned bit1 = y > 0;
    if (fabs(x) > .5) {
      if (m->overloads == 0) m->first_overload_frame = s->frames;
      sdm_monitor_increment(&m->overloads, &m->counter_saturated);
    }
    for (i = 0; i < order; ++i) {
      double a = fabs(next[i]);
      if (a > m->max_abs_state[i]) m->max_abs_state[i] = a;
    }
    if (m->history_bits < 28) {
      ++m->history_bits;
      m->ones28 += bit1;
    } else {
      m->ones28 += bit1;
      m->ones28 -= (m->history28 >> 27) & 1U;
    }
    m->history28 = ((m->history28 << 1) | bit1) & UINT32_C(0x0fffffff);
    if (m->history_bits == 28) {
      sdm_monitor_increment(&m->windows28, &m->counter_saturated);
      if (m->ones28 < m->min_ones28) m->min_ones28 = m->ones28;
      if (m->ones28 > m->max_ones28) m->max_ones28 = m->ones28;
      if (m->ones28 < 4 || m->ones28 > 24)
        sdm_monitor_increment(&m->excursions28, &m->counter_saturated);
    }
    if (m->run_length && bit1 == m->last_bit) {
      if (m->run_length != UINT32_MAX) ++m->run_length;
      else m->counter_saturated = 1;
    } else m->run_length = 1;
    m->last_bit = bit1;
    if (m->run_length > m->longest_run) m->longest_run = m->run_length;
    sdm_monitor_increment(&m->frames, &m->counter_saturated);
  }
  if (s->frames != UINT64_MAX) ++s->frames;
  else if (m) m->counter_saturated = 1;
  return 0;

nonfinite:
  if (m) {
    if (m->nonfinite == 0) m->first_bad_frame = s->frames;
    sdm_monitor_increment(&m->nonfinite, &m->counter_saturated);
  }
  return -1; /* no bank swap or decision/state commit */
}
#endif
