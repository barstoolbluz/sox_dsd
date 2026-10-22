/* P10 executable contract tests and explicitly named candidate renderer.
 * Links the configured production library, including its actual SRC backend.
 * This tool is not the installed CLI and cannot promote a mastering profile. */
#include "sox_i.h"
#include "pcmdsd.h"
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static unsigned long checks;
#define CHECK(x) do { ++checks; if (!(x)) { \
  fprintf(stderr,"P10 assertion line %d: %s\n",__LINE__,#x); exit(1); } } while (0)
static const uint32_t rates[]={2822400,5644800,11289600};
static const uint32_t sources[]={44100,48000,88200,96000,176400,192000,352800,384000,705600};
static const double test_bounds[8]={0x1p100,0x1p100,0x1p100,0x1p100,0x1p100,0x1p100,0x1p100,0x1p100};

static lsx_pcmdsd *create(uint32_t a,uint32_t b,double scale,const double *bounds)
{
  lsx_pcmdsd *p=NULL;
  CHECK(lsx_pcmdsd_candidate_create(a,b,scale,3,NULL,bounds,&p)==SOX_DSD_OK && p);
  return p;
}
static void envelope(void)
{
  lsx_pcmdsd *p;
  lsx_pcmdsd_report r;
  sox_sample_t out[32];
  double x[32]={0};
  size_t i,n,m;
  sdm_normal_t s;
  const sdm_profile_t *profile=sdm_profile_find("encode.mastering.v1.dsd64",rates[0]);
  int bit=91;unsigned coordinate=99;
  double bounds[8]={.1,.1,.1,.1,.1,.1,.1,.1};
  for (i=0;i<3;i++) {
    const lsx_pcmdsd_profile *d=lsx_pcmdsd_profile_find(rates[i]);
    /* P15 promoted the original 64/128/256 mastering profiles. The P10
     * developmental test must assert current positive qualification, not
     * resurrect its pre-P15 unavailable-profile assumption. */
    CHECK(d && d->native_hz==rates[i] && d->qualified && d->bounds);
    CHECK(d->working_hz==(i?176400:88200));
    CHECK(d->pass_hz==(i==0?20000:i==1?30000:40000));
    p=(void *)1;
    CHECK(lsx_pcmdsd_create(48000,rates[i],.5,0,&p)==SOX_DSD_OK && p);
    lsx_pcmdsd_destroy(p);p=NULL;
  }
  p=(void *)1;
  /* P17 adds an explicitly unqualified, test-only composite candidate.
   * The production constructor must still refuse the rate. */
  CHECK(lsx_pcmdsd_create(48000,22579200,.5,0,&p)==SOX_DSD_UNSUPPORTED && !p);
  CHECK(lsx_pcmdsd_candidate_create(48000,22579200,.5,0,NULL,NULL,&p)==SOX_DSD_OK && p);
  lsx_pcmdsd_destroy(p);p=NULL;
  /* P19 correction is an explicitly selected, separately guarded v2
   * candidate. The v1 default, original coefficients and public gate stay. */
  {
    const char *v2_id="encode.mastering.v2.dsd1024";
    const lsx_pcmdsd_profile *v2=lsx_pcmdsd_profile_find_id(45158400,v2_id);
    const sdm_profile_t *control=sdm_profile_find(v2_id,45158400);
    const double *a,*g;unsigned order;
    CHECK(lsx_pcmdsd_profile_find(45158400) &&
        !strcmp(lsx_pcmdsd_profile_find(45158400)->id,"encode.mastering.v1.dsd1024"));
    CHECK(v2 && !v2->qualified && !v2->certificate_sha256 && v2->bounds);
    CHECK(control && sdm_profile_rate(control)==45158400);
    CHECK(!sdm_profile_coefficients(control,&a,&g,&order) && order==7);
    CHECK(lsx_pcmdsd_create(176400,45158400,.5,0,&p)==SOX_DSD_UNSUPPORTED && !p);
    CHECK(lsx_pcmdsd_candidate_create(176400,45158400,.5,0,control,v2->bounds,&p)==SOX_DSD_OK && p);
    CHECK(lsx_pcmdsd_profile_of(p)==v2);
    lsx_pcmdsd_destroy(p);p=NULL;
  }
  CHECK(lsx_pcmdsd_candidate_create(0,2822400,.5,0,NULL,NULL,&p)==SOX_DSD_BAD_ARGUMENT && !p);
  CHECK(lsx_pcmdsd_candidate_create(48000,5644800,.5,0,profile,NULL,&p)==SOX_DSD_UNSUPPORTED && !p);
  p=create(88200,2822400,.5,test_bounds);
  n=12;m=0;
  CHECK(lsx_pcmdsd_process(p,NULL,&n,NULL,&m)==SOX_DSD_NEED_OUTPUT && !n && !m);
  CHECK(lsx_pcmdsd_report_get(p,&r)==SOX_DSD_OK && r.input_frames==0 && r.committed_frames==0);
  /* SOX_SAMPLE_MIN is slightly below -1 with the retained MAX normalization. */
  x[0]=.5*(double)INT32_MIN/SOX_SAMPLE_MAX; /* value of SOX_SAMPLE_MIN, without its inherited signed-shift macro */
  CHECK(lsx_pcmdsd_modulate(p,x,out,1)==SOX_DSD_OK);
  x[0]=.5+1./SOX_SAMPLE_MAX;
  CHECK(lsx_pcmdsd_modulate(p,x,out,1)==SOX_DSD_OK);
  x[0]=nextafter(x[0],INFINITY);
  CHECK(lsx_pcmdsd_modulate(p,x,out,1)==SOX_DSD_NUMERIC_ERROR);
  CHECK(lsx_pcmdsd_report_get(p,&r)==SOX_DSD_OK);
  CHECK(r.failure==LSX_PCMDSD_INTERPOLATION_OVERLOAD && r.first_bad_frame==2 && r.channel==3);
  CHECK(r.minimum_attenuation_db>0);
  x[0]=0;
  CHECK(lsx_pcmdsd_modulate(p,x,out,1)==SOX_DSD_NUMERIC_ERROR);
  lsx_pcmdsd_destroy(p);
  p=create(88200,2822400,1.,test_bounds);
  x[0]=.5+2./SOX_SAMPLE_MAX;
  CHECK(lsx_pcmdsd_modulate(p,x,out,1)==SOX_DSD_OK);
  x[0]=NAN;
  CHECK(lsx_pcmdsd_modulate(p,x,out,1)==SOX_DSD_NUMERIC_ERROR);
  CHECK(lsx_pcmdsd_report_get(p,&r)==SOX_DSD_OK && r.first_bad_frame==1);
  CHECK(r.failure==LSX_PCMDSD_INPUT_NONFINITE);
  lsx_pcmdsd_destroy(p);
  CHECK(sdm_normal_init(&s,profile)==0);
  CHECK(sdm_normal_step_guarded(&s,.2,&bit,bounds,&coordinate)==-2);
  CHECK(coordinate==0 && s.frames==0 && s.bank==0 && s.previous_decision==0 && bit==91);
  CHECK(sdm_normal_step_guarded(&s,NAN,&bit,test_bounds,&coordinate)==-1 && !s.frames);
  p=create(88200,2822400,.5,bounds);
  x[0]=.2;
  CHECK(lsx_pcmdsd_modulate(p,x,out,1)==SOX_DSD_NUMERIC_ERROR);
  CHECK(lsx_pcmdsd_report_get(p,&r)==SOX_DSD_OK && r.failure==LSX_PCMDSD_STATE_BOUND && r.coordinate==0 && !r.first_bad_frame);
  lsx_pcmdsd_destroy(p);
}

static void failed_block_commit(void)
{
  double input[512]={0};
  sox_sample_t *output=malloc(65536*sizeof(*output));
  lsx_pcmdsd *p;lsx_pcmdsd_report r;size_t n=512,m=65536;
  const double tight[8]={.1,.1,.1,.1,.1,.1,.1,.1};
  CHECK(output!=NULL);
  p=create(88200,2822400,.5,test_bounds);
  input[511]=NAN;
  CHECK(lsx_pcmdsd_process(p,input,&n,output,&m)==SOX_DSD_NUMERIC_ERROR);
  CHECK(m==0);
  CHECK(lsx_pcmdsd_report_get(p,&r)==SOX_DSD_OK);
  CHECK(r.failure==LSX_PCMDSD_INPUT_NONFINITE && r.committed_frames==0 && r.channel==3);
  n=512;m=65536;input[511]=0;
  CHECK(lsx_pcmdsd_process(p,input,&n,output,&m)==SOX_DSD_NUMERIC_ERROR && !n && !m);
  lsx_pcmdsd_destroy(p);
  p=create(88200,2822400,.5,tight);n=512;m=65536;
  {
    sox_dsd_status_t rc=lsx_pcmdsd_process(p,input,&n,output,&m);
    if(rc==SOX_DSD_NEED_INPUT) {
      CHECK(!m && n==512);m=65536;
      rc=lsx_pcmdsd_finish(p,output,&m);
    }
    CHECK(rc==SOX_DSD_NUMERIC_ERROR && !m);
  }
  CHECK(lsx_pcmdsd_report_get(p,&r)==SOX_DSD_OK);
  CHECK(r.failure==LSX_PCMDSD_STATE_BOUND && r.first_bad_frame==1 && r.committed_frames==0);
  CHECK(r.monitor.frames==1 && r.coordinate==0 && r.channel==3);
  m=65536;
  CHECK(lsx_pcmdsd_finish(p,output,&m)==SOX_DSD_NUMERIC_ERROR && !m);
  lsx_pcmdsd_destroy(p);free(output);
}

static sox_sample_t *exercise(uint32_t source,uint32_t native,size_t frames,
    size_t in_batch,size_t out_batch,size_t *total)
{
  lsx_pcmdsd *p=create(source,native,.5,test_bounds);
  lsx_pcmdsd_report r;
  uint64_t target=((uint64_t)frames*native+source/2)/source;
  sox_sample_t *out=calloc((size_t)target+2,sizeof(*out));
  double *in=calloc(frames+1,sizeof(*in));
  size_t used=0,made=0,iterations=0,i;
  CHECK(out && in);
  for (i=0;i<frames;i++) in[i]=.1*sin(6.283185307179586*997.*i/source);
  while (used<frames) {
    size_t n=min(in_batch,frames-used),m=min(out_batch,(size_t)target-made+1);
    sox_dsd_status_t rc=lsx_pcmdsd_process(p,in+used,&n,out+made,&m);
    CHECK(rc==SOX_DSD_NEED_INPUT || rc==SOX_DSD_NEED_OUTPUT);
    CHECK(n || m);
    used+=n;made+=m;
    CHECK(used<=frames && made<=target && ++iterations<target+frames+10000);
  }
  while (1) {
    size_t m=min(out_batch,(size_t)target-made+1);
    sox_dsd_status_t rc=lsx_pcmdsd_finish(p,out+made,&m);
    CHECK(rc==SOX_DSD_NEED_OUTPUT || rc==SOX_DSD_DONE);
    made+=m;
    CHECK(made<=target && ++iterations<target+frames+10000);
    if (rc==SOX_DSD_DONE) break;
    CHECK(m>0);
  }
  CHECK(made==target);
  {size_t m=3;CHECK(lsx_pcmdsd_finish(p,out,&m)==SOX_DSD_DONE && !m);}
  CHECK(lsx_pcmdsd_report_get(p,&r)==SOX_DSD_OK && r.input_frames==frames && r.committed_frames==target);
  lsx_pcmdsd_destroy(p);free(in);*total=made;return out;
}
static void stream_tests(void)
{
  size_t i,j,k;
  size_t sizes[]={0,1,2,7,8,9,31,32,33,255,256,257,4097};
  for (i=0;i<3;i++) for (j=0;j<9;j++) {
    size_t na,nb;
    sox_sample_t *a=exercise(sources[j],rates[i],97,97,4096,&na);
    sox_sample_t *b=exercise(sources[j],rates[i],97,7,13,&nb);
    CHECK(na==nb && !memcmp(a,b,na*sizeof(*a)));free(a);free(b);
  }
  for (k=0;k<array_length(sizes);k++) {
    size_t na,nb;
    sox_sample_t *a=exercise(48000,2822400,sizes[k],256,8192,&na);
    sox_sample_t *b=exercise(48000,2822400,sizes[k],1,17,&nb);
    CHECK(na==nb && !memcmp(a,b,na*sizeof(*a)));free(a);free(b);
  }
}

static void json_number(FILE *f,double x)
{if (isfinite(x))fprintf(f,"%.17g",x);else fputs("null",f);}
static int write_report(const char *path,lsx_pcmdsd *p,int rc,uint32_t source,
    uint32_t native,const char *profile,const char *mode,double cpu)
{
  lsx_pcmdsd_report r;
  size_t len=strlen(path)+5;
  char *temporary=malloc(len);
  FILE *f;unsigned i;int result;
  if (!temporary) return -1;
  snprintf(temporary,len,"%s.tmp",path);
  f=fopen(temporary,"w");
  if (!f) {free(temporary);return -1;}
  lsx_pcmdsd_report_get(p,&r);
  fprintf(f,"{\n\"schema\":\"P10/candidate-render/1\",\"qualification\":\"UNQUALIFIED\","
      "\"source_hz\":%u,\"native_hz\":%u,\"profile\":\"%s\",\"mode\":\"%s\","
      "\"status\":%d,\"failure\":%u,\"input_frames\":%" PRIu64
      ",\"committed_native_frames\":%" PRIu64 ",\"processed_native_frames\":%" PRIu64
      ",\"first_bad_frame\":",source,native,profile,mode,rc,(unsigned)r.failure,
      r.input_frames,r.committed_frames,r.monitor.frames);
  if (r.first_bad_frame==UINT64_MAX) fputs("null",f);else fprintf(f,"%" PRIu64,r.first_bad_frame);
  fprintf(f,",\"channel\":%u,\"coordinate\":%u,\"peak\":",r.channel,r.coordinate);json_number(f,r.peak);
  fputs(",\"failure_value\":",f);json_number(f,r.failure_value);
  fputs(",\"minimum_attenuation_db\":",f);json_number(f,r.minimum_attenuation_db);
  fprintf(f,",\"effective_pass_hz\":%.17g,\"cpu_seconds\":%.9g,"
      "\"windows28\":%" PRIu64 ",\"excursions28\":%" PRIu64
      ",\"min_ones28\":%u,\"max_ones28\":%u,\"longest_run\":%" PRIu64
      ",\"nonfinite_states\":%" PRIu64 ",\"monitor_overloads_nominal_half\":%" PRIu64
      ",\"max_abs_state\":[",r.effective_pass_hz,cpu,r.monitor.windows28,r.monitor.excursions28,
      r.monitor.min_ones28,r.monitor.max_ones28,r.monitor.longest_run,r.monitor.nonfinite,r.monitor.overloads);
  for (i=0;i<8;i++) {if(i)fputc(',',f);json_number(f,r.monitor.max_abs_state[i]);}
  fputs("]}\n",f);
  result=fclose(f);
  if (!result) result=rename(temporary,path);
  free(temporary);return result;
}

/* Packed chronological bits, MSB first. A partial failed block is never
 * written; the separate JSON preserves the failure and committed prefix. */
static int render(int argc,char **argv)
{
  uint32_t source=(uint32_t)strtoul(argv[2],NULL,10),native=(uint32_t)strtoul(argv[3],NULL,10);
  const char *id=argv[4],*mode=argv[6];
  double scale=strtod(argv[5],NULL);
  size_t in_batch=argc>10?(size_t)strtoul(argv[10],NULL,10):4096;
  size_t out_batch=argc>11?(size_t)strtoul(argv[11],NULL,10):8192;
  FILE *in=NULL,*out=NULL;
  double *input=NULL;
  sox_sample_t *output=NULL;
  lsx_pcmdsd *p=NULL;
  const lsx_pcmdsd_profile *profile=lsx_pcmdsd_profile_find(native);
  const sdm_profile_t *control=sdm_profile_find(id,native);
  const lsx_pcmdsd_profile *named=lsx_pcmdsd_profile_find_id(native,id);
  if (named) profile=named;
  unsigned byte=0,bits=0;int status=SOX_DSD_OK,io_error=0;
  clock_t start=clock();
  if (!profile || !control || !in_batch || !out_batch || in_batch>1048576 || out_batch>1048576) return 2;
  if (strcmp(mode,"training") && strcmp(mode,"guarded")) return 2;
  status=lsx_pcmdsd_candidate_create(source,native,scale,0,control,
      !strcmp(mode,"training")?NULL:profile->bounds,&p);
  if (status!=SOX_DSD_OK) {fprintf(stderr,"candidate create failed: %d\n",status);return 2;}
  in=!strcmp(argv[7],"-")?stdin:fopen(argv[7],"rb");out=fopen(argv[8],"wb");
  input=malloc(in_batch*sizeof(*input));output=malloc(out_batch*sizeof(*output));
  if (!in || !out || !input || !output) {io_error=1;goto done;}
  for (;;) {
    size_t got=0,used=0,i;
    unsigned char raw[8];
    while (got<in_batch) {
      uint64_t word=0;size_t n=fread(raw,1,8,in);unsigned k;
      if (!n) break;
      if (n!=8) {io_error=1;goto done;}
      for (k=0;k<8;k++) word|=(uint64_t)raw[k]<<(8*k);
      memcpy(input+got++,&word,8);
    }
    if (ferror(in)) {io_error=1;goto done;}
    do {
      size_t n=got-used,m=out_batch;
      status=got?lsx_pcmdsd_process(p,input+used,&n,output,&m):
          lsx_pcmdsd_finish(p,output,&m);
      if (status!=SOX_DSD_NEED_INPUT && status!=SOX_DSD_NEED_OUTPUT && status!=SOX_DSD_DONE) goto done;
      used+=n;
      for (i=0;i<m;i++) {
        byte=(byte<<1)|(output[i]>0);
        if (++bits==8) {
          if (fputc((int)byte&255,out)==EOF) {io_error=1;goto done;}
          bits=byte=0;
        }
      }
      if (status==SOX_DSD_DONE) goto done;
      if (!n && !m && got) {io_error=1;goto done;}
    } while (!got || used<got);
  }
done:
  if (out) {
    if (bits && fputc((int)(byte<<(8-bits))&255,out)==EOF) io_error=1;
    if (fclose(out)) io_error=1;
  }
  if (in && in!=stdin && fclose(in)) io_error=1;
  if (io_error) status=SOX_DSD_IO_ERROR;
  if (write_report(argv[9],p,status,source,native,id,mode,(double)(clock()-start)/CLOCKS_PER_SEC)) io_error=1;
  lsx_pcmdsd_destroy(p);free(input);free(output);
  return !io_error && status==SOX_DSD_DONE?0:1;
}

/* Full-composite soak: one encoder instance for the entire sequence. Saved
 * states verify deterministic replay after an interruption. No segment resets
 * the recurrence, FIR, SRC, run-length history, or 28-bit windows. */
static double soak_source_version(uint64_t frame,uint32_t hz,int nominal_v2)
{
  uint64_t minute=frame/((uint64_t)hz*60),local=frame%((uint64_t)hz*60);
  uint64_t word=frame+UINT64_C(0x9e3779b97f4a7c15);
  double t=(double)frame/hz,x=0.,ramp=1.;
  word=(word^(word>>30))*UINT64_C(0xbf58476d1ce4e5b9);
  word=(word^(word>>27))*UINT64_C(0x94d049bb133111eb);word^=word>>31;
  switch (minute%6) {
    case 0: x=0.;break;
    case 1: x=.7;break;
    case 2: x=-.7;break;
    case 3: x=.15*(sin(6.283185307179586*53*t)+sin(6.283185307179586*997*t)+
        sin(6.283185307179586*5501*t)+sin(6.283185307179586*17011*t));break;
    case 4: x=(nominal_v2?.45:.7)*((double)(word>>11)*0x1p-52-1.);break;
    default:x=.8*sin(6.283185307179586*1000*t);break;
  }
  if (local<hz/10) ramp=(double)local/(hz/10);
  else if ((uint64_t)hz*60-local<=hz/10)
    ramp=(double)((uint64_t)hz*60-local-1)/(hz/10);
  ramp=ramp*ramp*ramp*(10+ramp*(-15+6*ramp));
  return nearbyint(x*ramp*SOX_SAMPLE_MAX)/SOX_SAMPLE_MAX;
}
/* Original v1 is unchanged in content, to preserve first-failure replay. */
static int save_soak_state(const char *path,lsx_pcmdsd *p,uint64_t bits_hash)
{
  sdm_normal_t s;lsx_pcmdsd_report r;
  size_t len=strlen(path)+8;char *tmp=malloc(len);FILE *f,*old;unsigned i,j;
  int rc=0,a,b;
  if (!tmp) return -1;
  snprintf(tmp,len,"%s.tmp",path);f=fopen(tmp,"w");
  if (!f) {free(tmp);return -1;}
  lsx_pcmdsd_state_get(p,&s);lsx_pcmdsd_report_get(p,&r);
  fprintf(f,"P10-continuation-v1\ninput=%" PRIu64 "\nnative=%" PRIu64
      "\nbits_fnv64=%016" PRIx64 "\nbank=%u\nprevious=%a\n",
      r.input_frames,s.frames,bits_hash,s.bank,s.previous_decision);
  for(i=0;i<2;i++)for(j=0;j<8;j++)fprintf(f,"state%u_%u=%a\n",i,j,s.state[i][j]);
  fprintf(f,"history=%u\nones=%u\nhistory_bits=%u\nrun=%u\nlast=%u\n"
      "windows=%" PRIu64 "\nexcursions=%" PRIu64 "\nlongest=%" PRIu64
      "\npeak=%a\n",r.monitor.history28,r.monitor.ones28,r.monitor.history_bits,
      r.monitor.run_length,r.monitor.last_bit,r.monitor.windows28,r.monitor.excursions28,
      r.monitor.longest_run,r.peak);
  for(j=0;j<8;j++)fprintf(f,"maximum%u=%a\n",j,r.monitor.max_abs_state[j]);
  if (fclose(f)) {remove(tmp);free(tmp);return -1;}
  old=fopen(path,"r");
  if (old) {
    f=fopen(tmp,"r");if (!f) {fclose(old);free(tmp);return -1;}
    do {a=fgetc(old);b=fgetc(f);if(a!=b){rc=-1;break;}}while(a!=EOF);
    if(ferror(old)||ferror(f))rc=-1;
    fclose(f);fclose(old);
    if (!rc) remove(tmp); /* The previously committed snapshot stays untouched. */
    else fprintf(stderr,"soak replay state mismatch; candidate state retained in %s\n",tmp);
  } else if(rename(tmp,path)) rc=-1;
  free(tmp);return rc;
}
static int soak(int argc,char **argv)
{
  int corrected=!strcmp(argv[1],"--soak-dsd1024-v2") ||
      !strcmp(argv[1],"--soak-nominal-dsd1024-v2");
  int nominal_v2=!strcmp(argv[1],"--soak-nominal-v2") ||
      !strcmp(argv[1],"--soak-nominal-dsd1024-v2");
  uint32_t native=(uint32_t)strtoul(argv[2],NULL,10);
  uint64_t seconds=strtoull(argv[3],NULL,10),segment=strtoull(argv[4],NULL,10);
  const lsx_pcmdsd_profile *profile=corrected?
      lsx_pcmdsd_profile_find_id(native,"encode.mastering.v2.dsd1024"):
      lsx_pcmdsd_profile_find(native);
  const char *prefix=argv[5];
  double input[4096];sox_sample_t output[8192];lsx_pcmdsd *p=NULL;
  uint64_t accepted=0,target,next,sequence=0,hash=UINT64_C(14695981039346656037);
  size_t pathlen=strlen(prefix)+80;char *path=malloc(pathlen);
  int status=SOX_DSD_OK,rc=1;clock_t start=clock();
  (void)argc;
  if(!path||!profile||!seconds||!segment||segment>seconds||seconds>86400)goto done;
  target=seconds*profile->working_hz;next=segment*profile->working_hz;
  status=lsx_pcmdsd_candidate_create(profile->working_hz,native,.5,0,
      corrected?sdm_profile_find(profile->id,native):NULL,profile->bounds,&p);
  if(status!=SOX_DSD_OK)goto done;
  while(accepted<target) {
    size_t i,available=(size_t)min((uint64_t)array_length(input),target-accepted),used=0;
    uint64_t base=accepted;
    for(i=0;i<available;i++)input[i]=soak_source_version(base+i,profile->working_hz,nominal_v2);
    while(used<available) {
      size_t n=available-used,m=array_length(output);
      status=lsx_pcmdsd_process(p,input+used,&n,output,&m);
      if(status!=SOX_DSD_NEED_INPUT&&status!=SOX_DSD_NEED_OUTPUT)goto report;
      if(!n&&!m) {status=SOX_DSD_NUMERIC_ERROR;goto report;}
      used+=n;accepted+=n;
      for(i=0;i<m;i++){hash^=output[i]>0;hash*=UINT64_C(1099511628211);}
    }
    if(accepted>=next) {
      snprintf(path,pathlen,"%s-%04" PRIu64 ".state",prefix,++sequence);
      if(save_soak_state(path,p,hash))goto report;
      snprintf(path,pathlen,"%s-progress.json",prefix);
      if(write_report(path,p,status,profile->working_hz,native,profile->id,"soak-progress",
          (double)(clock()-start)/CLOCKS_PER_SEC))goto done;
      fprintf(stdout,"soak %u accepted=%" PRIu64 " segment=%" PRIu64 "\n",native,accepted,sequence);fflush(stdout);
      next+=segment*profile->working_hz;
    }
  }
  do {
    size_t i,m=array_length(output);status=lsx_pcmdsd_finish(p,output,&m);
    if(status!=SOX_DSD_NEED_OUTPUT&&status!=SOX_DSD_DONE)goto report;
    for(i=0;i<m;i++){hash^=output[i]>0;hash*=UINT64_C(1099511628211);}
  }while(status!=SOX_DSD_DONE);
  snprintf(path,pathlen,"%s-final.state",prefix);
  if(save_soak_state(path,p,hash))goto report;
  rc=0;
report:
  if (status!=SOX_DSD_DONE) {
    snprintf(path,pathlen,"%s-failure.state",prefix);
    if(save_soak_state(path,p,hash))rc=1;
  }
  snprintf(path,pathlen,"%s-result.json",prefix);
  if(write_report(path,p,status,profile->working_hz,native,profile->id,
      nominal_v2?"soak-nominal-v2":"soak",
      (double)(clock()-start)/CLOCKS_PER_SEC))rc=1;
done:
  lsx_pcmdsd_destroy(p);free(path);return rc;
}

/* Read-only instrumentation of the production composite at each handoff.
 * This deliberately does NOT bypass the modulator's fatal overload policy.
 * A rejected source yields prefix-only statistics and a nonzero exit code. */
typedef struct {
  uint64_t count, steady_count, over_half, over_envelope;
  long double sum, squares, steady_sum, steady_squares;
  double peak, steady_peak;
  uint64_t bins[101];
} p10_audit_stage;
typedef struct {
  p10_audit_stage stages[LSX_PCMDSD_STAGE_COUNT];
  uint32_t source_hz,native_hz,working_hz;
  double warmup_seconds,steady_stop_seconds;
} p10_audit;
static const char *audit_names[LSX_PCMDSD_STAGE_COUNT]={
  "source", "R_SRC", "R_prefilter", "native_SRC", "scaled_modulator_input"};
static void audit_observer(void *opaque,lsx_pcmdsd_stage stage,
    const double *samples,size_t n)
{
  p10_audit *a=opaque;
  p10_audit_stage *s=&a->stages[stage];
  uint32_t hz=stage==LSX_PCMDSD_STAGE_SOURCE?a->source_hz:
      stage==LSX_PCMDSD_STAGE_R||stage==LSX_PCMDSD_STAGE_PREFILTER?
      a->working_hz:a->native_hz;
  uint64_t start=(uint64_t)(a->warmup_seconds*hz);
  size_t i;
  for (i=0;i<n;i++) {
    double v=samples[i],abs_v=fabs(v);
    int bin=(int)fmin(abs_v*100.,100.);
    if (abs_v>s->peak)s->peak=abs_v;
    s->sum+=(long double)v;s->squares+=(long double)v*v;
    ++s->bins[bin];
    if(abs_v>.5)++s->over_half;
    if(abs_v>.5+2./SOX_SAMPLE_MAX)++s->over_envelope;
    if(s->count>=start && s->count<(uint64_t)(a->steady_stop_seconds*hz)) {
      s->steady_sum+=(long double)v;
      s->steady_squares+=(long double)v*v;
      if(abs_v>s->steady_peak)s->steady_peak=abs_v;
      ++s->steady_count;
    }
    ++s->count;
  }
}
static void audit_dump(const p10_audit *a,const char *name,
    const lsx_pcmdsd_report *report,int status)
{
  unsigned i,j;
  printf("{\"schema\":\"P10/stage-observation/1\",\"kind\":\"%s\","
      "\"source_hz\":%u,\"working_hz\":%u,\"native_hz\":%u,"
      "\"status\":%d,\"failure\":%u,\"first_bad_frame\":",
      name,a->source_hz,a->working_hz,a->native_hz,status,report->failure);
  if(report->first_bad_frame==UINT64_MAX)printf("null");
  else printf("%" PRIu64,report->first_bad_frame);
  printf(",\"peak_report\":%.17g,\"stages\":{",report->peak);
  for(i=0;i<LSX_PCMDSD_STAGE_COUNT;i++) {
    const p10_audit_stage *s=&a->stages[i];
    long double mean=s->count?s->sum/s->count:0;
    long double rms=s->count?sqrtl(s->squares/s->count):0;
    long double steady_mean=s->steady_count?s->steady_sum/s->steady_count:0;
    long double steady_rms=s->steady_count?sqrtl(s->steady_squares/s->steady_count):0;
    printf("%s\"%s\":{\"count\":%" PRIu64 ",\"peak\":%.17g,"
        "\"rms\":%.17g,\"mean\":%.17g,\"steady_count\":%" PRIu64
        ",\"steady_peak\":%.17g,\"steady_rms\":%.17g,\"steady_mean\":%.17g,"
        "\"over_half\":%" PRIu64 ",\"over_envelope\":%" PRIu64 ",\"abs_bins_0p01\":[",
        i?",":"",audit_names[i],s->count,s->peak,(double)rms,(double)mean,
        s->steady_count,s->steady_peak,(double)steady_rms,(double)steady_mean,
        s->over_half,s->over_envelope);
    for(j=0;j<101;j++)printf("%s%" PRIu64,j?",":"",s->bins[j]);
    printf("]}");
  }
  printf("}}\n");
}
static int stage_probe(int argc,char **argv)
{
  uint32_t native=(uint32_t)strtoul(argv[2],NULL,10),source=(uint32_t)strtoul(argv[3],NULL,10);
  const char *kind=argv[4];
  double seconds=strtod(argv[5],NULL);
  const lsx_pcmdsd_profile *profile=lsx_pcmdsd_profile_find(native);
  lsx_pcmdsd *p=NULL;lsx_pcmdsd_report r;
  p10_audit a={0};
  double input[4096];sox_sample_t output[8192];
  uint64_t count,accepted=0;int rc=SOX_DSD_NEED_INPUT;
  if(argc!=6||!profile||!source||!isfinite(seconds)||seconds<=0||seconds>90||
      (strcmp(kind,"dc")&&strcmp(kind,"original-noise")&&
       strcmp(kind,"nominal-noise")&&strcmp(kind,"attenuated-original-noise")))return 2;
  if(strcmp(kind,"dc") && source!=profile->working_hz)return 2;
  count=(uint64_t)nearbyint(seconds*source);
  a.source_hz=source;a.native_hz=native;a.working_hz=profile->working_hz;
  a.warmup_seconds=.2;a.steady_stop_seconds=!strcmp(kind,"dc")?1.:seconds;
  if(lsx_pcmdsd_candidate_create(source,native,.5,0,NULL,profile->bounds,&p)!=SOX_DSD_OK)return 2;
  lsx_pcmdsd_observe(p,audit_observer,&a);
  while(accepted<count) {
    size_t i,used=0,available=(size_t)min((uint64_t)array_length(input),count-accepted);
    for(i=0;i<available;i++) {
      uint64_t frame=accepted+i+UINT64_C(240)*source;
      double val=!strcmp(kind,"dc")?.6:
          soak_source_version(frame,source,!strcmp(kind,"nominal-noise"));
      if(!strcmp(kind,"attenuated-original-noise"))
        val=nearbyint((val*(.45/.7))*SOX_SAMPLE_MAX)/SOX_SAMPLE_MAX;
      input[i]=!strcmp(kind,"dc")?nearbyint(val*SOX_SAMPLE_MAX)/SOX_SAMPLE_MAX:val;
    }
    while(used<available) {
      size_t n=available-used,m=array_length(output);
      rc=lsx_pcmdsd_process(p,input+used,&n,output,&m);
      if(rc!=SOX_DSD_NEED_INPUT&&rc!=SOX_DSD_NEED_OUTPUT)goto completed;
      if(!n&&!m) {rc=SOX_DSD_NUMERIC_ERROR;goto completed;}
      used+=n;accepted+=n;
    }
  }
  do {
    size_t m=array_length(output);
    rc=lsx_pcmdsd_finish(p,output,&m);
    if(rc!=SOX_DSD_NEED_OUTPUT&&rc!=SOX_DSD_DONE)break;
  }while(rc!=SOX_DSD_DONE);
completed:
  lsx_pcmdsd_report_get(p,&r);
  audit_dump(&a,kind,&r,rc);
  lsx_pcmdsd_destroy(p);
  return rc==SOX_DSD_DONE?0:rc==SOX_DSD_NUMERIC_ERROR&&r.failure==LSX_PCMDSD_INTERPOLATION_OVERLOAD?4:1;
}

/* The same LUT and scalar coefficients as the inherited P09 kernel probe.
 * Guard mode retains the monitor; its cost is not omitted from P10 timing. */
static int state_bench(unsigned native,unsigned long samples,const char *mode)
{
  const lsx_pcmdsd_profile *profile=lsx_pcmdsd_profile_find(native);
  sdm_normal_t state;sdm_normal_monitor_t monitor;
  double input[1024];unsigned long i;uint64_t ones=0,hash=UINT64_C(14695981039346656037);
  clock_t begin;int monitored=strcmp(mode,"none")!=0,guarded=!strcmp(mode,"guard");
  if(!profile||!samples||samples>50000000UL||
      (strcmp(mode,"none")&&strcmp(mode,"monitor")&&strcmp(mode,"guard")))return 2;
  if(sdm_normal_init(&state,sdm_profile_find(profile->id,native)))return 2;
  sdm_normal_monitor_init(&monitor);
  if(monitored)sdm_normal_attach_monitor(&state,&monitor);
  for(i=0;i<1024;i++)input[i]=.18*sin((6.283185307179586*7/1024)*i);
  begin=clock();
  for(i=0;i<samples;i++) {
    int bit;unsigned coordinate;
    int rc=guarded?sdm_normal_step_guarded(&state,input[i&1023],&bit,profile->bounds,&coordinate):
        sdm_normal_step(&state,input[i&1023],&bit);
    if(rc)return 1;
    ones+=bit>0;hash^=bit>0;hash*=UINT64_C(1099511628211);
  }
  printf("{\"native_hz\":%u,\"samples\":%lu,\"mode\":\"%s\","
      "\"ones\":%" PRIu64 ",\"bits_fnv64\":\"%016" PRIx64 "\","
      "\"cpu_seconds\":%.9f,\"state_bytes\":%zu,\"monitor_bytes\":%zu}\n",
      native,samples,mode,ones,hash,(double)(clock()-begin)/CLOCKS_PER_SEC,
      sizeof(state),sizeof(monitor));
  return 0;
}

int main(int argc,char **argv)
{
  int rc=2;
  if (sox_init()!=SOX_SUCCESS) return 2;
  if (argc==2 && !strcmp(argv[1],"--unit")) {
    envelope();failed_block_commit();stream_tests();printf("{\"assertions\":%lu,\"failures\":0}\n",checks);rc=0;
  } else if (argc>=10 && argc<=12 && !strcmp(argv[1],"--render")) rc=render(argc,argv);
  else if (argc==6 && (!strcmp(argv[1],"--soak") ||
      !strcmp(argv[1],"--soak-nominal-v2") ||
      !strcmp(argv[1],"--soak-dsd1024-v2") ||
      !strcmp(argv[1],"--soak-nominal-dsd1024-v2"))) rc=soak(argc,argv);
  else if (argc==6 && !strcmp(argv[1],"--stage-probe")) rc=stage_probe(argc,argv);
  else if (argc==5 && !strcmp(argv[1],"--state-bench"))
    rc=state_bench((unsigned)strtoul(argv[2],NULL,10),strtoul(argv[3],NULL,10),argv[4]);
  else fprintf(stderr,"usage: %s --unit | --render sourceHz nativeHz profile scale training|guarded input.f64le bits report.json [inputBatch outputBatch] | --soak[-nominal-v2] nativeHz seconds segmentSeconds prefix\n",argv[0]);
  sox_quit();return rc;
}
