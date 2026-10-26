/* P11 AVX1: genuine independent AVX-only TU. Requires OSXSAVE, XCR0[2:1],
 * CPU AVX; NEVER compile with AVX2/FMA flags or whole-program -march=native. */
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

static void fir_avx1_block(const double *h,size_t taps,const double *s,
    size_t frames,size_t stride,int halfband,double *out)
{
  size_t n=0,i,mid=taps/2;
  for (;frames-n>=4;n+=4) {
    const double *p=s+n*stride;
    __m256d acc=_mm256_mul_pd(_mm256_set1_pd(h[mid]),
      _mm256_set_pd(p[3*stride+mid],p[2*stride+mid],p[stride+mid],p[mid]));
    for (i=0;i<mid;++i) {
      __m256d left,right;
      if (halfband && h[i]==0.0) continue;
      left=_mm256_set_pd(p[3*stride+i],p[2*stride+i],p[stride+i],p[i]);
      right=_mm256_set_pd(p[3*stride+taps-1-i],p[2*stride+taps-1-i],
                          p[stride+taps-1-i],p[taps-1-i]);
      acc=_mm256_add_pd(acc,_mm256_mul_pd(_mm256_set1_pd(h[i]),
                                           _mm256_add_pd(left,right)));
    }
    _mm256_storeu_pd(out+n,acc);
  }
  for (;n<frames;++n) out[n]=lsx_dsd_fir_scalar(h,taps,s+n*stride,halfband);
}

double lsx_dsd_fir_avx1_direct(const double *h,size_t taps,
    const double *s,int halfband)
{
  size_t i=0,mid=taps/2;
  double acc=h[mid]*s[mid],lanes[4];
  __m256d sums=_mm256_setzero_pd();
  if (halfband) return lsx_dsd_fir_scalar(h,taps,s,halfband);
  for (;i+4<=mid;i+=4) {
    __m256d left=_mm256_loadu_pd(s+i);
    __m256d right=_mm256_set_pd(s[taps-4-i],s[taps-3-i],
                                s[taps-2-i],s[taps-1-i]);
    sums=_mm256_add_pd(sums,_mm256_mul_pd(_mm256_loadu_pd(h+i),
                                         _mm256_add_pd(left,right)));
  }
  _mm256_storeu_pd(lanes,sums);
  acc+=lanes[0];acc+=lanes[1];acc+=lanes[2];acc+=lanes[3];
  for (;i<mid;++i) acc+=h[i]*(s[i]+s[taps-1-i]);
  return acc;
}

/* Normal SDM uses order-specialized register state and a serial, scalar-
 * ordered decision sum. Other orders retain the existing exact recurrence;
 * overlapping arguments and unusual FP environments use the scalar block. */

static int sdm_avx1_block(sdm_normal_t *s,const double *input,
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

const lsx_dsd_kernel lsx_dsd_kernel_avx1 = {
  "avx1", LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1,
  fir_avx1_block, lsx_dsd_fir_avx1_direct, sdm_avx1_block
};
