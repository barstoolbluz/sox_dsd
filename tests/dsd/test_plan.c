/* Independent P05 planner/numeric contract tests. No audio DSP is invoked. */
#include "dsd.h"
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks, failures;
#define CHECK(x) do { ++checks; if (!(x)) { ++failures; fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#x); } } while(0)
#define CLOSE(x,y) CHECK(fabs((x)-(y)) < 1.e-9)

static lsx_dsd_input_spec native(double rate, unsigned channels)
{
  lsx_dsd_input_spec x;
  memset(&x,0,sizeof(x));
  x.native_signal.rate=rate;
  x.native_signal.channels=channels;
  x.encoding=SOX_ENCODING_DSD;
  x.input_volume=1;
  x.layout_known=1;
  return x;
}
static lsx_dsd_input_spec pcm(double rate, unsigned channels)
{
  lsx_dsd_input_spec x=native(rate,channels);
  x.encoding=SOX_ENCODING_SIGN2;
  return x;
}
static lsx_dsd_plan_spec config(lsx_dsd_input_spec *input, size_t count, int native_output)
{
  lsx_dsd_plan_spec s;
  memset(&s,0,sizeof(s));
  s.policy.mode=LSX_DSD_MODE_AUTO;
  s.inputs=input;
  s.input_count=count;
  s.output_native_capable=native_output;
  s.output_pcm_capable=!native_output;
  s.output_dop_capable=!native_output;
  s.fallback_encoding=SOX_ENCODING_SIGN2;
  s.fallback_bits=24;
  s.combine=LSX_DSD_COMBINE_SEQUENCE;
  return s;
}
static lsx_dsd_effect_spec effect(char const *name)
{
  lsx_dsd_effect_spec e;
  memset(&e,0,sizeof(e));
  e.name=name;
  return e;
}
static int build(lsx_dsd_plan_spec *s, lsx_dsd_plan *p)
{
  char error[256];
  int ok=lsx_dsd_plan_build(s,p,error,sizeof(error));
  if (!ok && !*error) {fprintf(stderr,"missing error reason\n");++failures;}
  return ok;
}
static void numeric(void)
{
  uint32_t rate=0;
  uint64_t count=0;
  double pass=0,stop=0,r=0;
  unsigned m;
  for (m=1;m<=16;m*=2) {
    uint64_t got;
    CHECK(lsx_dsd_checked_interleaved(100,m,&got));
    CHECK(got==100*m);
  }
  CHECK(!lsx_dsd_checked_interleaved(UINT64_MAX,2,&count));
  CHECK(lsx_dsd_checked_interleaved(UINT64_MAX,1,&count));
  CHECK(count==UINT64_MAX);
  CHECK(!lsx_dsd_checked_interleaved(0,0,&count));
  CHECK(!lsx_dsd_checked_interleaved(10,2,NULL));
  CHECK(lsx_dsd_count_convert(16,2822400,88200,&count) && count==1);
  CHECK(lsx_dsd_count_convert(15,2822400,88200,&count) && count==0);
  CHECK(lsx_dsd_count_convert(32,2822400,88200,&count) && count==1);
  CHECK(lsx_dsd_count_convert(64,2822400,88200,&count) && count==2);
  CHECK(lsx_dsd_count_convert(1000001,44100,88200,&count) && count==2000002);
  CHECK(lsx_dsd_count_convert(UINT64_MAX,UINT32_MAX,1,&count) && count==4294967297ULL);
  CHECK(!lsx_dsd_count_convert(UINT64_MAX,1,UINT32_MAX,&count));
  CHECK(!lsx_dsd_count_convert(1,0,2,&count));
  CHECK(!lsx_dsd_count_convert(1,2,2,NULL));
  CHECK(lsx_dsd_integer_rate(2822400,&rate) && rate==2822400);
  CHECK(!lsx_dsd_integer_rate(88200.5,&rate));
  CHECK(!lsx_dsd_integer_rate(0,&rate));
  CHECK(!lsx_dsd_integer_rate(NAN,&rate));
  CHECK(!lsx_dsd_integer_rate(INFINITY,&rate));
  CHECK(!lsx_dsd_integer_rate(4294967296.,&rate));
  CHECK(lsx_dsd_rate_find(2822400)->multiplier==64);
  CHECK(lsx_dsd_rate_find(5644800)->multiplier==128);
  CHECK(lsx_dsd_rate_find(11289600)->multiplier==256);
  CHECK(lsx_dsd_rate_find(22579200)->capabilities==0);
  CHECK(lsx_dsd_rate_find(45158400)->capabilities==0);
  CHECK(!lsx_dsd_rate_find(3000000));
  CHECK(lsx_dsd_profile_edges(2822400,LSX_DSD_PROFILE_MASTERING,&pass,&stop,&r));
  CLOSE(pass,20000);CLOSE(stop,40000);CLOSE(r,88200);
  CHECK(lsx_dsd_profile_edges(5644800,LSX_DSD_PROFILE_MASTERING,&pass,&stop,&r));
  CLOSE(pass,30000);CLOSE(stop,60000);CLOSE(r,176400);
  CHECK(lsx_dsd_profile_edges(11289600,LSX_DSD_PROFILE_MASTERING,&pass,&stop,&r));
  CLOSE(pass,40000);CLOSE(stop,80000);CLOSE(r,176400);
  CHECK(lsx_dsd_profile_edges(2822400,LSX_DSD_PROFILE_WIDEBAND,&pass,&stop,&r));
  CLOSE(pass,35280);CLOSE(stop,44100);CLOSE(r,88200);
  CHECK(lsx_dsd_profile_edges(5644800,LSX_DSD_PROFILE_WIDEBAND,&pass,&stop,&r));
  CLOSE(pass,70560);CLOSE(stop,88200);CLOSE(r,176400);
  CHECK(lsx_dsd_profile_edges(11289600,LSX_DSD_PROFILE_WIDEBAND,&pass,&stop,&r));
  CLOSE(pass,141120);CLOSE(stop,176400);CLOSE(r,352800);
  CHECK(!lsx_dsd_profile_edges(22579200,LSX_DSD_PROFILE_MASTERING,&pass,&stop,&r));
  CHECK(!lsx_dsd_profile_edges(2822400,LSX_DSD_PROFILE_LEGACY,&pass,&stop,&r));
  CLOSE(lsx_dsd_effective_bandwidth(20000,88200,88200),20000);
  CLOSE(lsx_dsd_effective_bandwidth(35280,88200,44100),20947.5);
  CLOSE(lsx_dsd_effective_bandwidth(141120,352800,192000),91200);
  CLOSE(lsx_dsd_effective_bandwidth(40000,176400,44100),20947.5);
  CHECK(lsx_dsd_pcm_rate_supported(705600));
  CHECK(!lsx_dsd_pcm_rate_supported(96001));
}
static void graph(void)
{
  lsx_dsd_input_spec in[2];
  lsx_dsd_plan_spec spec;
  lsx_dsd_plan plan;
  lsx_dsd_effect_spec eff[3];
  in[0]=native(2822400,2); in[1]=native(2822400,2);
  spec=config(in,1,1);
  CHECK(build(&spec,&plan));
  CHECK(plan.executable && !plan.needs_unimplemented_dsp);
  CHECK(plan.output_domain==LSX_DSD_NATIVE && plan.output_rate==2822400);
  CHECK(plan.graph_decode_count==0 && plan.encode_count==0);
  CHECK(plan.trim_native_seek && plan.layout_identity_preserved);
  CLOSE(plan.inputs[0].reference,1);
  lsx_dsd_plan_free(&plan);

  eff[0]=effect("trim");spec.effects=eff;spec.effect_count=1;
  CHECK(build(&spec,&plan)); CHECK(plan.executable && plan.trim_native_seek);
  lsx_dsd_plan_free(&plan);
  eff[0]=effect("channels"); eff[0].flags=SOX_EFF_CHAN; eff[0].out_channels=2;
  CHECK(build(&spec,&plan)); CHECK(plan.executable && plan.layout_identity_preserved);
  lsx_dsd_plan_free(&plan);
  eff[0].out_channels=1;
  CHECK(build(&spec,&plan)); CHECK(!plan.executable && plan.graph_decode_count==1);
  lsx_dsd_plan_free(&plan);

  eff[0]=effect("gain");spec.effect_count=1;
  CHECK(build(&spec,&plan));
  CHECK(!plan.executable && plan.graph_decode_count==1 && plan.encode_count==1);
  CHECK(plan.step_count==3 && plan.steps[0].implicit && plan.steps[2].implicit);
  CLOSE(plan.modulator_input_scale,1);
  lsx_dsd_plan_free(&plan);
  spec.output_native_capable=0;spec.output_pcm_capable=1;
  spec.effect_count=0;
  CHECK(build(&spec,&plan));
  CHECK(plan.executable && !plan.needs_unimplemented_dsp && plan.graph_decode_count==1);
  CHECK(plan.output_domain==LSX_PCM_AUDIO && plan.output_rate==88200);
  CHECK(plan.output_bits==24 && plan.decoder_pass_hz==20000);
  lsx_dsd_plan_free(&plan);
  spec.policy.decode=LSX_DSD_PROFILE_WIDEBAND;
  spec.requested_output_rate=44100;
  CHECK(build(&spec,&plan));
  CLOSE(plan.effective_bandwidth_hz,20947.5);
  lsx_dsd_plan_free(&plan);
  spec.policy.bandwidth=LSX_DSD_BANDWIDTH_STRICT;
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan);
  spec.policy.bandwidth=LSX_DSD_BANDWIDTH_ADAPT;
  spec.policy.decode=LSX_DSD_PROFILE_MASTERING;

  spec=config(in,2,0);
  spec.combine=LSX_DSD_COMBINE_MIX;
  CHECK(build(&spec,&plan));
  CHECK(plan.input_decode_count==2 && !plan.graph_decode_count);
  CHECK(plan.steps[0].input_index==0 && plan.steps[1].input_index==1);
  CHECK(plan.combiner_domain==LSX_PCM_AUDIO && plan.combiner_rate==88200);
  lsx_dsd_plan_free(&plan);
  spec.combine=LSX_DSD_COMBINE_MERGE;
  CHECK(build(&spec,&plan)); CHECK(plan.combiner_channels==4);
  lsx_dsd_plan_free(&plan);
  spec.combine=LSX_DSD_COMBINE_MULTIPLY;
  CHECK(build(&spec,&plan)); CHECK(plan.input_decode_count==2);
  lsx_dsd_plan_free(&plan);
  spec.combine=LSX_DSD_COMBINE_MIX_POWER;
  CHECK(build(&spec,&plan)); CHECK(plan.input_decode_count==2);
  lsx_dsd_plan_free(&plan);
  spec.policy.mode=LSX_DSD_MODE_NATIVE;
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan);
  spec=config(in,1,1);in[0].input_volume=.5;
  CHECK(build(&spec,&plan));CHECK(plan.input_decode_count==1);
  CHECK(plan.inputs[0].volume_consumed_by_decoder);
  lsx_dsd_plan_free(&plan);
  in[0].input_volume=pow(10.,-3./20.); /* Pre-resolved -3 dB replay gain. */
  CHECK(build(&spec,&plan));
  CLOSE(plan.inputs[0].volume,pow(10.,-3./20.));
  CHECK(plan.inputs[0].volume_consumed_by_decoder);
  lsx_dsd_plan_free(&plan);
  in[0].input_volume=1;
  spec=config(in,2,0);spec.combine=LSX_DSD_COMBINE_MIX;
  in[1]=pcm(88200,2);
  CHECK(build(&spec,&plan)); CHECK(plan.input_decode_count==1);
  CLOSE(plan.combiner_rate,88200);
  CLOSE(plan.dsd_amplitude_per_pcm_unit,.5);
  lsx_dsd_plan_free(&plan);
  in[1]=pcm(96000,2);
  CHECK(build(&spec,&plan)); CHECK(plan.input_decode_count==1);
  CLOSE(plan.combiner_rate,96000);
  lsx_dsd_plan_free(&plan);
  in[0]=pcm(88200,2);
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan);

  in[0]=native(2822400,2); in[1]=native(2822400,2);
  spec=config(in,1,0);
  eff[0]=effect("dop");spec.effects=eff;spec.effect_count=1;
  CHECK(build(&spec,&plan));CHECK(plan.executable);
  CHECK(plan.output_domain==LSX_DOP_TRANSPORT && plan.output_rate==176400);
  CHECK(plan.output_bits==24 && plan.dop_count==1);
  lsx_dsd_plan_free(&plan);
  spec.requested_output_rate=88200;
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan);
  spec.requested_output_rate=0;
  eff[1]=effect("gain");spec.effect_count=2;
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan);
  spec.effect_count=1;
  eff[0]=effect("dsdpcm");
  /* P07 makes exactly this explicit single-input reconstruction executable. */
  CHECK(build(&spec,&plan));CHECK(plan.executable && !plan.needs_unimplemented_dsp && plan.graph_decode_count==1);
  lsx_dsd_plan_free(&plan);
  eff[1]=effect("dsdpcm");spec.effect_count=2;
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan);
  eff[0]=effect("pcmdsd");eff[0].dsd.rate_hz=5644800;
  spec.effect_count=1;
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan);
  in[0]=pcm(88200,2);spec=config(in,1,1);
  spec.effects=eff;spec.effect_count=1;
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan); /* explicit mismatched output DSD64 */
  spec.requested_output_rate=5644800;
  CHECK(build(&spec,&plan));CHECK(!plan.executable && plan.encode_count==1);
  CHECK(plan.output_rate==5644800);
  lsx_dsd_plan_free(&plan);
  eff[1]=effect("pcmdsd");eff[1].dsd.rate_hz=5644800;
  spec.effect_count=2;
  CHECK(!build(&spec,&plan));lsx_dsd_plan_free(&plan);
}


/* Focused state-machine tests independent of CLI file/format fixtures.  The
 * caller provides getopts metadata; the planner must never start an effect. */
static void corrective(void)
{
  lsx_dsd_input_spec in[2]={native(2822400,2),native(5644800,2)};
  lsx_dsd_plan_spec spec=config(in,1,0);
  lsx_dsd_effect_spec eff[4]={effect("dsdpcm"),effect("gain"),
                               effect("pcmdsd"),effect("dop")};
  lsx_dsd_plan p;

  in[0].input_volume=.5;
  eff[0].dsd.rate_hz=96000;
  spec.effects=eff;spec.effect_count=1;
  CHECK(build(&spec,&p));
  CHECK(p.input_decode_count==1 && p.graph_decode_count==0);
  CHECK(p.step_count==1 && p.steps[0].input_index==0);
  CHECK(p.combiner_rate==96000 && p.inputs[0].volume_consumed_by_decoder);
  lsx_dsd_plan_free(&p);

  spec.combine=LSX_DSD_COMBINE_MIX;spec.input_count=2;
  CHECK(build(&spec,&p));
  CHECK(p.input_decode_count==2 && p.graph_decode_count==0);
  CHECK(p.steps[0].input_index==0 && p.steps[1].input_index==1);
  lsx_dsd_plan_free(&p);
  eff[0].dsd.pinned_native_hz=2822400;
  CHECK(!build(&spec,&p));lsx_dsd_plan_free(&p);
  eff[0].dsd.pinned_native_hz=0;

  in[0]=pcm(88200,2);spec=config(in,1,0);
  eff[0]=effect("pcmdsd");eff[0].dsd.rate_hz=5644800;
  eff[1]=effect("dsdpcm");eff[1].dsd.rate_hz=176400;
  spec.effects=eff;spec.effect_count=2;
  CHECK(build(&spec,&p));
  CHECK(p.encode_count==1 && p.graph_decode_count==1);
  CHECK(p.steps[0].rate_after==5644800 && p.steps[1].rate_before==5644800);
  CHECK(p.decoder_id && !strcmp(p.decoder_id,"decode.mastering.v1.dsd128"));
  lsx_dsd_plan_free(&p);
  eff[1].dsd.pinned_native_hz=2822400;
  CHECK(!build(&spec,&p));lsx_dsd_plan_free(&p);
  eff[1].dsd.pinned_native_hz=0;
  eff[1]=effect("gain");
  CHECK(!build(&spec,&p));lsx_dsd_plan_free(&p);

  eff[1]=effect("dop");spec.effect_count=2;
  CHECK(build(&spec,&p));
  CHECK(p.output_domain==LSX_DOP_TRANSPORT && p.output_rate==352800);
  CHECK(p.native_output_hz==5644800 && p.encode_count==1);
  lsx_dsd_plan_free(&p);
  spec.requested_output_rate=176400;
  CHECK(!build(&spec,&p));lsx_dsd_plan_free(&p);

  in[0]=native(2822400,2);spec=config(in,1,0);
  eff[0]=effect("trim");spec.effects=eff;spec.effect_count=1;
  CHECK(build(&spec,&p));
  CHECK(p.graph_decode_count==1 && p.step_count==2);
  CHECK(!strcmp(p.steps[0].name,"implicit_dsdpcm"));
  CHECK(p.steps[1].rate_before==88200 && !p.trim_native_seek);
  lsx_dsd_plan_free(&p);

  spec=config(in,1,1);spec.requested_output_channels=1;spec.effect_count=0;
  CHECK(build(&spec,&p));
  CHECK(p.graph_decode_count==1 && p.encode_count==1);
  CHECK(p.output_channels==1 && !p.layout_identity_preserved);
  CHECK(p.step_count==3 && !strcmp(p.steps[1].name,"implicit_pcm_channels"));
  lsx_dsd_plan_free(&p);
  spec.policy.mode=LSX_DSD_MODE_NATIVE;
  CHECK(!build(&spec,&p));lsx_dsd_plan_free(&p);

  in[0]=pcm(2822400,2);spec=config(in,1,1);
  eff[0]=effect("sdm");eff[0].sdm_filter_name="sdm-5";
  spec.effects=eff;spec.effect_count=1;
  CHECK(build(&spec,&p));
  CHECK(p.executable && p.encode_count==1);
  CHECK(p.encoder_filter_name && !strcmp(p.encoder_filter_name,"sdm-5"));
  lsx_dsd_plan_free(&p);
  in[0]=pcm(88200,2);
  CHECK(!build(&spec,&p));lsx_dsd_plan_free(&p);

  in[0]=native(2822400,2);spec=config(in,1,1);
  spec.policy.normalizing=1;spec.effect_count=0;
  CHECK(build(&spec,&p));
  CHECK(p.graph_decode_count==1 && p.encode_count==1);
  CHECK(p.step_count==3 && !strcmp(p.steps[1].name,"auto_normalize"));
  CHECK(!p.executable);
  lsx_dsd_plan_free(&p);
  spec.policy.normalizing=0;spec.policy.guarded=1;
  CHECK(build(&spec,&p));
  CHECK(p.executable && p.step_count==0 && p.encode_count==0);
  lsx_dsd_plan_free(&p);
}
int main(void)
{
  numeric();graph();corrective();
  printf("P05 plan unit: %u assertions, %u failed\n",checks,failures);
  return failures?1:0;
}
