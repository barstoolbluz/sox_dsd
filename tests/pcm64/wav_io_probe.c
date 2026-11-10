/* Qualification-only caller for the private, actual-WAV-handler frame API.
 * This executable is not linked into the production command frontend. */
#include "sox_i.h"
#include "pcm_f64_io.h"
#include <signal.h>
#include <inttypes.h>
#include <string.h>
#include <stdlib.h>
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
#include <xmmintrin.h>
#endif

static sox_bool decline(const char *ignored UNUSED) { return sox_false; }
static unsigned long long number(const char *s)
{
  char *e=NULL;
  unsigned long long n=strtoull(s,&e,10);
  if (!s[0] || !e || *e) { fprintf(stderr,"bad integer: %s\n",s); exit(2); }
  return n;
}
static int code(const char *arg,sox_encoding_t *encoding,unsigned *bits)
{
  if (!strcmp(arg,"f64")) { *encoding=SOX_ENCODING_FLOAT;*bits=64; }
  else if (!strcmp(arg,"f32")) { *encoding=SOX_ENCODING_FLOAT;*bits=32; }
  else if (!strcmp(arg,"i8")) { *encoding=SOX_ENCODING_UNSIGNED;*bits=8; }
  else if (!strcmp(arg,"i16")) { *encoding=SOX_ENCODING_SIGN2;*bits=16; }
  else if (!strcmp(arg,"i24")) { *encoding=SOX_ENCODING_SIGN2;*bits=24; }
  else if (!strcmp(arg,"i32")) { *encoding=SOX_ENCODING_SIGN2;*bits=32; }
  else return 0;
  return 1;
}
static void fail(const char *where, const sox_format_t *ft)
{
  fprintf(stderr,"FAIL %s: %s\n",where,ft?ft->sox_errstr:"no format handle");
}
static int run(int argc,char **argv)
{
  sox_format_t *in=NULL,*out=NULL;
  lsx_pcm_f64_wav_facts facts;
  pcm_f64_format fmt;
  pcm_f64_progress p;
  pcm_f64_status status;
  sox_dsd_layout_t *layout=NULL;
  sox_encoding_t encoding=SOX_ENCODING_UNKNOWN;
  unsigned bits=0;
  bool big=false;
  uint64_t frames,read_frames=0,written_frames=0;
  size_t block=23, n;
  double samples[64*257];
  int rc=1;
  FILE *raw=NULL;
  const char *mode;

  if (argc<3) { fprintf(stderr,"usage: probe query|dump|copy|generate|mixed ...\n");return 2; }
  mode=argv[1];
  if (sox_init()!=SOX_SUCCESS) { fprintf(stderr,"sox_init failed\n");return 2; }
  if (!strcmp(mode,"generate")) {
    /* generate raw64 out type L|B channels rate declared_frames to_write
     *          [allow|deny] [report_path] */
    if (argc < 10 || !code(argv[4],&encoding,&bits)) { rc=2;goto finish; }
    raw=fopen(argv[2],"rb");
    if (!raw) { perror("raw input");goto finish; }
    big=argv[5][0]=='B';
    frames=number(argv[8]);
    if (frames==UINT64_MAX) { /* a sentinel for unknown, always refused */
      pcm_f64_format_init(&fmt,(uint32_t)number(argv[7]),(uint32_t)number(argv[6]),false,0);
    } else if (pcm_f64_format_init(&fmt,(uint32_t)number(argv[7]),
           (uint32_t)number(argv[6]),true,frames)!=PCM_F64_OK) goto finish;
    out=lsx_pcm_f64_wav_open_write(argv[3],&fmt,encoding,bits,big,NULL,NULL,
        argc>11 ? argv[11] : NULL,argc>10 && !strcmp(argv[10],"deny") ? decline : NULL);
    if (!out) { fail("safe open",NULL);goto finish; }
    frames=number(argv[9]);
    while (frames) {
      unsigned char snapshot[sizeof(samples)];
      n=(size_t)min((uint64_t)257,frames);
      if (fread(samples,sizeof(double)*fmt.channels,n,raw)!=n) {
        fail("short raw input",out);goto finish;
      }
      memcpy(snapshot,samples,n*sizeof(double)*fmt.channels);
      p=lsx_pcm_f64_wav_write(out,(pcm_f64_input){samples,n});
      if (p.status!=PCM_F64_OK || p.consumed_frames!=n ||
          memcmp(snapshot,samples,n*sizeof(double)*fmt.channels)) {
        fail("write, declared-count refusal, or borrowed buffer changed",out);
        goto finish;
      }
      written_frames+=n;
      frames-=n;
    }
    rc=0;
  } else {
    sox_signalinfo_t override={0};
    if (!strcmp(mode,"query") && argc>3)
      override.rate=(sox_rate_t)number(argv[3]);
    in=sox_open_read(argv[2],argc>3 && !strcmp(mode,"query") ? &override : NULL,
        NULL,"wav");
    if (!in) { fail("open input",NULL);goto finish; }
    status=lsx_pcm_f64_wav_query(in,&facts);
    if (status!=PCM_F64_OK) {
      fprintf(stderr,"native WAV unsupported: %s\n",pcm_f64_status_name(status));
      goto finish;
    }
    if (!strcmp(mode,"query")) {
      printf("rate=%u channels=%u frames=%" PRIu64 " bits=%u valid=%u mask=%08x ext=%u big=%u bytes=%" PRIu64 "\n",
          facts.stream.rate_hz,facts.stream.channels,facts.stream.total_frames,
          facts.container_bits,facts.valid_bits,facts.speaker_mask,
          facts.extensible,facts.big_endian,facts.data_bytes);
      rc=0;
    } else if (!strcmp(mode,"mixed")) {
      sox_sample_t legacy[64]={0};
      double first[64]={0}, second[64]={0};
      p=lsx_pcm_f64_wav_read(in,(pcm_f64_output){first,1});
      if (p.produced_frames!=1 || sox_read(in,legacy,facts.stream.channels)!=0 ||
          sox_seek(in,0,SOX_SEEK_SET)!=SOX_SUCCESS) goto finish;
      p=lsx_pcm_f64_wav_read(in,(pcm_f64_output){second,1});
      if (p.produced_frames!=1 || memcmp(first,second,facts.stream.channels*sizeof(double)))
        goto finish;
      if (sox_seek(in,0,SOX_SEEK_SET)!=SOX_SUCCESS ||
          sox_read(in,legacy,facts.stream.channels)!=facts.stream.channels ||
          lsx_pcm_f64_wav_read(in,(pcm_f64_output){second,1}).status!=PCM_F64_STATE)
        goto finish;
      /* Native read must work after a reset, finish precisely at EOF, and
       * repeated EOF must not advance the cursor or deliver extra frames. */
      if (sox_seek(in,0,SOX_SEEK_SET)!=SOX_SUCCESS) goto finish;
      for (read_frames=0; read_frames<facts.stream.total_frames; ++read_frames) {
        p=lsx_pcm_f64_wav_read(in,(pcm_f64_output){second,1});
        if (p.produced_frames!=1 || (read_frames+1==facts.stream.total_frames ?
            p.status!=PCM_F64_DONE : p.status!=PCM_F64_OK)) goto finish;
      }
      p=lsx_pcm_f64_wav_read(in,(pcm_f64_output){second,1});
      if (p.status!=PCM_F64_DONE || p.produced_frames) goto finish;
      if (sox_seek(in,0,SOX_SEEK_SET)!=SOX_SUCCESS) goto finish;
      p=lsx_pcm_f64_wav_read(in,(pcm_f64_output){second,1});
      if (p.produced_frames!=1 || memcmp(first,second,
            facts.stream.channels*sizeof(double))) goto finish;
      rc=0;
    } else if (!strcmp(mode,"daz")) {
      /* A test-only, in-process MXCSR check: assert both the first refusal
       * and its latch, without publishing even a partial decoded block. */
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
      unsigned original_csr = _mm_getcsr();
      bool enable;
      size_t bytes, i;
      pcm_f64_progress again;
      if (argc != 4 || (strcmp(argv[3],"on") && strcmp(argv[3],"off")) ||
          facts.encoding != SOX_ENCODING_FLOAT ||
          (facts.container_bits != 32 && facts.container_bits != 64) ||
          !facts.stream.total_frames || facts.stream.total_frames > 257) goto finish;
      enable = !strcmp(argv[3],"on");
      n = (size_t)facts.stream.total_frames;
      bytes = n * facts.stream.channels * sizeof(double);
      memset(samples,0xa5,bytes);
      _mm_setcsr((original_csr & ~(0x40u | 0x8000u)) | (enable ? 0x40u : 0));
      p = lsx_pcm_f64_wav_read(in,(pcm_f64_output){samples,n});
      /* Clear DAZ/FTZ before testing the latch, restore the original on exit. */
      _mm_setcsr(original_csr & ~(0x40u | 0x8000u));
      if (enable && facts.container_bits == 32) {
        if (p.status != PCM_F64_UNSUPPORTED || p.consumed_frames || p.produced_frames) {
          fprintf(stderr,"DAZ read failed to refuse: status=%s frames=%zu\n",
              pcm_f64_status_name(p.status),p.produced_frames);
          _mm_setcsr(original_csr);
          goto finish;
        }
        for (i=0;i<bytes;++i) if (((unsigned char *)samples)[i]!=0xa5) {
          fprintf(stderr,"DAZ read altered the rejected output buffer\n");
          _mm_setcsr(original_csr);
          goto finish;
        }
        again=lsx_pcm_f64_wav_read(in,(pcm_f64_output){samples,n});
        _mm_setcsr(original_csr);
        if (again.status != PCM_F64_IO || again.consumed_frames || again.produced_frames) {
          fprintf(stderr,"DAZ failure did not latch: status=%s frames=%zu\n",
              pcm_f64_status_name(again.status),again.produced_frames);
          goto finish;
        }
        for (i=0;i<bytes;++i) if (((unsigned char *)samples)[i]!=0xa5) {
          fprintf(stderr,"latched read altered the rejected output buffer\n");
          goto finish;
        }
        rc=0; /* Deliberate refusal was observed, no samples written. */
      } else {
        _mm_setcsr(original_csr);
        if (p.status != PCM_F64_DONE || p.produced_frames != n ||
            fwrite(samples,facts.stream.channels*sizeof(double),n,stdout)!=n)
          goto finish;
        rc=0;
      }
#else
      fprintf(stderr,"DAZ regression requires x86 SSE2\n");
      rc=2;
#endif
    } else if (!strcmp(mode,"copy") || !strcmp(mode,"dump")) {
      if (!strcmp(mode,"copy")) {
        if (argc<6 || !code(argv[4],&encoding,&bits)) { rc=2;goto finish; }
        big=argv[5][0]=='B';
        if (sox_dsd_get_layout(in,&layout)!=SOX_DSD_OK) goto finish;
        out=lsx_pcm_f64_wav_open_write(argv[3],&facts.stream,encoding,bits,big,
            layout,in,argc>8 ? argv[8] : NULL,
            argc>7 && !strcmp(argv[7],"deny") ? decline : NULL);
        if (!out) { fail("safe output",NULL); goto finish; }
      }
      if (argc>6 && !strcmp(mode,"copy")) block=(size_t)number(argv[6]);
      else if (argc>3 && !strcmp(mode,"dump")) block=(size_t)number(argv[3]);
      if (block<1 || block>257) { rc=2;goto finish; }
      for (;;) {
        p=lsx_pcm_f64_wav_read(in,(pcm_f64_output){samples,block});
        if (pcm_f64_is_failure(p.status)) { fail("native read",in);goto finish; }
        if (p.produced_frames) {
          read_frames+=p.produced_frames;
          if (out) {
            pcm_f64_progress w=lsx_pcm_f64_wav_write(out,
                (pcm_f64_input){samples,p.produced_frames});
            if (w.status!=PCM_F64_OK || w.consumed_frames!=p.produced_frames) {
              fail("native write",out);goto finish;
            }
            written_frames+=w.consumed_frames;
          } else if (fwrite(samples,sizeof(double)*facts.stream.channels,
                 p.produced_frames,stdout)!=p.produced_frames) goto finish;
        }
        if (p.status==PCM_F64_DONE) break;
        if (!p.produced_frames) { fail("no progress",in);goto finish; }
      }
      if (read_frames!=facts.stream.total_frames || (out && written_frames!=read_frames))
        goto finish;
      rc=0;
    } else rc=2;
  }
finish:
  if (out && sox_close(out)!=SOX_SUCCESS) { fprintf(stderr,"FAIL native WAV close\n");rc=1; }
  if (in && sox_close(in)!=SOX_SUCCESS) { fprintf(stderr,"FAIL WAV input close\n");rc=1; }
  if (raw && fclose(raw)) rc=1;
  if (layout) sox_dsd_layout_free(layout);
  if (sox_quit()!=SOX_SUCCESS) rc=1;
  if (rc!=0) fprintf(stderr,"probe mode=%s failed\n",mode);
  return rc;
}
int main(int argc,char **argv)
{
#ifdef SIGXFSZ
  signal(SIGXFSZ,SIG_IGN); /* short-write/flush failures reach errno */
#endif
  return run(argc,argv);
}
