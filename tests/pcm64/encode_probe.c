/* Phase 06A private admission and stream oracle probe.
 * Reads source-rate interleaved IEEE754 binary64 words from stdin, emits one
 * byte per chronological sign decision on stdout. The optional per-channel
 * trace records the EXACT post-clip binary64 words seen by the certified
 * resonator. Only the production composite/coordinator owns DSP state.
 * No header, vendor recurrence, or coefficient is modified by this probe. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "dsd_f64.h"
#include "pcmdsd.h"
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_CHANNELS 64u
#define OUTMAX LSX_DSD_F64_ENCODE_OUTPUT
#define INMAX LSX_DSD_F64_ENCODE_INPUT

typedef struct { FILE *file; uint64_t words; int failed; } trace_channel;

static void observed(void *opaque,const double *words,size_t n)
{
  trace_channel *t=opaque;
  if (t->failed) return;
  if (n>UINT64_MAX-t->words || (t->file && fwrite(words,sizeof(double),n,t->file)!=n))
    t->failed=1;
  else t->words+=n;
}

static int parse_u32(const char *s,uint32_t *out)
{
  char *end=NULL;
  unsigned long n;
  errno=0;n=strtoul(s,&end,10);
  if (!s[0] || !end || *end || errno || n>UINT32_MAX) return 0;
  *out=(uint32_t)n;return 1;
}

static int parse_double(const char *s,double *out)
{
  char *end=NULL;
  errno=0;*out=strtod(s,&end);
  return s[0] && end && !*end && !errno && isfinite(*out);
}

static int emit_bits(const sox_sample_t *out,size_t frames,unsigned channels)
{
  unsigned char bytes[OUTMAX*MAX_CHANNELS];
  size_t j,n=frames*channels;
  if (frames>OUTMAX || channels>MAX_CHANNELS) return 0;
  for (j=0;j<n;j++)bytes[j]=out[j]>0?1:0;
  return fwrite(bytes,1,n,stdout)==n;
}

static int encode(int argc,char **argv)
{
  lsx_dsd_f64_encoder enc={0};
  double input[INMAX*MAX_CHANNELS],reference=0,headroom=0;
  sox_sample_t bits[OUTMAX*MAX_CHANNELS];
  trace_channel traces[MAX_CHANNELS]={{0}};
  uint32_t source_rate,native_rate,nch,iblock,oblock,clip;
  unsigned channel;
  int result=1,entered=0;
  uint64_t total_input=0,total_bits=0;
  if (argc!=11 || !parse_u32(argv[2],&source_rate) ||
      !parse_u32(argv[3],&native_rate) || !parse_u32(argv[4],&nch) ||
      !parse_u32(argv[5],&iblock) || !parse_u32(argv[6],&oblock) ||
      !parse_u32(argv[7],&clip) || !parse_double(argv[8],&headroom) ||
      !parse_double(argv[9],&reference) ||
      !source_rate || !nch || nch>MAX_CHANNELS || !iblock || iblock>INMAX ||
      !oblock || oblock>OUTMAX || clip>1 ||
      (reference!=0.5 && reference!=1.) ||
      headroom<=0. || headroom>1. || !argv[10][0]) {
    fprintf(stderr,"encode_probe: invalid arguments\n");return 2;
  }
  if (sox_init()!=SOX_SUCCESS) {
    fprintf(stderr,"encode_probe: SoX initialization failed\n");return 2;
  }
  entered=1;
  if (lsx_dsd_f64_encode_init(&enc,source_rate,native_rate,nch,
          reference,headroom,clip)!=SOX_DSD_OK) {
    fprintf(stderr,"encode_probe: composite initialization failed\n");goto done;
  }
  for (channel=0;channel<nch;channel++) {
    if (strcmp(argv[10],"-")) {
      char filename[4096];
      int n=snprintf(filename,sizeof(filename),"%s.ch%u.f64",argv[10],channel);
      if (n<0 || (size_t)n>=sizeof(filename) ||
          !(traces[channel].file=fopen(filename,"wb"))) {
        fprintf(stderr,"encode_probe: trace open failed\n");goto done;
      }
    }
    lsx_dsd_f64_encode_observe_admitted(&enc,channel,observed,&traces[channel]);
  }
  for (;;) {
    size_t r=fread(input,sizeof(double)*nch,iblock,stdin);
    size_t used=0;
    if (ferror(stdin)) {
      fprintf(stderr,"encode_probe: source I/O error\n");goto done;
    }
    if (!r) break;
    while (used<r) {
      size_t n=r-used,m=oblock;
      sox_dsd_status_t st=lsx_dsd_f64_encode_process(&enc,input+used*nch,
          &n,bits,&m);
      if ((st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT) ||
          !emit_bits(bits,m,nch) || (!n && !m)) {
        fprintf(stderr,"encode_probe: composite process failed status=%d\n",(int)st);
        goto done;
      }
      used+=n;total_bits+=m;
    }
    total_input+=r;
  }
  /* Reject any dangling partial interleaved input word, including its bit
   * representation. fread() on frames cannot otherwise distinguish EOF. */
  if (ferror(stdin)) goto done;
  if (fgetc(stdin)!=EOF) {
    fprintf(stderr,"encode_probe: unaligned source trailing bytes\n");goto done;
  }
  for (;;) {
    size_t m=oblock;
    sox_dsd_status_t st=lsx_dsd_f64_encode_finish(&enc,bits,&m);
    if ((st!=SOX_DSD_NEED_OUTPUT && st!=SOX_DSD_DONE) ||
        !emit_bits(bits,m,nch) || (!m && st!=SOX_DSD_DONE)) {
      fprintf(stderr,"encode_probe: composite finish failed status=%d\n",(int)st);
      goto done;
    }
    total_bits+=m;
    if (st==SOX_DSD_DONE) break;
  }
  if (fflush(stdout) || enc.source_frames!=total_input ||
      enc.encoded_frames!=total_bits) {
    fprintf(stderr,"encode_probe: output accounting mismatch\n");goto done;
  }
  for (channel=0;channel<nch;channel++) {
    lsx_pcmdsd_report r={0};
    if (traces[channel].failed || traces[channel].words!=total_bits ||
        lsx_pcmdsd_report_get(lsx_dsd_f64_encode_channel(&enc,channel),&r)!=SOX_DSD_OK ||
        r.committed_frames!=total_bits || r.failure) {
      fprintf(stderr,"encode_probe: channel %u trace/accounting mismatch\n",channel);
      goto done;
    }
  }
  fprintf(stderr,"{\"source_frames\":\"%" PRIu64 "\",\"native_frames\":\"%" PRIu64
      "\",\"channels\":%u,\"source_rate\":%u,\"native_rate\":%u,\"record\":[",
      total_input,total_bits,nch,source_rate,native_rate);
  for (channel=0;channel<nch;channel++) {
    lsx_pcmdsd_report r={0};
    lsx_pcmdsd_report_get(lsx_dsd_f64_encode_channel(&enc,channel),&r);
    fprintf(stderr,"%s{\"channel\":%u,\"profile\":\"%s\",\"kernel\":\"%s\","
        "\"admitted\":\"%" PRIu64 "\",\"clipped\":\"%" PRIu64 "\","
        "\"peak\":%.17g,\"recovery_entries\":\"%" PRIu64 "\","
        "\"recovery_steps\":\"%" PRIu64 "\"}",
        channel?",":"",channel,
        lsx_pcmdsd_profile_of(lsx_dsd_f64_encode_channel(&enc,channel))->id,
        lsx_pcmdsd_kernel_name(lsx_dsd_f64_encode_channel(&enc,channel)),
        traces[channel].words,r.clipped_native_samples,r.peak,
        r.recovery_entries,r.recovery_steps);
  }
  fprintf(stderr,"]}\n");
  result=0;
done:
  for (channel=0;channel<MAX_CHANNELS;channel++) {
    if (traces[channel].file && fclose(traces[channel].file)) result=1;
  }
  lsx_dsd_f64_encode_destroy(&enc);
  if (entered && sox_quit()!=SOX_SUCCESS) result=1;
  return result;
}

static int selftest(void)
{
  lsx_dsd_f64_encoder e={0};
  double in[2]={0.,0.};
  sox_sample_t out[OUTMAX]={0};
  size_t n,m;
  int assertions=0;
#define CHECK(e) do {++assertions;if (!(e)) {\
    fprintf(stderr,"encode_probe: assertion %d: %s\n",__LINE__,#e);\
    return 1;}} while(0)
  CHECK(sox_init()==SOX_SUCCESS);
  CHECK(lsx_dsd_f64_encode_init(&e,44100,2822400,1,.5,1.,1)==SOX_DSD_OK);
  n=1;m=0;
  CHECK(lsx_dsd_f64_encode_process(&e,in,&n,out,&m)==SOX_DSD_NEED_OUTPUT);
  CHECK(n==0 && m==0);
  n=1;m=1;
  CHECK(lsx_dsd_f64_encode_process(&e,in,&n,out,&m)==SOX_DSD_NEED_INPUT);
  CHECK(n==1 && m<=1);
  do {
    m=1;CHECK(lsx_dsd_f64_encode_finish(&e,out,&m)==SOX_DSD_NEED_OUTPUT || e.done);
  } while (!e.done);
  CHECK(e.source_frames==1 && e.encoded_frames==64);
  m=1;CHECK(lsx_dsd_f64_encode_finish(&e,out,&m)==SOX_DSD_DONE && m==0);
  n=1;m=1;CHECK(lsx_dsd_f64_encode_process(&e,in,&n,out,&m)==SOX_DSD_BAD_ARGUMENT);
  CHECK(e.error==SOX_DSD_BAD_ARGUMENT);
  lsx_dsd_f64_encode_destroy(&e);
  CHECK(lsx_dsd_f64_encode_init(&e,44100,2822400,2,.5,1.,0)==SOX_DSD_OK);
  in[1]=NAN;n=1;m=2;
  CHECK(lsx_dsd_f64_encode_process(&e,in,&n,out,&m)==SOX_DSD_NUMERIC_ERROR);
  CHECK(n==0 && m==0 && e.source_frames==0 && e.encoded_frames==0);
  in[1]=0.;n=1;m=2;
  CHECK(lsx_dsd_f64_encode_process(&e,in,&n,out,&m)==SOX_DSD_NUMERIC_ERROR);
  lsx_dsd_f64_encode_destroy(&e);
  CHECK(lsx_dsd_f64_encode_init(&e,44100,2822400,1,.5,1.,0)==SOX_DSD_OK);
  m=0;CHECK(lsx_dsd_f64_encode_finish(&e,out,&m)==SOX_DSD_NEED_OUTPUT && e.finishing);
  m=512;CHECK(lsx_dsd_f64_encode_finish(&e,out,&m)==SOX_DSD_DONE && m==0);
  lsx_dsd_f64_encode_destroy(&e);
  CHECK(sox_quit()==SOX_SUCCESS);
  printf("PASS encode-probe assertions=%d\n",assertions);
  return 0;
#undef CHECK
}

int main(int argc,char **argv)
{
  if (argc==2 && !strcmp(argv[1],"--selftest")) return selftest();
  if (argc>=2 && !strcmp(argv[1],"--encode")) return encode(argc,argv);
  fprintf(stderr,"usage: encode_probe --selftest | --encode source_hz native_hz "
      "channels input_block output_block clip gain reference trace_prefix\n");
  return 2;
}
