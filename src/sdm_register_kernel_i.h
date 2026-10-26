/* Intentionally included twice by sdm_register_i.h, for orders 7 and 8.
 * Independent middle coordinates have the scalar DAG (curr+prev)-g*succ.
 * First and terminal coordinates have their own scalar DAGs. No dummy
 * coordinate is evaluated, and no zero coefficient is simplified away. */
static int LSX_SDM_REGISTER_NAME(sdm_normal_t *s, const double *input,
    size_t frames, sox_sample_t *output, size_t *committed,
    const double *bounds, unsigned *coordinate, double envelope, double *peak,
    const double *a, const double *g)
{
  sdm_normal_monitor_t *m = s->monitor;
  unsigned bank = s->bank;
  uint64_t frame = s->frames;
  double previous = s->previous_decision, peak_value = peak ? *peak : 0.;
  const __m128d sign = _mm_set1_pd(-0.);
  __m128d s45 = _mm_loadu_pd(s->state[bank] + 4), s67;
  __m128d max45 = _mm_setzero_pd(), max67 = _mm_setzero_pd();
  __m128d b45 = bounds ? _mm_loadu_pd(bounds + 4) : _mm_setzero_pd();
  __m128d b67 = _mm_setzero_pd();
  const __m128d a56 = _mm_loadu_pd(a + 5);
#if LSX_SDM_REGISTER_ORDER == 8
  const __m128d g56 = _mm_loadu_pd(g + 5);
  s67 = _mm_loadu_pd(s->state[bank] + 6);
  if (bounds) b67 = _mm_loadu_pd(bounds + 6);
#else
  const __m128d g5 = _mm_load_sd(g + 5);
  s67 = _mm_load_sd(s->state[bank] + 6);
  if (bounds) b67 = _mm_load_sd(bounds + 6);
#endif
#if defined(__AVX__)
  __m256d s03 = _mm256_loadu_pd(s->state[bank]);
  const __m256d a14 = _mm256_loadu_pd(a + 1);
  const __m256d g14 = _mm256_loadu_pd(g + 1);
  const __m256d sign4 = _mm256_set1_pd(-0.);
  __m256d max03 = _mm256_setzero_pd();
  __m256d b03 = bounds ? _mm256_loadu_pd(bounds) : _mm256_setzero_pd();
#else
  __m128d s01 = _mm_loadu_pd(s->state[bank]);
  __m128d s23 = _mm_loadu_pd(s->state[bank] + 2);
  const __m128d a12 = _mm_loadu_pd(a + 1), a34 = _mm_loadu_pd(a + 3);
  const __m128d g12 = _mm_loadu_pd(g + 1), g34 = _mm_loadu_pd(g + 3);
  __m128d max01 = _mm_setzero_pd(), max23 = _mm_setzero_pd();
  __m128d b01 = bounds ? _mm_loadu_pd(bounds) : _mm_setzero_pd();
  __m128d b23 = bounds ? _mm_loadu_pd(bounds + 2) : _mm_setzero_pd();
#endif
  size_t i;
  int rc = 0, retry = 0;
  double x = 0.;
  if (m) {
#if defined(__AVX__)
    max03 = _mm256_loadu_pd(m->max_abs_state);
#else
    max01 = _mm_loadu_pd(m->max_abs_state);
    max23 = _mm_loadu_pd(m->max_abs_state + 2);
#endif
    max45 = _mm_loadu_pd(m->max_abs_state + 4);
#if LSX_SDM_REGISTER_ORDER == 8
    max67 = _mm_loadu_pd(m->max_abs_state + 6);
#else
    max67 = _mm_load_sd(m->max_abs_state + 6);
#endif
  }
  for (i = 0; i < frames; ++i) {
    double n0, v;
    double *next = s->state[bank ^ 1];
    __m128d n56, abs45, abs67, old01;
    unsigned failed = 0, bit1;
#if LSX_SDM_REGISTER_ORDER == 8
    double n7;
#endif
#if defined(__AVX__)
    __m256d n14, successor, abs03, terms14;
    __m128d lo14, hi14;
    old01 = _mm256_castpd256_pd128(s03);
#else
    __m128d n12, n34, abs01, abs23;
    old01 = s01;
#endif
    x = input[i];
    if (!isfinite(x)) { retry = 1; break; }
    if (peak && fabs(x) > peak_value) peak_value = fabs(x);
    if (fabs(x) > envelope) { rc = LSX_DSD_SDM_OVERLOAD; break; }
    if (frame == UINT64_MAX) { rc = LSX_DSD_SDM_FRAME_LIMIT; break; }

    n0 = _mm_cvtsd_f64(old01) -
        g[0] * _mm_cvtsd_f64(_mm_unpackhi_pd(old01, old01)) + x - previous;
#if defined(__AVX__)
    /* successor = [s2,s3,s4,s5]; the shuffle is [s1,s2,s3,s4]. */
    successor = _mm256_permute2f128_pd(s03, _mm256_castpd128_pd256(s45), 0x21);
    n14 = _mm256_sub_pd(
        _mm256_add_pd(_mm256_shuffle_pd(s03, successor, 5), s03),
        _mm256_mul_pd(g14, successor));
    lo14 = _mm256_castpd256_pd128(n14);
    hi14 = _mm256_extractf128_pd(n14, 1);
#else
    n12 = _mm_sub_pd(_mm_add_pd(_mm_shuffle_pd(s01, s23, 1), s01),
                     _mm_mul_pd(g12, s23));
    n34 = _mm_sub_pd(_mm_add_pd(_mm_shuffle_pd(s23, s45, 1), s23),
                     _mm_mul_pd(g34, s45));
#endif
#if LSX_SDM_REGISTER_ORDER == 8
    n56 = _mm_sub_pd(_mm_add_pd(_mm_shuffle_pd(s45, s67, 1), s45),
                     _mm_mul_pd(g56, s67));
    n7 = _mm_cvtsd_f64(_mm_unpackhi_pd(s67, s67)) + _mm_cvtsd_f64(s67);
#else
    /* Upper lane is the terminal s6+s5, with NO multiply or subtract. */
    n56 = _mm_add_pd(_mm_shuffle_pd(s45, s67, 1), s45);
    n56 = _mm_sub_sd(n56, _mm_mul_sd(g5, s67));
#endif

    v = x + a[0] * n0;
#if defined(__AVX__)
    terms14 = _mm256_mul_pd(a14, n14);
    v = lsx_sdm_register_sum2(v, _mm256_castpd256_pd128(terms14));
    v = lsx_sdm_register_sum2(v, _mm256_extractf128_pd(terms14, 1));
    s03 = _mm256_insertf128_pd(
        _mm256_castpd128_pd256(_mm_unpacklo_pd(_mm_set_sd(n0), lo14)),
        _mm_shuffle_pd(lo14, hi14, 1), 1);
    s45 = _mm_shuffle_pd(hi14, n56, 1);
    _mm256_storeu_pd(next, s03);
#else
    v = lsx_sdm_register_sum2(v, _mm_mul_pd(a12, n12));
    v = lsx_sdm_register_sum2(v, _mm_mul_pd(a34, n34));
    s01 = _mm_unpacklo_pd(_mm_set_sd(n0), n12);
    s23 = _mm_shuffle_pd(n12, n34, 1);
    s45 = _mm_shuffle_pd(n34, n56, 1);
    _mm_storeu_pd(next, s01);
    _mm_storeu_pd(next + 2, s23);
#endif
    v = lsx_sdm_register_sum2(v, _mm_mul_pd(a56, n56));
#if LSX_SDM_REGISTER_ORDER == 8
    v += a[7] * n7;
    s67 = _mm_shuffle_pd(n56, _mm_set_sd(n7), 1);
    _mm_storeu_pd(next + 6, s67);
#else
    s67 = _mm_unpackhi_pd(n56, n56);
    _mm_store_sd(next + 6, s67);
#endif
    _mm_storeu_pd(next + 4, s45);
    /* The active bank is still the old state. Scalar re-execution overwrites
     * the rejected bank in scalar instruction order, including NaN payloads. */
    if (!isfinite(v)) { retry = 1; break; }

    abs45 = _mm_andnot_pd(sign, s45);
    abs67 = _mm_andnot_pd(sign, s67);
#if defined(__AVX__)
    abs03 = _mm256_andnot_pd(sign4, s03);
    if (bounds)
      failed = (unsigned)_mm256_movemask_pd(_mm256_cmp_pd(abs03, b03, _CMP_GT_OQ));
#else
    abs01 = _mm_andnot_pd(sign, s01);
    abs23 = _mm_andnot_pd(sign, s23);
    if (bounds)
      failed = (unsigned)_mm_movemask_pd(_mm_cmpgt_pd(abs01, b01)) |
          ((unsigned)_mm_movemask_pd(_mm_cmpgt_pd(abs23, b23)) << 2);
#endif
    if (bounds) {
      failed |= (unsigned)_mm_movemask_pd(_mm_cmpgt_pd(abs45, b45)) << 4;
#if LSX_SDM_REGISTER_ORDER == 8
      failed |= (unsigned)_mm_movemask_pd(_mm_cmpgt_pd(abs67, b67)) << 6;
#else
      failed |= ((unsigned)_mm_movemask_pd(_mm_cmpgt_sd(abs67, b67)) & 1u) << 6;
#endif
      if (failed) {
        if (coordinate) {
          unsigned j = 0;
          while (!(failed & (1u << j))) ++j;
          *coordinate = j;
        }
        rc = LSX_DSD_SDM_BOUNDS;
        break;
      }
    }
    /* Exactly sdm_normal_decision: signbit also distinguishes negative zero. */
    bit1 = !signbit(v);
    bank ^= 1;
    previous = bit1 ? 1. : -1.;
    if (m) {
      /* Old maximum is the SECOND operand: ties retain its original bits. */
#if defined(__AVX__)
      max03 = _mm256_max_pd(abs03, max03);
#else
      max01 = _mm_max_pd(abs01, max01);
      max23 = _mm_max_pd(abs23, max23);
#endif
      max45 = _mm_max_pd(abs45, max45);
#if LSX_SDM_REGISTER_ORDER == 8
      max67 = _mm_max_pd(abs67, max67);
#else
      max67 = _mm_max_sd(abs67, max67);
#endif
      lsx_sdm_register_monitor(m, x, bit1, frame);
    }
    ++frame; /* The preflight above rules out overflow. */
    output[i] = bit1 ? SOX_SAMPLE_MAX : -SOX_SAMPLE_MAX;
  }
  s->bank = bank;
  s->previous_decision = previous;
  s->frames = frame;
  if (m) {
#if defined(__AVX__)
    _mm256_storeu_pd(m->max_abs_state, max03);
#else
    _mm_storeu_pd(m->max_abs_state, max01);
    _mm_storeu_pd(m->max_abs_state + 2, max23);
#endif
    _mm_storeu_pd(m->max_abs_state + 4, max45);
#if LSX_SDM_REGISTER_ORDER == 8
    _mm_storeu_pd(m->max_abs_state + 6, max67);
#else
    _mm_store_sd(m->max_abs_state + 6, max67);
#endif
  }
  if (peak) *peak = peak_value;
  *committed = i;
  if (retry) {
    int bit;
    return sdm_normal_step_guarded(s, x, &bit, bounds, coordinate);
  }
  return rc;
}
