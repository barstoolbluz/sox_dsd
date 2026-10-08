/* P03 seek contract integration probe. Sequential decoded samples serve as
 * comparison for random-access slices; the Python side supplies independent
 * file bytes, formats and chronology and records every invocation. */
#include "sox_ng.h"
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_SAMPLES (1024U * 1024U)
#define READ_CAP (63U * 6U)

static int failure(const char *where, uint64_t at, size_t got, size_t want)
{
  fprintf(stderr, "seek-contract: %s at sample %" PRIu64 ": %zu != %zu\n",
          where, at, got, want);
  return 1;
}

static sox_format_t *open_with_channels(const char *path,
                                       const char *type, unsigned channels)
{
  if (strcmp(type, "raw")) return sox_open_read(path, NULL, NULL, NULL);
  else {
    sox_signalinfo_t signal = {44100, 0, 16, 0, NULL};
    sox_encodinginfo_t encoding;
    signal.channels = channels;
    sox_init_encodinginfo(&encoding);
    encoding.bits_per_sample = 16;
    encoding.encoding = SOX_ENCODING_SIGN2;
    return sox_open_read(path, &signal, &encoding, "raw");
  }
}

static int check_rejected(sox_format_t *f, uint64_t target)
{
  uint64_t const logical = f->olength;
  /* The files used by this test are ordinary file-backed inputs. */
  long const physical = ftell((FILE *)f->fp);
  int rc = sox_seek(f, target, SOX_SEEK_SET);
  if (rc == SOX_SUCCESS || f->olength != logical ||
      ftell((FILE *)f->fp) != physical)
    return failure("rejected seek moved the stream", target, rc, SOX_EOF);
  return 0;
}

/* The sequential decoder is NOT an oracle for empty DFF with trailing
 * metadata: it would also read MANF bytes if the handler were defective.
 * Python constructs these zero-audio fixtures without the SoX writer. */
static int run_empty_dff(const char *path, unsigned expected_channels)
{
  sox_format_t *f = open_with_channels(path, "auto", expected_channels);
  sox_sample_t buf[READ_CAP];
  unsigned i;
  int result = 1;
  if (!f) {
    fprintf(stderr, "seek-contract: cannot open empty DFF: %s\n", path);
    return 1;
  }
  if (f->signal.channels != expected_channels || f->signal.length != 0 ||
      f->olength != 0) {
    fprintf(stderr, "seek-contract: invalid zero-audio DFF header/position\n");
    goto out;
  }
  for (i = 0; i < 3; ++i) {
    if (sox_read(f, buf, READ_CAP) != 0 || f->olength != 0) {
      fprintf(stderr, "seek-contract: zero-audio DFF returned metadata as audio\n");
      goto out;
    }
    if (sox_seek(f, 0, SOX_SEEK_SET) != SOX_SUCCESS || f->olength != 0) {
      fprintf(stderr, "seek-contract: zero-audio DFF rewind failed\n");
      goto out;
    }
  }
  if (sox_read(f, buf, READ_CAP) != 0 || f->olength != 0) {
    fprintf(stderr, "seek-contract: zero-audio DFF returned audio after rewind\n");
    goto out;
  }
  printf("{\"result\":\"empty-dff\",\"frames\":0,\"channels\":%u,\"rewinds\":3}\n",
         expected_channels);
  result = 0;
out:
  if (sox_close(f) != SOX_SUCCESS)
    result = 1;
  return result;
}

static int run(const char *path, const char *type, unsigned expected_channels,
               int unsupported)
{
  sox_format_t *ref = NULL, *f = NULL;
  sox_sample_t *audio = NULL, buf[READ_CAP];
  size_t total = 0, n, checked = 0, cases = 0;
  unsigned channels;
  uint64_t frames, target;
  int result = 1;
  size_t i;
  static unsigned const positions[] = {0, 1, 3, 7, 8, 9, 15, 17, 32, 63, 96, 320};

  ref = open_with_channels(path, type, expected_channels);
  f = open_with_channels(path, type, expected_channels);
  if (!ref || !f) { fprintf(stderr, "seek-contract: open failed: %s\n", path); goto out; }
  channels = f->signal.channels;
  if (!channels || channels != expected_channels) {
    fprintf(stderr, "seek-contract: unexpected channel count %u\n", channels); goto out;
  }
  audio = malloc(MAX_SAMPLES * sizeof(*audio));
  if (!audio) goto out;
  while (total < MAX_SAMPLES) {
    size_t cap = READ_CAP - READ_CAP % channels;
    if (cap > MAX_SAMPLES - total) cap = MAX_SAMPLES - total;
    cap -= cap % channels;
    if (!cap) break;
    n = sox_read(ref, audio + total, cap);
    if (!n) break;
    total += n;
  }
  if (total == MAX_SAMPLES || total % channels ||
      (ref->signal.length && ref->signal.length != SOX_UNKNOWN_LEN &&
       total != ref->signal.length)) {
    fprintf(stderr, "seek-contract: invalid sequential oracle count %zu\n", total);
    goto out;
  }
  frames = total / channels;

  if (unsupported) {
    uint64_t pos;
    size_t initial = frames < 5 ? total : 5 * channels;
    if (sox_read(f, buf, initial) != initial) goto out;
    pos = f->olength;
    if (check_rejected(f, channels * 2)) goto out;
    n = sox_read(f, buf, channels);
    if (n != (pos < total ? channels : 0) ||
        (n && memcmp(buf, audio + pos, n * sizeof(*buf))))
      goto out;
    printf("{\"result\":\"unsupported\",\"frames\":%" PRIu64 ",\"channels\":%u}\n", frames, channels);
    result = 0;
    goto out;
  }

  /* Repeatedly decode to EOF, then seek backward and forward across both
   * local cache boundaries and distant positions in longer codec streams. */
  for (i = 0; i < sizeof(positions)/sizeof(positions[0]) + 7; ++i) {
    size_t const fixed = sizeof(positions)/sizeof(positions[0]);
    uint64_t frame = i < fixed ? positions[i] :
      i == fixed     ? frames / 2 :
      i == fixed + 1 ? frames / 4 :
      i == fixed + 2 ? (frames > 2048 ? frames - 2048 : frames / 3) :
      i == fixed + 3 ? frames / 8 :
      i == fixed + 4 ? (frames ? frames - 1 : 0) :
      i == fixed + 5 ? frames : 0;
    uint64_t request;
    size_t first = frames > 11 ? 11 * channels : total;
    size_t pos;
    if (frame > frames) continue;
    /* All non-final positions alternate aligned/unaligned public offsets. */
    target = frame * channels;
    request = target + ((i & 1) && frame < frames ? channels - 1 : 0);
    if (sox_read(f, buf, first) > first) goto out;
    if (sox_seek(f, request, SOX_SEEK_SET) != SOX_SUCCESS)
      { result = failure("legal seek rejected", request, 1, 0); goto out; }
    if (f->olength != target)
      { result = failure("logical position after seek", request, f->olength, target); goto out; }
    if (sox_read(f, buf, 0) != 0 || f->olength != target) goto out;
    pos = (size_t)target;
    while (pos < total) {
      size_t cap = READ_CAP - READ_CAP % channels;
      if (cap > total - pos) cap = total - pos;
      n = sox_read(f, buf, cap);
      if (!n || n > cap || memcmp(buf, audio + pos, n * sizeof(*buf)))
        { result = failure("sequential / random seek samples", pos, n, cap); goto out; }
      pos += n;
      checked += n;
    }
    if (sox_read(f, buf, channels) || f->olength != total) goto out;
    ++cases;
  }

  if (sox_seek(f, 0, SOX_SEEK_SET) ||
      sox_read(f, buf, frames ? channels : 0) != (frames ? channels : 0)) goto out;
  if (f->signal.length && f->signal.length != SOX_UNKNOWN_LEN &&
      f->signal.length <= UINT64_MAX - channels &&
      check_rejected(f, f->signal.length + channels)) goto out;
  if (check_rejected(f, UINT64_MAX)) goto out;
  /* The rejected target must not evict unread samples from a decoder cache. */
  if (frames > 1) {
    uint64_t next = f->olength;
    n = sox_read(f, buf, channels);
    if (n != channels || memcmp(buf, audio + next, n * sizeof(*buf)))
      { result = failure("samples after rejected seek", next, n, channels); goto out; }
  }
  {
    unsigned saved = f->signal.channels;
    f->signal.channels = 0;
    if (check_rejected(f, 0)) goto out;
    f->signal.channels = saved;
  }
  if (!strcmp(type, "raw")) {
    /* No known bound: prove that the byte-offset helper rejects overflow
     * without narrowing UINT64_MAX to off_t or moving the file. */
    uint64_t known_length = f->signal.length;
    f->signal.length = SOX_UNSPEC;
    if (check_rejected(f, UINT64_MAX - UINT64_MAX % channels)) goto out;
    f->signal.length = known_length;
  }
  printf("{\"result\":\"pass\",\"frames\":%" PRIu64
         ",\"channels\":%u,\"seeks\":%zu,\"compared_samples\":%zu}\n",
         frames, channels, cases, checked);
  result = 0;
out:
  if (f) sox_close(f);
  if (ref) sox_close(ref);
  free(audio);
  return result;
}

int main(int argc, char **argv)
{
  int rc;
  char *end;
  unsigned long channels;
  if (argc != 5) {
    fputs("usage: dsd_test_seek_contract PATH auto|raw CHANNELS supported|unsupported|empty-dff\n", stderr);
    return 2;
  }
  channels = strtoul(argv[3], &end, 10);
  if (*end || channels < 1 || channels > 6 ||
      (strcmp(argv[4], "supported") && strcmp(argv[4], "unsupported") &&
       strcmp(argv[4], "empty-dff"))) return 2;
  if (sox_init() != SOX_SUCCESS) return 3;
  rc = !strcmp(argv[4], "empty-dff") ?
    run_empty_dff(argv[1], (unsigned)channels) :
    run(argv[1], argv[2], (unsigned)channels, !strcmp(argv[4], "unsupported"));
  if (sox_quit() != SOX_SUCCESS && rc == 0) rc = 4;
  return rc;
}
