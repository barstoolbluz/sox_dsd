/* P13 isolated AVX-512F baseline. AVX2 enabled by GCC -mavx512f; no AVX-512DQ/BW/VL or FMA required.
 * The eight FIR output times are independent; SDM vectorizes its eight
 * coordinates, NOT time. Built with -ffp-contract=off and -fno-lto. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include "sdm_normal_commit_i.h"
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

/* Every lane reads the old bank only. prev = [x-y,s0,...,s6],
 * successor = [s1,...,s7,s7]. The final g is zero in each supported
 * profile. Mask inactive state coordinates for orders 4..7. The reduction
 * pairs lanes (0,4),(1,5),(2,6),(3,7), then (0,2),(1,3), then (0,1):
 * the same explicit pairwise tree as the inherited AVX2 kernel. */
static double sdm_avx512_math(const double *src,double *dst,
    const double *a,const double *g,unsigned order,double x,double y)
{
  const __m512i prev_perm=_mm512_setr_epi64(0,0,1,2,3,4,5,6);
  const __m512i next_perm=_mm512_setr_epi64(1,2,3,4,5,6,7,7);
  const __m512i swap_halves=_mm512_setr_epi64(4,5,6,7,0,1,2,3);
  const __m512i swap_quarters=_mm512_setr_epi64(2,3,0,1,6,7,4,5);
  const __m512i swap_pairs=_mm512_setr_epi64(1,0,3,2,5,4,7,6);
  const __mmask8 active=(__mmask8)((1u<<order)-1u);
  __m512d old=_mm512_loadu_pd(src);
  __m512d prev=_mm512_permutexvar_pd(prev_perm,old);
  __m512d next=_mm512_permutexvar_pd(next_perm,old);
  __m512d state,weighted;
  prev=_mm512_mask_mov_pd(prev,0x01,_mm512_set1_pd(x-y));
  state=_mm512_sub_pd(_mm512_add_pd(old,prev),
                       _mm512_mul_pd(next,_mm512_loadu_pd(g)));
  state=_mm512_maskz_mov_pd(active,state);
  _mm512_storeu_pd(dst,state);
  weighted=_mm512_mul_pd(state,_mm512_loadu_pd(a));
  weighted=_mm512_add_pd(weighted,
                         _mm512_permutexvar_pd(swap_halves,weighted));
  weighted=_mm512_add_pd(weighted,
                         _mm512_permutexvar_pd(swap_quarters,weighted));
  weighted=_mm512_add_pd(weighted,
                         _mm512_permutexvar_pd(swap_pairs,weighted));
  return x+_mm_cvtsd_f64(_mm512_castpd512_pd128(weighted));
}

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
  for (i=0;i<frames;++i) {
    double *next=s->state[s->bank^1];
    double v, x=input[i];
    unsigned j;
    int bit,rc;
    if (!isfinite(x)) return lsx_sdm_normal_reject_nonfinite(s);
    if (peak && fabs(x)>*peak) *peak=fabs(x);
    if (fabs(x)>envelope) return LSX_DSD_SDM_OVERLOAD;
    if (s->frames==UINT64_MAX) return LSX_DSD_SDM_FRAME_LIMIT;
    v=sdm_avx512_math(s->state[s->bank],next,a,g,order,x,
                      s->previous_decision);
    for (j=order;j<8;++j) next[j]=0.0;
    rc=lsx_sdm_normal_accept(s,x,v,order,&bit,bounds,coordinate);
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
