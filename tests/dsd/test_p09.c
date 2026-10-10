/* P09 strict-rate registry, scalar normal state and diagnostic probe.
 * Link the actual SoX library. Do not include or duplicate src/sdm.c.
 */
#define _POSIX_C_SOURCE 200809L
#include "sdm.h"
#include <math.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846264338327950288
#endif
#define CHECK(x) do { if (!(x)) { \
  fprintf(stderr,"P09 unit failure line %d: %s\n",__LINE__,#x); return 1; } \
} while (0)

static const char * const selected_ids[4] = {
  "encode.legacy.v1", "encode.mastering.v1",
  "encode.diagnostic.sdm6.v1", "encode.diagnostic.clans8.v1"
};
static const char * const names[4] = {"clans-4", "sdm-8", "sdm-6", "clans-8"};
static const unsigned rates[3] = { 2822400, 5644800, 11289600 };
static void make_id(char *out, size_t size, int kind, unsigned rate)
{
  (void)snprintf(out,size,"%s.dsd%u",selected_ids[kind],rate/44100);
}

static int units(void)
{
  unsigned j,k,i, checks=0;
  CHECK(sdm_profile_find(NULL,rates[0]) == NULL);
  CHECK(sdm_profile_find("encode.mastering.v1.dsd64",0) == NULL);
  CHECK(sdm_profile_find("encode.mastering.v1.dsd64",22579200) == NULL);
  CHECK(sdm_profile_find("encode.mastering.v1.dsd64",rates[1]) == NULL);
  CHECK(sdm_normal_decision(-0.) == -1);
  CHECK(sdm_normal_decision(+0.) == 1);
  for (j=0;j<3;j++) for (k=0;k<4;k++) {
    const sdm_profile_t *p;
    const double *a,*g;
    unsigned order;
    char id[96];
    sdm_normal_t s;
    make_id(id,sizeof(id),k,rates[j]);
    p=sdm_profile_find(id,rates[j]);
    CHECK(p && p==sdm_profile_find(id,rates[j]));
    CHECK(!strcmp(sdm_profile_id(p),id));
    CHECK(!strcmp(sdm_profile_filter_name(p),names[k]));
    CHECK(sdm_profile_rate(p)==rates[j]);
    CHECK(sdm_profile_working_rate(p)==(j==0?88200:176400));
    CHECK(sdm_profile_coefficients(p,&a,&g,&order)==0);
    CHECK(order==(k==0?4:k==2?6:8));
    CHECK(sdm_normal_init(&s,p)==0);
    CHECK(s.profile==p && s.previous_decision==0 && s.frames==0);
    for (i=0;i<2;i++) for (unsigned t=0;t<8;t++) CHECK(s.state[i][t]==0);
    CHECK(sdm_profile_find(id,rates[(j+1)%3])==NULL);
    CHECK(sdm_profile_find(id,22579200)==NULL);
    CHECK(sdm_normal_init(NULL,p)!=0);
    CHECK(sdm_normal_init(&s,NULL)!=0);
    CHECK(sdm_normal_init(&s,p)==0);
    checks+=10;
  }
  /* Independent recurrence computation, reading only the published a/g. */
  {
    const sdm_profile_t *p=sdm_profile_find("encode.mastering.v1.dsd64",rates[0]);
    sdm_normal_t normal;
    double old[8]={0}, next[8]={0}, prev=0;
    const double *a,*g;
    unsigned order;
    CHECK(sdm_profile_coefficients(p,&a,&g,&order)==0);
    CHECK(sdm_normal_init(&normal,p)==0);
    for (i=0;i<15000;i++) {
      unsigned t;
      int expected,got;
      double x=.31*sin((2*M_PI*997/rates[0])*i);
      double v=x;
      next[0]=old[0]-g[0]*old[1]+x-prev;
      v+=a[0]*next[0];
      for (t=1;t<order-1;t++) {
        next[t]=old[t]+old[t-1]-g[t]*old[t+1];
        v+=a[t]*next[t];
      }
      next[t]=old[t]+old[t-1];
      v+=a[t]*next[t];
      expected=signbit(v)?-1:1;
      CHECK(sdm_normal_step(&normal,x,&got)==0);
      CHECK(got==expected);
      CHECK(normal.previous_decision==expected);
      for (t=0;t<order;t++) CHECK(normal.state[normal.bank][t]==next[t]);
      memcpy(old,next,sizeof(old));
      prev=expected;
    }
    checks+=15000;
  }
  /* Different buffer boundaries must not reset the full 28-bit history. */
  {
    sdm_normal_t one,many;
    sdm_normal_monitor_t m0,m1;
    const sdm_profile_t *p=sdm_profile_find("encode.mastering.v1.dsd64",rates[0]);
    CHECK(sdm_normal_init(&one,p)==0 && sdm_normal_init(&many,p)==0);
    sdm_normal_monitor_init(&m0); sdm_normal_monitor_init(&m1);
    sdm_normal_attach_monitor(&one,&m0);
    sdm_normal_attach_monitor(&many,&m1);
    for (i=0;i<512;i++) {
      int a,b;
      double x=.2*sin((2*M_PI*1000/rates[0])*i);
      CHECK(sdm_normal_step(&one,x,&a)==0);
      if (i==13 || i==32 || i==64 || i==192)
        sdm_normal_attach_monitor(&many,&m1); /* never clears counters */
      CHECK(sdm_normal_step(&many,x,&b)==0);
      CHECK(a==b);
    }
    CHECK(m0.frames==512 && m0.windows28==485);
    CHECK(m0.history_bits==28 && m0.min_ones28<=m0.max_ones28);
    CHECK(memcmp(&m0,&m1,sizeof(m0))==0);
    CHECK(!memcmp(one.state,many.state,sizeof(one.state)));
    CHECK(m0.nonfinite==0 && m0.overloads==0);
    /* Monitor attachment cannot change the one-bit sequence or states. */
    {
      sdm_normal_t bare;
      CHECK(sdm_normal_init(&bare,p)==0);
      for (i=0;i<512;i++) {
        int y;
        double x=.2*sin((2*M_PI*1000/rates[0])*i);
        CHECK(sdm_normal_step(&bare,x,&y)==0);
      }
      CHECK(bare.frames==many.frames && bare.bank==many.bank);
      CHECK(!memcmp(bare.state,many.state,sizeof(bare.state)));
      CHECK(bare.previous_decision==many.previous_decision);
    }
    CHECK(sdm_legacy_allocation_bytes() >
          sizeof(sdm_normal_t)+sizeof(sdm_normal_monitor_t));
    m0.frames=UINT64_MAX; m0.windows28=UINT64_MAX;
    m0.excursions28=UINT64_MAX;
    CHECK(sdm_normal_step(&one,0,&(int){0})==0);
    CHECK(m0.frames==UINT64_MAX && m0.windows28==UINT64_MAX);
    CHECK(m0.counter_saturated);
    {
      unsigned bank=one.bank;
      uint64_t frame=one.frames;
      double previous=one.previous_decision;
      CHECK(sdm_normal_step(&one,NAN,&(int){0})==-1);
      CHECK(one.bank==bank && one.frames==frame && one.previous_decision==previous);
      CHECK(m0.nonfinite==1 && m0.first_bad_frame==frame);
    }
    checks+=8;
  }
  printf("P09 unit assertions passed: %u\n",checks);
  return 0;
}

static int coefficients(const char *id,unsigned rate,const char *file)
{
  const sdm_profile_t *p=sdm_profile_find(id,rate);
  const double *a,*g;
  FILE *out;
  unsigned order,i,j;
  if (!p || sdm_profile_coefficients(p,&a,&g,&order)) return 2;
  out=fopen(file,"wb");if (!out)return 3;
  for (i=0;i<16;i++) {
    uint64_t bits;
    unsigned char bytes[8];
    double d=i<8?a[i]:g[i-8];
    memcpy(&bits,&d,sizeof(bits));
    for(j=0;j<8;j++)bytes[j]=(unsigned char)(bits>>(j*8));
    if(fwrite(bytes,1,8,out)!=8){fclose(out);return 4;}
  }
  return fclose(out)?4:0;
}

static int render(const char *id,unsigned rate,double freq,double dbfs,
                  double seconds,const char *file)
{
  const sdm_profile_t *p=sdm_profile_find(id,rate);
  sdm_normal_t s;
  sdm_normal_monitor_t monitor;
  FILE *out;
  uint64_t n,i;
  unsigned bits=0,bits_used=0;
  double peak;
  if (!p || !(freq>0&&freq<rate/2) || !isfinite(dbfs) ||
      !(seconds>0&&seconds<=3600))return 2;
  if (seconds*(double)rate >= (double)UINT64_MAX)return 2;
  n=(uint64_t)(seconds*rate+.5);
  peak=.5*pow(10.,dbfs/20.);
  if (!(peak<=.5 && peak>0))return 2;
  if (sdm_normal_init(&s,p))return 3;
  sdm_normal_monitor_init(&monitor);
  sdm_normal_attach_monitor(&s,&monitor);
  out=fopen(file,"wb");if(!out)return 4;
  setvbuf(out,NULL,_IOFBF,128*1024);
  for (i=0;i<n;i++) {
    double x=peak*sin((2*M_PI*freq/rate)*i);
    int y;
    if (sdm_normal_step(&s,x,&y)) {fclose(out);return 5;}
    bits=(bits<<1) | (y>0);
    if(++bits_used==8) {
      if(fputc((int)bits,out)==EOF) {fclose(out);return 6;}
      bits=bits_used=0;
    }
  }
  if (bits_used && fputc((int)(bits<<(8-bits_used)),out)==EOF) {
    fclose(out);return 6;
  }
  if(fclose(out))return 6;
  printf("{\"profile_id\":\"%s\",\"rate_hz\":%u,\"frames\":%"PRIu64
    ",\"min_ones28\":%u,\"max_ones28\":%u,\"windows28\":%"PRIu64
    ",\"excursions28\":%"PRIu64",\"overloads\":%"PRIu64
    ",\"nonfinite\":%"PRIu64",\"longest_run\":%"PRIu64
    ",\"counter_saturated\":%u,\"max_abs_state\":[",
    id,rate,n,monitor.min_ones28,monitor.max_ones28,monitor.windows28,
    monitor.excursions28,monitor.overloads,monitor.nonfinite,
    monitor.longest_run,monitor.counter_saturated);
  for (i=0;i<8;i++)printf("%s%.17g",i?",":"",monitor.max_abs_state[i]);
  puts("]}");
  return 0;
}

static int timed_state(const char *id,unsigned rate,unsigned long samples,int monitored)
{
  const sdm_profile_t *p=sdm_profile_find(id,rate);
  sdm_normal_t state;
  sdm_normal_monitor_t diag;
  double sample_lut[1024];
  volatile uint64_t sum=0;
  clock_t start,finish;
  unsigned long i;
  if (!p || !(samples>0 && samples<=50000000UL)) return 2;
  for(i=0;i<1024;i++)sample_lut[i]=.18*sin((2*M_PI*7/1024)*i);
  if (sdm_normal_init(&state,p))return 3;
  sdm_normal_monitor_init(&diag);
  if (monitored)sdm_normal_attach_monitor(&state,&diag);
  start=clock();
  for(i=0;i<samples;i++) {
    int bit;
    if(sdm_normal_step(&state,sample_lut[i&1023],&bit))return 4;
    sum+=(unsigned)(bit>0);
  }
  finish=clock();
  printf("{\"profile_id\":\"%s\",\"rate\":%u,\"monitor\":%s,"
         "\"samples\":%lu,\"ones\":%"PRIu64",\"cpu_seconds\":%.9f,"
         "\"legacy_allocation_bytes\":%zu,\"normal_state_bytes\":%zu,"
         "\"monitor_bytes\":%zu}\n",id,rate,monitored?"true":"false",
         samples,(uint64_t)sum,(double)(finish-start)/CLOCKS_PER_SEC,
         sdm_legacy_allocation_bytes(),sizeof(state),sizeof(diag));
  return 0;
}

int main(int argc,char **argv)
{
  if (argc==2 && !strcmp(argv[1],"--unit"))return units();
  if (argc==6 && !strcmp(argv[1],"--state-bench"))
    return timed_state(argv[2],(unsigned)strtoul(argv[3],NULL,10),
                       strtoul(argv[4],NULL,10),!strcmp(argv[5],"monitor"));
  if (argc==5 && !strcmp(argv[1],"--coeff"))
    return coefficients(argv[2],(unsigned)strtoul(argv[3],NULL,10),argv[4]);
  if (argc==8 && !strcmp(argv[1],"--render"))
    return render(argv[2],(unsigned)strtoul(argv[3],NULL,10),
                  strtod(argv[4],NULL),strtod(argv[5],NULL),strtod(argv[6],NULL),argv[7]);
  fprintf(stderr,"usage: %s --unit | --coeff profile rate file | --render profile rate hz source-dbfs seconds bits-file\n",argv[0]);
  return 2;
}
