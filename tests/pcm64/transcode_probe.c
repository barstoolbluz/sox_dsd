/* Uninstalled Phase 06B oracle driver. Tests the production coordinator with
 * different native read, PCM FIFO and DSD sink sizes. All transport buffers
 * are bounded, and observation is read-only. Stdout: chronological 0/1 bits.
 * The binary PCM and post-interpolation traces go to test-owned files. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "dsd_f64.h"
#include "pcmdsd.h"
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TRANSCODE_MAX_INPUT 4096u
#define MAX_OUTPUT LSX_DSD_F64_ENCODE_OUTPUT
#define MAX_CH 64u

typedef struct { FILE *stream; uint64_t words; int failed; } trace;

static void pcm_trace(void *opaque,const double *words,size_t frames,unsigned ch)
{
  trace *t=opaque;
  size_t n=frames*ch;
  if (t->failed)return;
  if (n>UINT64_MAX-t->words || (t->stream &&
      fwrite(words,sizeof(double),n,t->stream)!=n))t->failed=1;
  else t->words+=n;
}

static void admitted_trace(void *opaque,const double *words,size_t count)
{
  trace *t=opaque;
  if (t->failed)return;
  if (count>UINT64_MAX-t->words || (t->stream &&
      fwrite(words,sizeof(double),count,t->stream)!=count))t->failed=1;
  else t->words+=count;
}

static int u32(const char *str,uint32_t *value)
{
  char *end=NULL;
  unsigned long n;
  errno=0;n=strtoul(str,&end,10);
  if (!str[0] || !end || *end || errno || n>UINT32_MAX)return 0;
  *value=(uint32_t)n;return 1;
}

static int u64(const char *str,uint64_t *value)
{
  char *end=NULL;
  unsigned long long n;
  errno=0;n=strtoull(str,&end,10);
  if (!str[0] || !end || *end || errno)return 0;
  *value=(uint64_t)n;return (unsigned long long)*value==n;
}

static int emit(const sox_sample_t *bits,size_t frames,unsigned channels)
{
  unsigned char raw[MAX_OUTPUT*MAX_CH];
  size_t j,n=frames*channels;
  if (frames>MAX_OUTPUT || channels>MAX_CH)return 0;
  for (j=0;j<n;j++)raw[j]=(unsigned char)(bits[j]>0);
  return fwrite(raw,1,n,stdout)==n;
}

/* Lifecycle and sticky-failure acceptance is exercised through the same
 * coordinator as the bit oracle. No test-only production hooks are added. */
static int lifecycle_selftest(void)
{
  lsx_dsd_f64_transcode t={0};
  sox_dsd_decode_options_t opts;
  sox_sample_t output[32]={0},invalid=0,valid=SOX_SAMPLE_MAX;
  double gain=1.;
  size_t n,m;
  unsigned i;
  int assertions=0,started=0,rc=1;
#define VERIFY(x) do { ++assertions; if (!(x)) { \
    fprintf(stderr,"transcode_probe lifecycle assertion %u: %s\n", \
        (unsigned)__LINE__,#x); goto end; } } while(0)
  if (sox_init()!=SOX_SUCCESS) return 2;
  started=1;
  sox_dsd_decode_options_init_extended(&opts);
  opts.native_hz=2822400;opts.output_hz=96000;opts.channels=1;
  opts.profile=SOX_DSD_DECODE_MASTERING;
  opts.level=SOX_DSD_LEVEL_PRESERVE;
  opts.bandwidth=SOX_DSD_BANDWIDTH_ADAPT;
  VERIFY(lsx_dsd_f64_transcode_init(&t,&opts,1,0,&gain,1,NULL,
      5644800,1.,1.,1,0,1)==SOX_DSD_OK);
  for (i=0;i<64;i++) {
    sox_dsd_status_t st;
    m=32;st=lsx_dsd_f64_transcode_finish(&t,output,&m);
    VERIFY(m==0 && (st==SOX_DSD_NEED_OUTPUT || st==SOX_DSD_DONE));
    if (st==SOX_DSD_DONE) break;
  }
  VERIFY(i<64 && t.done);
  m=32;VERIFY(lsx_dsd_f64_transcode_finish(&t,output,&m)==SOX_DSD_DONE && m==0);
  n=1;m=32;
  VERIFY(lsx_dsd_f64_transcode_process(&t,&valid,NULL,0,&n,output,&m)==
      SOX_DSD_BAD_ARGUMENT && n==0 && m==0);
  m=32;VERIFY(lsx_dsd_f64_transcode_finish(&t,output,&m)==SOX_DSD_BAD_ARGUMENT && m==0);
  lsx_dsd_f64_transcode_destroy(&t);
  VERIFY(lsx_dsd_f64_transcode_init(&t,&opts,1,4096,&gain,1,NULL,
      5644800,1.,1.,1,0,1)==SOX_DSD_OK);
  n=1;m=32;
  /* The qualified public decoder maps malformed carrier input to a sticky
   * NUMERIC_ERROR. The coordinator must propagate it unchanged. */
  VERIFY(lsx_dsd_f64_transcode_process(&t,&invalid,NULL,0,&n,output,&m)==
      SOX_DSD_NUMERIC_ERROR && n==0 && m==0 && t.error==SOX_DSD_NUMERIC_ERROR);
  n=1;m=32;
  VERIFY(lsx_dsd_f64_transcode_process(&t,&valid,NULL,0,&n,output,&m)==
      SOX_DSD_NUMERIC_ERROR && n==0 && m==0);
  m=32;VERIFY(lsx_dsd_f64_transcode_finish(&t,output,&m)==SOX_DSD_NUMERIC_ERROR && m==0);
  lsx_dsd_f64_transcode_destroy(&t);
  VERIFY(lsx_dsd_f64_transcode_init(&t,&opts,1,4096,&gain,1,NULL,
      5644800,1.,1.,1,0,1)==SOX_DSD_OK);
  m=32;VERIFY(lsx_dsd_f64_transcode_finish(&t,output,&m)==SOX_DSD_IO_ERROR && m==0);
  m=32;VERIFY(lsx_dsd_f64_transcode_finish(&t,output,&m)==SOX_DSD_IO_ERROR && m==0);
  lsx_dsd_f64_transcode_destroy(&t);
  VERIFY(lsx_dsd_f64_transcode_init(&t,&opts,1,0,&gain,1,NULL,
      5644800,1.,1.,1,0,1)==SOX_DSD_OK);
  m=0;VERIFY(lsx_dsd_f64_transcode_finish(&t,NULL,&m)==SOX_DSD_NEED_OUTPUT && m==0);
  n=1;m=32;
  VERIFY(lsx_dsd_f64_transcode_process(&t,&valid,NULL,0,&n,output,&m)==
      SOX_DSD_BAD_ARGUMENT && n==0 && m==0);
  m=32;VERIFY(lsx_dsd_f64_transcode_finish(&t,output,&m)==SOX_DSD_BAD_ARGUMENT && m==0);
  fprintf(stderr,"{\"lifecycle_selftest\":\"PASS\",\"assertions\":%d}\n",assertions);
  rc=0;
end:
  lsx_dsd_f64_transcode_destroy(&t);
  if (started && sox_quit()!=SOX_SUCCESS) rc=1;
  return rc;
#undef VERIFY
}

int main(int argc,char **argv)
{
  lsx_dsd_f64_transcode pipeline={0};
  sox_dsd_decode_options_t options;
  trace pcm={0},admitted[MAX_CH]={{0}};
  unsigned char raw[TRANSCODE_MAX_INPUT*MAX_CH];
  sox_sample_t *native=NULL,*out=NULL;
  uint32_t source_hz,pcm_hz,target_hz,nch,inblock,fifo,sink;
  uint64_t expected_native=0,seen_native=0,seen_output=0,intermediate=0,expected_out=0;
  double factors[]={1.};
  unsigned channel;
  int result=1,entered=0;
  if (argc==2 && !strcmp(argv[1],"--lifecycle-selftest"))
    return lifecycle_selftest();
  if (argc!=10 || !u32(argv[1],&source_hz) || !u32(argv[2],&pcm_hz) ||
      !u32(argv[3],&target_hz) || !u32(argv[4],&nch) ||
      !u32(argv[5],&inblock) || !u32(argv[6],&fifo) ||
      !u32(argv[7],&sink) || !u64(argv[8],&expected_native) ||
      !nch || nch>MAX_CH || !inblock || inblock>TRANSCODE_MAX_INPUT ||
      !fifo || fifo>LSX_DSD_F64_TRANSCODE_FIFO_MAX ||
      !sink || sink>MAX_OUTPUT) {
    fprintf(stderr,"transcode_probe: RATE PCM_RATE OUTPUT_RATE CHANNELS INPUT_BLOCK FIFO SINK NATIVE_FRAMES PREFIX\n");
    return 2;
  }
  if (sox_init()!=SOX_SUCCESS)return 2;
  entered=1;
  native=malloc((size_t)inblock*nch*sizeof(*native));
  out=malloc((size_t)sink*nch*sizeof(*out));
  if (!native || !out)goto done;
  sox_dsd_decode_options_init_extended(&options);
  options.native_hz=source_hz;
  options.output_hz=pcm_hz;
  options.channels=nch;
  options.profile=SOX_DSD_DECODE_MASTERING;
  options.level=SOX_DSD_LEVEL_PRESERVE;
  options.bandwidth=SOX_DSD_BANDWIDTH_ADAPT;
  if (lsx_dsd_f64_transcode_init(&pipeline,&options,1,expected_native,
        factors,1,NULL,target_hz,1.,1.,1,0,fifo)!=SOX_DSD_OK) {
    fprintf(stderr,"transcode_probe: coordinator refused input\n");goto done;
  }
  if (strcmp(argv[9],"-")) {
    char path[4096];
    int chars=snprintf(path,sizeof(path),"%s.pcm",argv[9]);
    if (chars<0 || (size_t)chars>=sizeof(path) ||
        !(pcm.stream=fopen(path,"wb")))goto done;
    lsx_dsd_f64_transcode_observe_pcm(&pipeline,pcm_trace,&pcm);
    for (channel=0;channel<nch;channel++) {
      chars=snprintf(path,sizeof(path),"%s.ch%u.admitted",argv[9],channel);
      if (chars<0 || (size_t)chars>=sizeof(path) ||
          !(admitted[channel].stream=fopen(path,"wb")))goto done;
      lsx_dsd_f64_encode_observe_admitted(&pipeline.encoder,channel,
          admitted_trace,&admitted[channel]);
    }
  }
  while (seen_native<expected_native) {
    size_t input=(size_t)((expected_native-seen_native)<inblock?
        expected_native-seen_native:inblock);
    size_t n=input*nch,cursor=0;
    if (fread(raw,1,n,stdin)!=n) {
      fprintf(stderr,"transcode_probe: truncated source bits\n");goto done;
    }
    for (cursor=0;cursor<n;cursor++) {
      if (raw[cursor]!=0 && raw[cursor]!=1) {
        fprintf(stderr,"transcode_probe: non-bit transport symbol\n");goto done;
      }
      native[cursor]=raw[cursor]?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
    }
    cursor=0;
    while (cursor<input) {
      size_t used=input-cursor,produced=sink;
      sox_dsd_status_t st=lsx_dsd_f64_transcode_process(&pipeline,
          native+cursor*nch,NULL,0,&used,out,&produced);
      if ((st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT) ||
          !emit(out,produced,nch) || (!used && !produced)) {
        fprintf(stderr,"transcode_probe: process failed %d at %" PRIu64 "\n",
            (int)st,seen_native+cursor);goto done;
      }
      cursor+=used;
      seen_output+=produced;
    }
    seen_native+=input;
  }
  if (fgetc(stdin)!=EOF || ferror(stdin)) {
    fprintf(stderr,"transcode_probe: trailing/failed native bits\n");goto done;
  }
  for (;;) {
    size_t produced=sink;
    sox_dsd_status_t st=lsx_dsd_f64_transcode_finish(&pipeline,out,&produced);
    if ((st!=SOX_DSD_DONE && st!=SOX_DSD_NEED_OUTPUT) ||
        !emit(out,produced,nch) || (!produced && st!=SOX_DSD_DONE)) {
      fprintf(stderr,"transcode_probe: finish failed %d\n",(int)st);goto done;
    }
    seen_output+=produced;
    if (st==SOX_DSD_DONE)break;
  }
  if (!lsx_dsd_count_convert(expected_native,source_hz,pcm_hz,&intermediate) ||
      !lsx_dsd_count_convert(intermediate,pcm_hz,target_hz,&expected_out) ||
      pipeline.decoder.pcm_seen!=intermediate ||
      pipeline.encoder.source_frames!=intermediate ||
      pipeline.encoder.encoded_frames!=seen_output || seen_output!=expected_out ||
      pipeline.pcm.input_frames!=intermediate || !pipeline.done ||
      !pipeline.decoder.finished || pcm.failed ||
      (pcm.stream && pcm.words!=intermediate*nch)) {
    fprintf(stderr,"transcode_probe: independent stage counts disagree\n");goto done;
  }
  for (channel=0;channel<nch;channel++) {
    if (admitted[channel].failed || (admitted[channel].stream &&
        admitted[channel].words!=seen_output)) {
      fprintf(stderr,"transcode_probe: admitted trace count mismatch\n");goto done;
    }
  }
  if (fflush(stdout))goto done;
  fprintf(stderr,"{\"input_native_frames\":\"%" PRIu64 "\","
      "\"intermediate_pcm_frames\":\"%" PRIu64 "\","
      "\"output_native_bits\":\"%" PRIu64 "\","
      "\"channels\":%u,\"fifo\":%u,\"sink\":%u}\n",
      seen_native,intermediate,seen_output,nch,fifo,sink);
  result=0;
done:
  for (channel=0;channel<nch;channel++)
    if (admitted[channel].stream && fclose(admitted[channel].stream))result=1;
  if (pcm.stream && fclose(pcm.stream))result=1;
  lsx_dsd_f64_transcode_destroy(&pipeline);
  free(native);free(out);
  if (entered && sox_quit()!=SOX_SUCCESS)result=1;
  return result;
}
