/* Host-agnostic feature-policy tests and adversarial exact SDM block oracle.
 * Compare independent SIMD entry points against the immutable scalar step;
 * do not compare a vector implementation to itself. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include "pcmdsd.h"
#include <float.h>
#include <fenv.h>
#include <math.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#if defined(__SSE2__)
#include <emmintrin.h>
#endif

#define VERIFY(cond) do { if (!(cond)) { \
  fprintf(stderr,"FAIL:%s:%d: %s\n",__FILE__,__LINE__,#cond); exit(1); \
} } while(0)

static uint32_t seed=0x69d931fa;
static uint32_t rnd(void)
{
  seed^=seed<<13; seed^=seed>>17; seed^=seed<<5;
  return seed;
}

static const lsx_dsd_kernel *tiers[5];
static unsigned tier_count;
static unsigned complete_features = LSX_DSD_CPU_SSE2 | LSX_DSD_CPU_AVX1 |
    LSX_DSD_CPU_AVX2 | LSX_DSD_CPU_AVX512F | LSX_DSD_CPU_FMA;

static void check_policy(void)
{
  const lsx_dsd_kernel *k=NULL,*baseline=NULL;
  unsigned flags;
  const unsigned rates[]={0,2822400u,5644800u,11289600u,
                             22579200u,45158400u};
  const char * requested[]={NULL,"","auto"};
  unsigned i,j;
  for (flags=0; flags<32; ++flags) for (i=0;i<6;++i) {
    unsigned available=0;
    unsigned f=flags; /* exhaustive including impossible CPUID combinations */
    const lsx_dsd_kernel *expect=NULL;
    VERIFY(lsx_dsd_kernel_select_sdm_rate_features("auto",f,rates[i],&k)==0);
    VERIFY(k);
    VERIFY((f & k->required_features)==k->required_features);
    VERIFY(k->sdm_block);
#if defined(__i386__) || FLT_EVAL_METHOD != 0
    VERIFY(k==&lsx_dsd_kernel_scalar);
#else
    /* Choose exactly the declared policy, not whichever descriptor happened
     * to be linked or whichever bogus features the caller claimed. */
#if defined(HAVE_DSD_AVX512)
    if (rates[i]>=22579200u &&
      (f&(LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX2|LSX_DSD_CPU_AVX512F))==
         (LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX2|LSX_DSD_CPU_AVX512F))
       expect=&lsx_dsd_kernel_avx512;
#endif
#if defined(HAVE_DSD_AVX2)
    if (!expect && (f&(LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX2))==
         (LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX2))
       expect=&lsx_dsd_kernel_avx2;
#endif
#if defined(HAVE_DSD_AVX512)
    if (!expect &&
       (f&(LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX2|LSX_DSD_CPU_AVX512F))==
         (LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX2|LSX_DSD_CPU_AVX512F))
       expect=&lsx_dsd_kernel_avx512;
#endif
#if defined(HAVE_DSD_AVX1)
    if (!expect && (f&(LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1))==
         (LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1))
       expect=&lsx_dsd_kernel_avx1;
#endif
#if defined(HAVE_DSD_SSE2)
    if (!expect && (f&LSX_DSD_CPU_SSE2)) expect=&lsx_dsd_kernel_sse2;
#endif
    if (!expect) expect=&lsx_dsd_kernel_scalar;
    VERIFY(k==expect);
#endif
    baseline=k;
    for (j=0;j<3;++j) {
      VERIFY(lsx_dsd_kernel_select_sdm_rate_features(requested[j],f,rates[i],&k)==0);
      VERIFY(k==baseline);
    }
    available|=(k==&lsx_dsd_kernel_scalar);
    (void)available;
    VERIFY(lsx_dsd_kernel_select_sdm_rate_features("bad-tier",f,rates[i],&k)==-1 && !k);
    VERIFY(lsx_dsd_kernel_select_sdm_rate_features("avx2-fma",f,rates[i],&k)==-2 && !k);
  }
  VERIFY(lsx_dsd_kernel_select_sdm_rate_features(NULL,0,2822400u,&k)==0 &&
         k==&lsx_dsd_kernel_scalar);
  VERIFY(lsx_dsd_kernel_select_sdm_rate_features("auto",complete_features,2822400u,NULL)==-1);
  VERIFY(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"auto",0,&k)==0 &&
         k==&lsx_dsd_kernel_scalar);
  printf("PASS exhaustive auto policy, 32 masks x 6 rates x 3 auto forms\n");
}

static void init_state(sdm_normal_t *s,sdm_normal_monitor_t *m,
    const sdm_profile_t *profile)
{
  unsigned i;
  VERIFY(sdm_normal_init(s,profile)==0);
  sdm_normal_monitor_init(m);
  sdm_normal_attach_monitor(s,m);
  /* Nonzero inactive coordinates catch kernels that clear scalar-owned
   * state on success or failure. The active state is untouched. */
  for (i=0;i<8;++i) s->state[1][i]=(double)(i+1)*0x1.2345p-11;
}

static void same(const sdm_normal_t *a,const sdm_normal_t *b,
    const sdm_normal_monitor_t *ma,const sdm_normal_monitor_t *mb)
{
  VERIFY(a->profile==b->profile);
  VERIFY(memcmp(a->state,b->state,sizeof(a->state))==0);
  VERIFY(memcmp(&a->previous_decision,&b->previous_decision,
                sizeof(a->previous_decision))==0);
  VERIFY(a->bank==b->bank && a->frames==b->frames);
  VERIFY(memcmp(ma,mb,sizeof(*ma))==0);
}

static void try_case(const lsx_dsd_kernel *tier,const sdm_profile_t *profile,
    unsigned scenario)
{
  sdm_normal_t a,b;
  sdm_normal_monitor_t ma,mb;
  double in[521], bounds[8], *p1=NULL, *p2=NULL;
  const double *active_bounds=bounds;
  sox_sample_t o1[521],o2[521];
  unsigned ca=UINT32_MAX, cb=UINT32_MAX;
  size_t n,got1=0,got2=0,j;
  int rc1,rc2;
  init_state(&a,&ma,profile);
  init_state(&b,&mb,profile);
  for (j=0;j<521;++j) {
    /* Intentionally use both zero and in-band distributions, no PRNG
     * dependency on ISA or vector length. */
    unsigned u=rnd();
    in[j]=scenario==0 ? (j%7==0 ? 0. : (int32_t)u*0x1p-34) :
      (scenario==1 ? .25*sin(j*0.031)+.07*cos(j*.0039) :
       ((int32_t)u*0x1p-33)*.11);
    o1[j]=(sox_sample_t)0x271619a4;
    o2[j]=(sox_sample_t)0x271619a4;
  }
  n=521;
  for (j=0;j<8;++j) bounds[j]=1e6;
  if (scenario==2) {
    /* Guard rejection is compared even for a poisoned inactive bank. */
    bounds[0]=0x1p-33;
  }
  if (scenario==3) { n=81;in[37]=NAN; }
  if (scenario==4) { n=81;in[37]=INFINITY; }
  if (scenario==5) { n=81;in[37]=-INFINITY; }
  if (scenario==6) { n=0; }
  if (scenario==7) { n=1;in[0]=DBL_MAX; }
  if (scenario==8) { n=1;a.frames=b.frames=UINT64_MAX; }
  if (scenario==9) { n=1;ma.frames=mb.frames=UINT64_MAX;
                      ma.overloads=mb.overloads=UINT64_MAX;
                      ma.counter_saturated=mb.counter_saturated=0; }
  if (scenario==10) { n=81;in[0]=.49; /* peak alias active state */
                       p1=&a.state[0][3];p2=&b.state[0][3]; }
  if (scenario==11) { n=81;in[0]=.49; /* peak alias inactive bank */
                       p1=&a.state[1][3];p2=&b.state[1][3]; }
  if (scenario==12) { n=81;in[0]=.49; /* subnormal near unsigned guard */
                      a.state[0][2]=b.state[0][2]=0x1p-1070; }
  if (scenario==13) { n=81;in[11]=-.51; }
  if (scenario==14) { n=1; a.state[0][0]=b.state[0][0]=NAN; }
  if (scenario==15) { n=1; a.state[0][1]=b.state[0][1]=INFINITY; }
  if (scenario==16) { n=1; a.state[0][2]=b.state[0][2]=-INFINITY; }
  if (scenario==17) { n=1; active_bounds=NULL;
                       sdm_normal_attach_monitor(&a,NULL);
                       sdm_normal_attach_monitor(&b,NULL); }
  if (scenario==18) { n=1; in[0]=-0.;
                       a.previous_decision=b.previous_decision=-0.; }
  if (scenario==19) { n=1; a.state[0][0]=b.state[0][0]=DBL_MAX;
                       a.state[0][1]=b.state[0][1]=-DBL_MAX; }
  if (scenario==20) { n=1; a.state[0][7]=b.state[0][7]=NAN; }
  if (scenario==21) { n=1; bounds[0]=-0.; }
  if (scenario==22) { n=1; bounds[2]=NAN; }
  if (scenario==23) { n=1; a.previous_decision=b.previous_decision=INFINITY; }
  rc1=lsx_dsd_kernel_scalar.sdm_block(&a,in,n,o1,&got1,active_bounds,&ca,.5,p1);
  rc2=tier->sdm_block(&b,in,n,o2,&got2,active_bounds,&cb,.5,p2);
  VERIFY(rc1==rc2 && got1==got2 && ca==cb);
  VERIFY(memcmp(o1,o2,sizeof(o1))==0);
  same(&a,&b,&ma,&mb);
  if (p1) VERIFY(memcmp(p1,p2,sizeof(*p1))==0);
}

static void compare_long(const lsx_dsd_kernel *tier,
    const sdm_profile_t *profile)
{
  sdm_normal_t a,b;
  sdm_normal_monitor_t ma,mb;
  double in[513], peak1=-1., peak2=-1.,bound[8];
  sox_sample_t o1[513],o2[513];
  unsigned i,round;
  size_t p;
  init_state(&a,&ma,profile); init_state(&b,&mb,profile);
  for(i=0;i<8;++i) bound[i]=1e8;
  for (round=0;round<150;++round) {
    size_t n=(round%5==0?1:(round%5==1?7:(round%5==2?256:
               (round%5==3?513:13))));
    size_t c1=0,c2=0;
    unsigned z1=UINT32_MAX,z2=UINT32_MAX;
    int rc1,rc2;
    for (p=0;p<n;++p) in[p]=((int32_t)rnd()*0x1p-32)*.28;
    rc1=lsx_dsd_kernel_scalar.sdm_block(&a,in,n,o1,&c1,bound,&z1,.5,&peak1);
    rc2=tier->sdm_block(&b,in,n,o2,&c2,bound,&z2,.5,&peak2);
    VERIFY(rc1==rc2 && c1==c2 && z1==z2);
    VERIFY(memcmp(o1,o2,c1*sizeof(*o1))==0);
    same(&a,&b,&ma,&mb);
    VERIFY(memcmp(&peak1,&peak2,sizeof(peak1))==0);
    if (rc1) break;
  }
}

static void test_exact(void)
{
  static const char *ids[]={
    "encode.mastering.v1.dsd64", "encode.mastering.v1.dsd128",
    "encode.mastering.v1.dsd256", "encode.mastering.v2.dsd512",
    "encode.mastering.v2.dsd1024", "encode.mastering.v1.dsd512",
    "encode.mastering.v1.dsd1024", "encode.legacy.v1.dsd64",
    "encode.legacy.v1.dsd128", "encode.legacy.v1.dsd256",
    "encode.diagnostic.sdm6.v1.dsd64","encode.diagnostic.sdm6.v1.dsd128",
    "encode.diagnostic.sdm6.v1.dsd256","encode.diagnostic.clans8.v1.dsd64",
    "encode.diagnostic.clans8.v1.dsd128","encode.diagnostic.clans8.v1.dsd256"};
  static const unsigned rates[]={2822400u,5644800u,11289600u,
    22579200u,45158400u,22579200u,45158400u,
    2822400u,5644800u,11289600u,2822400u,5644800u,11289600u,
    2822400u,5644800u,11289600u};
  unsigned i,k,scenario;
  for(k=0;k<tier_count;++k) for(i=0;i<16;++i) {
    const sdm_profile_t *profile=sdm_profile_find(ids[i],rates[i]);
    VERIFY(profile);
    compare_long(tiers[k],profile);
    for(scenario=0;scenario<24;++scenario)
      try_case(tiers[k],profile,scenario);
  }
  printf("PASS bitwise scalar oracle, %u tiers x 16 profiles x 24 adverse cases, monitor and dual-bank states\n",tier_count);
}

static void override(const char *name,const char *value)
{
#if defined(_WIN32)
  VERIFY(_putenv_s(name,value?value:"")==0);
#else
  VERIFY((value?setenv(name,value,1):unsetenv(name))==0);
#endif
}

static void test_real_context_selection(void)
{
  static const unsigned rates[]={2822400u,5644800u,11289600u,
                                  22579200u,45158400u};
  unsigned i;
  lsx_pcmdsd *p=NULL,*forced=NULL;
  const lsx_dsd_kernel *expected=NULL;
  override("SOX_DSD_KERNEL_SDM",NULL);
  override("LSX_DSD_SDM_KERNEL",NULL);
  for(i=0;i<5;++i) {
    const lsx_pcmdsd_profile *profile=lsx_pcmdsd_profile_find(rates[i]);
    VERIFY(profile && profile->qualified);
    VERIFY(lsx_dsd_kernel_select_sdm_rate(NULL,rates[i],&expected)==0);
    VERIFY(lsx_pcmdsd_candidate_create(88200,rates[i],.5,0,NULL,
             profile->bounds,&p)==SOX_DSD_OK && p);
    VERIFY(!strcmp(lsx_pcmdsd_kernel_name(p),expected->name));
    /* The named override must remain authoritative on an AUTO context. */
    override("LSX_DSD_SDM_KERNEL","invalid-old-hook");
    override("SOX_DSD_KERNEL_SDM","scalar");
    VERIFY(lsx_pcmdsd_candidate_create(88200,rates[i],.5,0,NULL,
             profile->bounds,&forced)==SOX_DSD_OK && forced);
    VERIFY(!strcmp(lsx_pcmdsd_kernel_name(forced),"scalar"));
    VERIFY(!strcmp(lsx_pcmdsd_kernel_name(p),expected->name));
    lsx_pcmdsd_destroy(forced);forced=NULL;
    override("SOX_DSD_KERNEL_SDM","unsupported-tier");
    VERIFY(lsx_pcmdsd_candidate_create(88200,rates[i],.5,0,NULL,
             profile->bounds,&forced)==SOX_DSD_BAD_ARGUMENT && !forced);
    override("SOX_DSD_KERNEL_SDM",NULL);
    override("LSX_DSD_SDM_KERNEL",NULL);
    lsx_pcmdsd_destroy(p);p=NULL;
  }
  puts("PASS real PCM-to-DSD contexts: 5 rates, forced precedence, snapshots");
}

int main(void)
{
  unsigned features=lsx_dsd_features_host();
  const char *names[]={"scalar","sse2","avx1","avx2","avx512"};
  unsigned i;
  const lsx_dsd_kernel *k=NULL;
  check_policy();
  for (i=0;i<5;++i)
    if (!lsx_dsd_kernel_select_features(LSX_DSD_SDM,names[i],features,&k))
      tiers[tier_count++]=k;
  test_exact();
#if defined(FE_DOWNWARD) && defined(FE_UPWARD) && defined(FE_TOWARDZERO)
  {
    const int rounds[]={FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
    const int prior=fegetround();
    if (prior>=0) {
      for (i=0;i<sizeof(rounds)/sizeof(rounds[0]);++i)
        if (fesetround(rounds[i])==0) test_exact();
      VERIFY(fesetround(prior)==0);
    }
  }
#endif
#if defined(__SSE2__)
  {
    unsigned original=_mm_getcsr();
    /* FTZ is architecturally available with SSE. DAZ is optional even for
     * SSE2 CPUs; do not set the optional MXCSR bit without checking FXSAVE. */
    _mm_setcsr(original | (1u<<15));
    test_exact();
    _mm_setcsr(original);
  }
#endif
  test_real_context_selection();
  return 0;
}
