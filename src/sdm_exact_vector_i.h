/* Binary64, scalar-ordered normal SDM recurrence for the isolated x86 TUs.
 * The independent middle-coordinate updates may run in SIMD lanes. The first
 * coordinate, terminal coordinate, and serial decision sum MUST retain the
 * exact P10 scalar expression and operation order. Do not enable FMA.
 *
 * This is private to the four ISA-specific translation units; no build
 * system additions or installed ABI changes are required.
 */
#ifndef LSX_SDM_EXACT_VECTOR_I_H
#define LSX_SDM_EXACT_VECTOR_I_H
#include <immintrin.h>
#include <float.h>

static inline double lsx_sdm_exact_vector_math(const double *old, double *next,
    const double *a, const double *g, unsigned order, double x, double y)
{
  unsigned i = 1;
  double v;
  /* Scalar reference: ((s0 - g0*s1) + x) - previous_decision.
   * Parenthesization is intentional; (x-y) is NOT interchangeable. */
  next[0] = old[0] - g[0] * old[1] + x - y;
#if defined(__AVX__)
  for (; i + 4 <= order - 1; i += 4) {
    __m256d curr = _mm256_loadu_pd(old + i);
    __m256d prev = _mm256_loadu_pd(old + i - 1);
    __m256d succ = _mm256_loadu_pd(old + i + 1);
    __m256d coeff = _mm256_loadu_pd(g + i);
    __m256d value = _mm256_sub_pd(_mm256_add_pd(curr, prev),
                                   _mm256_mul_pd(coeff, succ));
    _mm256_storeu_pd(next + i, value);
  }
#else
  for (; i + 2 <= order - 1; i += 2) {
    __m128d curr = _mm_loadu_pd(old + i);
    __m128d prev = _mm_loadu_pd(old + i - 1);
    __m128d succ = _mm_loadu_pd(old + i + 1);
    __m128d coeff = _mm_loadu_pd(g + i);
    __m128d value = _mm_sub_pd(_mm_add_pd(curr, prev),
                                _mm_mul_pd(coeff, succ));
    _mm_storeu_pd(next + i, value);
  }
#endif
  for (; i + 1 < order; ++i)
    next[i] = old[i] + old[i - 1] - g[i] * old[i + 1];
  next[order - 1] = old[order - 1] + old[order - 2];
  v = x + a[0] * next[0];
  for (i = 1; i < order; ++i)
    v += a[i] * next[i];
  return v;
}
#endif
