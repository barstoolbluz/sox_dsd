/* Host ISA selection for the DSD executable qualification suite.
 * Use the production CPUID/XCR0 probe, not compile-time -march or /proc flags.
 * Compiler/build omissions on a capable host must fail, never become skips.
 */
#include "dsd_kernels.h"
#include <stdio.h>
#include <string.h>

struct tier {
  const char *name;
  unsigned required;
};

static const struct tier tiers[] = {
  {"scalar", 0},
  {"sse2", LSX_DSD_CPU_SSE2},
  {"avx1", LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1},
  {"avx2", LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 | LSX_DSD_CPU_AVX2},
  /* The compiled AVX-512F kernel also requires AVX2 (see its descriptor). */
  {"avx512", LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 |
             LSX_DSD_CPU_AVX2 | LSX_DSD_CPU_AVX512F}
};

static int runnable(const struct tier *tier, unsigned features)
{
  return (features & tier->required) == tier->required;
}

static int self_test(void)
{
  static const struct {
    unsigned features;
    unsigned count;
  } cases[] = {
    {0, 1},
    {LSX_DSD_CPU_SSE2, 2},
    {LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1, 3},
    {LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 | LSX_DSD_CPU_AVX2, 4},
    {LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 | LSX_DSD_CPU_AVX2 |
     LSX_DSD_CPU_AVX512F, 5},
    /* AVX-512F cannot execute this compiled kernel without AVX2. */
    {LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 | LSX_DSD_CPU_AVX512F, 3},
    /* FMA must never be required for these non-FMA kernels. */
    {LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 | LSX_DSD_CPU_AVX2 |
     LSX_DSD_CPU_FMA, 4}
  };
  unsigned i, j, count;
  for (i = 0; i < sizeof(cases)/sizeof(cases[0]); ++i) {
    count = 0;
    for (j = 0; j < sizeof(tiers)/sizeof(tiers[0]); ++j)
      count += runnable(&tiers[j], cases[i].features);
    if (count != cases[i].count) {
      fprintf(stderr, "FAIL host ISA mask self-test %u: got %u expected %u\n",
              i, count, cases[i].count);
      return 1;
    }
  }
  puts("PASS host ISA selection: scalar, SSE2, AVX1, AVX2, AVX-512F masks");
  return 0;
}

int main(int argc, char **argv)
{
  unsigned i, features;
  const lsx_dsd_kernel *k = NULL;
  if (argc == 2 && !strcmp(argv[1], "--self-test")) return self_test();
  if (argc != 2 || strcmp(argv[1], "--tiers")) {
    fputs("usage: dsd_test_host_isa --tiers | --self-test\n", stderr);
    return 2;
  }
  features = lsx_dsd_features_host();
  for (i = 0; i < sizeof(tiers)/sizeof(tiers[0]); ++i) {
    if (!runnable(&tiers[i], features)) {
      fprintf(stderr, "SKIP DSD ISA %s: CPU/OS register state unavailable\n",
              tiers[i].name);
      continue;
    }
    /* A runnable tier that the build cannot select is a hard failure.
     * Check both independent kernel families, including scalar. */
    if (lsx_dsd_kernel_select_features(LSX_DSD_FIR, tiers[i].name,
                                      features, &k) || !k ||
        lsx_dsd_kernel_select_features(LSX_DSD_SDM, tiers[i].name,
                                      features, &k) || !k) {
      fprintf(stderr, "FAIL DSD ISA %s: host supports tier but build cannot run it\n",
              tiers[i].name);
      return 1;
    }
    if (i) putchar(' ');
    fputs(tiers[i].name, stdout);
  }
  putchar('\n');
  return 0;
}
