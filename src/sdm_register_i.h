/* Register-resident normal SDM, private to the isolated x86 kernel TUs.
 *
 * The scalar step and legacy effect remain independent. The fast path is
 * entered only for disjoint buffers and masked IEEE binary64 arithmetic.
 * See docs/dsd/SDM_REGISTER_PROOF.md for the operation and commit proof.
 */
#ifndef LSX_SDM_REGISTER_I_H
#define LSX_SDM_REGISTER_I_H
#include <float.h>
#include <immintrin.h>
#include <stdint.h>
#include <string.h>

#if defined(__FAST_MATH__)
#error "register SDM requires strict IEEE-754 arithmetic"
#endif

/* Subtraction, rather than end-address addition, also handles addresses
 * near UINTPTR_MAX. Called only with real object spans on x86. */
static int lsx_sdm_spans_overlap(const void *p, size_t pn,
    const void *q, size_t qn)
{
  uintptr_t a = (uintptr_t)p, b = (uintptr_t)q;
  if (!pn || !qn) return 0;
  return a <= b ? b - a < pn : a - b < qn;
}

/* No FP comparison here: inspecting a signaling NaN must not raise an
 * exception before the scalar sample/peak/envelope checks would do so. */
static int lsx_sdm_plain_bound(double x)
{
  uint64_t u, e;
  memcpy(&u, &x, sizeof(u));
  e = u & UINT64_C(0x7ff0000000000000);
  return !(u >> 63) && e != UINT64_C(0x7ff0000000000000) &&
      (e || !(u & UINT64_C(0x000fffffffffffff)));
}

static int lsx_sdm_register_safe(sdm_normal_t *s, const double *input,
    size_t frames, sox_sample_t *output, size_t *committed,
    const double *bounds, unsigned *coordinate, double *peak, unsigned order)
{
  struct span { const void *p; size_t n; } spans[8];
  unsigned i, j, n = 0;
  unsigned csr = _mm_getcsr();
  /* DAZ/FTZ can make a MAX instruction return different subnormal bits
   * from scalar compare-and-conditional-store. Unmasked exceptions also
   * require the original instruction/trap ordering. */
  if ((csr & ((1u << 6) | (1u << 15))) ||
      (csr & 0x1f80u) != 0x1f80u) return 0;
  if (frames > SIZE_MAX / sizeof(*input) ||
      frames > SIZE_MAX / sizeof(*output)) return 0;
#define SPAN(p_, n_) do { spans[n].p = (p_); spans[n++].n = (n_); } while (0)
  SPAN(s, sizeof(*s));
  if (s->monitor) SPAN(s->monitor, sizeof(*s->monitor));
  SPAN(input, frames * sizeof(*input));
  SPAN(output, frames * sizeof(*output));
  SPAN(committed, sizeof(*committed));
  if (bounds) SPAN(bounds, order * sizeof(*bounds));
  if (coordinate) SPAN(coordinate, sizeof(*coordinate));
  if (peak) SPAN(peak, sizeof(*peak));
#undef SPAN
  for (i = 0; i < n; ++i)
    for (j = 0; j < i; ++j)
      if (lsx_sdm_spans_overlap(spans[i].p, spans[i].n,
                              spans[j].p, spans[j].n)) return 0;
  /* Bound comparisons run in lanes only when none can signal. Likewise
   * unusual initial monitor maxima use the unchanged scalar semantics. */
  for (i = 0; i < order; ++i) {
    if (bounds && !lsx_sdm_plain_bound(bounds[i])) return 0;
    if (s->monitor && !lsx_sdm_plain_bound(s->monitor->max_abs_state[i]))
      return 0;
  }
  return 1;
}

/* The original acceptor's integer bookkeeping, with its precommit frame
 * index supplied explicitly. Peaks are updated separately in SIMD lanes.
 * The widths, saturation points and order of these operations are unchanged. */
static inline void lsx_sdm_register_monitor(sdm_normal_monitor_t *m,
    double x, unsigned bit1, uint64_t frame)
{
  if (fabs(x) > .5) {
    if (m->overloads == 0) m->first_overload_frame = frame;
    sdm_monitor_increment(&m->overloads, &m->counter_saturated);
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

static inline double lsx_sdm_register_sum2(double v, __m128d terms)
{
  v += _mm_cvtsd_f64(terms);
  v += _mm_cvtsd_f64(_mm_unpackhi_pd(terms, terms));
  return v;
}

#define LSX_SDM_REGISTER_ORDER 7
#define LSX_SDM_REGISTER_NAME lsx_sdm_register7
#include "sdm_register_kernel_i.h"
#undef LSX_SDM_REGISTER_NAME
#undef LSX_SDM_REGISTER_ORDER
#define LSX_SDM_REGISTER_ORDER 8
#define LSX_SDM_REGISTER_NAME lsx_sdm_register8
#include "sdm_register_kernel_i.h"
#undef LSX_SDM_REGISTER_NAME
#undef LSX_SDM_REGISTER_ORDER

#endif
