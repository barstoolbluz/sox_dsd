/* Private binary64 dB conversion shared by the gain effect and fixed DSD
 * headroom. Not part of the public SoX API; never export its symbols. */
#ifndef SOX_DSD_COREMATH_GAIN_H
#define SOX_DSD_COREMATH_GAIN_H

/* CORE-MATH binary64 exp10, vendored at coremath/exp10.c (MIT license). */
double cr_exp10(double);

static inline double dsd_coremath_gain_from_db(double db)
{
  /* Preserve both +0 and -0 as an exact, arithmetic-free unity factor. */
  if (db == 0.0)
    return 1.0;
  return cr_exp10(db / 20.0);
}

#endif
