/* Internal binary64 WAV entry points.  Not installed; no public format ABI. */
#ifndef LSX_PCM_F64_IO_H
#define LSX_PCM_F64_IO_H
#include "pcm_f64.h"
#include "sox_ng.h"
#include "sox_dsd.h"
sox_format_handler_t const *lsx_wav_format_fn(void);

typedef struct {
  pcm_f64_format stream;
  sox_encoding_t encoding;
  unsigned container_bits;
  unsigned valid_bits;
  uint32_t speaker_mask;
  bool has_speaker_mask;
  bool big_endian;
  bool extensible;
  uint64_t data_bytes;
} lsx_pcm_f64_wav_facts;

/* Queries the actual WAV handler state, never the filename extension or a
 * user-supplied encoding override. A successful query does not consume data. */
pcm_f64_status lsx_pcm_f64_wav_query(const sox_format_t *ft,
    lsx_pcm_f64_wav_facts *facts);
pcm_f64_progress lsx_pcm_f64_wav_read(sox_format_t *ft, pcm_f64_output out);
pcm_f64_progress lsx_pcm_f64_wav_write(sox_format_t *ft, pcm_f64_input in);

/* Phase 02B: built-in FLAC decoder integer ingress.  These are private
 * adapters, not a new FLAC format/parser or public sample representation.
 * Dynamic FLAC plugins are deliberately ineligible, even when they can be
 * opened by the legacy libSoX format registry. */
typedef struct {
  pcm_f64_format stream;
  unsigned bits_per_sample;     /* actual FLAC STREAMINFO width */
} lsx_pcm_f64_flac_facts;

pcm_f64_status lsx_pcm_f64_flac_query(const sox_format_t *ft,
    lsx_pcm_f64_flac_facts *facts);
pcm_f64_progress lsx_pcm_f64_flac_read(sox_format_t *ft, pcm_f64_output out);

/* FLAC handler-private, defined only when its built-in identity is linked.
 * The adapter guards both calls with formats.h's built-in FLAC condition. */
pcm_f64_status lsx_flac_native_facts(const sox_format_t *ft,
    lsx_pcm_f64_flac_facts *facts);
pcm_f64_status lsx_flac_native_decoder_state(const sox_format_t *ft,
    bool *at_eof);
/* Reader-owned, bounded scratch. Built-in only; may grow once per capacity.
 * The returned buffer remains valid until the next growth or close. */
sox_sample_t *lsx_flac_native_scratch(sox_format_t *ft, size_t samples);

/* Exact known-length, small RIFF/RIFX output ONLY. The writer is not exposed
 * to the CLI until the phase-specific qualification and native coordinator.
 * source and raw_source (if supplied) are checked against the actual
 * acquired output descriptor before any truncation.  report_path is also
 * checked for aliasing. Layout ownership remains with the WAV handler. */
sox_format_t *lsx_pcm_f64_wav_open_write(const char *path,
    const pcm_f64_format *format, sox_encoding_t encoding, unsigned bits,
    bool big_endian, const sox_dsd_layout_t *layout,
    const sox_format_t *source, FILE *raw_source, const char *report_path,
    sox_bool (*overwrite_permitted)(const char *filename));

/* WAV handler-private calls. Used only by the same-identity dispatch above
 * and the format-layer, descriptor-preserving native open implementation. */
pcm_f64_status lsx_wav_native_facts(const sox_format_t *,
    lsx_pcm_f64_wav_facts *);
pcm_f64_progress lsx_wav_native_read(sox_format_t *, pcm_f64_output);
pcm_f64_progress lsx_wav_native_write(sox_format_t *, pcm_f64_input);
pcm_f64_status lsx_wav_native_prepare_write(sox_format_t *, uint64_t, bool, uint32_t);

#endif
