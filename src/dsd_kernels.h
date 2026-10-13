/* P11 internal runtime-kernel interface. Not installed and not an ABI change.
 * All kernel implementations are built with contraction disabled. */
#ifndef LSX_DSD_KERNELS_H
#define LSX_DSD_KERNELS_H

#include <stddef.h>
#include <stdint.h>
#include "sdm.h"

/* The P06 one-window scalar reference remains callable on every host.
 * Oldest input sample is s[0], newest s[taps-1]. Odd tap count; center
 * first, then outer symmetric pairs in increasing index order. */
/* Internal production-bank specialization. Reads only s[0..56]; h must
 * be the reconstruction graph's 57-tap half-band bank. Fixed scalar order. */
double lsx_dsd_fir_halfband57(const double *h, const double *s);

double lsx_dsd_fir_scalar(const double *coeff, size_t taps,
                          const double *samples, int halfband);

/* A block reads windows rooted at input + i*stride (0<=i<frames), each
 * exactly taps doubles. Therefore the highest address read is
 * input[(frames-1)*stride+taps-1]. There are no speculative tail loads.
 * All inputs may be unaligned; output has exactly frames writable doubles.
 * The caller checks multiplication/addition overflow before supplying spans.
 * For frames==0 the pointers may be NULL and are never dereferenced.
 * FIR phase, history and endpoint completion remain caller-owned. */
typedef void (*lsx_dsd_fir_block_fn)(const double *coeff, size_t taps,
    const double *input, size_t frames, size_t stride, int halfband,
    double *output);
typedef double (*lsx_dsd_fir_single_fn)(const double *, size_t,
    const double *, int);

/* Normal/guarded (non-trellis) SDM. One call owns an entire block; each
 * committed frame advances exactly one state bank, frame index and monitor.
 * On error, committed is set to the complete prefix, bad_coordinate when
 * applicable; the failing sample is never committed. The caller must not
 * write an audio block after a failure. The state/profile is per channel. */
typedef int (*lsx_dsd_sdm_block_fn)(sdm_normal_t *state,
    const double *input, size_t frames, sox_sample_t *output,
    size_t *committed, const double bounds[8], unsigned *bad_coordinate,
    double envelope, double *peak);
/* Error codes are private to these block kernels. */
#define LSX_DSD_SDM_NONFINITE (-1)
#define LSX_DSD_SDM_BOUNDS    (-2)
#define LSX_DSD_SDM_OVERLOAD  (-3)
#define LSX_DSD_SDM_FRAME_LIMIT (-4)

enum lsx_dsd_kernel_family { LSX_DSD_FIR = 1, LSX_DSD_SDM = 2 };
enum lsx_dsd_kernel_feature { LSX_DSD_CPU_SSE2 = 1, LSX_DSD_CPU_AVX1 = 2,
  LSX_DSD_CPU_AVX2 = 4, LSX_DSD_CPU_FMA = 8,
  LSX_DSD_CPU_AVX512F = 16 };

typedef struct lsx_dsd_kernel {
  const char *name;
  unsigned required_features;
  lsx_dsd_fir_block_fn fir_block;
  lsx_dsd_fir_single_fn fir_single;
  lsx_dsd_sdm_block_fn sdm_block;
} lsx_dsd_kernel;

/* CPUID is injected for unit testing. Probes may return zero for a missing
 * leaf; max_leaf is checked before accessing leaf 1 or leaf 7. The XGETBV
 * callback is never invoked without all of XSAVE/OSXSAVE/AVX (leaf 1).
 * Non-x86 production builds return 0 without executing either instruction. */
typedef struct lsx_dsd_cpu_probe {
  void *opaque;
  unsigned (*cpuid)(void *opaque, unsigned leaf, unsigned subleaf,
                    unsigned regs[4]);
  uint64_t (*xgetbv)(void *opaque, unsigned index);
} lsx_dsd_cpu_probe;
unsigned lsx_dsd_features_probe(const lsx_dsd_cpu_probe *probe);
unsigned lsx_dsd_features_host(void);

/* requested is NULL or "auto", or a concrete "scalar", "sse2", "avx1", "avx2", "avx512".
 * If requested is NULL, the independent family environment variable is
 * read ONCE for this context: SOX_DSD_KERNEL_FIR / SOX_DSD_KERNEL_SDM.
 * The earlier LSX_DSD_FIR_KERNEL / LSX_DSD_SDM_KERNEL spellings are
 * compatibility aliases only, consulted if the matching SOX variable is unset.
 * Selection has no process-wide mutable cache. Unknown CPUs prefer SSE2 for
 * FIR, scalar for mastering SDM until a new kernel is qualified.
 * Returns 0, -1 for invalid name/family, -2 for unavailable tier. On error
 * *out is NULL and the caller must reject context creation. */
int lsx_dsd_kernel_select(enum lsx_dsd_kernel_family family,
    const char *requested, const lsx_dsd_kernel **out);
/* Same algorithm with injected capabilities, for deterministic tests. */
int lsx_dsd_kernel_select_features(enum lsx_dsd_kernel_family family,
    const char *requested, unsigned features, const lsx_dsd_kernel **out);

/* Link-visible candidates are referenced only from the baseline dispatcher.
 * AVX1 object is independently compiled without AVX2 or FMA, and never
 * entered without OSXSAVE/XCR0 checking. */
extern const lsx_dsd_kernel lsx_dsd_kernel_scalar;
#if defined(HAVE_DSD_SSE2)
extern const lsx_dsd_kernel lsx_dsd_kernel_sse2;
double lsx_dsd_fir_sse2_direct(const double *, size_t, const double *, int);
#endif
#if defined(HAVE_DSD_AVX1)
extern const lsx_dsd_kernel lsx_dsd_kernel_avx1;
double lsx_dsd_fir_avx1_direct(const double *, size_t, const double *, int);
#endif
#if defined(HAVE_DSD_AVX2)
extern const lsx_dsd_kernel lsx_dsd_kernel_avx2;
double lsx_dsd_fir_avx2_direct(const double *, size_t, const double *, int);
#endif

#if defined(HAVE_DSD_AVX512)
extern const lsx_dsd_kernel lsx_dsd_kernel_avx512;
double lsx_dsd_fir_avx512_direct(const double *, size_t, const double *, int);
#endif

#endif
