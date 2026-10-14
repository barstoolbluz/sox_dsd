/* P07 private F64 SRC signal exporter for independent SciPy comparison.
 * Carries no application graph/clipping or reference-model implementations. */
#include "rate_internal.h"
#include "dsd.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

static double signal_at(uint32_t hz,size_t i)
{
  double t=(double)i/hz;
  return .23*sin(2*M_PI*1007.3*t)+.17*cos(2*M_PI*4231.7*t)+
         .02*sin(2*M_PI*15329.31*t);
}

/* Composite production exporter: bits alternate in 512-native-frame runs.
 * Independent Python oracle derives its own FIR equivalent convolution. */
static int export_dsd(uint32_t native,uint32_t output,int profile,size_t length)
{
  sox_dsd_decode_options_t opts;
  sox_dsd_decoder_t *ctx=NULL;
  sox_sample_t *input=NULL;
  uint64_t target=0;
  size_t used=0,emitted=0;
  int steps=0;
  if (!lsx_dsd_count_convert(length,native,output,&target)) return 2;
  sox_dsd_decode_options_init(&opts);
  opts.native_hz=native;
  opts.output_hz=output;
  opts.profile=(sox_dsd_decode_profile_t)profile;
  opts.channels=1;
  if (sox_dsd_decoder_create(&opts,&ctx)!=SOX_DSD_OK) return 3;
  input=malloc((length+1)*sizeof(*input));
  if (!input) return 4;
  for (size_t i=0;i<length;i++)
    input[i]=((i/512)&1)?-SOX_SAMPLE_MAX:SOX_SAMPLE_MAX;
  while (used<length) {
    double out[256];
    size_t in=length-used,cap=256;
    sox_dsd_status_t rc;
    if (in>200) in=200;
    rc=sox_dsd_decoder_process(ctx,input+used,&in,out,&cap);
    if ((rc!=SOX_DSD_NEED_INPUT && rc!=SOX_DSD_NEED_OUTPUT) ||
        fwrite(out,sizeof(*out),cap,stdout)!=cap || (!in && !cap)) return 5;
    used+=in;emitted+=cap;
    if (++steps>1000000) return 6;
  }
  while (1) {
    double out[256];size_t cap=256;
    sox_dsd_status_t rc=sox_dsd_decoder_finish(ctx,out,&cap);
    if ((rc!=SOX_DSD_NEED_OUTPUT && rc!=SOX_DSD_DONE) ||
        fwrite(out,sizeof(*out),cap,stdout)!=cap) return 7;
    emitted+=cap;
    if (rc==SOX_DSD_DONE)break;
    if (!cap || ++steps>1000000)return 8;
  }
  free(input);sox_dsd_decoder_destroy(ctx);
  return emitted==target?0:9;
}

int main(int argc,char **argv)
{
  lsx_rate_f64_config cfg={0};
  lsx_rate_f64_t *src=NULL;
  size_t length,accepted=0,emitted=0;
  uint64_t expected;
  int iter=0;
  int is_impulse=argc==6 && !strcmp(argv[1],"--impulse");
  int is_tone=argc==6 && !strcmp(argv[1],"--tone");
  double tone_hz=0.0;
  size_t impulse_at=0;
  if (argc==6 && !strcmp(argv[1],"--dsd"))
    return export_dsd((uint32_t)strtoul(argv[2],NULL,10),
        (uint32_t)strtoul(argv[3],NULL,10),atoi(argv[4]),
        (size_t)strtoull(argv[5],NULL,10));
  if (argc!=4 && !is_impulse && !is_tone) return 2;
  cfg.input_hz=(uint32_t)strtoul(argv[is_impulse||is_tone?2:1],NULL,10);
  cfg.output_hz=(uint32_t)strtoul(argv[is_impulse||is_tone?3:2],NULL,10);
  length=(size_t)strtoull(argv[is_impulse||is_tone?4:3],NULL,10);
  if (is_tone) {
    char *end=NULL;
    tone_hz=strtod(argv[5],&end);
    if (!end || *end || !isfinite(tone_hz) || tone_hz<=0 ||
        tone_hz>=cfg.input_hz/2.0) return 2;
  }
  if (is_impulse) {
    impulse_at=(size_t)strtoull(argv[5],NULL,10);
    if (impulse_at>=length) return 2;
  }
  cfg.rejection_db=180;cfg.bandwidth_0db_pct=95;cfg.phase_percent=50;
  if (!lsx_dsd_count_convert(length,cfg.input_hz,cfg.output_hz,&expected) ||
      lsx_rate_f64_create(&cfg,&src)!=SOX_DSD_OK) return 3;
  while (accepted<length) {
    double in[128],out[1024];
    size_t in_count=length-accepted, out_count=1024;
    sox_dsd_status_t status;
    if (in_count>128) in_count=128;
    for (size_t i=0;i<in_count;i++)
      in[i]=is_impulse ? (accepted+i==impulse_at ? .5 : 0.)
             : is_tone ? .5*sin(2*M_PI*tone_hz*(accepted+i)/cfg.input_hz)
             : signal_at(cfg.input_hz,accepted+i);
    status=lsx_rate_f64_process(src,in,&in_count,out,&out_count);
    if ((status!=SOX_DSD_NEED_INPUT && status!=SOX_DSD_NEED_OUTPUT) ||
        fwrite(out,sizeof(*out),out_count,stdout)!=out_count) return 4;
    accepted+=in_count; emitted+=out_count;
    if (!in_count && !out_count) return 5;
    if (++iter>1000000) return 6;
  }
  while (1) {
    double out[1024];size_t out_count=1024;
    sox_dsd_status_t status=lsx_rate_f64_finish(src,expected,out,&out_count);
    if ((status!=SOX_DSD_NEED_OUTPUT && status!=SOX_DSD_DONE) ||
        fwrite(out,sizeof(*out),out_count,stdout)!=out_count) return 7;
    emitted+=out_count;
    if (status==SOX_DSD_DONE) break;
    if (!out_count || ++iter>1000000) return 8;
  }
  fprintf(stderr,"P07 F64 exported: %zu samples, ratio %u/%u\n",
          emitted,cfg.output_hz,cfg.input_hz);
  lsx_rate_f64_destroy(src);
  return emitted==expected?0:9;
}
