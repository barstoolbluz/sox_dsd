/* P00: executable SoX API observer. This program never defines expected audio.
 * Probe stdout is machine-readable; the independent Python test owns truth.
 */
#include "sox_ng.h"
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BUF_SAMPLES 8192U
#define HEAD_SAMPLES 8192U
#define MAX_READ_SAMPLES 10000000ULL

static int parse_u64(const char *text, uint64_t *out)
{
  char *end;
  unsigned long long v;
  if (!text || !*text || *text == '-') return -1;
  errno = 0;
  v = strtoull(text, &end, 10);
  if (errno || *end || end == text) return -1;
  *out = (uint64_t)v;
  return (unsigned long long)*out != v ? -1 : 0;
}

static int write_all(const char *file, uint64_t channels, uint64_t frames)
{
  sox_sample_t buffer[BUF_SAMPLES];
  sox_signalinfo_t signal = {2822400, 0, 1, 0, NULL};
  sox_encodinginfo_t enc;
  sox_format_t *f;
  uint64_t left;
  size_t i;
  int status;
  if (channels < 1 || channels > 100 || frames > (UINT64_MAX / channels) ||
      (channels * frames) > MAX_READ_SAMPLES) return 4;
  signal.channels = (unsigned)channels;
  signal.length = channels * frames;
  sox_init_encodinginfo(&enc);
  enc.encoding = SOX_ENCODING_DSD;
  enc.bits_per_sample = 1;
  f = sox_open_write(file, &signal, &enc, "dff", NULL, NULL);
  if (!f) return 5;
  for (i = 0; i < BUF_SAMPLES; ++i) buffer[i] = -SOX_SAMPLE_MAX;
  left = signal.length;
  while (left) {
    size_t n = left < BUF_SAMPLES ? (size_t)left : BUF_SAMPLES;
    n -= n % (size_t)channels;
    if (!n || sox_write(f, buffer, n) != n) {
      sox_close(f); return 6;
    }
    left -= n;
  }
  status = sox_close(f);
  printf("{\"write_ok\":%s,\"frames\":%" PRIu64 ",\"channels\":%" PRIu64 "}\n",
         status == SOX_SUCCESS ? "true" : "false", frames, channels);
  return status == SOX_SUCCESS ? 0 : 7;
}

static int read_all(const char *file, size_t cap, size_t initial,
                    int do_seek, uint64_t seek_offset, int fix_core)
{
  sox_sample_t buf[BUF_SAMPLES];
  sox_format_t *f;
  size_t n, first = 0, nbits = 0, calls = 0;
  uint64_t total = 0, pos = 0;
  char head[HEAD_SAMPLES + 1];
  int seek_rc = 0;
  if (cap > BUF_SAMPLES || initial > BUF_SAMPLES) return 4;
  f = sox_open_read(file, NULL, NULL, NULL);
  if (!f) {
    puts("{\"open\":false}");
    return 0;
  }
  if (initial) first = sox_read(f, buf, initial);
  if (do_seek) {
    seek_rc = sox_seek(f, seek_offset, SOX_SEEK_SET);
    pos = f->olength;
    /* Diagnostic-only override: isolate format-private state from the
       separately known stale generic position. Never change production. */
    if (fix_core && seek_rc == SOX_SUCCESS) f->olength = seek_offset;
  }
  if (cap == 0) {
    n = sox_read(f, buf, 0);
    calls++;
    total += n;
  } else {
    while (total < MAX_READ_SAMPLES) {
      n = sox_read(f, buf, cap);
      calls++;
      if (!n) break;
      if (total + n > MAX_READ_SAMPLES) { sox_close(f); return 8; }
      for (size_t i = 0; i < n && nbits < HEAD_SAMPLES; ++i)
        head[nbits++] = buf[i] > 0 ? '1' : '0';
      total += n;
    }
    if (total == MAX_READ_SAMPLES) { sox_close(f); return 9; }
  }
  head[nbits] = 0;
  printf("{\"open\":true,\"length\":%" PRIu64 ",\"channels\":%u,"
         "\"rate\":%.0f,\"first_read\":%zu,\"seek_rc\":%d,"
         "\"olength_after_seek\":%" PRIu64 ",\"remaining_returned\":%" PRIu64 ","
         "\"read_calls\":%zu,\"head_bits\":\"%s\"}\n",
         (uint64_t)f->signal.length, f->signal.channels, f->signal.rate,
         first, seek_rc, pos, total, calls, head);
  return sox_close(f) == SOX_SUCCESS ? 0 : 10;
}

/* P01: write independently supplied interleaved 0/1 bytes in whole-frame
 * calls. No expected payload or completion pattern exists in this observer. */
static int write_bits(const char *file, const char *source, unsigned channels,
                      size_t call_frames)
{
  uint8_t bits[BUF_SAMPLES];
  sox_sample_t buffer[BUF_SAMPLES];
  sox_signalinfo_t signal = {2822400, 0, 1, 0, NULL};
  sox_encodinginfo_t enc;
  sox_format_t *f;
  FILE *input;
  size_t count, pos = 0, i;
  int status;
  if (!channels || channels > 6 || !call_frames ||
      call_frames > BUF_SAMPLES / channels) return 4;
  input = fopen(source, "rb");
  if (!input) return 4;
  count = fread(bits, 1, sizeof(bits), input);
  status = ferror(input) || fgetc(input) != EOF || count % channels;
  fclose(input);
  if (status) return 4;
  for (i = 0; i < count; ++i) {
    if (bits[i] > 1) return 4;
    buffer[i] = bits[i] ? SOX_SAMPLE_MAX : -SOX_SAMPLE_MAX;
  }
  signal.channels = channels;
  signal.length = count;
  sox_init_encodinginfo(&enc);
  enc.encoding = SOX_ENCODING_DSD;
  enc.bits_per_sample = 1;
  f = sox_open_write(file, &signal, &enc, "dff", NULL, NULL);
  if (!f) return 5;
  while (pos < count) {
    size_t n = count - pos;
    if (n > call_frames * channels) n = call_frames * channels;
    if (sox_write(f, buffer + pos, n) != n) { sox_close(f); return 6; }
    pos += n;
  }
  status = sox_close(f);
  printf("{\"write_ok\":%s,\"samples\":%zu,\"channels\":%u}\n",
         status == SOX_SUCCESS ? "true" : "false", count, channels);
  return status == SOX_SUCCESS ? 0 : 7;
}

int main(int argc, char **argv)
{
  uint64_t a, b, c, offset = 0;
  int rc;
  if (argc < 2 || sox_init() != SOX_SUCCESS) return 2;
  if (!strcmp(argv[1], "write") && argc == 5) {
    if (parse_u64(argv[3], &a) || parse_u64(argv[4], &b)) return 3;
    rc = write_all(argv[2], a, b);
  } else if (!strcmp(argv[1], "read") && argc == 7) {
    if (parse_u64(argv[3], &a) || parse_u64(argv[4], &b) ||
        parse_u64(argv[6], &c)) return 3;
    if (strcmp(argv[5], "-") && parse_u64(argv[5], &offset)) return 3;
    if (a > BUF_SAMPLES || b > BUF_SAMPLES || c > 1) return 3;
    rc = read_all(argv[2], (size_t)a, (size_t)b,
                  strcmp(argv[5], "-") != 0, offset, (int)c);
  } else if (!strcmp(argv[1], "write-bits") && argc == 6) {
    if (parse_u64(argv[4], &a) || parse_u64(argv[5], &b) ||
        a > 6 || b > BUF_SAMPLES) return 3;
    rc = write_bits(argv[2], argv[3], (unsigned)a, (size_t)b);
  } else {
    fputs("usage: dsd_test_io write PATH CHANNELS FRAMES | read PATH CAP INITIAL OFFSET|- FIX_CORE | write-bits PATH INPUT CHANNELS CALL_FRAMES\n", stderr);
    rc = 2;
  }
  if (sox_quit() != SOX_SUCCESS && rc == 0) rc = 11;
  return rc;
}
