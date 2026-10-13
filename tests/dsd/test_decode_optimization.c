/* Decoder optimization contract regression. Include the production context
 * implementations only to reach otherwise impractical uint64 boundaries and
 * holdback states; ordinary streaming below uses the public API. This follows
 * the existing allocation-fault probe and does not add production test hooks.
 * --trace emits observable calls and binary64 samples for baseline/candidate
 * differential replay. Internal cached targets are deliberately not observable. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fenv.h>
#include <float.h>
#include <time.h>
#include <inttypes.h>
#include "../../src/dsd_decode.c"
#include "../../src/dsd_public.c"
#if defined(__unix__) || defined(__APPLE__)
#include <sys/mman.h>
#include <unistd.h>
#endif

static unsigned checks, serial;
static int trace;
#define REQUIRE(x) do { ++checks; if (!(x)) { \
  fprintf(stderr,"decoder optimization line %d: %s\n",__LINE__,#x); exit(1); \
} } while (0)

static void observe(sox_dsd_decoder_t *d, sox_dsd_status_t st,
    size_t used, size_t made, const double *out)
{
  sox_dsd_report_t r;
  memset(&r,0,sizeof(r)); r.size=sizeof(r);r.version=1;
  REQUIRE(sox_dsd_decoder_report(d,&r)==SOX_DSD_OK);
  if (trace) {
    printf("%u %d %zu %zu %" PRIu64 " %" PRIu64 " %" PRIu64 " %d\n",
      serial,st,used,made,r.native_frames,r.intermediate_frames,r.output_frames,r.status);
    for (size_t i=0;i<made*r.channels;++i) {
      uint64_t word; memcpy(&word,out+i,sizeof(word));
      printf("%016" PRIx64 "%c",word,(i+1)%r.channels ? ' ' : '\n');
    }
  }
}

static sox_dsd_decoder_t *create(unsigned native,unsigned pcm,unsigned channels,
    unsigned profile,const char *tier)
{
  sox_dsd_decode_options_t o;
  sox_dsd_decoder_t *d=NULL;
  sox_dsd_decode_options_init_extended(&o);
  o.native_hz=native;o.output_hz=pcm;o.channels=channels;o.profile=profile;
  o.kernel_fir=tier;
  REQUIRE(sox_dsd_decoder_create(&o,&d)==SOX_DSD_OK);
  return d;
}

static double *stream(unsigned native,unsigned pcm,unsigned channels,
    unsigned profile,size_t n,unsigned schedule,const char *tier)
{
  static const size_t chunks[]={1,3,31,2,257,19,4096};
  static const size_t caps[]={1,7,2,13,1};
  const size_t want=(size_t)(((uint64_t)n*pcm+native/2)/native);
  sox_dsd_decoder_t *d=create(native,pcm,channels,profile,tier);
  sox_sample_t *bits=calloc((n+1)*channels,sizeof(*bits));
  double *output=calloc((want+32)*channels,sizeof(*output));
  size_t used=0,made=0,calls=0;
  uint32_t seed=0x53d12807;
  REQUIRE(bits && output);
  for (size_t i=0;i<n*channels;++i) {
    seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;
    bits[i]=(seed&1)?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
  }
  ++serial;
  do {
    size_t in=n-used,out;
    sox_dsd_status_t st;
    if (schedule && in>chunks[calls%7]) in=chunks[calls%7];
    out=schedule?caps[calls%5]:want+16-made;
    if (calls%11==0) {
      size_t zero=0, offered=in;
      uint64_t before=d->native_frames,delivered=d->delivered;
      REQUIRE(sox_dsd_decoder_process(d,NULL,&offered,NULL,&zero)==SOX_DSD_NEED_OUTPUT);
      REQUIRE(offered==0 && zero==0 && d->native_frames==before && d->delivered==delivered);
    }
    st=sox_dsd_decoder_process(d,bits+used*channels,&in,output+made*channels,&out);
    REQUIRE(st==SOX_DSD_NEED_INPUT || st==SOX_DSD_NEED_OUTPUT);
    observe(d,st,in,out,output+made*channels);
    REQUIRE(in || out || !n);
    used+=in;made+=out;++calls;
    REQUIRE(made<=((uint64_t)used*pcm+native/2)/native);
    REQUIRE(calls<n*3+100);
  } while (used<n);
  for (;;) {
    size_t out=schedule?caps[calls++%5]:want+16-made;
    sox_dsd_status_t st=sox_dsd_decoder_finish(d,output+made*channels,&out);
    observe(d,st,0,out,output+made*channels);
    made+=out;
    REQUIRE(made<=want);
    if (st==SOX_DSD_DONE) break;
    REQUIRE(st==SOX_DSD_NEED_OUTPUT && out);
  }
  REQUIRE(made==want && d->native_frames==n);
  {
    size_t out=1,in=0; double sentinel=123.;
    REQUIRE(sox_dsd_decoder_finish(d,&sentinel,&out)==SOX_DSD_DONE && out==0 && sentinel==123.);
    out=1;
    REQUIRE(sox_dsd_decoder_process(d,NULL,&in,&sentinel,&out)==SOX_DSD_BAD_ARGUMENT);
  }
  free(bits);sox_dsd_decoder_destroy(d);return output;
}

static void errors_and_boundaries(const char *tier)
{
  const unsigned natives[]={2822400,5644800,11289600};
  const unsigned pcms[]={44100,48000,88200,96000,176400,192000,352800,384000,705600};
  const size_t invalid[]={0,1,31,32,1347,1348,1349,2725,4000};
  sox_sample_t bits[15000]; double out[15000];
  for (size_t i=0;i<15000;++i) bits[i]=SOX_SAMPLE_MAX;
  for (unsigned channels=1;channels<=3;++channels) {
    for (size_t k=0;k<sizeof(invalid)/sizeof(*invalid);++k) {
      sox_dsd_decoder_t *d=create(2822400,705600,channels,0,tier);
      size_t in=4500,cap=4500;
      ++serial;bits[invalid[k]*channels+channels-1]=0;
      REQUIRE(sox_dsd_decoder_process(d,bits,&in,out,&cap)==SOX_DSD_NUMERIC_ERROR);
      REQUIRE(in==0 && cap==0 && d->native_frames==invalid[k]);
      observe(d,SOX_DSD_NUMERIC_ERROR,in,cap,out);
      in=cap=0;
      REQUIRE(sox_dsd_decoder_process(d,NULL,&in,NULL,&cap)==SOX_DSD_NUMERIC_ERROR);
      REQUIRE(sox_dsd_decoder_finish(d,NULL,&cap)==SOX_DSD_NUMERIC_ERROR);
      bits[invalid[k]*channels+channels-1]=SOX_SAMPLE_MAX;
      sox_dsd_decoder_destroy(d);
    }
  }
  for (unsigned r=0;r<3;++r) for (unsigned p=0;p<9;++p) for (unsigned profile=0;profile<2;++profile) {
    sox_dsd_decoder_t *d=create(natives[r],pcms[p],1,profile,tier);
    const lsx_dsd_frontend_profile *f=lsx_dsd_frontend_profile_find(natives[r],profile);
    const uint64_t limit=UINT64_MAX-f->delay_native_frames-natives[r]/f->intermediate_hz;
    size_t in=8,cap=8;
    uint64_t expected;
    ++serial;
    d->native_frames=d->front->real_frames=limit-3;
    REQUIRE(lsx_dsd_count_convert(d->native_frames,natives[r],pcms[p],&d->target));
    REQUIRE(sox_dsd_decoder_process(d,bits,&in,out,&cap)==SOX_DSD_NUMERIC_ERROR);
    REQUIRE(in==0 && cap==0 && d->native_frames==limit && d->front->real_frames==limit);
    observe(d,SOX_DSD_NUMERIC_ERROR,in,cap,out);
    REQUIRE(lsx_dsd_count_convert(limit,natives[r],pcms[p],&expected));
    (void)expected; /* Cached release targets need not update without PCM. */
    sox_dsd_decoder_destroy(d);
    d=create(natives[r],pcms[p],1,profile,tier);
    d->native_frames=UINT64_MAX-1;in=cap=2;
    REQUIRE(sox_dsd_decoder_process(d,bits,&in,out,&cap)==SOX_DSD_BAD_ARGUMENT);
    REQUIRE(in==0 && cap==0 && d->native_frames==UINT64_MAX-1);
    sox_dsd_decoder_destroy(d);
#if defined(__SIZEOF_INT128__)
    for (unsigned i=0;i<100;++i) {
      uint64_t n=i<50 ? (uint64_t)i*natives[r]+i : UINT64_MAX-i;
      uint64_t value;
      __uint128_t wide=(__uint128_t)n*pcms[p]+natives[r]/2;
      REQUIRE(lsx_dsd_count_convert(n,natives[r],pcms[p],&value));
      REQUIRE(value==(uint64_t)(wide/natives[r]));
    }
#endif
  }
  /* Exercise an output held at the half-frame rounding threshold. This state
   * is injected so future latency changes cannot silently break the fallback. */
  {
    sox_dsd_decoder_t *d=create(2822400,705600,1,0,tier);
    size_t in=1,cap=1;
    ++serial;d->queue[0]=.25;d->qlen=1;
    REQUIRE(sox_dsd_decoder_process(d,bits,&in,out,&cap)==SOX_DSD_NEED_INPUT);
    REQUIRE(in==1 && cap==0 && d->qlen==1 && d->native_frames==1);
    observe(d,SOX_DSD_NEED_INPUT,in,cap,out);
    in=8;cap=1;
    REQUIRE(sox_dsd_decoder_process(d,bits,&in,out,&cap)==SOX_DSD_NEED_OUTPUT);
    REQUIRE(in==1 && cap==1 && out[0]==.25 && d->native_frames==2);
    observe(d,SOX_DSD_NEED_OUTPUT,in,cap,out);
    sox_dsd_decoder_destroy(d);
  }
}

#if defined(DSD_OPTIMIZATION)
static void kernel_identity(void)
{
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  double s[57]; unsigned x=0x97a113;
  int rounding=fegetround();
  for (unsigned m=0;m<4;++m) {
    REQUIRE(fesetround(modes[m])==0);
    for (unsigned k=0;k<10000;++k) {
      for (unsigned i=0;i<57;++i) {
        x^=x<<13;x^=x>>17;x^=x<<5;
        s[i]=((double)(int32_t)x)/2147483648.;
        if (k%11==0) s[i]*=DBL_MIN;
        if (k%13==0) s[i]=(i&1)?0.:-0.;
      }
      double a=lsx_dsd_fir_scalar(lsx_dsd_coeff_halfband,57,s,1);
      double b=lsx_dsd_fir_halfband57(lsx_dsd_coeff_halfband,s);
      REQUIRE(memcmp(&a,&b,sizeof(a))==0);
    }
  }
  REQUIRE(fesetround(rounding)==0);
#if defined(MAP_ANONYMOUS)
  {
    long page=sysconf(_SC_PAGESIZE);
    char *mem=mmap(NULL,(size_t)page*3,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    REQUIRE(mem!=MAP_FAILED);
    REQUIRE(mprotect(mem+page,(size_t)page,PROT_READ|PROT_WRITE)==0);
    for (unsigned end=0;end<2;++end) {
      double *p=(double *)(mem+page+(end?page-57*sizeof(double):0));
      for (unsigned i=0;i<57;++i) p[i]=(i&1)?1.:-1.;
      double a=lsx_dsd_fir_scalar(lsx_dsd_coeff_halfband,57,p,1);
      double b=lsx_dsd_fir_halfband57(lsx_dsd_coeff_halfband,p);
      REQUIRE(memcmp(&a,&b,sizeof(a))==0);
    }
    REQUIRE(munmap(mem,(size_t)page*3)==0);
  }
#endif
}
#endif

#if defined(DSD_OPTIMIZATION)
/* Stage-level comparison, not a full-decoder speed claim. The block arm pays
 * for input assembly, retained history and output traversal. Grouped real-time
 * outputs are intentionally NOT connected to the production streaming graph. */
static int benchmark_halfband(const char *tier,const char *mode,size_t frames)
{
  const lsx_dsd_kernel *kernel=NULL;
  double ring[114]={0},window[120]={0},out[32],sum=0.;
  size_t n=0,head=0,outputs=0,batch=0;
  clock_t begin;
  const int ordered=!strcmp(mode,"ordered");
  if (lsx_dsd_kernel_select(LSX_DSD_FIR,tier,&kernel)) return 2;
  if (!strncmp(mode,"block-",6)) batch=(size_t)strtoul(mode+6,NULL,10);
  if ((batch && batch!=2 && batch!=4 && batch!=8 && batch!=32) ||
      (!batch && strcmp(mode,"reference") && strcmp(mode,"ordered"))) return 2;
  begin=clock();
  while (n<frames) {
    if (batch) {
      size_t count=frames-n,produced;
      if (count>2*batch) count=2*batch;
      for (size_t i=0;i<count;++i)
        window[56+i]=(((uint32_t)(n+i)*1664525u+1013904223u)>>31)?1.:-1.;
      produced=(count+1)/2;
      kernel->fir_block(lsx_dsd_coeff_halfband,57,window,produced,2,1,out);
      for (size_t i=0;i<produced;++i) sum+=out[i];
      memmove(window,window+count,56*sizeof(double));
      n+=count;outputs+=produced;
    } else {
      double x=(((uint32_t)n*1664525u+1013904223u)>>31)?1.:-1.;
      ring[head]=ring[head+57]=x;
      if (!(n&1)) {
        sum+=ordered ?
          lsx_dsd_fir_halfband57(lsx_dsd_coeff_halfband,ring+head+1) :
          lsx_dsd_fir_scalar(lsx_dsd_coeff_halfband,57,ring+head+1,1);
        ++outputs;
      }
      head=head==56?0:head+1;++n;
    }
  }
  {
    double seconds=(double)(clock()-begin)/CLOCKS_PER_SEC;
    printf("{\"tier\":\"%s\",\"mode\":\"%s\",\"native_frames\":%zu,"
      "\"outputs\":%zu,\"cpu_seconds\":%.9g,\"cpu_ns_per_output\":%.9g,"
      "\"checksum\":\"%a\",\"stage_history_cost_included\":true}\n",
      tier,mode,frames,outputs,seconds,seconds*1e9/outputs,sum);
  }
  return 0;
}
#endif

int main(int argc,char **argv)
{
  const unsigned natives[]={2822400,5644800,11289600};
  const unsigned pcms[]={44100,48000,88200,96000,176400,192000,352800,384000,705600};
  const size_t tiny[]={0,1,2,15,16,17,31,32,33,56,57,63,64,65,1347,1348,1349,1636,2468,2724};
  const char *tier=argc>1?argv[1]:"scalar";
  trace=argc>2 && !strcmp(argv[2],"--trace");
#if defined(DSD_OPTIMIZATION)
  if (argc==5 && !strcmp(argv[1],"--bench")) {
    char *end;
    unsigned long long n=strtoull(argv[4],&end,10);
    if (*end || n<16384 || n>40000000) return 2;
    return benchmark_halfband(argv[2],argv[3],(size_t)n);
  }
#endif
  sox_init();
  for (unsigned r=0;r<3;++r) for (unsigned p=0;p<9;++p) for (unsigned profile=0;profile<2;++profile) {
    unsigned channels=(p%3==0)?1:(p%3==1)?2:6;
    size_t n=4099,want=(size_t)(((uint64_t)n*pcms[p]+natives[r]/2)/natives[r]);
    double *a=stream(natives[r],pcms[p],channels,profile,n,0,tier);
    double *b=stream(natives[r],pcms[p],channels,profile,n,1,tier);
    REQUIRE(memcmp(a,b,want*channels*sizeof(*a))==0);free(a);free(b);
    /* Tiny streams cover ties, partial bytes, ring wraps and lookahead edges. */
    for (unsigned t=0;t<sizeof(tiny)/sizeof(*tiny);++t) {
      double *v=stream(natives[r],pcms[p],1,profile,tiny[t],1,tier);free(v);
    }
  }
  errors_and_boundaries(tier);
#if defined(DSD_OPTIMIZATION)
  if (!trace) kernel_identity();
#endif
  sox_quit();
  fprintf(stderr,"decoder optimization PASS (%u assertions, %u stream cases, %s)\n",checks,serial,tier);
  return 0;
}
