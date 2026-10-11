/* P11 SSE2: independent FIR output-time lanes and the state-coordinate SDM
 * formulation inherited from sdm_x86.h. No AVX instructions in this unit. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include "sdm_normal_commit_i.h"
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
static double sdm_sse2_math(const double *src, double *dst,
    const double *a, const double *g, double x, double y)
{
  __m128d s0=_mm_loadu_pd(src),s1=_mm_loadu_pd(src+2);
  __m128d s2=_mm_loadu_pd(src+4),s3=_mm_loadu_pd(src+6);
  __m128d tx=_mm_shuffle_pd(_mm_set1_pd(x-y),s0,1);
  __m128d t0=_mm_shuffle_pd(s0,s1,1);
  __m128d t1=_mm_shuffle_pd(s1,s2,1);
  __m128d t2=_mm_shuffle_pd(s2,s3,1);
  __m128d t3=_mm_shuffle_pd(s3,s3,1);
  __m128d v0,v1;
  s0=_mm_sub_pd(_mm_add_pd(s0,tx),_mm_mul_pd(t0,_mm_loadu_pd(g)));
  s1=_mm_sub_pd(_mm_add_pd(s1,t0),_mm_mul_pd(t1,_mm_loadu_pd(g+2)));
  s2=_mm_sub_pd(_mm_add_pd(s2,t1),_mm_mul_pd(t2,_mm_loadu_pd(g+4)));
  s3=_mm_sub_pd(_mm_add_pd(s3,t2),_mm_mul_pd(t3,_mm_loadu_pd(g+6)));
  _mm_storeu_pd(dst,s0);_mm_storeu_pd(dst+2,s1);
  _mm_storeu_pd(dst+4,s2);_mm_storeu_pd(dst+6,s3);
  v0=_mm_add_pd(_mm_mul_pd(s0,_mm_loadu_pd(a)),
                _mm_mul_pd(s2,_mm_loadu_pd(a+4)));
  v1=_mm_add_pd(_mm_mul_pd(s1,_mm_loadu_pd(a+2)),
                _mm_mul_pd(s3,_mm_loadu_pd(a+6)));
  v0=_mm_add_pd(v0,v1);
  v0=_mm_add_pd(v0,_mm_shuffle_pd(v0,v0,1));
  return x + _mm_cvtsd_f64(v0);
}

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
  for (i=0;i<frames;++i) {
    double *next=s->state[s->bank^1];
    double v;
    unsigned j;
    int bit,rc;
    if (!isfinite(input[i])) return lsx_sdm_normal_reject_nonfinite(s);
    if (peak && fabs(input[i])>*peak) *peak=fabs(input[i]);
    if (fabs(input[i])>envelope) return LSX_DSD_SDM_OVERLOAD;
    if (s->frames==UINT64_MAX) return LSX_DSD_SDM_FRAME_LIMIT;
    v=sdm_sse2_math(s->state[s->bank],next,a,g,input[i],s->previous_decision);
    for (j=order;j<8;++j) next[j]=0.0; /* no inactive-bank history */
    rc=lsx_sdm_normal_accept(s,input[i],v,order,&bit,bounds,coordinate);
    if (rc) return rc;
    output[i]=bit>0?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
    *committed=i+1;
  }
  return 0;
}

const lsx_dsd_kernel lsx_dsd_kernel_sse2 = {
  "sse2", LSX_DSD_CPU_SSE2, fir_sse2_block, lsx_dsd_fir_sse2_direct, sdm_sse2_block
};
