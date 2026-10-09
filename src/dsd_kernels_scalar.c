/* P06 binary64 reference kernel, no input gain, clipping or dithering. */
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
  /* Outer-pair-first order is part of the scalar reference definition. */
  for (i = 0; i < mid; ++i) {
    if (halfband && h[i] == 0.0)
      continue;
    acc += h[i] * (s[i] + s[taps - 1 - i]);
  }
  return acc;
}
