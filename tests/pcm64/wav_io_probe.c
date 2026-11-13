/* Qualification-only caller for the private, actual-WAV-handler frame API.
 * This executable is not linked into the production command frontend. */
#include "sox_i.h"
#include "pcm_f64_io.h"
#include "wav-size.h"
#include <signal.h>
#include <inttypes.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <float.h>
#if defined(HAVE_UNISTD_H) && !defined(_WIN32)
#include <sys/stat.h>
#include <unistd.h>
#endif
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
#include <xmmintrin.h>
#endif

static sox_bool decline(const char *ignored UNUSED) { return sox_false; }
static unsigned long long number(const char *s)
{
  char *e=NULL;
  unsigned long long n;
  errno=0;
  n=strtoull(s,&e,10);
  if (!s[0] || s[0]=='-' || errno==ERANGE || !e || *e) {
    fprintf(stderr,"bad integer: %s\n",s); exit(2);
  }
  return n;
}
/* The probe uses a raw, seekable binary64 fixture.  Verify its available
 * input frames without reading sample data, before any native writer open.
 * A pipe or uninspectable source cannot satisfy this preflight contract. */
static bool raw_has_frames(FILE *raw, uint32_t channels, uint64_t frames)
{
#if defined(HAVE_UNISTD_H) && !defined(_WIN32)
  struct stat st;
  off_t offset;
  uint64_t needed;
  if (!raw || !channels || fstat(fileno(raw),&st) ||
      !S_ISREG(st.st_mode) || st.st_size<0 ||
      (offset=ftello(raw))<0 || offset>st.st_size ||
      frames > UINT64_MAX / ((uint64_t)channels*sizeof(double))) {
    fprintf(stderr,"raw input length cannot be verified before native output\n");
    return false;
  }
  needed=frames*channels*sizeof(double);
  if (needed > (uint64_t)(st.st_size-offset)) {
    fprintf(stderr,"short raw input: insufficient frames before native output\n");
    return false;
  }
  return true;
#else
  (void)raw; (void)channels; (void)frames;
  fprintf(stderr,"raw input length preflight is unavailable on this host\n");
  return false;
#endif
}

/* generate accepts a raw FILE* rather than a WAV format handle, so the
 * native writer cannot inspect this input itself.  Compare kernel file
 * identities (not spellings) before the output writer may acquire it. */
static bool raw_distinct_from_destination(FILE *raw, const char *destination)
{
#if defined(HAVE_UNISTD_H) && !defined(_WIN32)
  struct stat input, output;
  if (!raw || fstat(fileno(raw), &input)) {
    perror("raw input identity preflight");
    return false;
  }
  if (!strcmp(destination, "-")) {
    if (fstat(fileno(stdout), &output)) {
      perror("output identity preflight");
      return false;
    }
  } else if (stat(destination, &output)) {
    if (errno == ENOENT) return true; /* writer handles exclusive creation */
    perror("output identity preflight");
    return false;
  }
  if (input.st_dev == output.st_dev && input.st_ino == output.st_ino) {
    fprintf(stderr, "raw input aliases destination before native output\n");
    return false;
  }
  return true;
#else
  (void)raw; (void)destination;
  fprintf(stderr,"raw input identity preflight is unavailable on this host\n");
  return false;
#endif
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
  uint64_t frames,to_write=0,read_frames=0,written_frames=0,native_tail=0;
  uint64_t channels_arg,rate_arg;
  size_t block=23, n;
  double samples[64*257];
  int rc=1;
  FILE *raw=NULL;
  const char *mode;

  /* Test-harness capability query; no format handle or WAV data is opened.
   * A disabled/unsupported arithmetic backend must not turn a platform gate
   * into an apparent conformance failure. */
  if (argc == 2 && !strcmp(argv[1], "capabilities")) {
    /* Distinguish configured-out arithmetic, an unsupported host and a
     * broken runtime guard. A supported native build must never turn
     * NUMERIC/UNSUPPORTED into a qualification NOT_RUN. */
    printf("native_build=%s\n", PCM_F64_NATIVE_ENABLED ? "ENABLED" : "DISABLED");
#if defined(FLT_EVAL_METHOD) && FLT_EVAL_METHOD == 0 && \
    (((defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)) || \
     (defined(__aarch64__) && (defined(__GNUC__) || defined(__clang__))))
    printf("native_host=%s\n", pcm_f64_check_ieee_storage() == PCM_F64_OK ?
        "SUPPORTED" : "UNSUPPORTED");
#else
    printf("native_host=UNSUPPORTED\n");
#endif
    printf("native_dsp=%s\n", pcm_f64_status_name(pcm_f64_check_dsp_env()));
    return 0;
  }
  /* Check the native planner at astronomical counts without allocating
   * files. This executable links exactly the same checked C function as
   * the actual writer. Python supplies an independent integer oracle. */
  if (argc==7 && !strcmp(argv[1],"plan")) {
    uint64_t fr=number(argv[2]);
    uint64_t ch=number(argv[3]);
    uint64_t bits_arg=number(argv[4]);
    bool ext=!strcmp(argv[6],"1");
    bool floating=!strcmp(argv[5],"float");
    bool big=!strcmp(argv[5],"big");
    lsx_wav_native_sizes_t sizes;
    uint16_t fmt=(uint16_t)(ext ? 40 : floating ? 18 : 16);
    bool fact=ext || floating;
    if (ch<1 || ch>64 || bits_arg<8 || bits_arg>64 || bits_arg%8 ||
        ch*(bits_arg/8)>UINT16_MAX ||
        !lsx_wav_native_sizes(fr,(uint32_t)(ch*(bits_arg/8)),fmt,fact,big,&sizes)) {
      puts("REFUSED");return 0;
    }
    printf("frames=%" PRIu64 " data=%" PRIu64 " riff=%" PRIu64
           " file=%" PRIu64 " header=%u rf64=%u\n",fr,sizes.data_bytes,
           sizes.riff_bytes,sizes.file_bytes,sizes.header_bytes,(unsigned)sizes.rf64);
    return 0;
  }
  if (argc<3) { fprintf(stderr,"usage: probe capabilities|query|dump|copy|generate|sparse-zero|plan|mixed ...\n");return 2; }
  mode=argv[1];
  if (sox_init()!=SOX_SUCCESS) { fprintf(stderr,"sox_init failed\n");return 2; }
  if (!strcmp(mode,"sparse-zero")) {
    /* sparse-zero out type L|B channels rate declared_frames sparse_frames
     *             [native_tail_frames].
     * UINT64_MAX indicates unknown declared length. Optional real native
     * samples are appended after the sparse zero extent, allowing one test
     * to cross 4 GiB using the normal sample-writing path at bounded cost. */
    if ((argc!=9 && argc!=10) || !code(argv[3],&encoding,&bits) ||
        (strcmp(argv[4],"L") && strcmp(argv[4],"B"))) {
      rc=2;goto finish;
    }
    big=!strcmp(argv[4],"B");
    channels_arg=number(argv[5]);
    rate_arg=number(argv[6]);
    frames=number(argv[7]);
    to_write=number(argv[8]);
    native_tail=argc==10 ? number(argv[9]) : 0;
    if (channels_arg>UINT32_MAX || rate_arg>UINT32_MAX || native_tail>257 ||
        (native_tail && (encoding!=SOX_ENCODING_FLOAT || bits!=64))) {
      rc=2;goto finish;
    }
    if (frames==UINT64_MAX) {
      if (pcm_f64_format_init(&fmt,(uint32_t)rate_arg,(uint32_t)channels_arg,
                              false,0)!=PCM_F64_OK) goto finish;
    } else if (pcm_f64_format_init(&fmt,(uint32_t)rate_arg,
               (uint32_t)channels_arg,true,frames)!=PCM_F64_OK) goto finish;
    out=lsx_pcm_f64_wav_open_write(argv[2],&fmt,encoding,bits,big,NULL,NULL,NULL,
                                   NULL,NULL);
    if (!out) { fail("sparse safe open",NULL);goto finish; }
    status=lsx_wav_native_sparse_zero_frames(out,to_write);
    if (status!=PCM_F64_OK) {
      fprintf(stderr,"FAIL native sparse zero run: %s\n",pcm_f64_status_name(status));
      goto finish;
    }
    if (native_tail) {
      size_t frame_index, channel_index;
      for (frame_index=0; frame_index<native_tail; ++frame_index)
        for (channel_index=0; channel_index<fmt.channels; ++channel_index)
          samples[frame_index*fmt.channels+channel_index]=
              (frame_index+1)*0.125*(channel_index%2 ? -1. : 1.);
      p=lsx_pcm_f64_wav_write(out,(pcm_f64_input){samples,(size_t)native_tail});
      if (p.status!=PCM_F64_OK || p.consumed_frames!=native_tail) {
        fprintf(stderr,"FAIL native samples after sparse extent: %s %zu\n",
                pcm_f64_status_name(p.status),p.consumed_frames);
        goto finish;
      }
    }
    rc=0;
  } else if (!strcmp(mode,"generate")) {
    /* generate raw64 out type L|B channels rate declared_frames to_write
     *          [allow|deny] [report_path] */
    if (argc < 10 || argc > 12 || !code(argv[4],&encoding,&bits) ||
        (strcmp(argv[5],"L") && strcmp(argv[5],"B")) ||
        (argc>10 && strcmp(argv[10],"allow") && strcmp(argv[10],"deny"))) {
      rc=2;goto finish;
    }
    big=!strcmp(argv[5],"B");
    channels_arg=number(argv[6]);
    rate_arg=number(argv[7]);
    frames=number(argv[8]);
    to_write=number(argv[9]); /* Must parse before acquiring the output. */
    if (channels_arg>UINT32_MAX || rate_arg>UINT32_MAX) { rc=2;goto finish; }
    if (frames==UINT64_MAX) { /* a sentinel for unknown, always refused */
      if (pcm_f64_format_init(&fmt,(uint32_t)rate_arg,(uint32_t)channels_arg,
          false,0)!=PCM_F64_OK) goto finish;
    } else if (pcm_f64_format_init(&fmt,(uint32_t)rate_arg,
           (uint32_t)channels_arg,true,frames)!=PCM_F64_OK) goto finish;
    raw=fopen(argv[2],"rb");
    if (!raw) { perror("raw input");goto finish; }
    if (!raw_has_frames(raw,fmt.channels,to_write) ||
        !raw_distinct_from_destination(raw,argv[3])) goto finish;
    out=lsx_pcm_f64_wav_open_write(argv[3],&fmt,encoding,bits,big,NULL,NULL,raw,
        argc>11 ? argv[11] : NULL,argc>10 && !strcmp(argv[10],"deny") ? decline : NULL);
    if (!out) { fail("safe open",NULL);goto finish; }
    frames=to_write;
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
    in=lsx_pcm_f64_wav_open_read(argv[2],
        argc>3 && !strcmp(mode,"query") ? &override : NULL);
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
    } else if (!strcmp(mode,"reject-buffer")) {
      /* A failed native read must not publish part of an invalid frame/block. */
      size_t i, bytes;
      if (argc != 3 || facts.stream.total_frames < 1 ||
          facts.stream.total_frames > 257) goto finish;
      n=(size_t)facts.stream.total_frames;
      bytes=n*facts.stream.channels*sizeof(double);
      memset(samples,0xa5,bytes);
      p=lsx_pcm_f64_wav_read(in,(pcm_f64_output){samples,n});
      if (p.status != PCM_F64_NUMERIC || p.produced_frames || p.consumed_frames) {
        fprintf(stderr,"failed malformed read wrong status/count: %s %zu\n",
            pcm_f64_status_name(p.status),p.produced_frames);
        goto finish;
      }
      for (i=0;i<bytes;++i) if (((unsigned char *)samples)[i]!=0xa5) {
        fprintf(stderr,"failed malformed read mutated caller-owned buffer byte %zu\n",i);
        goto finish;
      }
      p=lsx_pcm_f64_wav_read(in,(pcm_f64_output){samples,n});
      if (p.status != PCM_F64_IO || p.produced_frames || p.consumed_frames) {
        fprintf(stderr,"failed malformed read did not latch\n");
        goto finish;
      }
      for (i=0;i<bytes;++i) if (((unsigned char *)samples)[i]!=0xa5) {
        fprintf(stderr,"latched malformed read mutated caller-owned buffer byte %zu\n",i);
        goto finish;
      }
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
      /* Block arguments are input-independent: refuse them before the writer
       * opens a destination, not after it has committed the WAV header. */
      if (argc>6 && !strcmp(mode,"copy")) {
        uint64_t requested=number(argv[6]);
        if (!requested || requested>257) { rc=2;goto finish; }
        block=(size_t)requested;
      } else if (argc>3 && !strcmp(mode,"dump")) {
        uint64_t requested=number(argv[3]);
        if (!requested || requested>257) { rc=2;goto finish; }
        block=(size_t)requested;
      }
      if (!strcmp(mode,"copy")) {
        if (argc<6 || argc>9 || !code(argv[4],&encoding,&bits) ||
            (strcmp(argv[5],"L") && strcmp(argv[5],"B")) ||
            (argc>7 && strcmp(argv[7],"allow") && strcmp(argv[7],"deny"))) {
          rc=2;goto finish;
        }
        big=!strcmp(argv[5],"B");
        if (sox_dsd_get_layout(in,&layout)!=SOX_DSD_OK) goto finish;
        out=lsx_pcm_f64_wav_open_write(argv[3],&facts.stream,encoding,bits,big,
            layout,in,NULL,argc>8 ? argv[8] : NULL,
            argc>7 && !strcmp(argv[7],"deny") ? decline : NULL);
        if (!out) { fail("safe output",NULL); goto finish; }
      }
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
