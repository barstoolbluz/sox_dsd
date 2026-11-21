/* Phase 08, test-only physical source-SRC -> centered-FIR stage witness.
 * Uses the existing read-only per-stage observer on the actual composite.
 * No production header, DSP, or callback behavior is modified. */
#include "sox_i.h"
#include "pcmdsd.h"
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  FILE *working, *filtered, *native, *scaled;
  uint64_t working_count, filtered_count, native_count, scaled_count;
  int failed;
} observation;

static void capture(void *opaque,lsx_pcmdsd_stage stage,const double *words,size_t n)
{
  observation *o=opaque;
  FILE *fp=stage==LSX_PCMDSD_STAGE_R?o->working:
      stage==LSX_PCMDSD_STAGE_PREFILTER?o->filtered:
      stage==LSX_PCMDSD_STAGE_NATIVE?o->native:
      stage==LSX_PCMDSD_STAGE_SCALED?o->scaled:NULL;
  uint64_t *count=stage==LSX_PCMDSD_STAGE_R?&o->working_count:
      stage==LSX_PCMDSD_STAGE_PREFILTER?&o->filtered_count:
      stage==LSX_PCMDSD_STAGE_NATIVE?&o->native_count:
      stage==LSX_PCMDSD_STAGE_SCALED?&o->scaled_count:NULL;
  if (!fp || !count || o->failed) return;
  if (n>UINT64_MAX-*count || fwrite(words,sizeof(*words),n,fp)!=n) o->failed=1;
  else *count+=n;
}

static int parse_u32(const char *str,uint32_t *out)
{
  char tail;
  unsigned long long v;
  if (!str || !*str || *str=='-' || sscanf(str,"%llu%c",&v,&tail)!=1 ||
      v>UINT32_MAX) return 0;
  *out=(uint32_t)v;return 1;
}

int main(int argc,char **argv)
{
  uint32_t native,source_frames,impulse_at;
  const lsx_pcmdsd_profile *profile;
  lsx_pcmdsd *encoder=NULL;
  observation o={0};
  lsx_pcmdsd_report report;
  char work_path[4096],filter_path[4096],native_path[4096],scaled_path[4096];
  uint64_t used=0, produced=0;
  int rc=2,entered=0,dual=0,attenuated=0;
  double headroom_gain=1.;
  dual=argc>=6 && !strcmp(argv[5],"dual");
  attenuated=argc==7 && dual && !strcmp(argv[6],"headroom3");
  if ((argc!=5 && !(argc==6 && dual) && !attenuated) || !parse_u32(argv[1],&native) ||
      !parse_u32(argv[2],&source_frames) ||
      !parse_u32(argv[3],&impulse_at) ||
      source_frames<128 || source_frames>8192 || impulse_at>=source_frames ||
      (native!=2822400 && native!=5644800) ||
      strlen(argv[4])>4000) return 2;
  if (snprintf(work_path,sizeof(work_path),"%s.working.f64",argv[4])<=0 ||
      snprintf(filter_path,sizeof(filter_path),"%s.filtered.f64",argv[4])<=0 ||
      snprintf(native_path,sizeof(native_path),"%s.native.f64",argv[4])<=0 ||
      snprintf(scaled_path,sizeof(scaled_path),"%s.scaled.f64",argv[4])<=0) return 2;
  if (sox_init()!=SOX_SUCCESS)return 2;
  entered=1;
  profile=lsx_pcmdsd_profile_find(native);
  if (!profile || !profile->qualified ||
      lsx_pcmdsd_create(44100,native,.5,0,&encoder)!=SOX_DSD_OK)goto done;
  o.working=fopen(work_path,"wb");o.filtered=fopen(filter_path,"wb");
  o.native=fopen(native_path,"wb");o.scaled=fopen(scaled_path,"wb");
  if (!o.working || !o.filtered || !o.native || !o.scaled)goto done;
  if (attenuated) {
    headroom_gain=pow(10.,-3./20.);
    lsx_pcmdsd_set_gain(encoder,headroom_gain);
  }
  lsx_pcmdsd_observe(encoder,capture,&o);
  while (used<source_frames) {
    double data[128];sox_sample_t encoded[4096];
    size_t avail=(size_t)(source_frames-used),consumed=0;
    if (avail>128)avail=128;
    for (size_t i=0;i<avail;i++) {
      uint64_t at=used+i;
      data[i]=at==impulse_at?0.5:
          dual && at==impulse_at+1?-0.25:
          dual && at==impulse_at+3?0.125:0.0;
    }
    while (consumed<avail) {
      size_t n=avail-consumed,m=4096;
      sox_dsd_status_t st=lsx_pcmdsd_process(encoder,data+consumed,&n,encoded,&m);
      if ((st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT) ||
          (!n && !m))goto done;
      consumed+=n;used+=n;produced+=m;
      if (o.failed)goto done;
    }
  }
  for (;;) {
    sox_sample_t encoded[4096];size_t m=4096;
    sox_dsd_status_t st=lsx_pcmdsd_finish(encoder,encoded,&m);
    if (st!=SOX_DSD_NEED_OUTPUT && st!=SOX_DSD_DONE)goto done;
    produced+=m;
    if (o.failed)goto done;
    if (st==SOX_DSD_DONE)break;
    if (!m)goto done;
  }
  if (lsx_pcmdsd_report_get(encoder,&report)!=SOX_DSD_OK ||
      report.failure || report.input_frames!=source_frames ||
      report.committed_frames!=produced ||
      o.working_count != ((uint64_t)source_frames*profile->working_hz+44100-1)/44100 ||
      o.filtered_count!=o.working_count ||
      produced != ((uint64_t)source_frames*native+22050)/44100 ||
      o.native_count<produced || o.scaled_count!=o.native_count)goto done;
  rc=0;
  printf("{\"native_hz\":%u,\"working_hz\":%u,\"source_frames\":%u,"
      "\"impulse_at\":%u,\"working_frames\":%" PRIu64 ","
      "\"filtered_frames\":%" PRIu64 ",\"native_frames\":%" PRIu64 ",\"headroom_factor\":\"%a\"}\n",
      native,profile->working_hz,source_frames,impulse_at,
      o.working_count,o.filtered_count,produced,headroom_gain);
done:
  if (o.working && (fflush(o.working) || fclose(o.working)))rc=1;
  if (o.filtered && (fflush(o.filtered) || fclose(o.filtered)))rc=1;
  if (o.native && (fflush(o.native) || fclose(o.native)))rc=1;
  if (o.scaled && (fflush(o.scaled) || fclose(o.scaled)))rc=1;
  if (encoder)lsx_pcmdsd_destroy(encoder);
  if (entered)sox_quit();
  if (rc) {remove(work_path);remove(filter_path);remove(native_path);remove(scaled_path);}
  return rc;
}
