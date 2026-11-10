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
