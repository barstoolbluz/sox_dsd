/* P12 AVX2 baseline: all AVX2-only operations are local to this isolated TU.
 * Four FIR output TIMES are independent; a normal SDM's eight coordinates
 * are parallel but its successive time samples are NEVER independent.
 * Compile with -mavx2 -mno-fma -ffp-contract=off -fno-lto. No FMA path. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include "sdm_normal_commit_i.h"
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

/* Canonical eight-coordinate normal SDM state recurrence, with neighbor
 * vectors constructed by FULL-WIDTH AVX2 64-bit lane permutation.
 * prev0=[x-y,s0,s1,s2], next0=[s1,s2,s3,s4]
 * prev1=[s3,s4,s5,s6], next1=[s5,s6,s7,s6] (g[7] is inactive).
 * s3/s4 are the explicitly handled cross-vector boundary elements.
 * Preserve multiply, add, subtract ordering; no contraction permitted. */
static double sdm_avx2_math(const double *src,double *dst,
    const double *a,const double *g,double x,double y)
{
  __m256d old0=_mm256_loadu_pd(src),old1=_mm256_loadu_pd(src+4);
  __m256d prev0,prev1,next0,next1,state0,state1,weighted,swap;
  prev0=_mm256_blend_pd(
      _mm256_permute4x64_pd(old0,_MM_SHUFFLE(2,1,0,0)),
      _mm256_set1_pd(x-y),1);
  next0=_mm256_blend_pd(
      _mm256_permute4x64_pd(old0,_MM_SHUFFLE(3,3,2,1)),
      _mm256_permute4x64_pd(old1,0),8);
  prev1=_mm256_blend_pd(
      _mm256_permute4x64_pd(old1,_MM_SHUFFLE(2,1,0,0)),
      _mm256_permute4x64_pd(old0,0xff),1);
  next1=_mm256_permute4x64_pd(old1,_MM_SHUFFLE(2,3,2,1));
  state0=_mm256_sub_pd(_mm256_add_pd(old0,prev0),
                       _mm256_mul_pd(next0,_mm256_loadu_pd(g)));
  state1=_mm256_sub_pd(_mm256_add_pd(old1,prev1),
                       _mm256_mul_pd(next1,_mm256_loadu_pd(g+4)));
  _mm256_storeu_pd(dst,state0);
  _mm256_storeu_pd(dst+4,state1);
  weighted=_mm256_add_pd(_mm256_mul_pd(state0,_mm256_loadu_pd(a)),
                         _mm256_mul_pd(state1,_mm256_loadu_pd(a+4)));
  /* Identical reduction tree to the AVX1 2x128 horizontal sum, but the
   * 256-bit cross-half shuffle is a single AVX2 full-width permutation. */
  swap=_mm256_permute4x64_pd(weighted,0x4e);
  weighted=_mm256_add_pd(weighted,swap);
  swap=_mm256_permute4x64_pd(weighted,0xb1);
  weighted=_mm256_add_pd(weighted,swap);
  return x+_mm_cvtsd_f64(_mm256_castpd256_pd128(weighted));
}

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
  for (i=0;i<frames;++i) {
    double *next=s->state[s->bank^1];
    double v;
    unsigned j;
    int bit,rc;
    if (!isfinite(input[i])) return lsx_sdm_normal_reject_nonfinite(s);
    if (peak && fabs(input[i])>*peak) *peak=fabs(input[i]);
    if (fabs(input[i])>envelope) return LSX_DSD_SDM_OVERLOAD;
    if (s->frames==UINT64_MAX) return LSX_DSD_SDM_FRAME_LIMIT;
    v=sdm_avx2_math(s->state[s->bank],next,a,g,input[i],s->previous_decision);
    for (j=order;j<8;++j) next[j]=0.0;
    rc=lsx_sdm_normal_accept(s,input[i],v,order,&bit,bounds,coordinate);
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
