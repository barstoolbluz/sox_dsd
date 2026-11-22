/* Test-only probe of the same private helper and COMPILED production
 * CORE-MATH object. Never link this into the shipped library or export ABI. */
#include "dsd_coremath_gain.h"
#include <fenv.h>
#include <float.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifdef __SSE__
#include <xmmintrin.h>
#endif

#pragma STDC FENV_ACCESS ON

#if FLT_RADIX != 2 || DBL_MANT_DIG != 53 || FLT_EVAL_METHOD != 0
#error CORE-MATH test needs strict binary64 evaluation
#endif

static uint64_t bits(double x)
{
  uint64_t v;
  memcpy(&v, &x, sizeof(v));
  return v;
}

int main(void)
{
  char mode;
  uint64_t raw;
  volatile double a = 1.0 + 0x1p-27;
  volatile double b = 1.0 - 0x1p-27;
  volatile double sub = 0x1p-1074;
  if (fegetround() != FE_TONEAREST || sub * 1.0 == 0.0 ||
      fma(a, b, -1.0) != -0x1p-54) {
    fputs("CORE-MATH fenv, subnormal, or FMA premise failed\n", stderr);
    return 2;
  }
#ifdef __SSE__
  if (_mm_getcsr() & ((1u << 15) | (1u << 6))) {
    fputs("CORE-MATH x86 FTZ/DAZ enabled\n", stderr);
    return 2;
  }
#endif
  while (scanf(" %c %" SCNx64, &mode, &raw) == 2) {
    double parsed, applied, x, factor;
    memcpy(&parsed, &raw, sizeof(parsed));
    if (mode != 'g' && mode != 'h')
      return 3;
    applied = mode == 'h' ? -parsed : parsed;
    x = applied / 20.0;
    factor = dsd_coremath_gain_from_db(applied);
    printf("%c %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
        mode, raw, bits(x), bits(factor));
  }
  if (ferror(stdin))
    return 4;
  return 0;
}
