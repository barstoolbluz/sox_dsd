/* Private IEEE binary64 PCM mechanics. No public ABI or codec dependency. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "pcm_f64.h"

#include <float.h>
#include <fenv.h>
#include <limits.h>
#include <math.h>
#include <string.h>

#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
#include <xmmintrin.h>
#endif

#ifndef PCM_F64_NATIVE_ENABLED
#define PCM_F64_NATIVE_ENABLED 0
#endif

static bool valid_bits(unsigned bits)
{
  return bits == 8 || bits == 16 || bits == 24 || bits == 32;
}

static bool valid_format(const pcm_f64_format *f)
{
  return f && f->rate_hz != 0 && f->channels >= 1 && f->channels <= 64 &&
      (f->length_known || f->total_frames == 0);
}

pcm_f64_status pcm_f64_format_init(pcm_f64_format *f, uint32_t rate,
    uint32_t channels, bool known, uint64_t frames)
{
  if (!f || !rate || !channels || channels > 64) return PCM_F64_ARGUMENT;
  f->rate_hz = rate;
  f->channels = channels;
  f->length_known = known;
  f->total_frames = known ? frames : 0;
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_frame_storage(size_t frames, uint32_t channels,
    size_t *samples, size_t *bytes)
{
  size_t n;
  if (!channels || channels > 64 || !samples || !bytes)
    return PCM_F64_ARGUMENT;
  if (frames > SIZE_MAX / channels) return PCM_F64_LIMIT;
  n = frames * (size_t)channels;
  if (n > SIZE_MAX / sizeof(double)) return PCM_F64_LIMIT;
  *samples = n;
  *bytes = n * sizeof(double);
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_validate_input(const pcm_f64_format *f,
    pcm_f64_input in)
{
  size_t ns, nb;
  pcm_f64_status status;
  if (!valid_format(f) || (!in.data && in.frames)) return PCM_F64_ARGUMENT;
  status = pcm_f64_frame_storage(in.frames, f->channels, &ns, &nb);
  if (status != PCM_F64_OK) return status;
  if (f->length_known && (uint64_t)in.frames > f->total_frames)
    return PCM_F64_LIMIT;
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_validate_output(const pcm_f64_format *f,
    pcm_f64_output out)
{
  size_t ns, nb;
  pcm_f64_status status;
  if (!valid_format(f) || (!out.data && out.capacity_frames))
    return PCM_F64_ARGUMENT;
  status = pcm_f64_frame_storage(out.capacity_frames, f->channels, &ns, &nb);
  if (status != PCM_F64_OK) return status;
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_advance(const pcm_f64_format *f,
    uint64_t previous, size_t extra, uint64_t *next)
{
  uint64_t delta;
  if (!valid_format(f) || !next) return PCM_F64_ARGUMENT;
#if SIZE_MAX > UINT64_MAX
  if (extra > UINT64_MAX) return PCM_F64_LIMIT;
#endif
  delta = (uint64_t)extra;
  if (UINT64_MAX - previous < delta) return PCM_F64_LIMIT;
  if (f->length_known && (previous > f->total_frames ||
      delta > f->total_frames - previous)) return PCM_F64_LIMIT;
  *next = previous + delta;
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_count_samples(uint64_t frames,
    uint32_t channels, uint64_t *samples)
{
  if (!samples || !channels || channels > 64) return PCM_F64_ARGUMENT;
  if (frames > UINT64_MAX / channels) return PCM_F64_LIMIT;
  *samples = frames * (uint64_t)channels;
  return PCM_F64_OK;
}

bool pcm_f64_is_failure(pcm_f64_status code)
{
  return code >= PCM_F64_ARGUMENT && code <= PCM_F64_STATE;
}

pcm_f64_status pcm_f64_latch(pcm_f64_failure *s, pcm_f64_status code)
{
  if (!s) return PCM_F64_ARGUMENT;
  if (pcm_f64_is_failure(s->failed)) return s->failed;
  if (s->failed != PCM_F64_OK || code > PCM_F64_STATE || code < PCM_F64_OK)
    return PCM_F64_ARGUMENT;
  if (pcm_f64_is_failure(code)) s->failed = code;
  return s->failed;
}

const char *pcm_f64_status_name(pcm_f64_status status)
{
  switch (status) {
  case PCM_F64_OK: return "OK";
  case PCM_F64_NEED_INPUT: return "NEED_INPUT";
  case PCM_F64_NEED_OUTPUT: return "NEED_OUTPUT";
  case PCM_F64_DONE: return "DONE";
  case PCM_F64_ARGUMENT: return "ARGUMENT";
  case PCM_F64_UNSUPPORTED: return "UNSUPPORTED";
  case PCM_F64_NUMERIC: return "NUMERIC";
  case PCM_F64_IO: return "IO";
  case PCM_F64_LIMIT: return "LIMIT";
  case PCM_F64_STATE: return "STATE";
  }
  return "UNKNOWN";
}

pcm_f64_status pcm_f64_check_ieee_storage(void)
{
#if CHAR_BIT != 8 || FLT_RADIX != 2 || DBL_MANT_DIG != 53 || \
    DBL_MIN_EXP != -1021 || DBL_MAX_EXP != 1024
  return PCM_F64_UNSUPPORTED;
#else
  /* Check the actual binary64 bit convention; integer word operations never
   * perform FP evaluation, including for signaling NaN payloads. */
  static const double one = 1.0;
  uint64_t raw;
  if (sizeof(double) != sizeof(uint64_t)) return PCM_F64_UNSUPPORTED;
  memcpy(&raw, &one, sizeof(raw));
  return raw == UINT64_C(0x3ff0000000000000) ?
      PCM_F64_OK : PCM_F64_UNSUPPORTED;
#endif
}

pcm_f64_status pcm_f64_check_dsp_env(void)
{
#if !PCM_F64_NATIVE_ENABLED || !defined(FLT_EVAL_METHOD) || FLT_EVAL_METHOD != 0
  return PCM_F64_UNSUPPORTED;
#else
  if (pcm_f64_check_ieee_storage() != PCM_F64_OK)
    return PCM_F64_UNSUPPORTED;
  if (fegetround() != FE_TONEAREST) return PCM_F64_NUMERIC;
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
  {
    unsigned int mxcsr = _mm_getcsr();
    unsigned short x87_cw;
    /* Six masked SSE traps, no flush-to-zero/denormals-are-zero, nearest.
     * Also reject non-nearest or unmasked x87 controls (a library may use x87).
     * Exception *flags* (MXCSR low 6) and x87 status are intentionally ignored. */
    __asm__ __volatile__("fnstcw %0" : "=m"(x87_cw));
    if ((mxcsr & 0x1f80u) != 0x1f80u ||
        (mxcsr & (0x6000u | 0x8000u | 0x0040u)) != 0 ||
        (x87_cw & 0x003fu) != 0x003fu ||
        (x87_cw & 0x0c00u) != 0)
      return PCM_F64_NUMERIC;
    return PCM_F64_OK;
  }
#elif defined(__aarch64__) && (defined(__GNUC__) || defined(__clang__))
  {
    uint64_t fpcr;
    /* FPCR: RMode[23:22], FZ[24], FZ16[19]; trap enables[12:8,15].
     * FP exception flags are in FPSR and are not a cause for refusal. */
    __asm__ __volatile__("mrs %0, fpcr" : "=r"(fpcr));
    if (fpcr & (UINT64_C(3) << 22 | UINT64_C(1) << 24 |
                UINT64_C(1) << 19 | UINT64_C(0x9f00)))
      return PCM_F64_NUMERIC;
    return PCM_F64_OK;
  }
#else
  /* Portable C has no FTZ/DAZ or mask query. Fail closed for native DSP. */
  return PCM_F64_UNSUPPORTED;
#endif
#endif
}

pcm_f64_status pcm_f64_classify(const double *value, pcm_f64_word_class *kind)
{
  uint64_t bits, exponent, fraction;
  if (!value || !kind) return PCM_F64_ARGUMENT;
  if (pcm_f64_check_ieee_storage() != PCM_F64_OK)
    return PCM_F64_UNSUPPORTED;
  memcpy(&bits, value, sizeof(bits));
  exponent = (bits >> 52) & UINT64_C(0x7ff);
  fraction = bits & UINT64_C(0xfffffffffffff);
  if (exponent != UINT64_C(0x7ff)) *kind = PCM_F64_WORD_FINITE;
  else if (!fraction) *kind = PCM_F64_WORD_INFINITY;
  else if (fraction & (UINT64_C(1) << 51)) *kind = PCM_F64_WORD_QNAN;
  else *kind = PCM_F64_WORD_SNAN;
  return PCM_F64_OK;
}

static pcm_f64_status require_finite(const double *v)
{
  pcm_f64_word_class kind;
  pcm_f64_status s = pcm_f64_classify(v, &kind);
  if (s != PCM_F64_OK) return s;
  return kind == PCM_F64_WORD_FINITE ? PCM_F64_OK : PCM_F64_NUMERIC;
}

pcm_f64_status pcm_f64_copy_finite(double *dst, const double *src,
    size_t count, size_t *bad_index)
{
  size_t i;
  pcm_f64_status s;
  if (bad_index) *bad_index = SIZE_MAX;
  if (count && (!src || !dst)) return PCM_F64_ARGUMENT;
  if (count > SIZE_MAX / sizeof(double)) return PCM_F64_LIMIT;
  for (i = 0; i < count; ++i) {
    s = require_finite(src + i);
    if (s != PCM_F64_OK) {
      if (bad_index) *bad_index = i;
      return s;
    }
  }
  if (count && dst != src) memcpy(dst, src, count * sizeof(double));
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_normalize_signed(int32_t code, unsigned bits,
    double *result)
{
  int64_t bound;
  if (!result || !valid_bits(bits)) return PCM_F64_ARGUMENT;
  bound = INT64_C(1) << (bits - 1);
  if ((int64_t)code < -bound || (int64_t)code >= bound)
    return PCM_F64_ARGUMENT;
  *result = ldexp((double)code, -(int)(bits - 1));
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_normalize_u8(uint8_t code, double *result)
{
  if (!result) return PCM_F64_ARGUMENT;
  return pcm_f64_normalize_signed((int32_t)code - 128, 8, result);
}

pcm_f64_status pcm_f64_normalize_aligned32(int32_t code, double *result)
{
  if (!result) return PCM_F64_ARGUMENT;
  *result = ldexp((double)code, -31);
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_fixed_gain(double *dst, const double *src,
    size_t count, double gain, size_t *bad_index)
{
  size_t i;
  pcm_f64_status s;
  if (bad_index) *bad_index = SIZE_MAX;
  if (count && (!dst || !src)) return PCM_F64_ARGUMENT;
  if (count > SIZE_MAX / sizeof(double)) return PCM_F64_LIMIT;
  s = require_finite(&gain);
  if (s != PCM_F64_OK) return s;
  /* Prevalidate the entire source before arithmetic: never signal on sNaN,
   * and never begin output if a later sample has an invalid source word. */
  for (i = 0; i < count; ++i) {
    s = require_finite(src + i);
    if (s != PCM_F64_OK) {
      if (bad_index) *bad_index = i;
      return s;
    }
  }
  if (gain == 1.0) {
    if (count && dst != src) memcpy(dst, src, count * sizeof(double));
    return PCM_F64_OK;
  }
  for (i = 0; i < count; ++i) {
    double product = src[i] * gain;
    s = require_finite(&product);
    if (s != PCM_F64_OK) {
      if (bad_index) *bad_index = i;
      return PCM_F64_NUMERIC;
    }
    dst[i] = product;
  }
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_nominal_excursion(double value, bool *outside)
{
  pcm_f64_status s;
  if (!outside) return PCM_F64_ARGUMENT;
  s = require_finite(&value);
  if (s != PCM_F64_OK) return s;
  *outside = value >= 1.0 || value < -1.0;
  return PCM_F64_OK;
}

pcm_f64_status pcm_f64_quantize_int(double value, unsigned bits,
    int32_t *aligned32, bool *saturated)
{
  bool negative;
  uint64_t magnitude, limit, aligned;
  double abs_value, whole, fraction;
  pcm_f64_status s;
  if (!aligned32 || !saturated || !valid_bits(bits))
    return PCM_F64_ARGUMENT;
  s = require_finite(&value);
  if (s != PCM_F64_OK) return s;
  *saturated = false;
  negative = signbit(value) != 0;
  abs_value = fabs(value);
  limit = UINT64_C(1) << (bits - 1);
  /* Saturate before scaling, so extreme finite words never overflow, and
   * x=-1 maps exactly to the representable negative endpoint. */
  if (abs_value >= 1.0) {
    if (negative) {
      magnitude = limit;
      /* A negative nominal excursion may still round exactly to the
       * representable minimum. Saturation starts at the OUT-OF-RANGE
       * half-step, not simply when x < -1. The threshold is a representable
       * binary64 dyadic for all supported widths. */
      *saturated = abs_value >= 1.0 + ldexp(1.0, -(int)bits);
    } else {
      magnitude = limit - 1;
      *saturated = true;
    }
  } else {
    /* Multiplication by a positive power of two is exact here. modf splits
     * that exact dyadic value without the false half-tie caused by adding
     * 0.5 before floor. The integer is at most 2^31, exactly represented. */
    fraction = modf(ldexp(abs_value, (int)bits - 1), &whole);
    magnitude = (uint64_t)whole;
    if (fraction >= 0.5) ++magnitude;  /* ties go AWAY from zero */
    if (!negative && magnitude >= limit) {
      magnitude = limit - 1;
      *saturated = true;
    }
  }
  aligned = magnitude * (UINT64_C(1) << (32 - bits));
  /* Magnitude is <= 2^31. Signed conversion happens only AFTER negation in
   * int64, avoiding implementation-defined unsigned-to-negative conversion. */
  *aligned32 = (int32_t)(negative ? -(int64_t)aligned : (int64_t)aligned);
  return PCM_F64_OK;
}
