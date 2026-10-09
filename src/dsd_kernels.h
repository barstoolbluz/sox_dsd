/* P06 private scalar FIR contract (not installed, no public dispatch yet). */
#ifndef LSX_DSD_KERNELS_H
#define LSX_DSD_KERNELS_H
#include <stddef.h>

/* samples[0] is the oldest, samples[taps-1] the newest, both numeric doubles.
 * Fixed order: center contribution first, then symmetric outer pairs inwards.
 * Half-band skips the exact structural zero coefficients. Compiler contraction
 * is disabled for this baseline. Rounding mode and FP environment are inherited;
 * no flush-to-zero or other process-wide FP state is changed. */
double lsx_dsd_fir_scalar(const double *coeff, size_t taps,
                          const double *samples, int halfband);
#endif
