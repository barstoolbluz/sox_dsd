/* P11 SSE2: independent FIR output-time lanes and the state-coordinate SDM
 * formulation inherited from sdm_x86.h. No AVX instructions in this unit. */
#include "sox_i.h"
#include "dsd_kernels.h"
#define LSX_SDM_INLINE_DECISION 1
#include "sdm_normal_commit_i.h"
#undef LSX_SDM_INLINE_DECISION
#include "sdm_exact_vector_i.h"
#include "sdm_register_i.h"
#include <emmintrin.h>
#include <math.h>

static void fir_sse2_block(const double *h, size_t taps, const double *s,
    size_t frames, size_t stride, int halfband, double *out)
{
  size_t n = 0, i, mid = taps/2;
  for (; frames-n >= 2; n += 2) {
    const double *p = s+n*stride;
    __m128d acc = _mm_mul_pd(_mm_set1_pd(h[mid]),
        _mm_set_pd(p[stride+mid],p[mid]));
    for (i=0;i<mid;++i) {
      __m128d ab, cd;
      if (halfband && h[i]==0.0) continue;
      ab=_mm_set_pd(p[stride+i],p[i]);
      cd=_mm_set_pd(p[stride+taps-1-i],p[taps-1-i]);
      acc=_mm_add_pd(acc,_mm_mul_pd(_mm_set1_pd(h[i]),_mm_add_pd(ab,cd)));
    }
    _mm_storeu_pd(out+n,acc);
  }
  for (; n < frames; ++n)
    out[n]=lsx_dsd_fir_scalar(h,taps,s+n*stride,halfband);
}

/* Single-output streaming FIR: vectorize independent tap contributions when
 * dense, without reading outside the caller's exactly-taps window. The
 * established scalar reference remains the half-band path. */
double lsx_dsd_fir_sse2_direct(const double *h, size_t taps,
    const double *s, int halfband)
{
  size_t i=0,mid=taps/2;
  double acc=h[mid]*s[mid], lanes[2];
  __m128d sums=_mm_setzero_pd();
  if (halfband) return lsx_dsd_fir_scalar(h,taps,s,halfband);
  for (; i+2<=mid; i+=2) {
    __m128d left=_mm_loadu_pd(s+i);
    __m128d right=_mm_set_pd(s[taps-2-i],s[taps-1-i]);
    sums=_mm_add_pd(sums,_mm_mul_pd(_mm_loadu_pd(h+i),
                                   _mm_add_pd(left,right)));
  }
  _mm_storeu_pd(lanes,sums);
  acc += lanes[0]; acc += lanes[1];
  for (; i<mid; ++i) acc+=h[i]*(s[i]+s[taps-1-i]);
  return acc;
}

/* All accesses are unaligned. A context/state bank has no alignment promise;
 * neither the external FIR input nor the application stack needs SSE padding. */

static int sdm_sse2_block(sdm_normal_t *s, const double *input,
    size_t frames, sox_sample_t *output, size_t *committed,
    const double bounds[8], unsigned *coordinate,
    double envelope, double *peak)
{
  const double *a,*g;
  unsigned order;
  size_t i;
  if (committed) *committed=0;
  if (!s || !s->profile || !committed || (frames && (!input || !output)) ||
      sdm_profile_coefficients(s->profile,&a,&g,&order) || order<4 || order>8)
    return -1;
#if defined(__i386__) || FLT_EVAL_METHOD != 0
  /* i386/x87 and excess-precision builds cannot promise SSE/AVX bitwise
   * equivalence to the scalar's extended intermediates. */
  return lsx_dsd_kernel_scalar.sdm_block(s,input,frames,output,committed,
                                          bounds,coordinate,envelope,peak);
#endif
  if (!frames) return 0;
  /* Register/monitor caching is valid only with disjoint object spans.
   * The scalar block also preserves legacy legal aliases and unusual FP
   * environments, including the sample-before-peak-load ordering. */
  if (!lsx_sdm_register_safe(s,input,frames,output,committed,bounds,
                             coordinate,peak,order))
    return lsx_dsd_kernel_scalar.sdm_block(s,input,frames,output,committed,
                                          bounds,coordinate,envelope,peak);
  if (order==7)
    return lsx_sdm_register7(s,input,frames,output,committed,bounds,
                              coordinate,envelope,peak,a,g);
  if (order==8)
    return lsx_sdm_register8(s,input,frames,output,committed,bounds,
                              coordinate,envelope,peak,a,g);
  for (i=0;i<frames;++i) {
    double *next=s->state[s->bank^1];
    double v;
    int bit,rc;
    if (!isfinite(input[i])) return lsx_sdm_normal_reject_nonfinite(s);
    if (peak && fabs(input[i])>*peak) *peak=fabs(input[i]);
    if (fabs(input[i])>envelope) return LSX_DSD_SDM_OVERLOAD;
    if (s->frames==UINT64_MAX) return LSX_DSD_SDM_FRAME_LIMIT;
    v=lsx_sdm_exact_vector_math(s->state[s->bank],next,a,g,order,input[i],s->previous_decision);
    /* A rare failed arithmetic step is recomputed with the original scalar
     * instructions to preserve its rejected-bank NaN payload. The original
     * acceptor only modifies three monitor fields before that rejection. */
    if (!isfinite(v))
      return sdm_normal_step_guarded(s,input[i],&bit,bounds,coordinate);
    {
      sdm_normal_monitor_t *m=s->monitor;
      uint64_t nonfinite=m?m->nonfinite:0;
      uint64_t bad_frame=m?m->first_bad_frame:0;
      unsigned saturated=m?m->counter_saturated:0;
      unsigned rejected_coordinate=0;
      /* Do not expose a vector-only nonfinite coordinate before the scalar
       * retry: the scalar may reject v before inspecting any state. */
      rc=lsx_sdm_normal_accept(s,input[i],v,order,&bit,bounds,&rejected_coordinate);
      if (rc==LSX_DSD_SDM_BOUNDS && coordinate)
        *coordinate=rejected_coordinate;
      if (rc==LSX_DSD_SDM_NONFINITE) {
        if (m) {m->nonfinite=nonfinite;m->first_bad_frame=bad_frame;
                m->counter_saturated=saturated;}
        return sdm_normal_step_guarded(s,input[i],&bit,bounds,coordinate);
      }
    }
    if (rc) return rc;
    output[i]=bit>0?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
    *committed=i+1;
  }
  return 0;
}

const lsx_dsd_kernel lsx_dsd_kernel_sse2 = {
  "sse2", LSX_DSD_CPU_SSE2, fir_sse2_block, lsx_dsd_fir_sse2_direct, sdm_sse2_block
};
