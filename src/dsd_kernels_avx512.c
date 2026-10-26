/* P13 isolated AVX-512F baseline. AVX2 enabled by GCC -mavx512f; no AVX-512DQ/BW/VL or FMA required.
 * The eight FIR output times are independent; SDM vectorizes its eight
 * coordinates, NOT time. Built with -ffp-contract=off and -fno-lto. */
#include "sox_i.h"
#include "dsd_kernels.h"
#define LSX_SDM_INLINE_DECISION 1
#include "sdm_normal_commit_i.h"
#undef LSX_SDM_INLINE_DECISION
#include "sdm_exact_vector_i.h"
#include "sdm_register_i.h"
#include <immintrin.h>
#include <math.h>

/* Exact eight stride-two windows: 0,2,...,14. The final masked load
 * accesses indices 8..14, never index 15. Both unaligned loads operate
 * entirely inside the caller's declared FIR span, including taps==1. */
static inline __m512d fir_eight_at(const double *p, size_t tap, size_t stride)
{
  if (stride == 1) return _mm512_loadu_pd(p + tap);
  if (stride == 2) {
    const __m512i even = _mm512_setr_epi64(0,2,4,6,8,10,12,14);
    __m512d lo = _mm512_loadu_pd(p + tap);
    __m512d hi = _mm512_maskz_loadu_pd(0x7f, p + tap + 8);
    return _mm512_permutex2var_pd(lo, even, hi);
  }
  /* Nonstandard stride is supported without speculative vector loads. */
  return _mm512_set_pd(p[7*stride+tap],p[6*stride+tap],
                       p[5*stride+tap],p[4*stride+tap],
                       p[3*stride+tap],p[2*stride+tap],
                       p[stride+tap],p[tap]);
}

static void fir_avx512_block(const double *h, size_t taps, const double *s,
    size_t frames, size_t stride, int halfband, double *out)
{
  const size_t mid=taps/2;
  size_t n=0,i;
  for (; frames-n>=8; n+=8) {
    const double *p=s+n*stride;
    __m512d acc=_mm512_mul_pd(_mm512_set1_pd(h[mid]),
                                fir_eight_at(p,mid,stride));
    for (i=0;i<mid;++i) {
      __m512d l,r;
      if (halfband && h[i]==0.0) continue;
      l=fir_eight_at(p,i,stride);
      r=fir_eight_at(p,taps-1-i,stride);
      acc=_mm512_add_pd(acc,_mm512_mul_pd(_mm512_set1_pd(h[i]),
                                              _mm512_add_pd(l,r)));
    }
    _mm512_storeu_pd(out+n,acc);
  }
  /* A scalar tail is lower overhead than mask+gather for <8 frames. */
  for (;n<frames;++n)
    out[n]=lsx_dsd_fir_scalar(h,taps,s+n*stride,halfband);
}

/* Production single-output streaming FIR: reverse exactly eight in-span
 * samples with AVX-512F VPERMPD. The scalar tail preserves the P06 order;
 * the lane accumulator is deliberately noncontracted. */
double lsx_dsd_fir_avx512_direct(const double *h,size_t taps,
    const double *s,int halfband)
{
  const size_t mid=taps/2;
  const __m512i reverse=_mm512_setr_epi64(7,6,5,4,3,2,1,0);
  __m512d sums=_mm512_setzero_pd();
  double lanes[8],acc=h[mid]*s[mid];
  size_t i=0,j;
  if (halfband) return lsx_dsd_fir_scalar(h,taps,s,halfband);
  for (;i+8<=mid;i+=8) {
    __m512d left=_mm512_loadu_pd(s+i);
    __m512d right=_mm512_permutexvar_pd(reverse,
                                         _mm512_loadu_pd(s+taps-8-i));
    sums=_mm512_add_pd(sums,_mm512_mul_pd(_mm512_loadu_pd(h+i),
                                             _mm512_add_pd(left,right)));
  }
  _mm512_storeu_pd(lanes,sums);
  for (j=0;j<8;++j) acc+=lanes[j];
  for (;i<mid;++i) acc+=h[i]*(s[i]+s[taps-1-i]);
  return acc;
}

/* Normal SDM uses the same narrow register layout as AVX1/AVX2; the tier's
 * AVX-512F FIR is independent. First and terminal coordinates retain their
 * scalar expressions, and decision products are added in ascending order.
 * Inactive coordinates are never evaluated or overwritten. */

static int sdm_avx512_block(sdm_normal_t *s,const double *input,
    size_t frames,sox_sample_t *output,size_t *committed,
    const double bounds[8],unsigned *coordinate,double envelope,double *peak)
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
    double v, x=input[i];
    int bit,rc;
    if (!isfinite(x)) return lsx_sdm_normal_reject_nonfinite(s);
    if (peak && fabs(x)>*peak) *peak=fabs(x);
    if (fabs(x)>envelope) return LSX_DSD_SDM_OVERLOAD;
    if (s->frames==UINT64_MAX) return LSX_DSD_SDM_FRAME_LIMIT;
    v=lsx_sdm_exact_vector_math(s->state[s->bank],next,a,g,order,x,
                      s->previous_decision);
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

const lsx_dsd_kernel lsx_dsd_kernel_avx512 = {
  "avx512", LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX2|LSX_DSD_CPU_AVX512F,
  fir_avx512_block,lsx_dsd_fir_avx512_direct,sdm_avx512_block
};
