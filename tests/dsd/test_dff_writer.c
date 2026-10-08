/* P01: execute the production writer's private arithmetic and error paths.
 * Only the I/O calls below can fail synthetically. The writer itself is
 * included unchanged; the configured library supplies its ordinary I/O.
 * Container and audio truth are independently checked in reference/writer.py.
 */
#include "sox_i.h"

enum { AUDIO, BYTE, QWORD, SEEK, FLUSH, IO_COUNT };
static unsigned calls[IO_COUNT], fail_at[IO_COUNT], checks;

static int failing(unsigned kind)
{
  return ++calls[kind] == fail_at[kind];
}

static size_t write_audio(sox_format_t *ft, uint8_t *buf, size_t len)
{
  return failing(AUDIO) ? 0 : lsx_write_b_buf(ft, buf, len);
}
static int write_byte(sox_format_t *ft, unsigned value)
{
  return failing(BYTE) ? SOX_EOF : lsx_writeb(ft, value);
}
static int write_qword(sox_format_t *ft, uint64_t value)
{
  return failing(QWORD) ? SOX_EOF : lsx_writeqw(ft, value);
}
static int seek_output(sox_format_t *ft, off_t offset, int whence)
{
  return failing(SEEK) ? SOX_EOF : lsx_seeki(ft, offset, whence);
}
static int flush_output(sox_format_t *ft)
{
  return failing(FLUSH) ? EOF : lsx_flush(ft);
}

#define lsx_write_b_buf write_audio
#define lsx_writeb write_byte
#define lsx_writeqw write_qword
#define lsx_seeki seek_output
#define lsx_flush flush_output
/* Avoid exporting a second copy of the format registry symbols. */
#define lsx_dsdiff_format_fn p01_test_dsdiff_format_fn
#define lsx_wsd_format_fn p01_test_wsd_format_fn
#include "../../src/dsdiff.c"

#define CHECK(c) do { ++checks; if (!(c)) { \
  fprintf(stderr, "line %d: %s\n", __LINE__, #c); return 1; } } while (0)

static void reset_io(void)
{
  memset(calls, 0, sizeof(calls));
  memset(fail_at, 0, sizeof(fail_at));
}

static int setup(sox_format_t *ft, struct dsdiff *dff, unsigned channels)
{
  memset(ft, 0, sizeof(*ft));
  memset(dff, 0, sizeof(*dff));
  reset_io();
  ft->priv = dff;
  ft->fp = tmpfile();
  CHECK(ft->fp != NULL);
  ft->filename = (char *)"P01-unit-output";
  ft->mode = 'w';
  ft->seekable = sox_true;
  ft->signal.channels = channels;
  ft->signal.rate = 2822400;
  ft->encoding.reverse_bytes = MACHINE_IS_BIGENDIAN ? sox_option_no : sox_option_yes;
  return 0;
}

static int arithmetic(void)
{
  sox_format_t ft;
  struct dsdiff dff;
  uint64_t n, span = 0;
  for (n = 0; n < 64; ++n) {
    CHECK(dff_chunk_span(n, &span) == SOX_SUCCESS);
    CHECK(span == 12 + n + (n & 1));
  }
  CHECK(dff_chunk_span(UINT64_MAX - 13, &span) == SOX_SUCCESS);
  CHECK(span == UINT64_MAX - 1);
  CHECK(dff_chunk_span(UINT64_MAX - 14, &span) == SOX_SUCCESS);
  CHECK(span == UINT64_MAX - 1);
  for (n = 0; n <= 12; ++n) {
    span = 123;
    CHECK(dff_chunk_span(UINT64_MAX - n, &span) == SOX_EOF);
    CHECK(span == 123);
  }
  CHECK(setup(&ft, &dff, 1) == 0);
  dff.data_size = UINT64_MAX - 127; /* Largest representable mono file. */
  CHECK(dff_writeheader(&ft, sox_true) == SOX_SUCCESS);
  CHECK(lsx_tell(&ft) == 126);
  CHECK(fclose(ft.fp) == 0);
  CHECK(setup(&ft, &dff, 1) == 0);
  dff.data_size = UINT64_MAX - 126; /* External pad overflows FRM8 span. */
  CHECK(dff_writeheader(&ft, sox_true) == SOX_EOF);
  CHECK(lsx_tell(&ft) == 0);
  CHECK(fclose(ft.fp) == 0);
  return 0;
}

static int tails(void)
{
  unsigned channels, tail, i;
  sox_sample_t bits[8 * 6];
  for (i = 0; i < array_length(bits); ++i) bits[i] = -SOX_SAMPLE_MAX;
  for (channels = 1; channels <= 6; ++channels) {
    for (tail = 1; tail <= 7; ++tail) {
      sox_format_t ft;
      struct dsdiff dff;
      uint8_t audio[6];
      off_t start;
      CHECK(setup(&ft, &dff, channels) == 0);
      CHECK(dff_startwrite(&ft) == SOX_SUCCESS);
      for (i = 0; i < channels; ++i) CHECK(dff.buf[i] == 0);
      start = lsx_tell(&ft);
      CHECK(dff_write(&ft, bits, tail * channels) == tail * channels);
      CHECK(dff.bit_pos == tail && dff.data_size == 0);
      CHECK(dff_stopwrite(&ft) == SOX_SUCCESS);
      CHECK(dff.buf == NULL && dff.data_size == channels);
      CHECK(fseeko(ft.fp, start, SEEK_SET) == 0);
      CHECK(fread(audio, 1, channels, ft.fp) == channels);
      for (i = 0; i < channels; ++i)
        CHECK(audio[i] == (0x69 & (0xff >> tail)));
      CHECK(fclose(ft.fp) == 0);
    }
  }
  return 0;
}

static int errors(void)
{
  sox_format_t ft;
  struct dsdiff dff;
  sox_sample_t bits[16];
  unsigned i;
  for (i = 0; i < array_length(bits); ++i) bits[i] = SOX_SAMPLE_MAX;

  CHECK(setup(&ft, &dff, 1) == 0);
  fail_at[QWORD] = 1;
  CHECK(dff_startwrite(&ft) == SOX_EOF && dff.buf == NULL);
  CHECK(fclose(ft.fp) == 0);

  /* A failed cluster must not count as accepted samples, or be retried
   * during finalization after a caller already observed a short write. */
  for (i = 1; i <= 2; ++i) {
    CHECK(setup(&ft, &dff, 1) == 0);
    CHECK(dff_startwrite(&ft) == SOX_SUCCESS);
    reset_io(); fail_at[AUDIO] = i;
    CHECK(dff_write(&ft, bits, 16) == (i - 1) * 8);
    CHECK(dff.data_size == i - 1);
    CHECK(dff_write(&ft, bits, 8) == 0);
    CHECK(dff_stopwrite(&ft) == SOX_EOF);
    CHECK(calls[AUDIO] == i && calls[SEEK] == 0 && dff.buf == NULL);
    CHECK(fclose(ft.fp) == 0);
  }
  CHECK(setup(&ft, &dff, 1) == 0);
  CHECK(dff_startwrite(&ft) == SOX_SUCCESS);
  CHECK(dff_write(&ft, bits, 3) == 3);
  reset_io(); fail_at[AUDIO] = 1;
  CHECK(dff_write(&ft, bits, 5) == 0);
  CHECK(dff_stopwrite(&ft) == SOX_EOF && calls[AUDIO] == 1);
  CHECK(fclose(ft.fp) == 0);

  CHECK(setup(&ft, &dff, 1) == 0);
  CHECK(dff_startwrite(&ft) == SOX_SUCCESS);
  CHECK(dff_write(&ft, bits, 1) == 1);
  reset_io(); fail_at[AUDIO] = 1;
  CHECK(dff_stopwrite(&ft) == SOX_EOF && dff.data_size == 0);
  CHECK(calls[SEEK] == 0 && dff.buf == NULL);
  CHECK(fclose(ft.fp) == 0);

  /* Fail each distinct finalization I/O operation. */
  for (i = BYTE; i < IO_COUNT; ++i) {
    CHECK(setup(&ft, &dff, i == BYTE ? 1 : 2) == 0);
    CHECK(dff_startwrite(&ft) == SOX_SUCCESS);
    CHECK(dff_write(&ft, bits, i == BYTE ? 8 : 16) == (i == BYTE ? 8 : 16));
    reset_io(); fail_at[i] = 1;
    CHECK(dff_stopwrite(&ft) == SOX_EOF && dff.buf == NULL);
    CHECK(calls[i] == 1);
    if (i == BYTE) CHECK(calls[SEEK] == 0);
    CHECK(fclose(ft.fp) == 0);
  }
  CHECK(setup(&ft, &dff, 1) == 0);
  CHECK(dff_startwrite(&ft) == SOX_SUCCESS);
  reset_io(); fail_at[QWORD] = 7; /* Final empty audio-size field. */
  CHECK(dff_stopwrite(&ft) == SOX_EOF && dff.buf == NULL);
  CHECK(ft.seekable == sox_true && calls[QWORD] == 7);
  CHECK(fclose(ft.fp) == 0);
  CHECK(setup(&ft, &dff, 1) == 0);
  CHECK(dff_startwrite(&ft) == SOX_SUCCESS);
  dff.data_size = UINT64_MAX;
  reset_io();
  CHECK(dff_write(&ft, bits, 8) == 0);
  CHECK(dff.data_size == UINT64_MAX && calls[AUDIO] == 0);
  CHECK(dff_stopwrite(&ft) == SOX_EOF && calls[SEEK] == 0);
  CHECK(fclose(ft.fp) == 0);
  return 0;
}

int main(void)
{
  if (arithmetic() || tails() || errors()) return 1;
  printf("{\"checks\":%u,\"tail_cases\":42,\"io_failure_cases\":11,"
         "\"arithmetic\":\"pass\",\"tails\":\"pass\",\"errors\":\"pass\"}\n", checks);
  return 0;
}
