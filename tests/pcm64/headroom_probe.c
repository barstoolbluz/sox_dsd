/* Phase 07 independent scan/replay trace oracle. It uses the same private
 * production PCM64 coordinator and certified modulator, but independently
 * observes the pre-gain/native and post-scale tap on every channel.
 * Trace storage is test-only and bounded to short fixture lengths. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "dsd_f64.h"
#include "sox_i.h"
#include "pcmdsd.h"
#include <errno.h>
#include <inttypes.h>
#include <float.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define CH_MAX 8u
#define IN LSX_DSD_F64_ENCODE_INPUT
#define OUT LSX_DSD_F64_ENCODE_OUTPUT

typedef struct {
  FILE *native;
  uint64_t count;
  double peak;
  int failed;
} trace;
static void observe(void *opaque,lsx_pcmdsd_stage stage,
    const double *v,size_t n)
{
  trace *t=opaque;
  size_t j;
  if (stage==LSX_PCMDSD_STAGE_NATIVE) {
    if (n>UINT64_MAX-t->count || fwrite(v,sizeof(double),n,t->native)!=n)
      t->failed=1;
    else t->count+=n;
  } else if(stage==LSX_PCMDSD_STAGE_SCALED) {
    for(j=0;j<n;j++) {
      double a=fabs(v[j]);
      if(!isfinite(v[j])) t->failed=1;
      if(a>t->peak)t->peak=a;
    }
  }
}
static int parse(const char *s,uint32_t *v)
{
  char *tail;unsigned long n;
  errno=0;n=strtoul(s,&tail,10);
  if(!s[0] || *tail || errno || n>UINT32_MAX)return 0;
  *v=(uint32_t)n;return 1;
}
static double from_bits(uint64_t bits)
{
  double result;
  memcpy(&result,&bits,sizeof(result));
  return result;
}
static double input_word(uint32_t frame,unsigned ch,uint32_t total,int pattern)
{
  /* Include below-int32 values, exact -0 and subnormal signed values. */
  static const uint64_t words[]={
    UINT64_C(0),UINT64_C(0x8000000000000000),
    UINT64_C(1),UINT64_C(0x8000000000000001),
    UINT64_C(0x3d70000000000000),UINT64_C(0xbd70000000000000),
    UINT64_C(0x3fe5555555555555),UINT64_C(0xbfe2492492492492)};
  double v;
  if (pattern==1) return 0.;
  if (pattern==2 && total && frame==total-1)return ch?-.99:.99;
  if (pattern==2)return frame%7==0?0.:from_bits(words[(frame+ch)%8])*1e-5;
  if (pattern==3)return frame==0?(ch?-.91:.91):0.;
  v=from_bits(words[(frame*7+ch*5)%8]);
  if ((frame%11)==0)v=sin((double)(frame+1)*(ch+1)*.174)*.29;
  return v;
}
static int run_encoder(lsx_dsd_f64_encoder *enc,const double *words,
    uint32_t frames,unsigned ch,unsigned in_step,unsigned out_step,
    uint64_t *done_frames,trace *watched,double *before_finish_peak)
{
  sox_sample_t bits[OUT*CH_MAX];
  uint32_t cursor=0;
  uint64_t total=0;
  while(cursor<frames) {
    size_t left=frames-cursor;
    if (left>in_step)left=in_step;
    while(left) {
      size_t accepted=left,produced=out_step;
      sox_dsd_status_t st=lsx_dsd_f64_encode_process(enc,
          words+(size_t)cursor*ch,&accepted,bits,&produced);
      if(st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT) {
        fprintf(stderr,"process status=%d at frame=%u\n",(int)st,cursor);
        return 0;
      }
      if(!accepted && !produced)return 0;
      if(produced>UINT64_MAX-total)return 0;
      total+=produced;
      cursor+=(uint32_t)accepted;
      left-=accepted;
    }
  }
  if (watched && before_finish_peak) {
    unsigned c;
    *before_finish_peak=0.;
    for (c=0;c<ch;c++) if (watched[c].peak>*before_finish_peak)
      *before_finish_peak=watched[c].peak;
  }
  for (;;) {
    size_t produced=out_step;
    sox_dsd_status_t st=lsx_dsd_f64_encode_finish(enc,bits,&produced);
    if(st!=SOX_DSD_DONE && st!=SOX_DSD_NEED_OUTPUT) {
      fprintf(stderr,"finish status=%d\n",(int)st);return 0;
    }
    if(produced>UINT64_MAX-total)return 0;
    total+=produced;
    if(st==SOX_DSD_DONE)break;
    if(!produced)return 0;
  }
  *done_frames=total;
  return 1;
}
static int failures(void)
{
  lsx_dsd_f64_spool s={0};
  double words[]={-0.,DBL_TRUE_MIN,.125,0.};
  double out[8]={0};
  pcm_f64_progress p;
  FILE *full;
  int good=1;
  if(lsx_dsd_f64_spool_open(&s,48000,2)!=PCM_F64_OK)return 0;
  good &= lsx_dsd_f64_spool_append(&s,words,2)==PCM_F64_OK;
  good &= lsx_dsd_f64_spool_rewind(&s)==PCM_F64_OK;
  good &= lsx_dsd_f64_spool_append(&s,words,1)==PCM_F64_STATE;
  good &= lsx_dsd_f64_spool_read(&s,out,2).status==PCM_F64_STATE;
  good &= lsx_dsd_f64_spool_close(&s)==PCM_F64_STATE;
  good &= lsx_dsd_f64_spool_close(&s)==PCM_F64_OK;
  if(lsx_dsd_f64_spool_open(&s,48000,2)!=PCM_F64_OK)return 0;
  good &= lsx_dsd_f64_spool_append(&s,words,2)==PCM_F64_OK;
  good &= lsx_dsd_f64_spool_rewind(&s)==PCM_F64_OK;
  good &= ftruncate(fileno(s.file),0)==0;
  p=lsx_dsd_f64_spool_read(&s,out,2);
  good &= p.status==PCM_F64_IO && p.produced_frames==0;
  p=lsx_dsd_f64_spool_read(&s,out,2);
  good &= p.status==PCM_F64_IO;
  good &= lsx_dsd_f64_spool_close(&s)==PCM_F64_IO;
  if(lsx_dsd_f64_spool_open(&s,48000,2)!=PCM_F64_OK)return 0;
  good &= lsx_dsd_f64_spool_append(&s,words,2)==PCM_F64_OK;
  good &= lsx_dsd_f64_spool_rewind(&s)==PCM_F64_OK;
  p=lsx_dsd_f64_spool_read(&s,out,2);
  good &= p.status==PCM_F64_DONE && p.produced_frames==2;
  good &= memcmp(words,out,sizeof(words))==0;
  good &= lsx_dsd_f64_spool_close(&s)==PCM_F64_OK;
#ifdef __linux__
  if(lsx_dsd_f64_spool_open(&s,48000,2)!=PCM_F64_OK)return 0;
  /* Substitute a failing descriptor only in the test object, not globally. */
  good &= lsx_close_tmpfile_checked(s.file)==0;
  s.file=NULL;
  full=fopen("/dev/full","wb");
  if(full) {
    s.file=full;
    (void)setvbuf(s.file,NULL,_IONBF,0);
    good &= lsx_dsd_f64_spool_append(&s,words,2)==PCM_F64_IO;
    good &= lsx_dsd_f64_spool_append(&s,words,2)==PCM_F64_IO;
    good &= lsx_dsd_f64_spool_rewind(&s)==PCM_F64_IO;
    good &= lsx_dsd_f64_spool_close(&s)==PCM_F64_IO;
  }
  else s.file=NULL;
#endif
  puts(good?"{\"status\":\"PASS\",\"fault_cases\":10}":
            "{\"status\":\"FAIL\",\"fault_cases\":10}");
  return good;
}
static int normal(int argc,char **argv)
{
  uint32_t source=0,native=0,channels=0,frames=0,scan_step=0,replay_step=0,
      reference_int=0,pattern=0;
  int ok=0,spool_mismatch=0;
  uint32_t mutation=0;
  size_t scalar_size,i;
  double *words=NULL,*replayed=NULL,gain=0,peak=0,max_observed=0,
      predrain_peak=0;
  lsx_dsd_f64_encoder scan={0},replay={0};
  lsx_dsd_f64_spool spool={0};
  trace a[CH_MAX]={{0}},b[CH_MAX]={{0}};
  uint64_t scan_count=0,replay_count=0,expected=0,trace_count=0;
  FILE *source_capture=NULL,*spool_capture=NULL;
  unsigned ch;
  if ((argc!=11 && argc!=13) || !parse(argv[1],&source) || !parse(argv[2],&native) ||
      !parse(argv[3],&channels) || !parse(argv[4],&frames) ||
      !parse(argv[5],&scan_step) || !parse(argv[6],&replay_step) ||
      !parse(argv[7],&reference_int) || !parse(argv[8],&pattern) ||
      !parse(argv[9],&mutation) || strcmp(argv[10],"run") ||
      channels==0 || channels>CH_MAX || scan_step==0 || scan_step>IN ||
      replay_step==0 || replay_step>IN || reference_int>1 || pattern>3 ||
      mutation>2 || frames>9000 || frames>SIZE_MAX/channels/sizeof(double)) {
    fputs("headroom_probe: bad arguments\n",stderr);return 2;
  }
  scalar_size=(size_t)frames*channels;
  words=calloc(scalar_size?scalar_size:1,sizeof(double));
  replayed=malloc((scalar_size?scalar_size:1)*sizeof(double));
  if(!words || !replayed)goto done;
  for(i=0;i<scalar_size;i++)
    words[i]=input_word((uint32_t)(i/channels),(unsigned)(i%channels),frames,(int)pattern);
  /* Optional, bounded test-only captures. Keep the exact in-memory double
   * representations, including signed zero and subnormals. */
  if(argc==13) {
    source_capture=fopen(argv[11],"wb");
    spool_capture=fopen(argv[12],"wb");
    if(!source_capture || !spool_capture)goto done;
  }
  if(lsx_dsd_f64_spool_open(&spool,source,channels)!=PCM_F64_OK)goto done;
  if(lsx_dsd_f64_encode_init(&scan,source,native,channels,
        reference_int?1.:.5,1.,false)!=SOX_DSD_OK ||
      lsx_dsd_f64_encode_scan_begin(&scan)!=SOX_DSD_OK)goto done;
  for(ch=0;ch<channels;ch++) {
    a[ch].native=tmpfile();b[ch].native=tmpfile();
    if (!a[ch].native || !b[ch].native)goto done;
    lsx_pcmdsd_observe(scan.channel[ch],observe,a+ch);
  }
  /* Spool exact words in chunks unrelated to composite process chunk sizes. */
  for(i=0;i<frames;) {
    size_t amount=frames-i;
    if(amount>scan_step)amount=scan_step;
    if(source_capture && fwrite(words+i*channels,sizeof(double),amount*channels,
          source_capture)!=amount*channels)goto done;
    if(lsx_dsd_f64_spool_append(&spool,words+i*channels,amount)!=PCM_F64_OK)goto done;
    i+=amount;
  }
  if(source_capture) {
    FILE *f=source_capture;
    source_capture=NULL;
    if(fclose(f))goto done;
  }
  if(!run_encoder(&scan,words,frames,channels,scan_step,17,&scan_count,
         a,&predrain_peak) ||
      lsx_dsd_f64_encode_scan_peak(&scan,&peak)!=SOX_DSD_OK ||
      lsx_dsd_f64_headroom_gain(peak,native,&gain)!=SOX_DSD_OK ||
      lsx_dsd_f64_spool_rewind(&spool)!=PCM_F64_OK)goto done;
  for(ch=0;ch<channels;ch++) {
    if(a[ch].failed || a[ch].count!=scan_count)goto done;
    if(a[ch].peak>max_observed)max_observed=a[ch].peak;
  }
  if (memcmp(&peak,&max_observed,sizeof(double))) {
    fprintf(stderr,"scan peak %.17g != native tap peak %.17g\n",peak,max_observed);
    goto done;
  }
  if(mutation==1) { /* Deliberate int32-quantizing spool mutant. */
    (void)lsx_dsd_f64_spool_close(&spool);
    if(lsx_dsd_f64_spool_open(&spool,source,channels)!=PCM_F64_OK)goto done;
    for(i=0;i<scalar_size;i++)replayed[i]=nearbyint(words[i]*2147483648.)/2147483648.;
    if(lsx_dsd_f64_spool_append(&spool,replayed,frames)!=PCM_F64_OK ||
       lsx_dsd_f64_spool_rewind(&spool)!=PCM_F64_OK)goto done;
  }
  if(mutation==2) { /* Deliberately exclude all native samples in EOF drain. */
    if(lsx_dsd_f64_headroom_gain(predrain_peak,native,&gain)!=SOX_DSD_OK)
      goto done;
  }
  if(lsx_dsd_f64_encode_init(&replay,source,native,channels,
        reference_int?1.:.5,gain,true)!=SOX_DSD_OK)goto done;
  for(ch=0;ch<channels;ch++)lsx_pcmdsd_observe(replay.channel[ch],observe,b+ch);
  /* The replay input must match the captured source, bit for bit. */
  for(i=0;i<frames;) {
    pcm_f64_progress p=lsx_dsd_f64_spool_read(&spool,
        replayed+i*channels,replay_step);
    if(pcm_f64_is_failure(p.status) || p.produced_frames>replay_step ||
       p.produced_frames>frames-i ||
       (!p.produced_frames && p.status!=PCM_F64_DONE))goto done;
    if(p.produced_frames) {
      size_t n=p.produced_frames*channels;
      /* These bytes are from the real spool read, never from expected words. */
      if(spool_capture && fwrite(replayed+i*channels,sizeof(double),n,
            spool_capture)!=n)goto done;
      if(memcmp(words+i*channels,replayed+i*channels,n*sizeof(double))) {
        if(mutation==1)spool_mismatch=1; /* Finish capture before rejecting. */
        else {fputs("source/spool bit mismatch\n",stderr);goto done;}
      }
    }
    i+=p.produced_frames;
    if(p.status==PCM_F64_DONE)break;
  }
  if(spool_capture) {
    FILE *f=spool_capture;
    spool_capture=NULL;
    if(fclose(f))goto done;
  }
  if(spool_mismatch) {
    fputs("mutation detected: int32 spool changed binary64 words\n",stderr);
    goto done;
  }
  if(i!=frames || !run_encoder(&replay,replayed,frames,channels,replay_step,511,
       &replay_count,NULL,NULL) || scan_count!=replay_count ||
       !lsx_dsd_count_convert(frames,source,native,&expected) ||
       expected!=scan_count)goto done;
  for(ch=0;ch<channels;ch++) {
    double av[137],bv[137];size_t n,m;
    if(b[ch].failed || b[ch].count!=a[ch].count ||
       fflush(a[ch].native) || fflush(b[ch].native) ||
       fseek(a[ch].native,0,SEEK_SET) || fseek(b[ch].native,0,SEEK_SET))goto done;
    while((n=fread(av,sizeof(double),137,a[ch].native))!=0) {
      m=fread(bv,sizeof(double),n,b[ch].native);
      if(m!=n || memcmp(av,bv,n*sizeof(double)))goto done;
      trace_count+=n;
    }
    if(ferror(a[ch].native) || ferror(b[ch].native) ||
       fread(bv,sizeof(double),1,b[ch].native)!=0)goto done;
  }
  if(mutation==2) { /* The actual tail MUST change the policy decision. */
    double true_gain=0;
    if(lsx_dsd_f64_headroom_gain(peak,native,&true_gain)!=SOX_DSD_OK)
      goto done;
    if(gain!=true_gain && predrain_peak<peak &&
        max_observed*gain>lsx_pcmdsd_warn_clip_ceiling(native)) {
      fprintf(stderr,"mutation detected: omitted EOF tail peak %.17g < %.17g, "
          "wrong gain %.17g vs %.17g\n",predrain_peak,peak,gain,true_gain);
      goto done;
    }
    fputs("tail omission mutant escaped acceptance fixture\n",stderr);
    goto done;
  }
  if(max_observed*gain > lsx_pcmdsd_warn_clip_ceiling(native)*(1+2e-12)) {
    fprintf(stderr,"gain did not admit scan peak: %.17g %.17g\n",max_observed,gain);
    goto done;
  }
  if(peak<=lsx_pcmdsd_warn_clip_ceiling(native) && gain!=1.)goto done;
  if(peak>lsx_pcmdsd_warn_clip_ceiling(native) &&
      gain!=lsx_pcmdsd_warn_clip_ceiling(native)*(1.-1e-12)/peak)goto done;
  if(lsx_dsd_f64_spool_close(&spool)!=PCM_F64_OK)goto done;
  ok=1;
  printf("{\"status\":\"PASS\",\"source_hz\":%u,\"native_hz\":%u,"
         "\"channels\":%u,\"source_frames\":%u,\"native_frames\":%" PRIu64 ","
         "\"trace_words\":%" PRIu64 ",\"peak\":%.17g,\"gain\":%.17g,"
         "\"reference\":%.1f,\"mutation\":%d}\n",
         source,native,channels,frames,scan_count,trace_count,peak,gain,
         reference_int?1.:.5,mutation);
done:
  if(!ok)fprintf(stderr,"headroom_probe: FAILURE source=%u native=%u channels=%u "
      "frames=%u pattern=%u mutant=%d\n",source,native,channels,frames,pattern,mutation);
  if(source_capture)fclose(source_capture);
  if(spool_capture)fclose(spool_capture);
  (void)lsx_dsd_f64_spool_close(&spool);
  lsx_dsd_f64_encode_destroy(&scan);
  lsx_dsd_f64_encode_destroy(&replay);
  for(ch=0;ch<CH_MAX;ch++){
    if(a[ch].native)fclose(a[ch].native);
    if(b[ch].native)fclose(b[ch].native);
  }
  free(words);free(replayed);
  return ok?0:1;
}
int main(int argc,char **argv)
{
  int rc;
  if(sox_init()!=SOX_SUCCESS)return 3;
  rc=argc==2 && !strcmp(argv[1],"--faults")?!failures():
     normal(argc,argv);
  sox_quit();return rc;
}
