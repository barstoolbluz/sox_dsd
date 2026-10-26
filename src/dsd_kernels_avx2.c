/* P12 AVX2 baseline: all AVX2-only operations are local to this isolated TU.
 * Four FIR output TIMES are independent; a normal SDM's eight coordinates
 * are parallel but its successive time samples are NEVER independent.
 * Compile with -mavx2 -mno-fma -ffp-contract=off -fno-lto. No FMA path. */
#include "sox_i.h"
#include "dsd_kernels.h"
#define LSX_SDM_ACCEPT_FINITE_V 1
#define LSX_SDM_INLINE_DECISION 1
#include "sdm_normal_commit_i.h"
#undef LSX_SDM_INLINE_DECISION
#undef LSX_SDM_ACCEPT_FINITE_V
#include "sdm_exact_vector_i.h"
#include "sdm_register_i.h"
#include <immintrin.h>
#include <math.h>

/* Four successive stride-two outputs read offsets [0,2,4,6].
 * An eight-element window is formed with two unaligned vector loads and a
 * FULL-WIDTH AVX2 vpermpd (not the AVX1 per-128-bit shuffle). The even
 * variant may read index 7, so only use it when index 7 is in the declared
 * caller span. The odd variant reads offsets [-1..6], selecting [1,3,5,7];
 * this avoids reading beyond the final tap on the right side of the FIR. */
static inline __m256d stride2_even(const double *p)
{
  __m256d lo = _mm256_loadu_pd(p);
  __m256d hi = _mm256_loadu_pd(p+4);
  return _mm256_permute4x64_pd(_mm256_unpacklo_pd(lo,hi), 0xd8);
}
static inline __m256d stride2_odd(const double *p)
{
  __m256d lo = _mm256_loadu_pd(p);
  __m256d hi = _mm256_loadu_pd(p+4);
  return _mm256_permute4x64_pd(_mm256_unpackhi_pd(lo,hi), 0xd8);
}

static inline __m256d at_four_times(const double *p,size_t tap,size_t stride)
{
  if (stride == 1) return _mm256_loadu_pd(p+tap);
  if (stride == 2) return stride2_even(p+tap);
  return _mm256_set_pd(p[3*stride+tap],p[2*stride+tap],
                       p[stride+tap],p[tap]);
}

static void fir_avx2_block(const double *h,size_t taps,const double *s,
    size_t frames,size_t stride,int halfband,double *out)
{
  size_t n=0,i,mid=taps/2;
  for (; frames-n >= 4; n+=4) {
    const double *p=s+n*stride;
    /* taps==1, stride==2: a full eight-element load would read index 7
     * although the declared input span ends at 6. Use four exact loads. */
    __m256d center = (stride==2 && taps==1)
      ? _mm256_set_pd(p[6],p[4],p[2],p[0])
      : at_four_times(p,mid,stride);
    __m256d acc=_mm256_mul_pd(_mm256_set1_pd(h[mid]),center);
    for (i=0;i<mid;++i) {
      __m256d left,right;
      size_t far=taps-1-i;
      if (halfband && h[i]==0.0) continue;
      left=at_four_times(p,i,stride);
      /* Rightmost tap plus lane 3 is the last legal element of input.
       * Form its stride-two vector from [far-1..far+6], never far+7. */
      right=(stride==2)?stride2_odd(p+far-1)
            :at_four_times(p,far,stride);
      acc=_mm256_add_pd(acc,_mm256_mul_pd(_mm256_set1_pd(h[i]),
                                          _mm256_add_pd(left,right)));
    }
    _mm256_storeu_pd(out+n,acc);
  }
  for (;n<frames;++n)
    out[n]=lsx_dsd_fir_scalar(h,taps,s+n*stride,halfband);
}

/* The decoder currently calls the direct single-output streaming FIR. Use
 * genuine full-width AVX2 lane reversal for its contiguous symmetric window
 * (no speculative over-read). Retain scalar half-band order as inherited. */
double lsx_dsd_fir_avx2_direct(const double *h,size_t taps,
    const double *s,int halfband)
{
  size_t i=0,mid=taps/2;
  double acc=h[mid]*s[mid],lanes[4];
  __m256d sums=_mm256_setzero_pd();
  if (halfband) return lsx_dsd_fir_scalar(h,taps,s,halfband);
  for (;i+4<=mid;i+=4) {
    __m256d left=_mm256_loadu_pd(s+i);
    __m256d right=_mm256_permute4x64_pd(
        _mm256_loadu_pd(s+taps-4-i),0x1b);
    sums=_mm256_add_pd(sums,_mm256_mul_pd(_mm256_loadu_pd(h+i),
                                         _mm256_add_pd(left,right)));
  }
  _mm256_storeu_pd(lanes,sums);
  acc+=lanes[0];acc+=lanes[1];acc+=lanes[2];acc+=lanes[3];
  for (;i<mid;++i) acc+=h[i]*(s[i]+s[taps-1-i]);
  return acc;
}

/* Normal SDM keeps order-seven/eight state in registers, vectorizes only
 * independent middle coordinates, and retains the first/terminal scalar
 * expressions and serial decision sum. No contraction is permitted. */

static int sdm_avx2_block(sdm_normal_t *s,const double *input,
    size_t frames,sox_sample_t *output,size_t *committed,
    const double bounds[8],unsigned *coordinate,
    double envelope,double *peak)
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
      unsigned rejected_coordinate=0;
      /* isfinite(v) was checked above; therefore no active next[i] can
       * be nonfinite. Preserve first-failing-coordinate bounds order. */
      rc=lsx_sdm_normal_accept(s,input[i],v,order,&bit,bounds,
                                         &rejected_coordinate);
      if (rc==LSX_DSD_SDM_BOUNDS && coordinate)
        *coordinate=rejected_coordinate;
    }
    if (rc) return rc;
    output[i]=bit>0?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
    *committed=i+1;
  }
  return 0;
}

const lsx_dsd_kernel lsx_dsd_kernel_avx2 = {
  "avx2", LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX2,
  fir_avx2_block,lsx_dsd_fir_avx2_direct,sdm_avx2_block
};
