/* Test-only call through the actual compiled FIR implementation.
 * Compile with --gc-sections to omit unrelated SDM entrypoints. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "dsd_kernels.h"
#include "pcmdsd_coeffs.h"
int main(void)
{
  unsigned rate;
  int count=0;
  while (scanf("%u", &rate)==1) {
    const double *h;
    size_t n,i;
    double samples[77];
    if (rate==64) {h=lsx_pcmdsd_coeff_master64_256;n=61;}
    else if (rate==128) {h=lsx_pcmdsd_coeff_master128;n=77;}
    else return 2;
    for (i=0;i<n;i++) if (scanf("%la", &samples[i])!=1 ||
         !isfinite(samples[i])) return 2;
    printf("%a\n", lsx_dsd_fir_scalar(h,n,samples,0));
    ++count;
  }
  return count ? 0:2;
}
