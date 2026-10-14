/* P15 qualification-only binary64 exporter, not a DSP implementation.
 * Feed caller-supplied, chronological interleaved native 0/1 bits into the
 * public DSD decoder. No one-bit input synthesis or independent reference
 * mathematics live here. stdout = native little-endian binary64 frames.
 * stderr carries the selected real FIR kernel and successful frame counts.
 *
 * Usage: native_hz pcm_hz mastering|wideband kernel channels frames chunk [preserve|sacd]
 * stdin: frames * channels bytes, each byte EXACTLY 0 or 1.
 */
#include "sox_dsd.h"
#include "dsd_decode.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <limits.h>
#include <errno.h>

#define MAX_CH 8u
#define OUT_CAP 4096u
#define MAX_FRAMES UINT64_C(50000000)

static int fail(const char *where)
{
  fprintf(stderr,"P15 instrument ERROR: %s\n",where);
  return 1;
}
static int parse(const char *s, unsigned long long *v)
{
  char *end;
  unsigned long long n;
  if (!s || !*s || *s=='-' || *s=='+' || *s==' ') return 0;
  errno=0;
  n=strtoull(s,&end,10);
  if (errno || !*s || *end) return 0;
  *v=n;
  return 1;
}
static int emit(const double *p, size_t frames, unsigned channels)
{
  return fwrite(p,sizeof(*p)*channels,frames,stdout)==frames;
}
int main(int argc, char **argv)
{
  unsigned long long a[5];
  unsigned channels, chunk;
  uint32_t native, output;
  uint64_t total, produced=0, accepted=0;
  unsigned char *bits=NULL;
  sox_sample_t *source=NULL;
  double *pcm=NULL;
  sox_dsd_decoder_t *decoder=NULL;
  sox_dsd_decode_options_t cfg;
  sox_dsd_report_t report;
  const char *profile, *tier, *real_tier;
  int status=1;
  const uint16_t endian=1;
  if ((argc!=8 && argc!=9) || *(const unsigned char *)&endian!=1)
    return fail("usage/endian: native pcm profile tier channels frames chunk [level]; little-endian required");
  if (!parse(argv[1],&a[0]) || !parse(argv[2],&a[1]) ||
      !parse(argv[5],&a[2]) || !parse(argv[6],&a[3]) || !parse(argv[7],&a[4]) ||
      a[0]>UINT32_MAX || a[1]>UINT32_MAX || !a[2] || a[2]>MAX_CH ||
      a[3]>MAX_FRAMES || !a[4] || a[4]>65536)
    return fail("invalid numeric arguments");
  native=(uint32_t)a[0];output=(uint32_t)a[1];channels=(unsigned)a[2];
  total=(uint64_t)a[3];chunk=(unsigned)a[4];
  profile=argv[3];tier=argv[4];
  if (strcmp(profile,"mastering") && strcmp(profile,"wideband"))
    return fail("invalid profile");
  if (strcmp(tier,"scalar") && strcmp(tier,"sse2") && strcmp(tier,"avx1") &&
      strcmp(tier,"avx2") && strcmp(tier,"avx512"))
    return fail("invalid forced FIR tier");
  bits=malloc((size_t)chunk*channels);
  source=malloc((size_t)chunk*channels*sizeof(*source));
  pcm=malloc((size_t)OUT_CAP*channels*sizeof(*pcm));
  if (!bits || !source || !pcm) goto done;
  sox_dsd_decode_options_init_extended(&cfg);
  cfg.native_hz=native;cfg.output_hz=output;cfg.channels=channels;
  cfg.profile=!strcmp(profile,"mastering")?SOX_DSD_DECODE_MASTERING:SOX_DSD_DECODE_WIDEBAND;
  cfg.kernel_fir=tier;
  if (argc==9) {
    if (!strcmp(argv[8],"sacd")) cfg.level=SOX_DSD_LEVEL_SACD;
    else if (strcmp(argv[8],"preserve")) goto done;
  }
  if (sox_dsd_decoder_create(&cfg,&decoder)!=SOX_DSD_OK) {
    fprintf(stderr,"P15 instrument UNSUPPORTED tier=%s native=%u output=%u\n",tier,native,output);
    goto done;
  }
  real_tier=lsx_dsd_decoder_kernel_name(decoder);
  if (!real_tier || strcmp(real_tier,tier)) goto done;
  while (accepted < total) {
    size_t frames=(size_t)((total-accepted)<chunk ? total-accepted : chunk), read=0;
    size_t bytes=frames*channels;
    while (read<bytes) {
      size_t n=fread(bits+read,1,bytes-read,stdin);
      if (!n) goto done;
      read+=n;
    }
    for (size_t j=0;j<bytes;j++) {
      if (bits[j]>1u) goto done;
      source[j]=bits[j]?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
    }
    size_t used=0;
    while (used<frames) {
      size_t in=frames-used,cap=OUT_CAP;
      sox_dsd_status_t st=sox_dsd_decoder_process(decoder,source+used*channels,&in,pcm,&cap);
      if ((st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT) ||
          (in==0 && cap==0) || !emit(pcm,cap,channels)) goto done;
      used+=in;produced+=cap;
    }
    accepted+=frames;
  }
  if (fgetc(stdin)!=EOF || ferror(stdin)) goto done; /* reject trailing data */
  for (unsigned i=0;i<1000000;i++) {
    size_t cap=OUT_CAP;
    sox_dsd_status_t st=sox_dsd_decoder_finish(decoder,pcm,&cap);
    if ((st!=SOX_DSD_NEED_OUTPUT && st!=SOX_DSD_DONE) ||
        !emit(pcm,cap,channels)) goto done;
    produced+=cap;
    if (st==SOX_DSD_DONE) {
      uint64_t expected;
      memset(&report,0,sizeof(report));report.size=sizeof(report);report.version=1;
      if (sox_dsd_decoder_report(decoder,&report)!=SOX_DSD_OK) goto done;
      /* Checked quotient/remainder from the original native-frame count. */
      if (total > UINT64_MAX/output) goto done;
      expected=(total*output+native/2)/native;
      if (produced!=expected || report.output_frames!=expected ||
          report.native_frames!=total || report.channels!=channels ||
          report.native_hz!=native || report.output_hz!=output) goto done;
      fprintf(stderr,"P15_PROBE_OK native=%u pcm=%u profile=%s tier=%s channels=%u input=%llu output=%llu chunk=%u level=%s\n",
          native,output,profile,real_tier,channels,(unsigned long long)total,
          (unsigned long long)produced,chunk,cfg.level==SOX_DSD_LEVEL_SACD?"sacd":"preserve");
      status=0;break;
    }
    if (!cap) goto done;
  }
done:
  if (decoder) sox_dsd_decoder_destroy(decoder);
  free(bits);free(source);free(pcm);
  if (fflush(stdout)!=0) status=1;
  if (status) fprintf(stderr,"P15 instrument ERROR: incomplete/invalid stream, unsupported build or decoder contract\n");
  return status;
}
