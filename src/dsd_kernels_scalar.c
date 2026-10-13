/* P06 binary64 reference kernel, no input gain, clipping or dithering. */
#include "sox_i.h"
#include "dsd_kernels.h"

#if defined(__clang__)
#pragma clang fp contract(off)
#define LSX_DSD_NO_CONTRACT
#elif defined(__GNUC__)
#define LSX_DSD_NO_CONTRACT __attribute__((optimize("fp-contract=off")))
#else
#pragma STDC FP_CONTRACT OFF
#define LSX_DSD_NO_CONTRACT
#endif

LSX_DSD_NO_CONTRACT
double lsx_dsd_fir_scalar(const double *h, size_t taps,
                          const double *s, int halfband)
{
  size_t i, mid = taps / 2;
  double acc = h[mid] * s[mid];
  for (i = 0; i < mid; ++i) {
    if (halfband && h[i] == 0.0) continue;
    acc += h[i] * (s[i] + s[taps - 1 - i]);
  }
  return acc;
}

/* The reconstruction graph's immutable 57-tap half-band bank has zero
 * even taps except the center. Keep the reference's center-first, ascending
 * odd-pair order, but remove per-tap zero tests and loop bookkeeping.
 * This is not a generic half-band kernel: callers must use that bank. */
LSX_DSD_NO_CONTRACT
double lsx_dsd_fir_halfband57(const double *h, const double *s)
{
  double acc = h[28] * s[28];
#define PAIR(i) acc += h[i] * (s[i] + s[56 - (i)])
  PAIR(1);  PAIR(3);  PAIR(5);  PAIR(7);
  PAIR(9);  PAIR(11); PAIR(13); PAIR(15);
  PAIR(17); PAIR(19); PAIR(21); PAIR(23);
  PAIR(25); PAIR(27);
#undef PAIR
  return acc;
}

static void fir_scalar_block(const double *h, size_t taps, const double *s,
    size_t frames, size_t stride, int halfband, double *out)
{
  size_t i;
  for (i = 0; i < frames; ++i)
    out[i] = lsx_dsd_fir_scalar(h,taps,s+i*stride,halfband);
}

static int sdm_scalar_block(sdm_normal_t *s, const double *input,
    size_t frames, sox_sample_t *out, size_t *committed,
    const double bounds[8], unsigned *coordinate,
    double envelope, double *peak)
{
  size_t i;
  if (committed) *committed = 0;
  if (!s || !s->profile || !committed || (frames && (!input || !out))) return -1;
  for (i=0;i<frames;++i) {
    int bit, rc;
    double x=input[i];
    if (!isfinite(x)) return sdm_normal_step_guarded(s,x,&bit,bounds,coordinate);
    if (peak && fabs(x)>*peak) *peak=fabs(x);
    if (fabs(x)>envelope) return LSX_DSD_SDM_OVERLOAD;
    if (s->frames==UINT64_MAX) return LSX_DSD_SDM_FRAME_LIMIT;
    rc=sdm_normal_step_guarded(s,x,&bit,bounds,coordinate);
    if (rc) return rc;
    out[i] = bit > 0 ? SOX_SAMPLE_MAX : -SOX_SAMPLE_MAX;
    *committed = i+1;
  }
  return 0;
}

const lsx_dsd_kernel lsx_dsd_kernel_scalar = {
  "scalar", 0, fir_scalar_block, lsx_dsd_fir_scalar, sdm_scalar_block
};
