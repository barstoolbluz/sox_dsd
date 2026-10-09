/* P06 executable private scalar reconstruction contract and vector exporter.
 * All audio input is canonical +/-SOX_SAMPLE_MAX, not boolean 0/1 samples. */
#include "dsd_decode.h"
#include "dsd_coeffs.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <limits.h>
#include <time.h>
#include "dsd_kernels.h"

static unsigned long tests;
#define CHECK(cond) do { ++tests; if (!(cond)) { \
  fprintf(stderr,"P06 test failure at line %d: %s\n",__LINE__,#cond); exit(1); \
} } while (0)

struct profile {const char *name; uint32_t rate; lsx_dsd_decode profile;};
static const struct profile profiles[] = {
  {"master64",2822400,LSX_DSD_PROFILE_MASTERING},
  {"master128",5644800,LSX_DSD_PROFILE_MASTERING},
  {"master256",11289600,LSX_DSD_PROFILE_MASTERING},
  {"wide64",2822400,LSX_DSD_PROFILE_WIDEBAND},
  {"wide128",5644800,LSX_DSD_PROFILE_WIDEBAND},
  {"wide256",11289600,LSX_DSD_PROFILE_WIDEBAND},
};

static int native_bit(size_t i, unsigned c, int pattern, size_t length)
{
  uint32_t x = (uint32_t)i * UINT32_C(1664525) + (uint32_t)c * UINT32_C(1013904223)
       + (uint32_t)(i >> 3) * UINT32_C(2246822519);
  x ^= x >> 13;
  switch (pattern) {
    case 0: return (x & 1u) != 0;
    case 1: return 0;
    case 2: return 1;
    default: return i == (length / 2) && c == 0;
  }
}

static void check_bank(const double *h, unsigned n, int half)
{
  double sum=0;
  unsigned k;
  CHECK((n & 3u)==1u);
  for (k=0;k<n;k++) {
    CHECK(h[k]==h[n-1-k]);
    if (half && k!=n/2 && ((int)k-(int)n/2)%2==0)
      CHECK(h[k]==0.0);
    sum+=h[k];
  }
  if (half) CHECK(h[n/2] == 0.5);
  CHECK(fabs(sum-1) < 2e-15);
}

static double *exercise(const struct profile *p, unsigned channels, size_t n,
                       int pattern, int uneven, size_t *n_output)
{
  lsx_dsd_reconstruction *ctx = NULL;
  lsx_dsd_reconstruction_info meta;
  sox_sample_t *source = NULL;
  double *result;
  size_t used = 0, have = 0, output_limit;
  unsigned D, j;
  CHECK(lsx_dsd_reconstruction_create(p->rate,p->profile,channels,&ctx)==SOX_DSD_OK);
  CHECK(ctx!=NULL);
  CHECK(lsx_dsd_reconstruction_info_get(ctx,&meta)==SOX_DSD_OK);
  D=meta.factor;
  CHECK(meta.stages == ((D==64)?6u:5u));
  CHECK(meta.delay_native_frames%meta.factor ==
         (meta.phases[0] | (meta.phases[1]<<1) | (meta.phases[2]<<2)
             | (meta.phases[3]<<3) | (meta.phases[4]<<4) |
               ((meta.stages==6 ? meta.phases[5] : 0)<<5)));
  CHECK(meta.channels == channels && meta.native_hz == p->rate);
  CHECK(meta.allocated_bytes > 0 && meta.allocated_bytes < 65536 + (size_t)channels*8192);
  output_limit=n/D+(n%D!=0);
  result=calloc((output_limit+1)*(size_t)channels,sizeof(double));
  CHECK(result != NULL);
  if (n) {
    CHECK(n <= SIZE_MAX/channels);
    source=malloc(n*channels*sizeof(sox_sample_t));
    CHECK(source != NULL);
    for (size_t i=0;i<n;i++)
      for (unsigned c=0;c<channels;c++)
        source[i*channels+c] = native_bit(i,c,pattern,n)?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
  }
  /* Zero output capacity neither consumes input nor advances a filter. */
  {size_t in=n, out=0;
   CHECK(lsx_dsd_reconstruction_process(ctx,source,&in,result,&out)==SOX_DSD_NEED_OUTPUT);
   CHECK(in==0 && out==0);
  }
  for (j=0;used<n;j++) {
    size_t input = n-used, available = uneven ? (size_t)(1+((j*17u+3u)%41u)) : input;
    size_t out = uneven ? (size_t)(1+((j*7u+1u)%5u)) : output_limit+1;
    sox_dsd_status_t status;
    if (input>available) input=available;
    status=lsx_dsd_reconstruction_process(ctx,source+used*channels,&input,
                                            result+have*channels,&out);
    CHECK(status==SOX_DSD_NEED_OUTPUT || status==SOX_DSD_NEED_INPUT);
    CHECK(input>0 && have+out<=output_limit);
    used+=input;have+=out;
  }
  {size_t out=0;
   CHECK(lsx_dsd_reconstruction_finish(ctx,result+have*channels,&out)==SOX_DSD_NEED_OUTPUT);
   CHECK(out==0);
  }
  for (j=0;have<output_limit;j++) {
    size_t out=uneven ? (size_t)(1+(j%3u)) : output_limit+1;
    sox_dsd_status_t status=lsx_dsd_reconstruction_finish(ctx,result+have*channels,&out);
    CHECK(status==SOX_DSD_NEED_OUTPUT || status==SOX_DSD_DONE);
    CHECK(out<=output_limit-have);
    have+=out;
    CHECK(j<1000000u);
  }
  {size_t out=1;
   CHECK(lsx_dsd_reconstruction_finish(ctx,result+have*channels,&out)==SOX_DSD_DONE);
   CHECK(out==0);
  }
  {size_t input=0,out=1;
   CHECK(lsx_dsd_reconstruction_process(ctx,NULL,&input,result,&out)==SOX_DSD_BAD_ARGUMENT);
   CHECK(input==0 && out==0);
  }
  CHECK(have==output_limit);
  for (size_t i=0;i<have*channels;i++) CHECK(isfinite(result[i]));
  lsx_dsd_reconstruction_destroy(ctx);
  free(source);
  *n_output=have;
  return result;
}

static void test_invalid(void)
{
  lsx_dsd_reconstruction *ctx = NULL;
  sox_sample_t input[4] = {SOX_SAMPLE_MAX,-SOX_SAMPLE_MAX,0,SOX_SAMPLE_MAX};
  double output[4] = {0};
  size_t nin=2,nout=2;
  CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_MASTERING,2,&ctx)==SOX_DSD_OK);
  CHECK(lsx_dsd_reconstruction_process(ctx,input,&nin,output,&nout)==SOX_DSD_BAD_ARGUMENT);
  CHECK(nin==1 && nout==0);
  nin=1;nout=2;
  CHECK(lsx_dsd_reconstruction_process(ctx,input,&nin,output,&nout)==SOX_DSD_BAD_ARGUMENT);
  CHECK(nin==0 && nout==0);
  lsx_dsd_reconstruction_destroy(ctx);
  for (size_t bad=0;bad<3;bad++) {
    sox_sample_t invalid[]={0,(sox_sample_t)INT32_MIN,SOX_SAMPLE_MAX-1};
    ctx=NULL;
    CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_MASTERING,1,&ctx)==SOX_DSD_OK);
    nin=1;nout=2;
    CHECK(lsx_dsd_reconstruction_process(ctx,&invalid[bad],&nin,output,&nout)==SOX_DSD_BAD_ARGUMENT);
    CHECK(nin==0 && nout==0);
    lsx_dsd_reconstruction_destroy(ctx);
  }
  ctx=NULL;
  CHECK(lsx_dsd_reconstruction_create(45158400,LSX_DSD_PROFILE_MASTERING,1,&ctx)==SOX_DSD_UNSUPPORTED);
  CHECK(ctx==NULL);
  CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_LEGACY,1,&ctx)==SOX_DSD_UNSUPPORTED);
  CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_MASTERING,0,&ctx)==SOX_DSD_BAD_ARGUMENT);
  CHECK(lsx_dsd_reconstruction_create(2822400,LSX_DSD_PROFILE_MASTERING,1,NULL)==SOX_DSD_BAD_ARGUMENT);
  lsx_dsd_reconstruction_destroy(NULL);
}

static void unit(void)
{
  static unsigned const channel_counts[]={1,2,5,6};
  check_bank(lsx_dsd_coeff_halfband,57,1);
  check_bank(lsx_dsd_coeff_master64_256,117,0);
  check_bank(lsx_dsd_coeff_master128,153,0);
  check_bank(lsx_dsd_coeff_wideband,257,0);
  test_invalid();
  for (size_t p=0;p<sizeof(profiles)/sizeof(profiles[0]);p++)
    for (size_t c=0;c<sizeof(channel_counts)/sizeof(channel_counts[0]);c++) {
      unsigned channels=channel_counts[c];
      for (size_t n=0;n<=33;n++) {
        size_t a,b;
        double *ordinary=exercise(&profiles[p],channels,n,0,0,&a);
        double *irregular=exercise(&profiles[p],channels,n,0,1,&b);
        CHECK(a==b && memcmp(ordinary,irregular,a*channels*sizeof(double))==0);
        free(ordinary);free(irregular);
      }
      for (size_t n=79;n<=79+2;n++) {
        size_t a,b;
        double *ordinary=exercise(&profiles[p],channels,n,0,0,&a);
        double *irregular=exercise(&profiles[p],channels,n,0,1,&b);
        CHECK(a==b && memcmp(ordinary,irregular,a*channels*sizeof(double))==0);
        free(ordinary);free(irregular);
      }
      {size_t a,b; /* Multiple ring wraps and final stage latency. */
       double *ordinary=exercise(&profiles[p],channels,5099,0,0,&a);
       double *irregular=exercise(&profiles[p],channels,5099,0,1,&b);
       CHECK(a==b && memcmp(ordinary,irregular,a*channels*sizeof(double))==0);
       free(ordinary);free(irregular);
      }
    }
  printf("P06 scalar unit PASS (%lu assertions; 6 profiles, 1/2/5/6 channels, lengths 0..33 and ring wrap)\n",tests);
}

static void vectors(void)
{
  static unsigned const channel_counts[]={1,2,5,6};
  static size_t const lengths[]={0,1,2,3,4,31,32,33,129,511,5099};
  for (size_t p=0;p<sizeof(profiles)/sizeof(profiles[0]);p++)
    for (size_t c=0;c<sizeof(channel_counts)/sizeof(channel_counts[0]);c++)
      for (size_t k=0;k<sizeof(lengths)/sizeof(lengths[0]);k++)
        for (int pattern=0;pattern<4;pattern++) {
          size_t output;
          unsigned channels=channel_counts[c];
          double *values=exercise(&profiles[p],channels,lengths[k],pattern,1,&output);
          printf("{\"profile\":\"%s\",\"channels\":%u,\"length\":%zu,\"pattern\":%d,\"values\":[",
                 profiles[p].name,channels,lengths[k],pattern);
          for (size_t i=0;i<output*channels;i++)
            printf("%s\"%a\"",i?",":"",values[i]);
          printf("]}\n");
          free(values);
        }
}

/* Deterministic development microbenchmarks; not a 5% release gate. */
static void benchmark(const char *profile, unsigned channels, size_t frames)
{
  const struct profile *selected=NULL;
  lsx_dsd_reconstruction *ctx=NULL;
  lsx_dsd_reconstruction_info meta;
  sox_sample_t *bits;
  double *pcm;
  size_t read=0, emitted=0;
  clock_t begin, end;
  volatile double checksum=0.0;
  for (size_t i=0;i<sizeof(profiles)/sizeof(profiles[0]);i++)
    if (!strcmp(profiles[i].name,profile)) selected=&profiles[i];
  if (!selected || channels==0 || channels>6 || frames<1) exit(2);
  CHECK(lsx_dsd_reconstruction_create(selected->rate,selected->profile,channels,&ctx)==SOX_DSD_OK);
  CHECK(lsx_dsd_reconstruction_info_get(ctx,&meta)==SOX_DSD_OK);
  bits=malloc(4096*channels*sizeof(*bits));
  pcm=malloc(4096*channels*sizeof(*pcm));
  CHECK(bits && pcm);
  for (size_t i=0;i<4096;i++)for (unsigned c=0;c<channels;c++)
    bits[i*channels+c]=native_bit(i,c,0,frames)?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
  begin=clock();
  while(read<frames){
    size_t n=frames-read;
    size_t out=4096;
    if(n>4096)n=4096;
    CHECK(lsx_dsd_reconstruction_process(ctx,bits,&n,pcm,&out)==SOX_DSD_NEED_INPUT);
    read+=n;emitted+=out;
    for(size_t i=0;i<out*channels;i++)checksum+=pcm[i];
  }
  {size_t out=4096;
   CHECK(lsx_dsd_reconstruction_finish(ctx,pcm,&out)==SOX_DSD_DONE);
   emitted+=out;
   for(size_t i=0;i<out*channels;i++)checksum+=pcm[i];
  }
  end=clock();
  CHECK(emitted == frames/meta.factor+(frames%meta.factor!=0));
  printf("{\"profile\":\"%s\",\"native_hz\":%u,\"intermediate_hz\":%u,\"channels\":%u,\"frames\":%zu,\"output_frames\":%zu,\"cpu_seconds\":%.9f,\"frames_per_cpu_second\":%.3f,\"owned_bytes\":%zu,\"checksum\":%.16g,\"stage_taps\":[",
      profile,selected->rate,meta.intermediate_hz,channels,frames,emitted,
      (double)(end-begin)/CLOCKS_PER_SEC,frames/((double)(end-begin)/CLOCKS_PER_SEC),meta.allocated_bytes,(double)checksum);
  for (unsigned j=0;j<meta.stages;j++)printf("%s%u",j?",":"",meta.taps[j]);
  printf("]}\n");
  free(bits);free(pcm);lsx_dsd_reconstruction_destroy(ctx);
}

static void benchmark_kernels(size_t repetitions)
{
  const struct {const char *name; const double *coeff;size_t taps;int hb;} banks[]={
    {"halfband",lsx_dsd_coeff_halfband,57,1},
    {"master64_256",lsx_dsd_coeff_master64_256,117,0},
    {"master128",lsx_dsd_coeff_master128,153,0},
    {"wideband",lsx_dsd_coeff_wideband,257,0}};
  double samples[257];
  for (size_t i=0;i<257;i++)samples[i]=i&1?1.0:-1.0;
  for(size_t b=0;b<sizeof(banks)/sizeof(banks[0]);b++){
    volatile double checksum=0;
    clock_t start=clock();
    for(size_t i=0;i<repetitions;i++)
      checksum+=lsx_dsd_fir_scalar(banks[b].coeff,banks[b].taps,samples,banks[b].hb);
    double elapsed=(double)(clock()-start)/CLOCKS_PER_SEC;
    printf("{\"bank\":\"%s\",\"taps\":%zu,\"iterations\":%zu,\"cpu_seconds\":%.9f,\"ns_per_output\":%.3f,\"checksum\":%.16g}\n",
           banks[b].name,banks[b].taps,repetitions,elapsed,
           elapsed*1.e9/repetitions,(double)checksum);
  }
}

int main(int argc, char **argv)
{
  if (argc==5 && !strcmp(argv[1],"--bench")) benchmark(argv[2],(unsigned)strtoul(argv[3],NULL,10),(size_t)strtoull(argv[4],NULL,10));
  else if (argc==3 && !strcmp(argv[1],"--bench-kernels")) benchmark_kernels((size_t)strtoull(argv[2],NULL,10));
  else if (argc==2 && !strcmp(argv[1],"--vectors")) vectors();
  else if (argc==1 || (argc==2 && !strcmp(argv[1],"--unit"))) unit();
  else {fprintf(stderr,"usage: %s [--unit|--vectors]\n",argv[0]);return 2;}
  return 0;
}
