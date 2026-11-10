/* Reproducible normal-SDM benchmark. Production-sized blocks; guarded and
 * monitored. Compile this SAME file against baseline and candidate libraries.
 * The timer excludes fixture generation, dispatch and summary calculation. */
#define _POSIX_C_SOURCE 200809L
#include "dsd_kernels.h"
#include "pcmdsd.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double seconds(struct timespec a, struct timespec b)
{
  return (double)(b.tv_sec-a.tv_sec)+(double)(b.tv_nsec-a.tv_nsec)*1e-9;
}

static uint64_t hash_bytes(uint64_t h, const void *p, size_t n)
{
  const unsigned char *b=p;
  while(n--) { h^=*b++; h*=UINT64_C(1099511628211); }
  return h;
}

int main(int argc, char **argv)
{
  const sdm_profile_t *p;
  const lsx_pcmdsd_profile *production;
  const lsx_dsd_kernel *k;
  const double *a,*g,*bounds;
  double artificial[8],peak=0.,*in;
  sox_sample_t *out;
  sdm_normal_t state;
  sdm_normal_monitor_t monitor;
  struct timespec c0,c1,w0,w1;
  uint64_t sum=0, digest=UINT64_C(14695981039346656037);
  size_t i,frames,block,done,fixture=65536;
  unsigned rate,order;
  double cpu,wall;
  int rc;
  if(argc!=6) {
    fprintf(stderr,"usage: %s tier profile native_hz frames block_size\n",argv[0]);
    return 2;
  }
  rate=(unsigned)strtoul(argv[3],NULL,10);
  frames=(size_t)strtoull(argv[4],NULL,10);
  block=(size_t)strtoull(argv[5],NULL,10);
  if(frames<16384 || frames>UINT64_C(200000000) || !block || block>16384)
    return 2;
  p=sdm_profile_find(argv[2],rate);
  if(!p || sdm_profile_coefficients(p,&a,&g,&order) ||
      lsx_dsd_kernel_select_sdm_rate(argv[1],rate,&k))return 2;
  (void)a;(void)g;
  production=lsx_pcmdsd_profile_find(rate);
  for(i=0;i<8;++i)artificial[i]=1e18;
  bounds=production && !strcmp(production->id,argv[2]) ? production->bounds : artificial;
  /* A periodic, low-level 2-tone fixture avoids timed trigonometry. Every
   * sample is finite and within the production envelope. */
  in=malloc((fixture+block)*sizeof(*in));
  out=malloc(block*sizeof(*out));
  if(!in || !out)return 3;
  for(i=0;i<fixture+block;++i) {
    double phase=2.*3.14159265358979323846*(double)(i%fixture)/(double)fixture;
    in[i]=.11*sin(17.*phase)+.03*cos(41.*phase);
  }
  if(sdm_normal_init(&state,p))return 3;
  sdm_normal_monitor_init(&monitor);
  sdm_normal_attach_monitor(&state,&monitor);
  clock_gettime(CLOCK_MONOTONIC,&w0);
  clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&c0);
  for(i=0;i<frames;) {
    size_t n=frames-i<block?frames-i:block;
    rc=k->sdm_block(&state,in+i%fixture,n,out,&done,bounds,NULL,.5,&peak);
    if(rc || done!=n) {
      fprintf(stderr,"guard failed: %s/%s frame=%zu rc=%d committed=%zu\n",
          argv[1],argv[2],i,rc,done);
      return 4;
    }
    sum=(sum<<1)|(sum>>63);
    sum^=(uint32_t)out[n/2];
    i+=n;
  }
  clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&c1);
  clock_gettime(CLOCK_MONOTONIC,&w1);
  cpu=seconds(c0,c1);wall=seconds(w0,w1);
  if(!(cpu>0) || monitor.frames!=frames || monitor.nonfinite ||
      monitor.overloads || monitor.counter_saturated)return 5;
  digest=hash_bytes(digest,state.state,sizeof(state.state));
  digest=hash_bytes(digest,&state.previous_decision,sizeof(state.previous_decision));
  digest=hash_bytes(digest,&state.bank,sizeof(state.bank));
  digest=hash_bytes(digest,&state.frames,sizeof(state.frames));
  digest=hash_bytes(digest,&monitor,sizeof(monitor));
  printf("{\"requested_tier\":\"%s\",\"tier\":\"%s\",\"profile\":\"%s\","
      "\"rate\":%u,\"order\":%u,\"frames\":%zu,\"block\":%zu,"
      "\"cpu_seconds\":%.9f,\"wall_seconds\":%.9f,\"cpu_ns_per_frame\":%.9f,"
      "\"sample_checksum\":\"%016" PRIx64 "\",\"state_monitor_hash\":\"%016" PRIx64 "\","
      "\"guards_active\":true,\"monitor_active\":true,\"bounds\":\"%s\",\"peak\":%.17g}\n",
      argv[1],k->name,argv[2],rate,order,frames,block,cpu,wall,1e9*cpu/frames,
      sum,digest,bounds==artificial?"synthetic 1e18":"production",peak);
  free(in);free(out);
  return 0;
}
