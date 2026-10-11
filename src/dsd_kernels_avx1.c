/* P11 AVX1: genuine independent AVX-only TU. Requires OSXSAVE, XCR0[2:1],
 * CPU AVX; NEVER compile with AVX2/FMA flags or whole-program -march=native. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include "sdm_normal_commit_i.h"
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

/* Same AVX double state-coordinate shuffle/reduction as the pre-P11 legacy
 * sdm_x86.h AVX branch, adapted to guarded P09 normal-state ownership. */
static double sdm_avx1_math(const double *src,double *dst,
    const double *a,const double *g,double x,double y)
{
  __m256d s0=_mm256_loadu_pd(src),s1=_mm256_loadu_pd(src+4);
  __m256d sx=_mm256_set1_pd(x-y);
  __m256d p0=_mm256_permute_pd(s0,5),p1=_mm256_permute_pd(s1,5);
  __m256d tx=_mm256_blend_pd(p0,_mm256_permute2f128_pd(sx,p0,0x21),0x5);
  __m256d t0=_mm256_blend_pd(p1,_mm256_permute2f128_pd(p0,p1,0x21),0x5);
  __m256d t1=_mm256_permute2f128_pd(tx,t0,0x21);
  __m256d t2=_mm256_blend_pd(p1,_mm256_permute2f128_pd(p1,p1,0x21),0xa);
  __m256d v0,v1;
  __m128d v;
  s0=_mm256_sub_pd(_mm256_add_pd(s0,tx),
                   _mm256_mul_pd(t1,_mm256_loadu_pd(g)));
  s1=_mm256_sub_pd(_mm256_add_pd(s1,t0),
                   _mm256_mul_pd(t2,_mm256_loadu_pd(g+4)));
  _mm256_storeu_pd(dst,s0);_mm256_storeu_pd(dst+4,s1);
  v0=_mm256_mul_pd(s0,_mm256_loadu_pd(a));
  v1=_mm256_mul_pd(s1,_mm256_loadu_pd(a+4));
  v0=_mm256_add_pd(v0,v1);
  v=_mm_add_pd(_mm256_castpd256_pd128(v0),_mm256_extractf128_pd(v0,1));
  v=_mm_add_pd(v,_mm_permute_pd(v,1));
  return x+_mm_cvtsd_f64(v);
}

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
  for (i=0;i<frames;++i) {
    double *next=s->state[s->bank^1];
    double v;
    unsigned j;
    int bit,rc;
    if (!isfinite(input[i])) return lsx_sdm_normal_reject_nonfinite(s);
    if (peak && fabs(input[i])>*peak) *peak=fabs(input[i]);
    if (fabs(input[i])>envelope) return LSX_DSD_SDM_OVERLOAD;
    if (s->frames==UINT64_MAX) return LSX_DSD_SDM_FRAME_LIMIT;
    v=sdm_avx1_math(s->state[s->bank],next,a,g,input[i],s->previous_decision);
    for (j=order;j<8;++j) next[j]=0.0;
    rc=lsx_sdm_normal_accept(s,input[i],v,order,&bit,bounds,coordinate);
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
