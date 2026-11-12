/* Phase 02B: actual built-in FLAC reader probe, linked against libSoX.
 * The sample oracle is separate, in io_flac.py, not in this program. */
#include "sox_i.h"
#include "pcm_f64_io.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int length_arg(const char *s, size_t *value)
{
  char *end;
  unsigned long n;
  if (!s || !*s || *s == '-' || *s == '+') return 0;
  errno = 0;
  n = strtoul(s, &end, 10);
  if (errno || *end || !n || n > 4096) return 0;
  *value = (size_t)n;
  return 1;
}

int main(int argc, char **argv)
{
  sox_format_t *in = NULL;
  lsx_pcm_f64_flac_facts f;
  pcm_f64_progress p;
  const char *mode;
  size_t block = 31, n, total = 0, i;
  sox_sample_t legacy[4096 * 8];
  double output[4096 * 8];
  int rc = 1;
  if (argc < 2) return 2;
  mode = argv[1];
  if (!strcmp(mode, "capabilities")) {
#if defined(HAVE_FLAC) && (defined(STATIC_FLAC) || !defined(HAVE_LIBLTDL))
    puts("linkage=builtin");
#elif defined(HAVE_FLAC)
    puts("linkage=plugin");
#else
    puts("linkage=absent");
#endif
    printf("native_dsp=%s\n", pcm_f64_status_name(pcm_f64_check_dsp_env()));
    return 0;
  }
  if (argc < 3 || argc > 4 || (argc == 4 && !length_arg(argv[3], &block)))
    return 2;
  if (sox_init() != SOX_SUCCESS) return 1;
  in = sox_open_read(argv[2], NULL, NULL, "flac");
  if (!in) {
    fprintf(stderr, "FLAC open failed\n");
    goto done;
  }
  if (!strcmp(mode, "legacy")) {
    size_t ch = in->signal.channels;
    size_t count = block * ch;
    if (!ch || ch > 8) goto done;
    for (;;) {
      n = sox_read(in, legacy, count);
      if (in->sox_errno) goto done;
      if (n && fwrite(legacy, sizeof(sox_sample_t), n, stdout) != n)
        goto done;
      total += n;
      if (n < count) break;
    }
    rc = 0;
    goto done;
  }
  p.status = lsx_pcm_f64_flac_query(in, &f);
  if (!strcmp(mode, "capability")) {
    printf("status=%s\n", pcm_f64_status_name(p.status));
    rc = 0;
    goto done;
  }
  if (p.status != PCM_F64_OK) {
    fprintf(stderr, "native FLAC unsupported: %s\n",
        pcm_f64_status_name(p.status));
    goto done;
  }
  if (!strcmp(mode, "query")) {
    printf("rate=%u channels=%u bits=%u known=%u frames=%" PRIu64 "\n",
        f.stream.rate_hz, f.stream.channels, f.bits_per_sample,
        (unsigned)f.stream.length_known, f.stream.total_frames);
    rc = 0;
    goto done;
  }
  if (!strcmp(mode, "zero")) {
    double word = 123.0;
    p = lsx_pcm_f64_flac_read(in, (pcm_f64_output){&word,0});
    if (p.status != PCM_F64_NEED_OUTPUT || p.produced_frames != 0 ||
        p.consumed_frames || word != 123.0 || in->olength) goto done;
    p = lsx_pcm_f64_flac_read(in, (pcm_f64_output){output,1});
    if (p.produced_frames != 1 || p.consumed_frames ||
        (p.status != PCM_F64_OK && p.status != PCM_F64_DONE) ||
        in->olength != f.stream.channels) goto done;
    p = lsx_pcm_f64_flac_read(in, (pcm_f64_output){NULL,0});
    if (p.produced_frames || p.consumed_frames ||
        (p.status != PCM_F64_NEED_OUTPUT && p.status != PCM_F64_DONE)) goto done;
    rc = 0;
    goto done;
  }
  if (!strcmp(mode, "mixed")) {
    /* Private ingress uses the same decoder, so a legacy read can proceed
     * after it without a second codec, lost samples, or a hidden reset. */
    if (f.stream.total_frames < 3 || f.stream.channels > 8) goto done;
    p = lsx_pcm_f64_flac_read(in, (pcm_f64_output){output,1});
    if (p.produced_frames != 1 ||
        sox_read(in, legacy, f.stream.channels) != f.stream.channels ||
        sox_seek(in, 0, SOX_SEEK_SET) != SOX_SUCCESS) goto done;
    p = lsx_pcm_f64_flac_read(in, (pcm_f64_output){output+f.stream.channels,1});
    if (p.produced_frames != 1 ||
        memcmp(output, output+f.stream.channels, f.stream.channels*sizeof(double)))
      goto done;
    rc = 0;
    goto done;
  }
  if (strcmp(mode, "dump")) { rc = 2; goto done; }
  for (;;) {
    p = lsx_pcm_f64_flac_read(in, (pcm_f64_output){output,block});
    if (p.consumed_frames || p.produced_frames > block ||
        (p.produced_frames && fwrite(output, f.stream.channels*sizeof(double),
                                     p.produced_frames, stdout) != p.produced_frames))
      goto done;
    total += p.produced_frames;
    if (p.status == PCM_F64_DONE) break;
    if (p.status != PCM_F64_OK || p.produced_frames == 0) {
      fprintf(stderr, "native FLAC read failed: %s after %zu frames\n",
          pcm_f64_status_name(p.status), total);
      goto done;
    }
  }
  if (f.stream.length_known && total != f.stream.total_frames) goto done;
  p = lsx_pcm_f64_flac_read(in, (pcm_f64_output){output,block});
  if (p.status != PCM_F64_DONE || p.produced_frames || p.consumed_frames)
    goto done;
  rc = 0;
done:
  if (in && sox_close(in) != SOX_SUCCESS) rc = 1;
  if (sox_quit() != SOX_SUCCESS) rc = 1;
  if (rc) fprintf(stderr, "flac probe %s failed\n", mode);
  return rc;
}
