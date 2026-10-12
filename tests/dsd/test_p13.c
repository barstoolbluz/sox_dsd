/* P13 independently executable AVX-512F capability and kernel acceptance.
 * Mock CPUID never executes a vector instruction. Real kernel tests run only
 * after production CPUID+XGETBV selects the target on the current host. */
#define _GNU_SOURCE
#include "sox_i.h"
#include "dsd_kernels.h"
#include <float.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(__unix__) || defined(__APPLE__)
#include <sys/mman.h>
#include <unistd.h>
#define P13_GUARD_PAGES 1
#endif
#ifndef MAP_ANONYMOUS
#ifdef MAP_ANON
#define MAP_ANONYMOUS MAP_ANON
#endif
#endif
#define CHECK(e) do { if (!(e)) { fprintf(stderr,"P13 FAIL %s:%d: %s\n",\
  __FILE__,__LINE__,#e); return 1; } } while (0)

typedef struct {
  unsigned maxleaf,leaf1ecx,leaf1edx,leaf7ebx,reads7,reads_xcr0;
  uint64_t xcr0;
} mock_cpu;
static unsigned cpuid(void *v,unsigned leaf,unsigned sub,unsigned r[4])
{
  mock_cpu *m=v;
  memset(r,0,4*sizeof(*r));
  if (leaf>m->maxleaf)return 0;
  if (leaf==0)r[0]=m->maxleaf;
  if (leaf==1){r[2]=m->leaf1ecx;r[3]=m->leaf1edx;}
  if (leaf==7 && sub==0){r[1]=m->leaf7ebx;++m->reads7;}
  return 1;
}
static uint64_t xgetbv(void *v,unsigned idx)
{
  mock_cpu *m=v;
  if(idx!=0)abort();
  ++m->reads_xcr0;
  return m->xcr0;
}
static int caps(void)
{
  mock_cpu m={0};
  lsx_dsd_cpu_probe p={&m,cpuid,xgetbv};
  unsigned feat,b;
  const lsx_dsd_kernel *k=NULL;
  m.maxleaf=7;
  m.leaf1ecx=(1u<<26)|(1u<<27)|(1u<<28);
  m.leaf1edx=(1u<<26);
  m.leaf7ebx=(1u<<16); /* CPUID AVX-512F with AVX2 absent */
  m.xcr0=0xe6;
  feat=lsx_dsd_features_probe(&p);
  CHECK((feat&(LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX512F))==
        (LSX_DSD_CPU_SSE2|LSX_DSD_CPU_AVX1|LSX_DSD_CPU_AVX512F));
  CHECK(!(feat&(LSX_DSD_CPU_AVX2|LSX_DSD_CPU_FMA)));
  /* GCC -mavx512f implicitly enables AVX2 on this toolchain. A CPU
   * offering AVX-512F but not AVX2 must fail closed rather than running
   * code under an ISA mask too narrow for its actual compilation flags. */
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"avx512",feat,&k)==-2 && !k);
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_SDM,"avx512",feat,&k)==-2 && !k);
  m.leaf7ebx|=(1u<<5); /* advertise AVX2 independently */
  feat=lsx_dsd_features_probe(&p);
  CHECK((feat&LSX_DSD_CPU_AVX2) && !(feat&LSX_DSD_CPU_FMA));
#if defined(HAVE_DSD_AVX512)
  CHECK(!lsx_dsd_kernel_select_features(LSX_DSD_FIR,"avx512",feat,&k));
  CHECK(k==&lsx_dsd_kernel_avx512);
  CHECK(!lsx_dsd_kernel_select_features(LSX_DSD_SDM,"avx512",feat,&k));
  CHECK(k==&lsx_dsd_kernel_avx512);
#else
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"avx512",feat,&k)==-2);
#endif
  for (b=0;b<64;++b) {
    m.xcr0=0xe6u & ~(UINT64_C(1)<<b);
    /* Only required XCR0 bits matter; unrelated OS state is irrelevant. */
    feat=lsx_dsd_features_probe(&p);
    CHECK(!!(feat&LSX_DSD_CPU_AVX512F)==
      (b!=1 && b!=2 && b!=5 && b!=6 && b!=7));
  }
  m.xcr0=0xe6;
  m.leaf7ebx=0;
  CHECK(!(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX512F));
  m.leaf7ebx=(1u<<16)|(1u<<5);
  m.maxleaf=1;
  CHECK(!(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX512F));
  m.maxleaf=7;
  m.leaf1ecx&=~(1u<<27);
  b=m.reads_xcr0;
  CHECK(!(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX512F));
  CHECK(m.reads_xcr0==b);
  m.leaf1ecx|=(1u<<27);
  m.leaf1edx=0;
  CHECK(!(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX512F));
  m.leaf1edx=(1u<<26);
  p.xgetbv=NULL;
  CHECK(!(lsx_dsd_features_probe(&p)&LSX_DSD_CPU_AVX512F));
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"avx512",0,&k)==-2 && !k);
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_SDM,"avx512-fma",~0u,&k)==-2 && !k);
  CHECK(lsx_dsd_kernel_select_features(LSX_DSD_FIR,"avx512-fma",~0u,&k)==-2 && !k);
  CHECK(!lsx_dsd_kernel_select_features(LSX_DSD_FIR,"auto",0,&k) &&
        k==&lsx_dsd_kernel_scalar);
#if defined(HAVE_DSD_SSE2)
  CHECK(!lsx_dsd_kernel_select_features(LSX_DSD_FIR,"auto",~0u,&k) &&
        k==&lsx_dsd_kernel_sse2);
#endif
  CHECK(!lsx_dsd_kernel_select_features(LSX_DSD_SDM,"auto",~0u,&k) &&
        k==&lsx_dsd_kernel_scalar);
  puts("P13 PASS CPUID AVX-512F/AVX2 mask, XCR0, FMA failure, defaults");
  return 0;
}

static int fir(const lsx_dsd_kernel *k)
{
#if defined(P13_GUARD_PAGES) && defined(MAP_ANONYMOUS)
  /* All odd tap lengths supported by the symmetric FIR contract. */
  static const unsigned lengths[]={0,1,2,3,4,5,7,8,9,13,15,16,17,23};
  long pg0=sysconf(_SC_PAGESIZE);
  size_t page,j,t,f,stride,half,side,check_count=0;
  unsigned char *map,*buf;
  CHECK(pg0>=4096);
  page=(size_t)pg0;
  map=mmap(NULL,3*page,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
  CHECK(map!=MAP_FAILED);
  CHECK(mprotect(map,page,PROT_NONE)==0);
  CHECK(mprotect(map+2*page,page,PROT_NONE)==0);
  buf=map+page;
  for (t=1;t<=257;t+=2) {
    const size_t count=t;
    double h[257];
    for(j=0;j<count;++j)h[j]=.01/(1+fabs((double)j-(double)(count/2)));
    for(j=0;j<count/2;++j)h[count-1-j]=h[j];
    for(half=0;half<2;++half) {
      if (half) for(j=0;j<count/2;++j)
        if(j&1)h[j]=h[count-1-j]=0.;
      for(stride=1;stride<=3;++stride) {
        for(f=0;f<sizeof(lengths)/sizeof(*lengths);++f) {
          const size_t n=lengths[f],samples=n?(n-1)*stride+count:0;
          for(side=0;side<2;++side) {
            double *s=(double *)(side?buf+page-samples*sizeof(double):buf);
            double out[25];
            CHECK(samples*sizeof(double)<=page);
            for(j=0;j<samples;++j)s[j]=.13*sin(j*.13)+.04*cos(j*.07);
            for(j=0;j<25;++j)out[j]=123.25;
            k->fir_block(h,count,s,n,stride,(int)half,out);
            CHECK(out[n]==123.25);
            for(j=0;j<n;++j) {
              size_t a;
              double expected=lsx_dsd_fir_scalar(h,count,s+j*stride,(int)half);
              double peak=1.,l1=0.,eps;
              long double oracle=(long double)h[count/2]*(long double)s[j*stride+count/2];
              for(a=0;a<count;++a) {
                l1+=fabs(h[a]);
                if(fabs(s[j*stride+a])>peak)peak=fabs(s[j*stride+a]);
              }
              for(a=0;a<count/2;++a) {
                if(half && h[a]==0.)continue;
                oracle+=(long double)h[a]*((long double)s[j*stride+a]+
                                      (long double)s[j*stride+count-1-a]);
              }
              eps=16*DBL_EPSILON*count*l1*peak+1e-16;
              CHECK(fabs(out[j]-expected)<=eps);
              CHECK(fabsl((long double)out[j]-oracle)<=eps);
              CHECK(fabs(k->fir_single(h,count,s+j*stride,(int)half)-expected)<=eps);
              ++check_count;
            }
          }
        }
      }
    }
  }
  CHECK(munmap(map,3*page)==0);
  printf("P13 PASS FIR %zu page-bounded comparisons, taps 1..257, tails 0..23\n",check_count);
  return 0;
#else
  (void)k;
  puts("P13 UNRUN protected-page FIR: requires mmap/mprotect");
  return 2;
#endif
}

static int sdm(const lsx_dsd_kernel *k)
{
  static const char *ids[]={"encode.mastering.v1.dsd64",
    "encode.mastering.v1.dsd128","encode.mastering.v1.dsd256",
    "encode.diagnostic.sdm6.v1.dsd64","encode.diagnostic.clans8.v1.dsd64"};
  static const unsigned rates[]={2822400,5644800,11289600,2822400,2822400};
  double x[1024],bounds[8];
  sox_sample_t whole[1024],parts[1024];
  sdm_normal_t a,b;
  sdm_normal_monitor_t ma,mb;
  size_t n,p,q,c,j;
  for(j=0;j<1024;++j)x[j]=.11*sin(j*.017)+.03;
  for(p=0;p<sizeof(ids)/sizeof(*ids);++p) {
    const sdm_profile_t *profile=sdm_profile_find(ids[p],rates[p]);
    size_t committed=99;
    CHECK(profile && !sdm_normal_init(&a,profile) && !sdm_normal_init(&b,profile));
    sdm_normal_monitor_init(&ma);sdm_normal_monitor_init(&mb);
    sdm_normal_attach_monitor(&a,&ma);sdm_normal_attach_monitor(&b,&mb);
    CHECK(!k->sdm_block(&a,NULL,0,NULL,&committed,NULL,NULL,INFINITY,NULL) &&
          committed==0 && a.frames==0);
    for(n=1;n<=1024;n*=2) {
      CHECK(!sdm_normal_init(&a,profile) && !sdm_normal_init(&b,profile));
      sdm_normal_monitor_init(&ma);sdm_normal_monitor_init(&mb);
      sdm_normal_attach_monitor(&a,&ma);sdm_normal_attach_monitor(&b,&mb);
      CHECK(!k->sdm_block(&a,x,n,whole,&committed,NULL,NULL,INFINITY,NULL) && committed==n);
      for(q=0;q<n;) {
        size_t piece=(q%13)+1;
        if(piece>n-q)piece=n-q;
        CHECK(!k->sdm_block(&b,x+q,piece,parts+q,&c,NULL,NULL,INFINITY,NULL) && c==piece);
        q+=piece;
      }
      CHECK(!memcmp(whole,parts,n*sizeof(*whole)));
      CHECK(!memcmp(a.state,b.state,sizeof(a.state)) && a.bank==b.bank &&
            a.frames==b.frames && a.previous_decision==b.previous_decision);
      CHECK(!memcmp(&ma,&mb,sizeof(ma)));
    }
    CHECK(!sdm_normal_init(&a,profile));
    for(j=0;j<8;++j)bounds[j]=1e-9;
    {
      unsigned coord=UINT_MAX;
      sox_sample_t out=2345;
      CHECK(k->sdm_block(&a,x,1,&out,&committed,bounds,&coord,
                         INFINITY,NULL)==LSX_DSD_SDM_BOUNDS);
      CHECK(!committed && !a.frames && !a.bank && out==2345 && coord<8);
      x[0]=NAN;
      CHECK(k->sdm_block(&a,x,1,&out,&committed,NULL,NULL,INFINITY,NULL)==
            LSX_DSD_SDM_NONFINITE && !committed && !a.frames);
      x[0]=.03;
      CHECK(k->sdm_block(&a,x,1,&out,&committed,NULL,NULL,.01,NULL)==
            LSX_DSD_SDM_OVERLOAD && !committed && !a.frames);
      a.frames=UINT64_MAX;
      CHECK(k->sdm_block(&a,x,1,&out,&committed,NULL,NULL,INFINITY,NULL)==
            LSX_DSD_SDM_FRAME_LIMIT && !committed && a.frames==UINT64_MAX);
    }
  }
  puts("P13 PASS SDM orders 4/6/8, tail blocks, guards, monitor, determinism");
  return 0;
}

int main(void)
{
  const lsx_dsd_kernel *k=NULL;
  int r;
  CHECK(caps()==0);
  r=lsx_dsd_kernel_select(LSX_DSD_FIR,"avx512",&k);
  if (r==-2) {puts("P13 UNRUN: host/compiler lacks usable AVX-512F");return 2;}
  CHECK(r==0 && k && !strcmp(k->name,"avx512"));
  CHECK(fir(k)==0);
  CHECK(sdm(k)==0);
  puts("P13 PASS AVX-512F executable qualification");
  return 0;
}
