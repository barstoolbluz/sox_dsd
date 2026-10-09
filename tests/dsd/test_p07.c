/* P07 executable API contract.  Exercise the *linked production library*:
 * count arithmetic, private SRC identity, both level policies, multichannel
 * ownership, output counts and byte-for-byte chunk independence. */
#include "sox_dsd.h"
#include "dsd.h"
#include "rate_internal.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static unsigned long checks;
#define CHECK(x) do { ++checks; if (!(x)) { \
  fprintf(stderr,"P07 assertion line %d: %s\n",__LINE__,#x); exit(1); \
} } while (0)
static const uint32_t native_rates[]={2822400,5644800,11289600};
static const uint32_t pcm_rates[]={44100,48000,88200,96000,176400,192000,352800,384000,705600};

typedef struct { double *output; size_t frames; } result;

static uint64_t expected(uint64_t frames,uint32_t a,uint32_t b)
{
  uint64_t q=frames/a, r=frames%a, num;
  CHECK(q <= UINT64_MAX/b);
  num=q*b + (r*b+a/2)/a;
  return num;
}

static void count_tests(void)
{
  uint64_t result;
  size_t i,j;
  CHECK(!lsx_dsd_count_convert(UINT64_MAX,1,UINT32_MAX,&result));
  CHECK(!lsx_dsd_count_convert(1,0,44100,&result));
  CHECK(!lsx_dsd_count_convert(1,2822400,0,&result));
  for (i=0;i<sizeof(native_rates)/sizeof(native_rates[0]);i++)
    for (j=0;j<sizeof(pcm_rates)/sizeof(pcm_rates[0]);j++)
      for (uint64_t n=0;n<1000;n++) {
        CHECK(lsx_dsd_count_convert(n,native_rates[i],pcm_rates[j],&result));
        CHECK(result==expected(n,native_rates[i],pcm_rates[j]));
      }
  CHECK(lsx_dsd_count_convert(1,2822400,705600,&result) && result==0);
  /* A rounded intermediate length of ceil(1/32)=1 at R=88200 yields
   * eight spurious final frames if one rounds twice. */
  CHECK((1u*705600+88200/2)/88200!=result);
}

static void identity_src(void)
{
  lsx_rate_f64_config cfg={88200,88200,180.,95.,50};
  lsx_rate_f64_t *ctx=NULL,*bad=(void*)1;
  double in[17],out[24]={0};
  size_t i,n=17,m=7;
  CHECK(lsx_rate_f64_create(&cfg,&ctx)==SOX_DSD_OK && ctx!=NULL);
  for (i=0;i<17;i++) in[i]=(double)(i*i-30.)/128.;
  CHECK(lsx_rate_f64_process(ctx,in,&n,out,&m)==SOX_DSD_NEED_OUTPUT);
  CHECK(n==7 && m==7 && memcmp(in,out,7*sizeof(double))==0);
  n=10;m=17;
  CHECK(lsx_rate_f64_process(ctx,in+7,&n,out+7,&m)==SOX_DSD_NEED_INPUT);
  CHECK(n==10 && m==10 && memcmp(in,out,17*sizeof(double))==0);
  m=17;
  CHECK(lsx_rate_f64_finish(ctx,17,out,&m)==SOX_DSD_DONE && m==0);
  m=17;
  CHECK(lsx_rate_f64_finish(ctx,17,out,&m)==SOX_DSD_DONE && m==0);
  lsx_rate_f64_destroy(ctx);
  cfg.phase_percent=42;
  CHECK(lsx_rate_f64_create(&cfg,&bad)==SOX_DSD_BAD_ARGUMENT && bad==NULL);
}

static result exercise(uint32_t native,uint32_t pcm,
    sox_dsd_decode_profile_t profile,sox_dsd_decode_level_t level,
    unsigned channels,size_t frames,size_t in_batch,size_t out_batch)
{
  sox_dsd_decode_options_t opt;
  sox_dsd_decoder_t *ctx=NULL;
  sox_dsd_report_t report;
  sox_sample_t *source=NULL;
  result rv;
  size_t used=0, made=0;
  size_t cap=(size_t)expected(frames,native,pcm);
  size_t iter=0;
  rv.frames=cap; rv.output=calloc((cap+2)*channels,sizeof(double));
  CHECK(rv.output);
  sox_dsd_decode_options_init(&opt);
  opt.native_hz=native;opt.output_hz=pcm;opt.profile=profile;
  opt.level=level;opt.channels=channels;
  CHECK(sox_dsd_decoder_create(&opt,&ctx)==SOX_DSD_OK && ctx);
  source=malloc((frames+1)*channels*sizeof(*source));CHECK(source);
  for (size_t i=0;i<frames;i++)
    for (unsigned c=0;c<channels;c++)
      source[i*channels+c]=(i/8+c)%3==0?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
  while (used<frames) {
    size_t in=frames-used, out=cap-made+1;
    sox_dsd_status_t rc;
    if (in>in_batch) in=in_batch;
    if (out>out_batch) out=out_batch;
    CHECK(out>0 && in>0);
    rc=sox_dsd_decoder_process(ctx,source+used*channels,&in,
        rv.output+made*channels,&out);
    CHECK(rc==SOX_DSD_NEED_INPUT || rc==SOX_DSD_NEED_OUTPUT);
    used+=in; made+=out;
    CHECK(used<=frames && made<=cap && ++iter<frames*4+5000);
    CHECK(in || out);
  }
  while (1) {
    size_t out=cap-made+1;
    sox_dsd_status_t rc;
    if (out>out_batch) out=out_batch;
    CHECK(out>0);
    rc=sox_dsd_decoder_finish(ctx,rv.output+made*channels,&out);
    CHECK(rc==SOX_DSD_NEED_OUTPUT || rc==SOX_DSD_DONE);
    made+=out;
    CHECK(made<=cap && ++iter<frames*4+15000);
    if (rc==SOX_DSD_DONE) break;
    CHECK(out>0);
  }
  CHECK(made==cap);
  {size_t out=10;
   CHECK(sox_dsd_decoder_finish(ctx,rv.output,&out)==SOX_DSD_DONE && out==0);}
  memset(&report,0,sizeof(report));report.size=sizeof(report);report.version=1;
  CHECK(sox_dsd_decoder_report(ctx,&report)==SOX_DSD_OK);
  CHECK(report.native_frames==frames && report.output_frames==cap);
  CHECK(report.output_hz==pcm && report.native_hz==native && report.channels==channels);
  CHECK(report.intermediate_frames <= frames/32+1);
  CHECK(report.applied_gain==(level==SOX_DSD_LEVEL_SACD?2.:1.));
  CHECK(report.status==SOX_DSD_DONE);
  sox_dsd_decoder_destroy(ctx);free(source);
  return rv;
}

static void public_tests(void)
{
  size_t i,j,p;
  for (i=0;i<3;i++) for (j=0;j<9;j++) for (p=0;p<2;p++) {
    result a,b;
    a=exercise(native_rates[i],pcm_rates[j],(sox_dsd_decode_profile_t)p,
        SOX_DSD_LEVEL_PRESERVE,2,4097,4097,4097);
    b=exercise(native_rates[i],pcm_rates[j],(sox_dsd_decode_profile_t)p,
        SOX_DSD_LEVEL_PRESERVE,2,4097,53,11);
    CHECK(a.frames==b.frames);
    CHECK(!memcmp(a.output,b.output,a.frames*2*sizeof(double)));
    free(a.output);free(b.output);
  }
  {size_t sizes[]={0,1,2,31,32,33,63,64,65,96,97,511,512,513,1024};
   for (i=0;i<sizeof(sizes)/sizeof(sizes[0]);i++) {
     result a=exercise(2822400,705600,SOX_DSD_DECODE_MASTERING,
         SOX_DSD_LEVEL_PRESERVE,1,sizes[i],sizes[i]+1,16);
     CHECK(a.frames==expected(sizes[i],2822400,705600));
     free(a.output);
   }}
  { /* Independent channels and SACD level must scale without mixing. */
    result a=exercise(2822400,88200,SOX_DSD_DECODE_MASTERING,
        SOX_DSD_LEVEL_PRESERVE,2,16384,4096,1024);
    result b=exercise(2822400,88200,SOX_DSD_DECODE_MASTERING,
        SOX_DSD_LEVEL_SACD,2,16384,1,17);
    CHECK(a.frames==b.frames);
    for (i=0;i<a.frames*2;i++) CHECK(b.output[i]==2*a.output[i]);
    free(a.output);free(b.output);
  }
}

/* Public binary64 values must remain over-range until the *graph* adapter.
 * This is a real all-positive one-bit stream, not an artificial SRC input. */
static void api_overrange(void)
{
  const size_t frames = 32768, expected_frames = 1024;
  sox_sample_t *ones = malloc(frames * sizeof(*ones));
  double *preserve = calloc(expected_frames + 4, sizeof(*preserve));
  double *sacd = calloc(expected_frames + 4, sizeof(*sacd));
  unsigned mode;
  CHECK(ones && preserve && sacd);
  for (size_t i=0;i<frames;++i) ones[i]=SOX_SAMPLE_MAX;
  for (mode=0;mode<2;++mode) {
    sox_dsd_decode_options_t opt;
    sox_dsd_decoder_t *ctx=NULL;
    double *dst = mode?sacd:preserve;
    size_t used=0, made=0, iter=0;
    sox_dsd_decode_options_init(&opt);
    opt.native_hz=2822400; opt.output_hz=88200;
    opt.channels=1; opt.level=mode?SOX_DSD_LEVEL_SACD:SOX_DSD_LEVEL_PRESERVE;
    CHECK(sox_dsd_decoder_create(&opt,&ctx)==SOX_DSD_OK);
    while (used<frames) {
      size_t in=frames-used, out=expected_frames+2-made;
      sox_dsd_status_t st=sox_dsd_decoder_process(ctx,ones+used,&in,dst+made,&out);
      CHECK(st==SOX_DSD_NEED_INPUT || st==SOX_DSD_NEED_OUTPUT);
      used+=in; made+=out;
      CHECK((in || out) && made<=expected_frames && ++iter<frames+100);
    }
    for (;;) {
      size_t out=expected_frames+2-made;
      sox_dsd_status_t st=sox_dsd_decoder_finish(ctx,dst+made,&out);
      CHECK(st==SOX_DSD_NEED_OUTPUT || st==SOX_DSD_DONE);
      made+=out; CHECK(made<=expected_frames && ++iter<frames+200);
      if (st==SOX_DSD_DONE) break;
      CHECK(out);
    }
    CHECK(made==expected_frames);
    sox_dsd_decoder_destroy(ctx);
  }
  {double peak=0.;
   for (size_t i=0;i<expected_frames;++i) {
     CHECK(sacd[i]==2*preserve[i]);
     if (sacd[i]>peak) peak=sacd[i];
   }
   CHECK(peak>1.1 && peak<2.5);
  }
  free(ones); free(preserve); free(sacd);
}

int main(void)
{
  count_tests();identity_src();public_tests();api_overrange();
  printf("P07 %lu assertions, 0 failures\n",checks);
  return 0;
}
