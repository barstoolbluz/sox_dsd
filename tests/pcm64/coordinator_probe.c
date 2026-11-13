/* Phase 05A independent caller-buffer contract probe. No CLI, no SoX int32
 * effects chain, and no public ABI: build the production coordinator itself. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "dsd_f64.h"
#include <fenv.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned long assertions;
#define CHECK(e) do {++assertions; if (!(e)) { \
  fprintf(stderr,"coordinator line %d: %s\n",__LINE__,#e);return 1;} } while(0)

static double from_bits(uint64_t b)
{
  double d;memcpy(&d,&b,sizeof(d));return d;
}
static uint64_t bits(double d)
{
  uint64_t b;memcpy(&b,&d,sizeof(b));return b;
}
static double fixture(size_t frame,unsigned chan)
{
  const uint64_t words[]={
      UINT64_C(0x8000000000000000), UINT64_C(0),
      UINT64_C(0x0000000000000001), UINT64_C(0x8000000000000001),
      UINT64_C(0x3d70000000000000), UINT64_C(0xbfd4000000000000),
      UINT64_C(0x3ff4000000000000), UINT64_C(0x4000000000000000),
      UINT64_C(0x7fefffffffffffff), UINT64_C(0xffefffffffffffff)};
  return from_bits(words[(frame*13+chan*7)%10]);
}

static int test_blocks(size_t count)
{
  pcm_f64_format f;
  lsx_dsd_f64_stream s;
  double *in,*out;
  size_t k,offset=0;
  unsigned channels=2, map[2]={0,1};
  pcm_f64_progress p;
  CHECK(pcm_f64_format_init(&f,48000,channels,true,count)==PCM_F64_OK);
  CHECK(lsx_dsd_f64_init(&s,&f,NULL,0,map)==PCM_F64_OK);
  in=calloc(count*channels+1,sizeof(double));
  out=calloc(count*channels+1,sizeof(double));
  CHECK(in && out);
  for(k=0;k<count*channels;k++)in[k]=fixture(k/channels,(unsigned)(k%channels));
  CHECK(lsx_dsd_f64_process(&s,(pcm_f64_input){NULL,0},
      (pcm_f64_output){NULL,0}).status==PCM_F64_NEED_INPUT);
  if (count) CHECK(lsx_dsd_f64_process(&s,(pcm_f64_input){in,1},
      (pcm_f64_output){NULL,0}).status==PCM_F64_NEED_OUTPUT);
  while(offset<count) {
    size_t request=(offset*17+7)%37+1,cap=(offset*11+1)%17+1;
    if (request>count-offset) request=count-offset;
    p=lsx_dsd_f64_process(&s,(pcm_f64_input){in+offset*channels,request},
        (pcm_f64_output){out+offset*channels,cap});
    CHECK(p.consumed_frames==p.produced_frames);
    CHECK(p.produced_frames==(request<cap?request:cap));
    CHECK(p.status==(request>cap?PCM_F64_NEED_OUTPUT:PCM_F64_OK));
    offset+=p.consumed_frames;
  }
  CHECK(!memcmp(in,out,count*channels*sizeof(double)));
  CHECK(s.input_frames==count && s.output_frames==count && !s.transformed);
  CHECK(lsx_dsd_f64_finish(&s,(pcm_f64_output){NULL,0}).status==PCM_F64_DONE);
  CHECK(lsx_dsd_f64_finish(&s,(pcm_f64_output){NULL,0}).status==PCM_F64_DONE);
  CHECK(lsx_dsd_f64_process(&s,(pcm_f64_input){NULL,0},
      (pcm_f64_output){NULL,0}).status==PCM_F64_STATE);
  CHECK(lsx_dsd_f64_finish(&s,(pcm_f64_output){NULL,0}).status==PCM_F64_STATE);
  lsx_dsd_f64_destroy(&s);
  free(in);free(out);
  return 0;
}

static int test_permutation_gains(void)
{
  pcm_f64_format f;
  lsx_dsd_f64_stream s;
  double in[8],out[8];
  double factors[3]={0.75,0.5,2.0};
  unsigned map[2]={1,0};
  pcm_f64_progress p;
  unsigned i;
  CHECK(pcm_f64_format_init(&f,96000,2,true,4)==PCM_F64_OK);
  for(i=0;i<8;i++)in[i]=(double)((int)i-4)/16.;
  CHECK(lsx_dsd_f64_init(&s,&f,factors,3,map)==PCM_F64_OK);
  CHECK(s.transformed && s.permuted);
  p=lsx_dsd_f64_process(&s,(pcm_f64_input){in,4},
      (pcm_f64_output){out,1});
  CHECK(p.status==PCM_F64_NEED_OUTPUT && p.consumed_frames==1 && p.produced_frames==1);
  CHECK(out[0]==(((in[1]*0.75)*0.5)*2.) && out[1]==(((in[0]*0.75)*0.5)*2.));
  p=lsx_dsd_f64_process(&s,(pcm_f64_input){in+2,3},
      (pcm_f64_output){out+2,3});
  CHECK(p.status==PCM_F64_OK && p.consumed_frames==3);
  for(i=0;i<4;i++) {
    CHECK(out[2*i]==(((in[2*i+1]*0.75)*0.5)*2.));
    CHECK(out[2*i+1]==(((in[2*i]*0.75)*0.5)*2.));
  }
  CHECK(lsx_dsd_f64_finish(&s,(pcm_f64_output){NULL,0}).status==PCM_F64_DONE);
  lsx_dsd_f64_destroy(&s);
  return 0;
}

static int test_failures(void)
{
  pcm_f64_format f;
  lsx_dsd_f64_stream s;
  double in[4]={0.,0.25,-0.0,1.},out[4]={7.,7.,7.,7.};
  double gain=0.5;
  unsigned bad_map[2]={0,0},map[2]={0,1};
  pcm_f64_progress p;
  CHECK(pcm_f64_format_init(&f,44100,2,true,2)==PCM_F64_OK);
  CHECK(lsx_dsd_f64_init(&s,&f,NULL,0,bad_map)==PCM_F64_ARGUMENT);
  CHECK(lsx_dsd_f64_init(&s,&f,NULL,0,map)==PCM_F64_OK);
  in[3]=from_bits(UINT64_C(0x7ff0000000000001));
  p=lsx_dsd_f64_process(&s,(pcm_f64_input){in,2},(pcm_f64_output){out,2});
  CHECK(p.status==PCM_F64_NUMERIC && !p.consumed_frames && !p.produced_frames);
  CHECK(out[0]==7. && out[1]==7. && out[2]==7. && out[3]==7.);
  p=lsx_dsd_f64_process(&s,(pcm_f64_input){in,1},(pcm_f64_output){out,2});
  CHECK(p.status==PCM_F64_NUMERIC && !p.consumed_frames && !p.produced_frames);
  CHECK(lsx_dsd_f64_finish(&s,(pcm_f64_output){NULL,0}).status==PCM_F64_NUMERIC);
  lsx_dsd_f64_destroy(&s);
  CHECK(lsx_dsd_f64_init(&s,&f,&gain,1,map)==PCM_F64_OK);
  CHECK(lsx_dsd_f64_finish(&s,(pcm_f64_output){NULL,0}).status==PCM_F64_IO);
  CHECK(lsx_dsd_f64_finish(&s,(pcm_f64_output){NULL,0}).status==PCM_F64_IO);
  lsx_dsd_f64_destroy(&s);
  CHECK(lsx_dsd_f64_init(&s,&f,NULL,0,map)==PCM_F64_OK);
  CHECK(lsx_dsd_f64_process(&s,(pcm_f64_input){in,3},
      (pcm_f64_output){out,3}).status==PCM_F64_LIMIT);
  lsx_dsd_f64_destroy(&s);
  return 0;
}

static int test_fenv(void)
{
  pcm_f64_format f;
  lsx_dsd_f64_stream s;
  double in[2]={from_bits(UINT64_C(0x8000000000000000)),
                from_bits(UINT64_C(0x0000000000000001))},out[2];
  double gain=1.125;
  unsigned map[2]={0,1};
  int original=fegetround();
  pcm_f64_status st;
  CHECK(pcm_f64_format_init(&f,44100,2,true,1)==PCM_F64_OK);
  CHECK(original==FE_TONEAREST);
  CHECK(fesetround(FE_UPWARD)==0);
  CHECK(lsx_dsd_f64_init(&s,&f,NULL,0,map)==PCM_F64_OK);
  CHECK(lsx_dsd_f64_process(&s,(pcm_f64_input){in,1},
      (pcm_f64_output){out,1}).status==PCM_F64_OK);
  CHECK(bits(out[0])==bits(in[0]) && bits(out[1])==bits(in[1]));
  CHECK(lsx_dsd_f64_finish(&s,(pcm_f64_output){NULL,0}).status==PCM_F64_DONE);
  lsx_dsd_f64_destroy(&s);
  st=lsx_dsd_f64_init(&s,&f,&gain,1,map);
  CHECK(st==PCM_F64_NUMERIC || st==PCM_F64_UNSUPPORTED);
  CHECK(fesetround(original)==0);
  return 0;
}

int main(void)
{
  static const size_t counts[]={0,1,7,256,511,4096,4097,8193};
  size_t i;
  for(i=0;i<sizeof(counts)/sizeof(counts[0]);i++)
    if(test_blocks(counts[i]))return 1;
  if(test_permutation_gains() || test_failures() || test_fenv())return 1;
  printf("PASS coordinator assertions=%lu blocks=8 ordered_gains=3 partial_buffers=PASS hostile_fenv=PASS first_error_latch=PASS\n",assertions);
  return 0;
}
