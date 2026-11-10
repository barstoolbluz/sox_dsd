/* Test-only MXCSR environment injector. Never linked into libsox_ng. */
#if (defined(__x86_64__) || defined(__i386__)) && defined(__SSE2__)
#include <xmmintrin.h>
#include <stdlib.h>
__attribute__((constructor)) static void inject_mxcsr(void)
{
  const char *value = getenv("PCM64_TEST_MXCSR_OR");
  if (value && *value)
    _mm_setcsr(_mm_getcsr() | (unsigned)strtoul(value, NULL, 0));
}
#endif
