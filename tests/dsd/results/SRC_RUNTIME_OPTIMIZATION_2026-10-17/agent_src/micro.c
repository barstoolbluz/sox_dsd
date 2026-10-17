
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <assert.h>
#include <sched.h>
typedef double sample_t;
typedef struct {double *data; size_t len, pos;} fifo_t;
typedef struct {double *poly_fir_coefs;} shared_t;
typedef struct {fifo_t fifo; int pre, pre_post; double out_in_ratio; shared_t *shared; union{struct {uint32_t fraction; int32_t integer;} parts; int64_t all;} at,step; int n,L;} stage_t;
static void *lsx_fifo_reserve(fifo_t *f,size_t n){f->len=n;return f->data;}
static void *lsx_fifo_read(fifo_t *f,size_t n,void*x){void*p=f->data+f->pos;(void)x;f->pos+=n;return p;}
static void lsx_fifo_trim_by(fifo_t *f,size_t n){assert(n<=f->len);f->len-=n;}
#define lsx_warn(...) abort()
#define stage_read_p(p) ((p)->fifo.data+(p)->fifo.pos+(p)->pre)
#define stage_occupancy(p) ((int)((p)->fifo.len-(p)->fifo.pos-(p)->pre_post))
#define coef(coef_p,interp_order,fir_len,phase_num,coef_interp_num,fir_coef_num) coef_p[(fir_len)*((interp_order)+1)*(phase_num)+((interp_order)+1)*(fir_coef_num)+(interp_order-coef_interp_num)]

#define FUNCTION poly_base
#define FIR_LENGTH p->n
#define CONVOLVE while(j < FIR_LENGTH) _
#include "/workspace/scratch/4dd8292178b8/sox_ng/src/rate_poly_fir0.h"

#define FUNCTION poly_recur
#define FIR_LENGTH p->n
#define CONVOLVE while(j < FIR_LENGTH) _
#include "/workspace/scratch/4dd8292178b8/agent_src/rate_poly_fir0_recurrence.h"

static const sample_t half_fir_coefs_8[] = {
  0.3115465451887802, -0.08734497241282892, 0.03681452335604365,
  -0.01518925831569441, 0.005454118437408876, -0.001564400922162005,
  0.0003181701445034203, -3.48001341225749e-5,
};

#define FUNCTION half8_base
#define COEFS half_fir_coefs_8
#define CONVOLVE _ _ _ _ _ _ _ _ 
#include "/workspace/scratch/4dd8292178b8/sox_ng/src/rate_half_fir.h"

#define FUNCTION half8_batch2
#define COEFS half_fir_coefs_8
#define CONVOLVE _ _ _ _ _ _ _ _ 
#include "/workspace/scratch/4dd8292178b8/agent_src/rate_half_fir_batch2.h"

#define FUNCTION half8_batch4
#define COEFS half_fir_coefs_8
#define CONVOLVE _ _ _ _ _ _ _ _ 
#include "/workspace/scratch/4dd8292178b8/agent_src/rate_half_fir_batch4.h"

static const sample_t half_fir_coefs_13[] = {
  0.3140822554324578, -0.0940458550886253, 0.04545990399121566,
  -0.02338339450796002, 0.01164429409071052, -0.005380686021429845,
  0.002242915773871009, -0.000822047600000082, 0.0002572510962395222,
  -6.607320708956279e-5, 1.309926399120154e-5, -1.790719575255006e-6,
  1.27504961098836e-7,
};

#define FUNCTION half13_base
#define COEFS half_fir_coefs_13
#define CONVOLVE _ _ _ _ _ _ _ _ _ _ _ _ _ 
#include "/workspace/scratch/4dd8292178b8/sox_ng/src/rate_half_fir.h"

#define FUNCTION half13_batch2
#define COEFS half_fir_coefs_13
#define CONVOLVE _ _ _ _ _ _ _ _ _ _ _ _ _ 
#include "/workspace/scratch/4dd8292178b8/agent_src/rate_half_fir_batch2.h"

#define FUNCTION half13_batch4
#define COEFS half_fir_coefs_13
#define CONVOLVE _ _ _ _ _ _ _ _ _ _ _ _ _ 
#include "/workspace/scratch/4dd8292178b8/agent_src/rate_half_fir_batch4.h"

static double tick(void){struct timespec t;clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&t);return t.tv_sec+1e-9*t.tv_nsec;}
static uint64_t state=14;
static uint64_t rnd(void){state^=state>>12;state^=state<<25;state^=state>>27;return state*2685821657736338717ULL;}
static double random_sample(void){return (double)((int64_t)(rnd()>>12)-(INT64_C(1)<<51))*0x1p-51;}
typedef void(*fn)(stage_t*,fifo_t*);
static double ibuf[262144],ob0[1048576],ob1[1048576],coefs[262144];
static stage_t init(int n,int L,int M,int count,int phase,int half){
static shared_t shared;stage_t s;memset(&s,0,sizeof s);shared.poly_fir_coefs=coefs;s.shared=&shared;s.n=n;s.L=L;s.step.parts.integer=M;s.at.parts.integer=phase;s.pre=half?2*n:0;s.pre_post=half?4*n:n-1;s.fifo.data=ibuf;s.fifo.len=count+s.pre_post;s.out_in_ratio=(double)L/M;return s;}
static int compare(fn a,fn b,int n,int L,int M,int count,int phase,int half){
 stage_t x=init(n,L,M,count,phase,half),y=x;fifo_t of0={ob0,0,0},of1={ob1,0,0};
 a(&x,&of0);b(&y,&of1);
 if(of0.len!=of1.len||x.fifo.pos!=y.fifo.pos||x.at.parts.integer!=y.at.parts.integer||memcmp(ob0,ob1,of0.len*sizeof(double))){fprintf(stderr,"DIFF n=%d L=%d M=%d cnt=%d phase=%d half=%d lens=%zu,%zu pos=%zu,%zu at=%d,%d\n",n,L,M,count,phase,half,of0.len,of1.len,x.fifo.pos,y.fifo.pos,x.at.parts.integer,y.at.parts.integer);return 1;}return 0;
}
static double bench(fn f,int n,int L,int M,int half,int reps){
 stage_t save=init(n,L,M,8192,0,half);fifo_t out={ob0,0,0};volatile double chk=0;double t=tick();
 for(int k=0;k<reps;k++){stage_t s=save;f(&s,&out);chk+=out.data[k%out.len];}
 t=tick()-t;if(chk==1.1)printf("%f",chk);return t;
}
int main(int argc,char**argv){cpu_set_t cp;CPU_ZERO(&cp);int core=argc>1?atoi(argv[1]):0;CPU_SET(core,&cp);if(sched_setaffinity(0,sizeof cp,&cp))perror("affinity");
 for(size_t i=0;i<sizeof ibuf/sizeof*ibuf;i++)ibuf[i]=random_sample();
 for(size_t i=0;i<sizeof coefs/sizeof*coefs;i++)coefs[i]=random_sample()*0x1p-4;
 int total=0;int lengths[]={1,2,3,11,16,32,63,128};int counts[]={0,1,2,3,9,31,257,1023};int ratios[][2]={{1,1},{3,1},{3,2},{80,147},{160,147},{147,160},{4,5},{128,1},{128,17}};
 for(size_t n=0;n<sizeof lengths/sizeof*lengths;n++)for(size_t count=0;count<sizeof counts/sizeof*counts;count++)for(size_t r=0;r<sizeof ratios/sizeof*ratios;r++)for(int phase=0;phase<ratios[r][0];phase++){
 if(compare(poly_base,poly_recur,lengths[n],ratios[r][0],ratios[r][1],counts[count],phase,0))return 2;total++;
 }
 for(int n=8;n<=13;n+=5)for(size_t c=0;c<sizeof counts/sizeof*counts;c++){
 fn b=n==8?half8_base:half13_base;fn c2=n==8?half8_batch2:half13_batch2;fn c4=n==8?half8_batch4:half13_batch4;
 if(compare(b,c2,n,1,2,counts[c],0,1)||compare(b,c4,n,1,2,counts[c],0,1))return 2;total+=2;
 }
 printf("{\"validation_cases\":%d,\"measurements\":[\n",total);
 for(int rep=0;rep<7;rep++){
  for(int n=11;n<=88;n*=2){double a,b;if(rep&1){b=bench(poly_recur,n,80,147,0,1500);a=bench(poly_base,n,80,147,0,1500);}else{a=bench(poly_base,n,80,147,0,1500);b=bench(poly_recur,n,80,147,0,1500);}printf("{\"case\":\"poly%d_80_147\",\"rep\":%d,\"base\":%.9f,\"optimized\":%.9f,\"speedup\":%.6f},\n",n,rep,a,b,a/b);}
  for(int n=8;n<=13;n+=5){fn base=n==8?half8_base:half13_base,c2=n==8?half8_batch2:half13_batch2,c4=n==8?half8_batch4:half13_batch4;
   double a=bench(base,n,1,2,1,1500),b=bench(c2,n,1,2,1,1500),c=bench(c4,n,1,2,1,1500);
   printf("{\"case\":\"half%d_batch2\",\"rep\":%d,\"base\":%.9f,\"optimized\":%.9f,\"speedup\":%.6f},\n",n,rep,a,b,a/b);
   printf("{\"case\":\"half%d_batch4\",\"rep\":%d,\"base\":%.9f,\"optimized\":%.9f,\"speedup\":%.6f}%s\n",n,rep,a,c,a/c,(rep==6&&n==13)?"":",");
  }
 }
 puts("]}");return 0;
}
