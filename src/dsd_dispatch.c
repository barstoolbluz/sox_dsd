/* Baseline-ISA dispatcher. NEVER compile this TU with -mavx/-mavx2, LTO,
 * -march=native, or compiler flags enabling cross-target inlining. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include <float.h>
#include <stdlib.h>
#include <string.h>
#if defined(__i386__) || defined(__x86_64__)
#define LSX_DSD_X86 1
#if defined(__GNUC__) || defined(__clang__)
#include <cpuid.h>
#endif
#endif

#if defined(LSX_DSD_X86) && (defined(__GNUC__) || defined(__clang__))
static unsigned host_cpuid(void *opaque, unsigned leaf, unsigned subleaf,
                            unsigned r[4])
{
  unsigned maxleaf = __get_cpuid_max(0, NULL);
  (void)opaque;
  if (leaf > maxleaf) return 0;
  __cpuid_count(leaf, subleaf, r[0], r[1], r[2], r[3]);
  return 1;
}
static uint64_t host_xgetbv(void *opaque, unsigned index)
{
  unsigned a, d;
  (void)opaque;
  /* The only call site is guarded by CPUID.OSXSAVE. */
  __asm__ volatile ("xgetbv" : "=a" (a), "=d" (d) : "c" (index));
  return ((uint64_t)d << 32) | a;
}
#endif

unsigned lsx_dsd_features_probe(const lsx_dsd_cpu_probe *p)
{
  unsigned regs[4] = {0}, maxleaf, leaf1ecx, leaf1edx, features = 0;
  uint64_t xcr0;
  if (!p || !p->cpuid || !p->cpuid(p->opaque, 0, 0, regs)) return 0;
  maxleaf = regs[0];
  if (maxleaf < 1 || !p->cpuid(p->opaque, 1, 0, regs)) return 0;
  leaf1ecx = regs[2]; leaf1edx = regs[3];
  if (leaf1edx & (1u << 26)) features |= LSX_DSD_CPU_SSE2;
  /* AVX's YMM state is legal only when BOTH kernel and CPU support it.
   * Avoid XGETBV on machines which do not advertise OSXSAVE. */
  if ((leaf1ecx & ((1u<<26) | (1u<<27) | (1u<<28))) !=
      ((1u<<26) | (1u<<27) | (1u<<28)) || !p->xgetbv)
    return features;
  xcr0 = p->xgetbv(p->opaque, 0);
  if ((xcr0 & 0x6u) == 0x6u && (features & LSX_DSD_CPU_SSE2))
    features |= LSX_DSD_CPU_AVX1;
  /* FMA is a separately advertised capability, NOT a requirement for AVX2.
   * Only read leaf 7 when the CPU reports it and AVX OS state is enabled. */
  if ((features & LSX_DSD_CPU_AVX1) && (leaf1ecx & (1u << 12)))
    features |= LSX_DSD_CPU_FMA;
  if ((features & LSX_DSD_CPU_AVX1) && maxleaf >= 7 &&
      p->cpuid(p->opaque, 7, 0, regs) && (regs[1] & (1u << 5)))
    features |= LSX_DSD_CPU_AVX2;
  /* ZMM/opmask state is independent of AVX2: AVX-512F only needs leaf-7
   * bit 16 and XCR0 0xE6. Do not infer DQ/BW/VL or FMA availability. */
  if ((features & LSX_DSD_CPU_AVX1) && (xcr0 & UINT64_C(0xe6)) == UINT64_C(0xe6) &&
      maxleaf >= 7 && p->cpuid(p->opaque, 7, 0, regs) &&
      (regs[1] & (1u << 16)))
    features |= LSX_DSD_CPU_AVX512F;
  return features;
}

unsigned lsx_dsd_features_host(void)
{
#if defined(LSX_DSD_X86) && (defined(__GNUC__) || defined(__clang__))
  const lsx_dsd_cpu_probe ops = { NULL, host_cpuid, host_xgetbv };
  return lsx_dsd_features_probe(&ops);
#else
  return 0;
#endif
}

/* Selection is deterministic and paid for once when an encoder context is
 * created. The two tiers whose kernel cost is closest are chosen by rate;
 * higher rates favor the 512F implementation, and lower rates AVX2. No FMA
 * specialization is inferred from CPUID and no tier is selected unless its
 * object was actually built and its OS-managed register state is available.
 *
 * Rate is a policy input, not an ISA capability. The static ranking is a
 * measured default, not a claim that every CPU favors the same tier. */
static const char *sdm_auto_name(unsigned features, unsigned native_hz)
{
#if defined(__i386__) || FLT_EVAL_METHOD != 0
  /* x87 can retain extra precision; SIMD is not the scalar reference. */
  (void)features; (void)native_hz;
  return "scalar";
#else
#if defined(HAVE_DSD_AVX512)
  if (native_hz >= 22579200u &&
      (features & (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 |
                   LSX_DSD_CPU_AVX2 | LSX_DSD_CPU_AVX512F)) ==
                  (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 |
                   LSX_DSD_CPU_AVX2 | LSX_DSD_CPU_AVX512F))
    return "avx512";
#endif
#if defined(HAVE_DSD_AVX2)
  if ((features & (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 |
                   LSX_DSD_CPU_AVX2)) ==
                  (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 | LSX_DSD_CPU_AVX2))
    return "avx2";
#endif
#if defined(HAVE_DSD_AVX512)
  if ((features & (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 |
                   LSX_DSD_CPU_AVX2 | LSX_DSD_CPU_AVX512F)) ==
                  (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 |
                   LSX_DSD_CPU_AVX2 | LSX_DSD_CPU_AVX512F))
    return "avx512";
#endif
#if defined(HAVE_DSD_AVX1)
  if ((features & (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1)) ==
                  (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1))
    return "avx1";
#endif
#if defined(HAVE_DSD_SSE2)
  if (features & LSX_DSD_CPU_SSE2) return "sse2";
#endif
  (void)features; (void)native_hz;
  return "scalar";
#endif
}

static int select_features_at_rate(enum lsx_dsd_kernel_family family,
    const char *requested, unsigned features, unsigned native_hz,
    const lsx_dsd_kernel **out)
{
  const lsx_dsd_kernel *k = NULL;
  if (!out) return -1;
  *out = NULL;
  if (family != LSX_DSD_FIR && family != LSX_DSD_SDM) return -1;
  if (!requested || !*requested || !strcmp(requested, "auto")) {
    if (family == LSX_DSD_SDM) requested = sdm_auto_name(features,native_hz);
#if defined(HAVE_DSD_SSE2)
    else requested = (features & LSX_DSD_CPU_SSE2) ? "sse2" : "scalar";
#else
    else requested = "scalar";
#endif
  }
  if (!strcmp(requested, "scalar")) k = &lsx_dsd_kernel_scalar;
#if defined(HAVE_DSD_SSE2)
  else if (!strcmp(requested, "sse2")) k = &lsx_dsd_kernel_sse2;
#else
  else if (!strcmp(requested, "sse2")) return -2;
#endif
#if defined(HAVE_DSD_AVX1)
  else if (!strcmp(requested, "avx1")) k = &lsx_dsd_kernel_avx1;
#else
  else if (!strcmp(requested, "avx1")) return -2;
#endif
#if defined(HAVE_DSD_AVX2)
  else if (!strcmp(requested, "avx2")) k = &lsx_dsd_kernel_avx2;
#else
  else if (!strcmp(requested, "avx2")) return -2;
#endif
#if defined(HAVE_DSD_AVX512)
  else if (!strcmp(requested, "avx512")) k = &lsx_dsd_kernel_avx512;
#else
  else if (!strcmp(requested, "avx512")) return -2;
#endif
  /* Optional FMA specializations require independent qualification. */
  else if (!strcmp(requested, "avx512-fma")) return -2;
  /* Reserved optional specialization is not installed by the P12 baseline.
   * Never alias it to non-FMA code or treat CPUID.FMA as qualification. */
  else if (!strcmp(requested, "avx2-fma")) return -2;
  else return -1;
  if ((features & k->required_features) != k->required_features) return -2;
  if ((family == LSX_DSD_FIR && (!k->fir_block || !k->fir_single)) ||
      (family == LSX_DSD_SDM && !k->sdm_block)) return -2;
  *out = k;
  return 0;
}

int lsx_dsd_kernel_select_features(enum lsx_dsd_kernel_family family,
    const char *requested, unsigned features, const lsx_dsd_kernel **out)
{
  return select_features_at_rate(family,requested,features,0,out);
}

int lsx_dsd_kernel_select_sdm_rate_features(const char *requested,
    unsigned features, unsigned native_hz, const lsx_dsd_kernel **out)
{
  return select_features_at_rate(LSX_DSD_SDM,requested,features,native_hz,out);
}

static int select_host_rate(enum lsx_dsd_kernel_family family,
    const char *requested, unsigned native_hz, const lsx_dsd_kernel **out)
{
  const char *name = requested;
  if (!name) {
    /* Public SOX_DSD_KERNEL_* hooks are authoritative. The original P11
     * LSX_DSD_* spellings remain compatibility fallbacks only. Selection
     * snapshots the chosen name once at context creation, never per sample. */
    if (family == LSX_DSD_FIR) {
      name = getenv("SOX_DSD_KERNEL_FIR");
      if (!name) name = getenv("LSX_DSD_FIR_KERNEL");
    } else if (family == LSX_DSD_SDM) {
      name = getenv("SOX_DSD_KERNEL_SDM");
      if (!name) name = getenv("LSX_DSD_SDM_KERNEL");
    }
  }
  return select_features_at_rate(family,name,lsx_dsd_features_host(),native_hz,out);
}

int lsx_dsd_kernel_select(enum lsx_dsd_kernel_family family,
    const char *requested, const lsx_dsd_kernel **out)
{
  return select_host_rate(family,requested,0,out);
}

int lsx_dsd_kernel_select_sdm_rate(const char *requested,
    unsigned native_hz, const lsx_dsd_kernel **out)
{
  return select_host_rate(LSX_DSD_SDM,requested,native_hz,out);
}
