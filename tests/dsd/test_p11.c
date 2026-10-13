#if !defined(_WIN32) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L
#endif
/* P11 executable dispatch, FIR, normal-SDM and bounded-tail regression.
 * No assertion relies on the host advertising AVX2 or on CPUID masking.
 * Mocked CPUID checks selection; actual forced tests execute on this host. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include "dsd_decode.h"
#include "dsd_coeffs.h"
#include "pcmdsd.h"
#include <float.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define CHECK(c,msg) do {if(!(c)){fprintf(stderr,"FAIL %s:%d: %s\n",\
                              __FILE__,__LINE__,msg);exit(1);}}while(0)

typedef struct {
  unsigned max_leaf, ecx, edx, ebx7, leaf0, leaf1, leaf7, xgets;
  uint64_t xcr0;
} mock_cpu;
static unsigned fake_cpuid(void *v,unsigned leaf,unsigned subleaf,unsigned r[4])
{
  mock_cpu *m=v;
  memset(r,0,4*sizeof(*r));
  if (leaf>m->max_leaf) return 0;
  if (!leaf) {++m->leaf0;r[0]=m->max_leaf;}
  else if (leaf==1) {++m->leaf1;r[2]=m->ecx;r[3]=m->edx;}
  else if (leaf==7 && !subleaf) {++m->leaf7;r[1]=m->ebx7;}
  return 1;
}
static uint64_t fake_xgetbv(void *v,unsigned index)
{
  mock_cpu *m=v;
  CHECK(index==0,"unexpected xgetbv index");
  ++m->xgets;
  return m->xcr0;
}
static void test_caps(void)
{
  mock_cpu m={0};
  lsx_dsd_cpu_probe p={&m,fake_cpuid,fake_xgetbv};
  const lsx_dsd_kernel *k;
  unsigned features;
  CHECK(lsx_dsd_features_probe(NULL)==0,"null probe");
  CHECK(lsx_dsd_features_probe(&p)==0 && m.leaf1==0 && !m.xgets,
        "missing leaf 1 must never issue XGETBV");
  m.max_leaf=1;m.edx=1u<<26;m.ecx=(1u<<26)|(1u<<28);m.xcr0=6;
  features=lsx_dsd_features_probe(&p);
  CHECK(features==LSX_DSD_CPU_SSE2 && !m.xgets,"OSXSAVE missing");
  m.ecx=(1u<<27)|(1u<<28);
  CHECK(lsx_dsd_features_probe(&p)==LSX_DSD_CPU_SSE2 && !m.xgets,"XSAVE missing");
  m.ecx=(1u<<26)|(1u<<27);
  CHECK(lsx_dsd_features_probe(&p)==LSX_DSD_CPU_SSE2 && !m.xgets,"CPU AVX missing");
  m.ecx|=(1u<<28);
  for (m.xcr0=0;m.xcr0<8;++m.xcr0) {
    features=lsx_dsd_features_probe(&p);
    CHECK(!!(features&LSX_DSD_CPU_AVX1)==((m.xcr0&6)==6),"XCR0 mask");
  }
  m.max_leaf=7;m.xcr0=6;m.ebx7=0;
  CHECK((lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX1) &&
        m.leaf7==1 && !(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX2),
        "AVX1 availability remains independent of AVX2 capability");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"scalar",0,&k)==0 &&
        k==&lsx_dsd_kernel_scalar,"scalar universal");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"nonesuch",3,&k)==-1 && !k,
        "unknown force fails closed");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_SDM,"avx2",3,&k)==-2 && !k,
        "AVX2 force fails when leaf 7 capability absent");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_SDM,"avx2-fma",15,&k)==-2 && !k,
        "unbuilt FMA descriptor must never alias AVX2 baseline");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"avx1",0,&k)==-2 && !k,
        "unsupported force fails closed");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_SDM,"sse2",0,&k)==-2 && !k,
        "unsupported SDM force fails closed");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_SDM,"auto",3,&k)==0 &&
        k==&lsx_dsd_kernel_scalar,"certified master remains scalar by default");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"auto",0,&k)==0 &&
        k==&lsx_dsd_kernel_scalar,"non-x86 scalar fallback");
#if defined(HAVE_DSD_SSE2)
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"auto",3,&k)==0 &&
        k==&lsx_dsd_kernel_sse2,"unknown x86 FIR prefers SSE2");
#endif
#if defined(HAVE_DSD_AVX1)
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_SDM,"avx1",3,&k)==0 &&
        k==&lsx_dsd_kernel_avx1,"AVX1 independent of AVX2");
#endif
#if defined(HAVE_DSD_AVX2)
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_SDM,"avx2",7,&k)==0 &&
        k==&lsx_dsd_kernel_avx2,"AVX2 does not require FMA");
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"avx2",7,&k)==0 &&
        k==&lsx_dsd_kernel_avx2,"AVX2 independent FIR available without FMA");
#endif
  /* Incomplete CPUID leaf-7/XCR0 must not enable AVX2 or issue XGETBV on
   * CPUs without OSXSAVE. Only leaf-1 FMA+OSXSAVE grants FMA feature. */
  m.max_leaf=7;m.xcr0=6;m.ebx7=1u<<5;m.ecx=(1u<<26)|(1u<<27)|(1u<<28);
  CHECK((lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX2)!=0,
        "AVX2 enabled by CPUID leaf7 and YMM OS state");
  CHECK(!(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_FMA),"FMA absent despite AVX2");
  m.ecx|=1u<<12;
  CHECK((lsx_dsd_features_probe(&p)&LSX_DSD_CPU_FMA)!=0,"FMA detected separately");
  m.xcr0=2;
  CHECK(!(lsx_dsd_features_probe(&p)&(LSX_DSD_CPU_AVX2|LSX_DSD_CPU_FMA)),
        "missing YMM state disables AVX2 and FMA");
  m.xcr0=6;m.max_leaf=1;
  CHECK(!(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX2),
        "missing leaf seven disables AVX2");
  m.max_leaf=7;m.ecx&=~(1u<<27);
  {unsigned before=m.leaf7, reads=m.xgets;
   CHECK(!(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX2) &&
         m.leaf7==before && m.xgets==reads,
         "no feature-leaf7 or XGETBV access without OSXSAVE");}
  CHECK(sdm_normal_decision(-0.0)==-1 && sdm_normal_decision(0.0)==1,
        "negative-zero quantizer tie rule");
  printf("PASS cpuid mock, XCR0, independent family policy, negative-zero\n");
}

/* Override coverage operates on real contexts, not merely names accepted by
 * the selector. The public version-1 record is also tested at its old size. */
static void set_override(const char *name,const char *value)
{
#if defined(_WIN32)
  CHECK(_putenv_s(name,value?value:"")==0,"set Windows test override");
#else
  CHECK((value?setenv(name,value,1):unsetenv(name))==0,"set test override");
#endif
}

static void test_context_overrides(void)
{
  static const char *tiers[]={"scalar","sse2","avx1","avx2"};
  unsigned i;
  lsx_dsd_reconstruction *fir_first=NULL,*fir_second=NULL;
  lsx_pcmdsd *sdm_first=NULL,*sdm_second=NULL;
  sox_dsd_decoder_t *dec=NULL;
  sox_dsd_decode_options_t opt;
  const lsx_dsd_kernel *kernel=NULL;
  const lsx_pcmdsd_profile *profile=lsx_pcmdsd_profile_find(2822400);
  CHECK(profile!=NULL,"P10 profile available for P11 context tests");
  set_override("LSX_DSD_FIR_KERNEL","avx2");
  set_override("LSX_DSD_SDM_KERNEL","avx2");
  for(i=0;i<sizeof(tiers)/sizeof(*tiers);++i) {
    const char *tier=tiers[i];
    int supported=lsx_dsd_kernel_select(LSX_DSD_FIR,tier,&kernel)==0;
    if(!supported) continue; /* scalar always, ISA tiers only if supported */
    set_override("SOX_DSD_KERNEL_FIR",tier);
    set_override("SOX_DSD_KERNEL_SDM",tier);
    CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_MASTERING,1,
              &fir_second)==SOX_DSD_OK,"documented FIR force creates context");
    CHECK(!strcmp(lsx_dsd_reconstruction_kernel_name(fir_second),tier),
          "documented FIR force selects requested implementation");
    CHECK(lsx_pcmdsd_candidate_create(88200,2822400,.5,0,NULL,
              profile->bounds,&sdm_second)==SOX_DSD_OK,
          "documented SDM force creates candidate context");
    CHECK(!strcmp(lsx_pcmdsd_kernel_name(sdm_second),tier),
          "documented SDM force selects requested implementation");
    if(!fir_first) {fir_first=fir_second;fir_second=NULL;}
    if(!sdm_first) {sdm_first=sdm_second;sdm_second=NULL;}
    if(fir_first && fir_second)
      CHECK(!strcmp(lsx_dsd_reconstruction_kernel_name(fir_first),"scalar"),
            "first decoder retains its kernel after another context is created");
    if(sdm_first && sdm_second)
      CHECK(!strcmp(lsx_pcmdsd_kernel_name(sdm_first),"scalar"),
            "first encoder retains its kernel after another context is created");
    lsx_dsd_reconstruction_destroy(fir_second);fir_second=NULL;
    lsx_pcmdsd_destroy(sdm_second);sdm_second=NULL;
  }
  CHECK(fir_first && sdm_first,"scalar context snapshots created");
  set_override("SOX_DSD_KERNEL_FIR","unknown-p11-fir");
  CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_MASTERING,1,
            &fir_second)==SOX_DSD_UNSUPPORTED && !fir_second,
        "unknown documented FIR override fails at creation");
  set_override("SOX_DSD_KERNEL_SDM","unknown-p11-sdm");
  CHECK(lsx_pcmdsd_candidate_create(88200,2822400,.5,0,NULL,
            profile->bounds,&sdm_second)==SOX_DSD_BAD_ARGUMENT && !sdm_second,
        "unknown documented SDM override fails at creation");
  set_override("SOX_DSD_KERNEL_FIR","avx2-fma");
  CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_MASTERING,1,
            &fir_second)==SOX_DSD_UNSUPPORTED && !fir_second,
        "unsupported documented FIR override fails without substitution");
  set_override("SOX_DSD_KERNEL_SDM","avx2-fma");
  CHECK(lsx_pcmdsd_candidate_create(88200,2822400,.5,0,NULL,
            profile->bounds,&sdm_second)==SOX_DSD_UNSUPPORTED && !sdm_second,
        "unsupported documented SDM override fails without substitution");
  CHECK(!strcmp(lsx_dsd_reconstruction_kernel_name(fir_first),"scalar") &&
        !strcmp(lsx_pcmdsd_kernel_name(sdm_first),"scalar"),
        "earlier contexts remain independent after override failures");
  lsx_dsd_reconstruction_destroy(fir_first);
  lsx_pcmdsd_destroy(sdm_first);

  /* Original initializer must never overwrite an old-sized allocation. */
  {
    union {
      sox_dsd_decode_options_t alignment;
      unsigned char bytes[sizeof(sox_dsd_decode_options_t)+16];
    } storage;
    const size_t legacy=offsetof(sox_dsd_decode_options_t,kernel_fir);
    memset(&storage,0x5a,sizeof(storage));
    sox_dsd_decode_options_init((sox_dsd_decode_options_t *)storage.bytes);
    CHECK(((sox_dsd_decode_options_t *)storage.bytes)->size==legacy &&
          storage.bytes[legacy]==0x5a &&
          storage.bytes[legacy+sizeof(void *)]==0x5a,
          "original options initializer writes only its P07 ABI prefix");
  }
  sox_dsd_decode_options_init_extended(&opt);
  CHECK(opt.size==sizeof(opt) && !opt.kernel_fir,
        "extended options initializer clears new field and advertises full size");
  opt.native_hz=2822400;opt.output_hz=88200;opt.channels=1;
  opt.kernel_fir="scalar";
  CHECK(sox_dsd_decoder_create(&opt,&dec)==SOX_DSD_OK &&
        !strcmp(lsx_dsd_decoder_kernel_name(dec),"scalar"),
        "library option overrides an invalid environment force");
  sox_dsd_decoder_destroy(dec);dec=NULL;
  opt.kernel_fir="avx2-fma";
  CHECK(sox_dsd_decoder_create(&opt,&dec)==SOX_DSD_UNSUPPORTED && !dec,
        "public decoder returns UNSUPPORTED for unavailable library selection");
  opt.kernel_fir="garbage";
  CHECK(sox_dsd_decoder_create(&opt,&dec)==SOX_DSD_UNSUPPORTED && !dec,
        "public decoder returns UNSUPPORTED for unknown library selection");
  sox_dsd_decode_options_init(&opt);
  opt.native_hz=2822400;opt.output_hz=88200;opt.channels=1;
  CHECK(opt.size==offsetof(sox_dsd_decode_options_t,kernel_fir),
        "old initializer retains old size for legacy caller");
  set_override("SOX_DSD_KERNEL_FIR","scalar");
  CHECK(sox_dsd_decoder_create(&opt,&dec)==SOX_DSD_OK &&
        !strcmp(lsx_dsd_decoder_kernel_name(dec),"scalar"),
        "original-size version-1 record remains usable");
  sox_dsd_decoder_destroy(dec);dec=NULL;
  opt.size=offsetof(sox_dsd_decode_options_t,kernel_fir)-1;
  CHECK(sox_dsd_decoder_create(&opt,&dec)==SOX_DSD_BAD_ARGUMENT && !dec,
        "truncated version-1 record rejected");
  opt.size=sizeof(opt);opt.version=2;
  CHECK(sox_dsd_decoder_create(&opt,&dec)==SOX_DSD_BAD_ARGUMENT && !dec,
        "unsupported semantic version rejected");

  /* Compatibility aliases still function when no documented hook is set. */
  set_override("SOX_DSD_KERNEL_FIR",NULL);
  set_override("SOX_DSD_KERNEL_SDM",NULL);
  set_override("LSX_DSD_FIR_KERNEL","scalar");
  set_override("LSX_DSD_SDM_KERNEL","scalar");
  CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_MASTERING,1,
            &fir_second)==SOX_DSD_OK &&
        !strcmp(lsx_dsd_reconstruction_kernel_name(fir_second),"scalar"),
        "legacy FIR alias remains a fallback");
  CHECK(lsx_pcmdsd_candidate_create(88200,2822400,.5,0,NULL,
            profile->bounds,&sdm_second)==SOX_DSD_OK &&
        !strcmp(lsx_pcmdsd_kernel_name(sdm_second),"scalar"),
        "legacy SDM alias remains a fallback");
  lsx_dsd_reconstruction_destroy(fir_second);
  lsx_pcmdsd_destroy(sdm_second);
  set_override("LSX_DSD_FIR_KERNEL",NULL);
  set_override("LSX_DSD_SDM_KERNEL",NULL);
  puts("PASS documented override, per-context retention, public option precedence/ABI");
}

static unsigned rng=0x73523d19;
static double random_finite(void)
{
  rng ^= rng<<13; rng^=rng>>17; rng^=rng<<5;
  return ((int32_t)rng / 2147483648.) * .7;
}
static void test_fir(const lsx_dsd_kernel *k)
{
  static const unsigned taps_list[]={1,3,57,61,77,117,153,257};
  double h[257],data[1024+2],out[23],ref[23],canary=12345.25;
  size_t t,j,n,w,stride;
  for(t=0;t<sizeof(taps_list)/sizeof(*taps_list);++t) {
    unsigned taps=taps_list[t],mid=taps/2;
    for(j=0;j<taps;++j) h[j]=random_finite()*.01;
    for(j=0;j<mid;++j) h[taps-1-j]=h[j];
    h[mid]=.5;
    for(stride=1;stride<=3;++stride) for(n=0;n<=17;++n) {
      for(j=0;j<sizeof(data)/sizeof(double);++j) data[j]=random_finite();
      for(w=0;w<2;++w) {
        size_t i;
        if(w && taps>1) {
          for(j=0;j<mid;++j)
            if(j&1) h[j]=h[taps-1-j]=0.0;
        }
        out[n]=canary;
        k->fir_block(h,taps,data+1,n,stride,(int)w,out);
        CHECK(out[n]==canary,"FIR overran the bounded output tail");
        for(i=0;i<n;++i) {
          long double hp=h[mid]*(long double)data[1+i*stride+mid];
          double norm=0.0,peak=1.0,eps;
          size_t q;
          ref[i]=lsx_dsd_fir_scalar(h,taps,data+1+i*stride,(int)w);
          for(q=0;q<mid;++q) {
            if(w && h[q]==0.0) continue;
            hp+=(long double)h[q]*((long double)data[1+i*stride+q]+
                 (long double)data[1+i*stride+taps-1-q]);
          }
          for(q=0;q<taps;++q) {
            norm+=fabs(h[q]);
            if(fabs(data[1+i*stride+q])>peak)peak=fabs(data[1+i*stride+q]);
          }
          eps=16*DBL_EPSILON*taps*norm*peak+1e-16;
          CHECK(fabs(out[i]-ref[i])<=eps,"FIR block/scalar envelope");
          CHECK(fabsl((long double)out[i]-hp)<=eps,"FIR high-precision envelope");
          CHECK(fabs(k->fir_single(h,taps,data+1+i*stride,(int)w)-ref[i])<=eps,
                "FIR single production envelope");
          CHECK(fabs((out[i]-ref[i])*SOX_SAMPLE_MAX)<.5,
                "FIR graph cannot deviate by more than one LSB");
        }
      }
    }
  }
  printf("PASS FIR tier=%s odd taps, aligned/unaligned, tails, stride, oracle\n",k->name);
}

static void test_sdm(const lsx_dsd_kernel *k)
{
  static const char *ids[]={
    "encode.mastering.v1.dsd64","encode.mastering.v1.dsd128",
    "encode.mastering.v1.dsd256","encode.diagnostic.sdm6.v1.dsd64",
    "encode.diagnostic.clans8.v1.dsd64"};
  static const unsigned rates[]={2822400,5644800,11289600,2822400,2822400};
  const size_t n=8192;
  double input[8192], small_bounds[8];
  sox_sample_t full[8192],split[8192];
  sdm_normal_t a,b;
  sdm_normal_monitor_t ma,mb;
  size_t p,q,j;
  for(j=0;j<n;++j)
    input[j]=.10*sin(6.283185307179586*(double)j/183.)+.02;
  for(p=0;p<sizeof(ids)/sizeof(*ids);++p) {
    const sdm_profile_t *profile=sdm_profile_find(ids[p],rates[p]);
    size_t committed;
    CHECK(profile,"test profile missing");
    CHECK(!sdm_normal_init(&a,profile) && !sdm_normal_init(&b,profile),"init");
    sdm_normal_monitor_init(&ma);sdm_normal_monitor_init(&mb);
    sdm_normal_attach_monitor(&a,&ma);sdm_normal_attach_monitor(&b,&mb);
    CHECK(!k->sdm_block(&a,input,n,full,&committed,NULL,NULL,INFINITY,NULL) &&
          committed==n,"full SDM block");
    q=0;
    while(q<n) {
      size_t chunk=(q%37)+1;
      if(chunk>n-q)chunk=n-q;
      CHECK(!k->sdm_block(&b,input+q,chunk,split+q,&committed,
                          NULL,NULL,INFINITY,NULL) && committed==chunk,
            "split SDM block");
      q+=chunk;
    }
    CHECK(!memcmp(full,split,sizeof(full)),"SDM within-tier buffer byte invariance");
    CHECK(!memcmp(a.state,b.state,sizeof(a.state)) &&
          a.bank==b.bank && a.frames==b.frames &&
          a.previous_decision==b.previous_decision,
          "SDM state continuity independent of block boundaries");
    CHECK(!memcmp(&ma,&mb,sizeof(ma)),"SDM monitor continuity");
    CHECK(ma.frames==n && ma.windows28==n-27 && ma.nonfinite==0,
          "SDM monitor counted all frames");
    for(q=0;q<8;++q) small_bounds[q]=.000001;
    sdm_normal_init(&a,profile);
    sdm_normal_monitor_init(&ma);sdm_normal_attach_monitor(&a,&ma);
    {
      unsigned coordinate=UINT_MAX;
      double guard_input[]={.10};
      sox_sample_t guard_output[]={123};
      int rc=k->sdm_block(&a,guard_input,1,guard_output,&committed,
                          small_bounds,&coordinate,INFINITY,NULL);
      CHECK(rc==LSX_DSD_SDM_BOUNDS && committed==0 && a.frames==0 &&
            guard_output[0]==123 && coordinate<8,"finite guard uncommitted");
      CHECK(a.bank==0 && a.previous_decision==0.0,"guard preserves active state");
      guard_input[0]=NAN;
      rc=k->sdm_block(&a,guard_input,1,guard_output,&committed,
                      NULL,NULL,INFINITY,NULL);
      CHECK(rc==LSX_DSD_SDM_NONFINITE && committed==0 && ma.nonfinite==1 &&
            ma.first_bad_frame==0 && a.frames==0,"nonfinite rejection");
    }
  }
  printf("PASS SDM tier=%s 4/6/8 states, monitor, guarded failure, block invariance\n",k->name);
}

/* Frozen analytic stimulus, same meaning and sine argument as P09's
 * independent scalar probe. This routine alone is not a mastering approval. */
static int render(const char *tier,const char *id,unsigned rate,double hz,
    double source_db,double seconds,const char *path)
{
  const sdm_profile_t *profile=sdm_profile_find(id,rate);
  const lsx_dsd_kernel *k;
  sdm_normal_t st;
  sdm_normal_monitor_t monitor;
  FILE *f;
  uint64_t n,i;
  double peak,inputs[512];
  sox_sample_t outputs[512];
  unsigned packed=0,used=0;
  int rc;
  if (!profile || !(hz>0 && hz<rate/2) || !isfinite(source_db) ||
      !(seconds>=1.51 && seconds<=60.) ||
      (rc=lsx_dsd_kernel_select(LSX_DSD_SDM,tier,&k))) {
    fprintf(stderr,"invalid or unsupported render profile/ISA (%s)\n",tier);
    return 2;
  }
  n=(uint64_t)(seconds*rate+.5);
  peak=.5*pow(10.,source_db/20.);
  if (!isfinite(peak) || !(peak>0 && peak<=.5))return 2;
  if (sdm_normal_init(&st,profile))return 2;
  sdm_normal_monitor_init(&monitor);sdm_normal_attach_monitor(&st,&monitor);
  f=fopen(path,"wb");if(!f)return 3;
  setvbuf(f,NULL,_IOFBF,128*1024);
  for(i=0;i<n;) {
    size_t j,done=0,block=(size_t)((n-i)>512?512:(n-i));
    for(j=0;j<block;++j)
      inputs[j]=peak*sin((6.283185307179586*hz/rate)*(i+j));
    rc=k->sdm_block(&st,inputs,block,outputs,&done,NULL,NULL,INFINITY,NULL);
    if(rc || done!=block){fclose(f);return 4;}
    for(j=0;j<block;++j) {
      packed=(packed<<1)|(outputs[j]>0);
      if(++used==8) {
        if(fputc((int)packed,f)==EOF){fclose(f);return 5;}
        packed=used=0;
      }
    }
    i+=block;
  }
  if (used && fputc((int)(packed<<(8-used)),f)==EOF) {fclose(f);return 5;}
  if(fclose(f))return 5;
  printf("{\"tier\":\"%s\",\"profile_id\":\"%s\",\"rate_hz\":%u,"
         "\"frames\":%"PRIu64",\"min_ones28\":%u,\"max_ones28\":%u,"
         "\"windows28\":%"PRIu64",\"excursions28\":%"PRIu64","
         "\"overloads\":%"PRIu64",\"nonfinite\":%"PRIu64","
         "\"longest_run\":%"PRIu64",\"counter_saturated\":%u,"
         "\"max_abs_state\":[",
         tier,id,rate,n,monitor.min_ones28,monitor.max_ones28,
         monitor.windows28,monitor.excursions28,monitor.overloads,
         monitor.nonfinite,monitor.longest_run,monitor.counter_saturated);
  for(i=0;i<8;++i)printf("%s%.17g",i?",":"",monitor.max_abs_state[i]);
  puts("]}");return 0;
}


/* Kernel timing is not whole-decoder attribution. The original FIR cases
 * remain synthetic dense 153-tap, stride-one cases. Explicit production-bank
 * cases cover the 57-tap half-band and terminal banks with stride TWO. The
 * decoder currently calls only single-output kernels; block cases measure an
 * available primitive, not a path integrated into reconstruction.
 * SDM checks and monitors are active, but its 1e18 state bounds are synthetic,
 * NOT the certified mastering bounds. Setup and dispatch are outside timing. */
typedef struct {
  const char *name, *bank;
  const double *coeff;
  size_t taps, stride;
  int halfband, block;
} bench_fir_case;

static const bench_fir_case bench_fir_cases[] = {
  {"fir-single", "synthetic-dense-153", NULL, 153, 1, 0, 0},
  {"fir-block", "synthetic-dense-153", NULL, 153, 1, 0, 1},
  {"fir-halfband-single", "halfband-57", lsx_dsd_coeff_halfband, 57, 2, 1, 0},
  {"fir-halfband-block", "halfband-57", lsx_dsd_coeff_halfband, 57, 2, 1, 1},
  {"fir-master64-single", "master64-256-117", lsx_dsd_coeff_master64_256, 117, 2, 0, 0},
  {"fir-master64-block", "master64-256-117", lsx_dsd_coeff_master64_256, 117, 2, 0, 1},
  {"fir-master128-single", "master128-153", lsx_dsd_coeff_master128, 153, 2, 0, 0},
  {"fir-master128-block", "master128-153", lsx_dsd_coeff_master128, 153, 2, 0, 1},
  {"fir-wideband-single", "wideband-257", lsx_dsd_coeff_wideband, 257, 2, 0, 0},
  {"fir-wideband-block", "wideband-257", lsx_dsd_coeff_wideband, 257, 2, 0, 1}
};

static int bench(const char *tier, const char *mode, size_t frames)
{
  const lsx_dsd_kernel *k=NULL;
  const size_t chunk=4096;
  const bench_fir_case *work=NULL;
  double input[2*4096+257],h[153],fir_output[4096],sdm_input[4096];
  const double *coeff;
  sox_sample_t native_output[4096];
  sdm_normal_t state;
  sdm_normal_monitor_t monitor;
  double bounds[8],max_peak=0.,checksum=0.,cpu_time;
  clock_t before,after;
  size_t i,j,done;
  int fir,rc;
  const sdm_profile_t *profile=sdm_profile_find("encode.mastering.v1.dsd64",2822400);
  for(i=0;i<sizeof(bench_fir_cases)/sizeof(*bench_fir_cases);++i)
    if(!strcmp(mode,bench_fir_cases[i].name)) {work=&bench_fir_cases[i];break;}
  fir=work!=NULL;
  if(frames<16384 || frames>40000000 || !profile || (!fir && strcmp(mode,"sdm")))
    return 3;
  rc=lsx_dsd_kernel_select(fir?LSX_DSD_FIR:LSX_DSD_SDM,tier,&k);
  if(rc) {fprintf(stderr,"UNRUN: unavailable kernel: %s (%d)\n",tier,rc);return 2;}
  for(i=0;i<153;++i) h[i]=.003/(1.+fabs((double)i-76.));
  h[76]=.18;
  coeff=fir && work->coeff ? work->coeff : h;
  for(i=0;i<sizeof(input)/sizeof(*input);++i)
    input[i]=.1*sin((double)i*.027)+.02*cos((double)i*.003);
  for(i=0;i<chunk;++i)
    sdm_input[i]=.11*sin(2.*3.141592653589793*997.*(double)i/2822400.);
  for(i=0;i<8;++i) bounds[i]=1e18;
  if(!fir) {
    if(sdm_normal_init(&state,profile))return 4;
    sdm_normal_monitor_init(&monitor);
    sdm_normal_attach_monitor(&state,&monitor);
  }
  before=clock();
  for(i=0;i<frames;) {
    size_t n=frames-i<chunk?frames-i:chunk;
    if(fir) {
      if(work->block)
        k->fir_block(coeff,work->taps,input,n,work->stride,work->halfband,fir_output);
      else
        for(j=0;j<n;++j)
          fir_output[j]=k->fir_single(coeff,work->taps,input+j*work->stride,work->halfband);
      checksum+=fir_output[n/2];
    } else {
      rc=k->sdm_block(&state,sdm_input,n,native_output,&done,
                      bounds,NULL,.5,&max_peak);
      if(rc || done!=n) {
        fprintf(stderr,"SDM benchmark guard failed at frame %zu, status %d\n",i,rc);
        return 4;
      }
      checksum+=(native_output[n/2]>0 ? 1. : -1.);
    }
    i+=n;
  }
  after=clock();
  cpu_time=(double)(after-before)/CLOCKS_PER_SEC;
  if(!isfinite(cpu_time)||cpu_time<=0) return 4;
  if(!fir && (monitor.frames!=frames || monitor.nonfinite ||
              monitor.overloads || monitor.counter_saturated))return 4;
  printf("{\"tier\":\"%s\",\"mode\":\"%s\",\"frames\":%zu,"
         "\"cpu_seconds\":%.9g,\"cpu_ns_per_frame\":%.9g,"
         "\"checksum\":%.17g,\"guards_active\":%s,\"monitor_active\":%s,"
         "\"coefficient_bank\":\"%s\",\"taps\":%zu,\"stride\":%zu,"
         "\"halfband\":%s,\"frame_unit\":\"%s\",\"state_bounds\":\"%s\"}\n",
         tier,mode,frames,cpu_time,1e9*cpu_time/frames,checksum,
         fir?"false":"true",fir?"false":"true",
         fir?work->bank:"encode.mastering.v1.dsd64",fir?work->taps:0,
         fir?work->stride:0,fir && work->halfband?"true":"false",
         fir?"FIR output":"native SDM output",fir?"not applicable":"synthetic 1e18");
  return 0;
}

int main(int argc,char **argv)
{
  if(argc==5 && !strcmp(argv[1],"--bench"))
    return bench(argv[2],argv[3],(size_t)strtoull(argv[4],NULL,10));
  if(argc==9 && !strcmp(argv[1],"--render"))
    return render(argv[2],argv[3],(unsigned)strtoul(argv[4],NULL,10),
                  strtod(argv[5],NULL),strtod(argv[6],NULL),
                  strtod(argv[7],NULL),argv[8]);
  unsigned host;
  const lsx_dsd_kernel *k;
  static const char *tier[]={"scalar","sse2","avx1","avx2"};
  unsigned i;
  test_caps();
  test_context_overrides();
  host=lsx_dsd_features_host();
  /* Preserve the original P11 emulator qualifier stdout contract. */
  printf("P11 host feature mask=%u (SSE2=%d AVX1=%d)\n",
      host & (LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1),
      !!(host&LSX_DSD_CPU_SSE2),!!(host&LSX_DSD_CPU_AVX1));
  printf("P12 host feature mask=%u (SSE2=%d AVX1=%d AVX2=%d FMA=%d)\n",host,
      !!(host&LSX_DSD_CPU_SSE2),!!(host&LSX_DSD_CPU_AVX1),
      !!(host&LSX_DSD_CPU_AVX2),!!(host&LSX_DSD_CPU_FMA));
  for (i=0;i<sizeof(tier)/sizeof(*tier);++i) {
    int r=lsx_dsd_kernel_select(LSX_DSD_FIR,tier[i],&k);
    if (r==-2) {printf("UNRUN tier=%s unavailable hardware/compiler\n",tier[i]);continue;}
    CHECK(r==0 && k && !strcmp(k->name,tier[i]),"forced FIR dispatch");
    test_fir(k);
    CHECK(lsx_dsd_kernel_select(LSX_DSD_SDM,tier[i],&k)==0,
          "independent SDM dispatch for same tier");
    test_sdm(k);
  }
  puts("P11 kernel unit suite PASS");
  puts("P12 kernel unit suite PASS");
  return 0;
}
