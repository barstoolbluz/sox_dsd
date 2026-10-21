/* P18 unit gate: private rate x container x operation decisions are independent
 * of field width and of the P17 *development* coefficient candidates.
 * No high-rate effect or file writer is invoked as if it were qualified.
 */
#define _POSIX_C_SOURCE 200809L
#include "dsd.h"
#include "sox_ng.h"
#include <stdint.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static unsigned long checks;
#define CHECK(x) do { ++checks; if (!(x)) { \
  fprintf(stderr,"P18 FAIL %s:%d: %s\n",__FILE__,__LINE__,#x); return 1; \
} } while (0)

extern const sox_effect_handler_t *lsx_dop_effect_fn(void);

static int capabilities(void)
{
  const uint32_t high[]={22579200u,45158400u};
  const uint32_t low[]={2822400u,5644800u,11289600u};
  size_t i; int f,o;
  for (i=0;i<2;i++) {
    const lsx_dsd_rate *r=lsx_dsd_rate_find(high[i]);
    CHECK(r && !r->capabilities && !r->decode_mastering_id &&
        !r->decode_wideband_id && !r->encode_mastering_id);
    for (f=LSX_DSD_ENDPOINT_DSF;f<=LSX_DSD_ENDPOINT_DFF;f++) {
      for (o=LSX_DSD_OPERATION_READ;o<=LSX_DSD_OPERATION_WRITE;o++) {
        CHECK(lsx_dsd_capability_check(high[i],f,o)==LSX_DSD_CAP_UNQUALIFIED);
        CHECK(strstr(lsx_dsd_capability_description(high[i],f,o),
            "P17 high-rate DSP qualification incomplete")!=NULL);
      }
    }
    CHECK(lsx_dsd_capability_check(high[i],LSX_DSD_ENDPOINT_DOP,
        LSX_DSD_OPERATION_TRANSPORT)==LSX_DSD_CAP_UNQUALIFIED);
    CHECK(lsx_dsd_capability_check(high[i],LSX_DSD_ENDPOINT_WSD,
        LSX_DSD_OPERATION_READ)==LSX_DSD_CAP_UNQUALIFIED);
    CHECK(lsx_dsd_capability_check(high[i],LSX_DSD_ENDPOINT_DOP,
        LSX_DSD_OPERATION_READ)==LSX_DSD_CAP_UNSUPPORTED);
    CHECK(lsx_dsd_capability_check(high[i],LSX_DSD_ENDPOINT_DSF,
        LSX_DSD_OPERATION_TRANSPORT)==LSX_DSD_CAP_UNSUPPORTED);
  }
  for (i=0;i<3;i++) {
    CHECK(lsx_dsd_rate_find(low[i]) && lsx_dsd_rate_find(low[i])->capabilities);
    for (f=LSX_DSD_ENDPOINT_DSF;f<=LSX_DSD_ENDPOINT_DFF;f++)
      for (o=LSX_DSD_OPERATION_READ;o<=LSX_DSD_OPERATION_WRITE;o++)
        CHECK(lsx_dsd_capability_check(low[i],f,o)==LSX_DSD_CAP_OK);
    CHECK(lsx_dsd_capability_check(low[i],LSX_DSD_ENDPOINT_DOP,
        LSX_DSD_OPERATION_TRANSPORT)==LSX_DSD_CAP_OK);
  }
  CHECK(lsx_dsd_capability_check(45158401,LSX_DSD_ENDPOINT_DSF,
      LSX_DSD_OPERATION_READ)==LSX_DSD_CAP_UNSUPPORTED);
  CHECK(lsx_dsd_capability_check(0,LSX_DSD_ENDPOINT_DFF,
      LSX_DSD_OPERATION_READ)==LSX_DSD_CAP_UNSUPPORTED);
  return 0;
}

static int rates_and_dop(void)
{
  uint32_t pcm=0,integer=0;
  const uint32_t high[]={22579200u,45158400u};
  const uint32_t transport[]={1411200u,2822400u};
  size_t i;
  CHECK(lsx_dsd_integer_rate(4294967295.0,&integer) && integer==UINT32_MAX);
  CHECK(!lsx_dsd_integer_rate(4294967296.0,&integer));
  CHECK(!lsx_dsd_integer_rate(22579200.5,&integer));
  CHECK(!lsx_dsd_integer_rate(-1,&integer));
  CHECK(!lsx_dsd_integer_rate(0,&integer));
  for (i=0;i<2;i++) {
    CHECK(lsx_dsd_integer_rate((double)high[i],&integer) && integer==high[i]);
    CHECK(lsx_dsd_dop_pcm_rate(high[i],&pcm) && pcm==transport[i]);
    CHECK((uint64_t)pcm*16u==high[i]);
  }
  CHECK(lsx_dsd_dop_pcm_rate(2822400,&pcm) && pcm==176400);
  CHECK(!lsx_dsd_dop_pcm_rate(22579201,&pcm));
  CHECK(!lsx_dsd_dop_pcm_rate(UINT32_MAX,&pcm));
  CHECK(!lsx_dsd_dop_pcm_rate(0,&pcm));
  CHECK(!lsx_dsd_dop_pcm_rate(22579200,NULL));
  for (i=0;i<2;i++) {
    const sox_effect_handler_t *h=lsx_dop_effect_fn();
    sox_effect_t effect={0};
    effect.handler=*h;
    effect.priv=calloc(1,h->priv_size);
    CHECK(effect.priv);
    effect.in_signal.rate=high[i];
    effect.in_signal.precision=1;
    effect.in_signal.channels=2;
    effect.out_signal.rate=transport[i];
    effect.out_signal.channels=2;
    CHECK(h->start(&effect)!=SOX_SUCCESS); /* refusal before buffer allocate */
    free(effect.priv);
  }
  return 0;
}

/* Sparse arithmetic exercises durations far beyond uint32 sample counts.
 * The results are compared against independent quotient/remainder formulas.
 * No high-rate disk output is created: it is unauthorized by P18. */
static int sizes(void)
{
  const uint64_t frames[]={0,1,7,8,9,32768,32769,
      UINT64_C(22579200)*3600, UINT64_C(45158400)*3600*24,
      (UINT64_C(1)<<48), UINT64_MAX};
  const unsigned channels[]={1,2,6};
  size_t i,j;
  for (i=0;i<sizeof(frames)/sizeof(frames[0]);i++) {
    for (j=0;j<sizeof(channels)/sizeof(channels[0]);j++) {
      uint64_t dsf, dff, span, blocks, bytes_per_channel;
      unsigned c=channels[j];
      int dsf_ok=lsx_dsd_dsf_extent(frames[i],c,4096,&dsf);
      int dff_ok=lsx_dsd_dff_extent(frames[i],c,&dff,&span);
      blocks=frames[i]/32768u+(frames[i]%32768u!=0);
      bytes_per_channel=frames[i]/8u+(frames[i]%8u!=0);
      CHECK(dsf_ok==(blocks<=UINT64_MAX/(4096u*c)));
      if (dsf_ok) {
        CHECK(dsf==blocks*4096u*c);
        CHECK(dsf%4096u==0);
        CHECK(dsf>=blocks*4096u);
      }
      CHECK(dff_ok==(bytes_per_channel<=UINT64_MAX/c &&
          bytes_per_channel*c<=UINT64_MAX-12u-((bytes_per_channel*c)&1u)));
      if (dff_ok) {
        CHECK(dff==bytes_per_channel*c);
        CHECK(span==12u+dff+(dff&1u));
        CHECK(!(span&1u));
        CHECK(span>=12u);
      }
    }
  }
  {
    uint64_t total;
    CHECK(lsx_dsd_checked_interleaved(UINT64_MAX/6,6,&total) &&
          total==UINT64_MAX/6*6);
    CHECK(!lsx_dsd_checked_interleaved(UINT64_MAX,6,&total));
    CHECK(lsx_dsd_count_convert(UINT64_MAX,1,1,&total) && total==UINT64_MAX);
    CHECK(!lsx_dsd_count_convert(UINT64_MAX,1,2,&total));
    CHECK(lsx_dsd_count_convert(UINT64_C(45158400)*3600*24,
          45158400,2822400,&total) && total==UINT64_C(2822400)*3600*24);
    CHECK(!lsx_dsd_dsf_extent(UINT64_MAX,8,4096,&total));
    CHECK(!lsx_dsd_dff_extent(UINT64_MAX,8,&total,&total));
    CHECK(!lsx_dsd_dff_extent(1,1,NULL,&total));
    CHECK(!lsx_dsd_dsf_extent(1,0,4096,&total));
  }
  return 0;
}

/* Direct public API callers must not be able to bypass the CLI planner.
 * Exercise both writers at both disabled rates; preserve existing file data
 * to verify refusal happens before opening or truncating the destination. */
static int writer_api_denial(void)
{
  static const uint32_t high[]={22579200u,45158400u};
  static const char *types[]={"dsf","dff"};
  static const char sentinel[]="P18 KEEP EXISTING BYTES";
  char path[]="/tmp/sox-p18-api-XXXXXX";
  char actual[sizeof(sentinel)];
  sox_signalinfo_t sig={0};
  sox_encodinginfo_t enc={0};
  struct stat st;
  size_t i,j;
  int fd=mkstemp(path);
  CHECK(fd>=0);
  CHECK(write(fd,sentinel,sizeof(sentinel))==(ssize_t)sizeof(sentinel));
  CHECK(sox_init()==SOX_SUCCESS);
  sig.channels=2;
  sig.precision=1;
  sox_init_encodinginfo(&enc);
  enc.encoding=SOX_ENCODING_DSD;
  enc.bits_per_sample=1;
  for (i=0;i<sizeof(high)/sizeof(*high);i++) {
    sig.rate=high[i];
    for (j=0;j<sizeof(types)/sizeof(*types);j++) {
      CHECK(sox_open_write(path,&sig,&enc,types[j],NULL,NULL)==NULL);
      CHECK(!fstat(fd,&st) && st.st_size==(off_t)sizeof(sentinel));
      CHECK(lseek(fd,0,SEEK_SET)==0);
      CHECK(read(fd,actual,sizeof(actual))==(ssize_t)sizeof(actual));
      CHECK(!memcmp(actual,sentinel,sizeof(actual)));
    }
  }
  CHECK(sox_quit()==SOX_SUCCESS);
  CHECK(close(fd)==0);
  CHECK(unlink(path)==0);
  return 0;
}

int main(int argc, char **argv)
{
  if (argc==1 || !strcmp(argv[1],"registry")) {
    if (capabilities() || writer_api_denial()) return 1;
    if (argc>1) goto done;
  }
  if (argc==1 || !strcmp(argv[1],"transport")) {
    if (rates_and_dop()) return 1;
    if (argc>1) goto done;
  }
  if (argc==1 || !strcmp(argv[1],"sizes")) {
    if (sizes()) return 1;
    if (argc>1) goto done;
  }
  if (argc>1 && strcmp(argv[1],"registry") && strcmp(argv[1],"transport") &&
      strcmp(argv[1],"sizes")) {fprintf(stderr,"usage: dsd_test_p18 [registry|transport|sizes]\n");return 2;}
done:
  printf("P18 PASS %lu checks (high-rate capabilities disabled)\n",checks);
  return 0;
}
