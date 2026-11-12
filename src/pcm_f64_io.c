/* Private dispatch: accept the actual compiled WAV handler only. */
#include "sox_i.h"
#include "pcm_f64_io.h"

sox_format_handler_t const *lsx_wav_format_fn(void);

static bool is_wav(const sox_format_t *ft)
{
  const sox_format_handler_t *wav = lsx_wav_format_fn();
  return ft && ft->handler.startread == wav->startread &&
      ft->handler.startwrite == wav->startwrite &&
      ft->handler.priv_size == wav->priv_size;
}

pcm_f64_status lsx_pcm_f64_wav_query(const sox_format_t *ft,
    lsx_pcm_f64_wav_facts *facts)
{
  if (!ft || !facts) return PCM_F64_ARGUMENT;
  return is_wav(ft) ? lsx_wav_native_facts(ft, facts) : PCM_F64_UNSUPPORTED;
}

pcm_f64_progress lsx_pcm_f64_wav_read(sox_format_t *ft, pcm_f64_output out)
{
  pcm_f64_progress p = {0, 0, PCM_F64_UNSUPPORTED};
  if (!ft || ft->mode != 'r') p.status = PCM_F64_ARGUMENT;
  else if (is_wav(ft)) return lsx_wav_native_read(ft, out);
  return p;
}

pcm_f64_progress lsx_pcm_f64_wav_write(sox_format_t *ft, pcm_f64_input in)
{
  pcm_f64_progress p = {0, 0, PCM_F64_UNSUPPORTED};
  if (!ft || ft->mode != 'w') p.status = PCM_F64_ARGUMENT;
  else if (is_wav(ft)) return lsx_wav_native_write(ft, in);
  return p;
}

/* Only compiled-in FLAC has a provable handler and decoder identity.  Keep
 * this guard exactly aligned with the static registry in formats.h.  A plugin
 * is still usable through the ordinary libSoX read path, not this adapter. */
#if defined(HAVE_FLAC) && (defined(STATIC_FLAC) || !defined(HAVE_LIBLTDL))
#define PCM_F64_BUILTIN_FLAC 1
sox_format_handler_t const *lsx_flac_format_fn(void);
static bool is_builtin_flac(const sox_format_t *ft)
{
  const sox_format_handler_t *flac = lsx_flac_format_fn();
  return ft && ft->mode == 'r' && flac &&
      ft->handler.startread == flac->startread &&
      ft->handler.read == flac->read &&
      ft->handler.stopread == flac->stopread &&
      ft->handler.priv_size == flac->priv_size;
}
#else
#define PCM_F64_BUILTIN_FLAC 0
#endif

pcm_f64_status lsx_pcm_f64_flac_query(const sox_format_t *ft,
    lsx_pcm_f64_flac_facts *facts)
{
  if (!ft || !facts) return PCM_F64_ARGUMENT;
#if PCM_F64_BUILTIN_FLAC
  if (is_builtin_flac(ft)) {
    pcm_f64_status status = pcm_f64_check_dsp_env();
    if (status != PCM_F64_OK) return status;
    return lsx_flac_native_facts(ft, facts);
  }
#endif
  return PCM_F64_UNSUPPORTED;
}

pcm_f64_progress lsx_pcm_f64_flac_read(sox_format_t *ft, pcm_f64_output out)
{
  pcm_f64_progress result = {0, 0, PCM_F64_UNSUPPORTED};
#if PCM_F64_BUILTIN_FLAC
  lsx_pcm_f64_flac_facts facts;
  uint64_t already, remaining;
  bool eof = false;
  /* Borrow up to 4096 frames of codec integer words, retained by the FLAC
   * reader across calls. Bounded by libFLAC's eight-channel maximum; avoids
   * repeated decoder leftover allocations without a large stack frame. */
  if (!ft || ft->mode != 'r') {
    result.status = PCM_F64_ARGUMENT;
    return result;
  }
  result.status = lsx_pcm_f64_flac_query(ft, &facts);
  if (result.status != PCM_F64_OK) return result;
  result.status = pcm_f64_validate_output(&facts.stream, out);
  if (result.status != PCM_F64_OK) return result;
  if (ft->olength % facts.stream.channels) {
    result.status = PCM_F64_STATE;
    return result;
  }
  already = ft->olength / facts.stream.channels;
  if (facts.stream.length_known && already >= facts.stream.total_frames) {
    result.status = already == facts.stream.total_frames ?
        PCM_F64_DONE : PCM_F64_STATE;
    return result;
  }
  result.status = lsx_flac_native_decoder_state(ft, &eof);
  if (result.status != PCM_F64_OK) return result;
  if (eof) {
    result.status = facts.stream.length_known ? PCM_F64_IO : PCM_F64_DONE;
    return result;
  }
  if (!out.capacity_frames) {
    result.status = PCM_F64_NEED_OUTPUT;
    return result;
  }
  remaining = out.capacity_frames;
  if (facts.stream.length_known &&
      remaining > facts.stream.total_frames - already)
    remaining = facts.stream.total_frames - already;
  while (remaining) {
    size_t frames = (size_t)min(remaining, UINT64_C(4096));
    size_t requested = frames * facts.stream.channels;
    size_t got, i;
    sox_sample_t *words;
    /* sox_read is the existing built-in FLAC decoder and transports exact
     * left-aligned signed integer PCM, not float-quantized audio.  Each
     * codec code is mapped to its 32-bit SoX carrier without rounding. */
    if (pcm_f64_check_dsp_env() != PCM_F64_OK) {
      result.status = PCM_F64_UNSUPPORTED;
      return result;
    }
    words = lsx_flac_native_scratch(ft, requested);
    if (!words) {
      result.status = PCM_F64_IO;
      return result;
    }
    got = sox_read(ft, words, requested);
    result.status = lsx_flac_native_decoder_state(ft, &eof);
    if (result.status != PCM_F64_OK || got % facts.stream.channels) {
      result.status = PCM_F64_IO;
      return result;
    }
    /* The dyadic factor is exactly representable.  All 32-bit signed
     * values convert to double exactly (53 mantissa bits), including
     * INT32_MIN, INT32_MAX and a single low-order bit.  Unlike division by
     * INT32_MAX there is no asymmetric endpoint or rounding error. */
    for (i = 0; i < got; ++i)
      out.data[result.produced_frames * facts.stream.channels + i] =
          (double)words[i] * 0x1p-31;
    result.produced_frames += got / facts.stream.channels;
    already += got / facts.stream.channels;
    remaining -= got / facts.stream.channels;
    if (got < requested) {
      result.status = facts.stream.length_known &&
          already != facts.stream.total_frames ? PCM_F64_IO :
          (eof ? PCM_F64_DONE : PCM_F64_IO);
      return result;
    }
  }
  result.status = facts.stream.length_known &&
      already == facts.stream.total_frames ? PCM_F64_DONE : PCM_F64_OK;
#else
  (void)ft;
  (void)out;
#endif
  return result;
}
