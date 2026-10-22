/* P17 experimental high-rate DSP test, uninstalled and not a writer gate.
 * Test oracle is a separately generated chronological bit sequence. The
 * packed layouts are generated independently from the production adapter.
 */
#define _POSIX_C_SOURCE 200809L
#include "sox_dsd.h"
#include "dsd_decode.h"
#include "dsd_packed.h"
#include "dsd.h"
#include "pcmdsd.h"
#include "pcmdsd_guards.h"
#include "sdm.h"
#include <stdint.h>
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static uint64_t checks, passed, skipped;
#define CHECK(expr) do {++checks; if (!(expr)) { \
  fprintf(stderr,"P17 FAIL %s:%d: %s\n",__FILE__,__LINE__,#expr);exit(1); \
} } while(0)
static const uint32_t high_rates[2]={22579200u,45158400u};
static const uint32_t pcm_rates[9]={44100,48000,88200,96000,176400,
  192000,352800,384000,705600};
static const char *kernels[5]={"scalar","sse2","avx1","avx2","avx512"};

/* Bits are independent of native/PCM algorithms and unequal between lanes. */
static int bit(size_t frame,unsigned channel)
{
  uint64_t v=(uint64_t)frame*0x9e3779b97f4a7c15ULL ^
    (uint64_t)(channel+41)*0xbf58476d1ce4e5b9ULL;
  v^=v>>30;v*=0xbf58476d1ce4e5b9ULL;
  v^=v>>27;v*=0x94d049bb133111ebULL;
  return (int)((v^(v>>31))&1);
}
typedef struct {sox_dsd_packed_block_t b;unsigned char *owned;} fixture;
static fixture make_fixture(size_t frames,unsigned channels,unsigned offset,int planar)
{
  fixture f={0};size_t bytes=(offset+frames+7)/8;
  CHECK(frames>0 && channels>0 && frames<=SIZE_MAX-offset-7);
  CHECK(bytes<=SIZE_MAX/channels);
  f.owned=calloc(bytes*channels,1);CHECK(f.owned);
  sox_dsd_packed_block_init(&f.b);
  f.b.data=f.owned;f.b.bytes=bytes*channels;f.b.frames=frames;
  f.b.channels=channels;f.b.bit_offset=offset;
  f.b.last_valid_bits=(unsigned)((offset+frames-1)%8+1);
  f.b.byte_stride=planar?1:channels;
  f.b.channel_stride=planar?bytes:1;
  f.b.bit_order=planar?SOX_DSD_PACKED_LSB:SOX_DSD_PACKED_MSB;
  for(size_t i=0;i<frames;i++)for(unsigned c=0;c<channels;c++){
    size_t b=offset+i,at=planar?c*bytes+b/8:(b/8)*channels+c;
    unsigned shift=planar?(b%8):(7-b%8);
    if(bit(i,c))f.owned[at]|=(unsigned char)(1u<<shift);
  }
  CHECK(lsx_dsd_packed_validate(&f.b));
  return f;
}
typedef struct {double *samples;size_t n;} decoded;
static decoded render(uint32_t hz,uint32_t out_rate,int kind,unsigned channels,
    const char *kernel,const fixture *packed,int use_packed,int *unsupported)
{
  decoded res={0};size_t frames=packed->b.frames,used=0,made=0,iterations=0;
  sox_dsd_decoder_t *d=NULL;sox_dsd_decode_options_t opt;
  sox_sample_t *expanded=NULL;sox_dsd_status_t rc;
  /* One PCM frame for every native frame is a generous, checked upper bound. */
  CHECK(frames<=SIZE_MAX/channels);
  res.samples=calloc((frames+64)*channels,sizeof(*res.samples));CHECK(res.samples);
  expanded=malloc(frames*channels*sizeof(*expanded));CHECK(expanded);
  for(size_t i=0;i<frames;i++)for(unsigned c=0;c<channels;c++)
    expanded[i*channels+c]=bit(i,c)?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
  sox_dsd_decode_options_init_extended(&opt);
  opt.native_hz=hz;opt.output_hz=out_rate;opt.channels=channels;
  opt.profile=kind?SOX_DSD_DECODE_WIDEBAND:SOX_DSD_DECODE_MASTERING;
  opt.kernel_fir=kernel;
  rc=sox_dsd_decoder_create(&opt,&d);
  if(rc==SOX_DSD_UNSUPPORTED){*unsupported=1;goto done;}
  CHECK(rc==SOX_DSD_OK && d);
  while(used<frames){
    size_t in=frames-used,output=1+iterations%29;
    if(in>431)in=431;
    rc=use_packed?sox_dsd_decoder_process_packed(d,&packed->b,used,
            &in,res.samples+made*channels,&output):
        sox_dsd_decoder_process(d,expanded+used*channels,
            &in,res.samples+made*channels,&output);
    CHECK(rc==SOX_DSD_NEED_INPUT || rc==SOX_DSD_NEED_OUTPUT);
    CHECK(in||output);
    used+=in;made+=output;
    CHECK(made<=frames+32 && ++iterations<frames+3000);
  }
  for(;;){
    size_t cap=1+iterations%29;
    rc=sox_dsd_decoder_finish(d,res.samples+made*channels,&cap);
    CHECK(rc==SOX_DSD_DONE || rc==SOX_DSD_NEED_OUTPUT);
    made+=cap;CHECK(made<=frames+32);
    if(rc==SOX_DSD_DONE)break;
    CHECK(++iterations<frames+3000);
  }
  res.n=made;
  {uint64_t expected;CHECK(lsx_dsd_count_convert(frames,hz,out_rate,&expected));
    CHECK(made==expected);}
done:
  sox_dsd_decoder_destroy(d);free(expanded);
  return res;
}
static void unit(void)
{
  uint64_t count;
  for(size_t i=0;i<2;i++){
    uint32_t hz=high_rates[i];const lsx_dsd_rate *rate=lsx_dsd_rate_find(hz);
    const lsx_dsd_frontend_profile *master=lsx_dsd_frontend_profile_find(hz,LSX_DSD_PROFILE_MASTERING);
    const lsx_dsd_frontend_profile *wide=lsx_dsd_frontend_profile_find(hz,LSX_DSD_PROFILE_WIDEBAND);
    const lsx_pcmdsd_profile *encoder=lsx_pcmdsd_profile_find(hz);
    const sdm_profile_t *sdm=sdm_profile_find(encoder?encoder->id:NULL,hz);
    lsx_dsd_reconstruction *d=NULL;lsx_dsd_reconstruction_info info;
    CHECK(rate && rate->capabilities==0);
    CHECK(!rate->decode_mastering_id && !rate->decode_wideband_id && !rate->encode_mastering_id);
    CHECK(master && wide && encoder && sdm);
    CHECK(encoder->qualified==0 && encoder->certificate_sha256==NULL);
    CHECK(encoder->bounds!=NULL);
    for(unsigned coord=0;coord<8;coord++)
      CHECK(encoder->bounds[coord]==lsx_pcmdsd_guards[i+3][coord]);
    CHECK(!lsx_pcmdsd_qualified(hz));
    CHECK(master->intermediate_hz==176400 && master->pass_hz==40000 && master->stop_hz==80000);
    CHECK(wide->intermediate_hz==hz/32 && wide->pass_hz==wide->intermediate_hz*.4);
    CHECK(wide->stop_hz==wide->intermediate_hz*.5);
    CHECK(master->stages==(i?8u:7u) && master->delay_native_frames==(i?10980u:5476u));
    CHECK(wide->stages==5 && wide->delay_native_frames==2468);
    CHECK(lsx_dsd_frontend_profile_find(hz,LSX_DSD_PROFILE_MASTERING_V2)==NULL);
    CHECK(lsx_dsd_reconstruction_create(hz,LSX_DSD_PROFILE_MASTERING,1,&d)==SOX_DSD_OK);
    CHECK(lsx_dsd_reconstruction_info_get(d,&info)==SOX_DSD_OK);
    CHECK(info.stages==master->stages && info.factor==hz/176400);
    CHECK(info.delay_native_frames==master->delay_native_frames);
    CHECK(info.allocated_bytes>0 && info.taps[info.stages-1]==117);
    for(unsigned j=0;j<info.stages;j++)
      CHECK(info.phases[j]==((info.delay_native_frames>>j)&1u));
    lsx_dsd_reconstruction_destroy(d);
    CHECK(sdm_profile_rate(sdm)==hz && sdm_profile_working_rate(sdm)==176400);
    CHECK(!sdm_profile_find("encode.mastering.v1.dsd256",hz));
    CHECK(!sdm_profile_find(encoder->id,11289600));
    CHECK(!sdm_profile_find(encoder->id,hz/2));
    CHECK(lsx_dsd_effective_bandwidth(wide->pass_hz,wide->intermediate_hz,705600)
        <=335160.0);
    if(i){
      sox_dsd_decode_options_t opt;sox_dsd_decoder_t *ctx=NULL;
      sox_dsd_decode_options_init_extended(&opt);
      opt.native_hz=hz;opt.output_hz=705600;opt.channels=1;
      opt.profile=SOX_DSD_DECODE_WIDEBAND;
      opt.bandwidth=SOX_DSD_BANDWIDTH_STRICT;
      CHECK(sox_dsd_decoder_create(&opt,&ctx)==SOX_DSD_UNSUPPORTED && !ctx);
      opt.bandwidth=SOX_DSD_BANDWIDTH_ADAPT;
      CHECK(sox_dsd_decoder_create(&opt,&ctx)==SOX_DSD_OK && ctx);
      sox_dsd_decoder_destroy(ctx);
    }
  }
  CHECK(lsx_dsd_count_convert(UINT64_MAX,45158400,45158400,&count));
  CHECK(count==UINT64_MAX);
  CHECK(!lsx_dsd_count_convert(UINT64_MAX,176400,45158400,&count));
  CHECK(lsx_dsd_count_convert(1,45158400,705600,&count) && count==0);
  CHECK(lsx_dsd_count_convert(32,45158400,705600,&count) && count==1);
  CHECK(lsx_dsd_count_convert(0,45158400,705600,&count) && count==0);
  CHECK(!lsx_dsd_frontend_profile_find(33000000,LSX_DSD_PROFILE_MASTERING));
  /* Normalized recurrence and state scaling: for the SAME input sequence, the
   * candidate has identical bit decisions and state across physical clocks. */
  {const sdm_profile_t *base=sdm_profile_find("encode.mastering.v1.dsd256",11289600);
   CHECK(base);
   for(size_t i=0;i<2;i++){
     const sdm_profile_t *candidate=sdm_profile_find(i?
       "encode.mastering.v1.dsd1024":"encode.mastering.v1.dsd512",high_rates[i]);
     sdm_normal_t a,b;int x,y;
     CHECK(candidate && sdm_normal_init(&a,base)==0);
     CHECK(sdm_normal_init(&b,candidate)==0);
     for(unsigned n=0;n<4096;n++){
       double value=.21*sin((double)n*.011)+.13*cos((double)n*.049);
       CHECK(sdm_normal_step(&a,value,&x)==0);
       CHECK(sdm_normal_step(&b,value,&y)==0);
       CHECK(x==y);
       CHECK(isfinite(b.state[b.bank][0]));
     }
     CHECK(!memcmp(a.state,b.state,sizeof(a.state)));
   }
  }
  printf("P17 unit PASS checks=%" PRIu64 "\n",checks);
}
static void matrix(void)
{
  for(size_t i=0;i<2;i++)for(unsigned pr=0;pr<2;pr++)
  for(size_t o=0;o<9;o++)for(unsigned channel_set=0;channel_set<3;channel_set++)
  for(unsigned tier=0;tier<5;tier++)for(unsigned layout=0;layout<2;layout++)
  for(unsigned offset=0;offset<8;offset++){
    unsigned channels=(unsigned[]){1,2,6}[channel_set];int unavailable=0,unavailable_packed=0;
    fixture f=make_fixture(1031,channels,offset,(int)layout);
    decoded a=render(high_rates[i],pcm_rates[o],pr,channels,kernels[tier],&f,0,&unavailable);
    decoded b=render(high_rates[i],pcm_rates[o],pr,channels,kernels[tier],&f,1,&unavailable_packed);
    CHECK(unavailable==unavailable_packed);
    if(!unavailable){
      CHECK(a.n==b.n);
      CHECK(memcmp(a.samples,b.samples,a.n*channels*sizeof(double))==0);
      passed++;
    }else skipped++;
    free(a.samples);free(b.samples);free(f.owned);
  }
  printf("P17 matrix PASS pairs=%" PRIu64 " unavailable=%" PRIu64 " checks=%" PRIu64 "\n",
    passed,skipped,checks);
}
static void encode(void)
{
  for(unsigned i=0;i<2;i++){
    const uint32_t hz=high_rates[i];lsx_pcmdsd *p=NULL;
    size_t used=0,made=0,iterations=0;
    const size_t input_frames=128;
    double input[128];sox_sample_t native[512];sox_dsd_status_t rc;
    for(size_t j=0;j<input_frames;j++)input[j]=.1*sin((double)j*.03);
    CHECK(lsx_pcmdsd_create(176400,hz,.5,0,&p)==SOX_DSD_UNSUPPORTED && !p);
    CHECK(lsx_pcmdsd_candidate_create(176400,hz,.5,0,NULL,NULL,&p)==SOX_DSD_OK && p);
    while(used<input_frames){
      size_t in=input_frames-used,out=512;
      rc=lsx_pcmdsd_process(p,input+used,&in,native,&out);
      CHECK(rc==SOX_DSD_NEED_INPUT || rc==SOX_DSD_NEED_OUTPUT);
      used+=in;made+=out;CHECK(in||out);
      CHECK(++iterations<10000);
    }
    for(;;){
      size_t out=512;
      rc=lsx_pcmdsd_finish(p,native,&out);
      CHECK(rc==SOX_DSD_DONE || rc==SOX_DSD_NEED_OUTPUT);
      made+=out;if(rc==SOX_DSD_DONE)break;
      CHECK(++iterations<10000);
    }
    {lsx_pcmdsd_report report;uint64_t expected;
     CHECK(lsx_dsd_count_convert(input_frames,176400,hz,&expected));
     CHECK(made==expected);
     CHECK(lsx_pcmdsd_report_get(p,&report)==SOX_DSD_OK);
     CHECK(report.failure==LSX_PCMDSD_NO_ERROR);
     CHECK(report.committed_frames==expected);
     CHECK(report.peak<=.5+1e-6);
    }
    lsx_pcmdsd_destroy(p);p=NULL;
    /* Overload and sticky failure must remain effective even with UNQUALIFIED
     * candidate bounds (the normal .5 sample envelope is not optional). */
    CHECK(lsx_pcmdsd_candidate_create(176400,hz,.5,0,NULL,NULL,&p)==SOX_DSD_OK && p);
    {double over=.75,quiet=.05;size_t taken=1,capacity=1;
     lsx_pcmdsd_report report;
     CHECK(lsx_pcmdsd_modulate(p,&over,native,1)==SOX_DSD_NUMERIC_ERROR);
     CHECK(lsx_pcmdsd_modulate(p,&quiet,native,1)==SOX_DSD_NUMERIC_ERROR);
     CHECK(lsx_pcmdsd_report_get(p,&report)==SOX_DSD_OK);
     CHECK(report.failure==LSX_PCMDSD_INTERPOLATION_OVERLOAD);
     CHECK(report.first_bad_frame==0 && report.failure_value==over);
     CHECK(lsx_pcmdsd_process(p,&quiet,&taken,native,&capacity)==SOX_DSD_NUMERIC_ERROR);
    }
    lsx_pcmdsd_destroy(p);passed++;
  }
  printf("P17 encode-candidate PASS rates=%" PRIu64 " checks=%" PRIu64 "\n",passed,checks);
}
static double now(void)
{
  struct timespec t;CHECK(clock_gettime(CLOCK_MONOTONIC,&t)==0);
  return t.tv_sec+t.tv_nsec*1.e-9;
}
/* Private candidate bitstream, explicitly NOT a DSF/DFF/DoP writer.
 * stdin = fixed-count IEEE754 binary64 normalized PCM at 176400 Hz.
 * stdout = one 0/1 byte per native bit. stderr = state/guard diagnostics. */
static int encode_export(uint32_t hz,size_t count)
{
  lsx_pcmdsd *ctx=NULL;
  double *input=NULL;size_t used=0;
  uint64_t emitted=0;sox_sample_t native[512];unsigned char encoded[512];
  sox_dsd_status_t rc;lsx_pcmdsd_report report;
  CHECK((hz==high_rates[0]||hz==high_rates[1]) && count>0 && count<=65536);
  input=malloc(count*sizeof(*input));CHECK(input);
  CHECK(fread(input,sizeof(*input),count,stdin)==count);
  CHECK(getchar()==EOF);
  CHECK(lsx_pcmdsd_candidate_create(176400,hz,.5,0,NULL,NULL,&ctx)==SOX_DSD_OK && ctx);
  while(used<count){
    size_t take=count-used, output=512;
    if(take>256)take=256;
    rc=lsx_pcmdsd_process(ctx,input+used,&take,native,&output);
    CHECK(rc==SOX_DSD_NEED_INPUT || rc==SOX_DSD_NEED_OUTPUT);
    CHECK(take || output);used+=take;
    for(size_t i=0;i<output;i++){
      CHECK(native[i]==SOX_SAMPLE_MAX || native[i]==-SOX_SAMPLE_MAX);
      encoded[i]=native[i]==SOX_SAMPLE_MAX;
    }
    CHECK(fwrite(encoded,1,output,stdout)==output);emitted+=output;
  }
  for(;;){
    size_t output=512;
    rc=lsx_pcmdsd_finish(ctx,native,&output);
    CHECK(rc==SOX_DSD_DONE || rc==SOX_DSD_NEED_OUTPUT);
    for(size_t i=0;i<output;i++){
      CHECK(native[i]==SOX_SAMPLE_MAX || native[i]==-SOX_SAMPLE_MAX);
      encoded[i]=native[i]==SOX_SAMPLE_MAX;
    }
    CHECK(fwrite(encoded,1,output,stdout)==output);emitted+=output;
    if(rc==SOX_DSD_DONE)break;
  }
  CHECK(lsx_pcmdsd_report_get(ctx,&report)==SOX_DSD_OK);
  CHECK(report.failure==LSX_PCMDSD_NO_ERROR);
  {uint64_t expected;
    CHECK(lsx_dsd_count_convert(count,176400,hz,&expected));
    CHECK(expected==emitted && report.committed_frames==expected);}
  fprintf(stderr,"P17_ENCODE_EXPORT rate=%u frames=%" PRIu64
     " state0=%.9g peak=%.9g ones28_min=%u ones28_max=%u windows28=%" PRIu64 "\n",
     hz,emitted,report.monitor.max_abs_state[0],report.peak,
     report.monitor.min_ones28,report.monitor.max_ones28,
     report.monitor.windows28);
  lsx_pcmdsd_destroy(ctx);free(input);return 0;
}

/* Bounded benchmark: a repeated deterministic 4096-frame source block, so
 * even 122 audio seconds of DSD1024 never creates a file-sized allocation.
 * This measures front-end/DSP and checksum, NOT disk I/O, physical material,
 * thermal stability, or independent rate-1024 codec interoperability. */
static uint64_t digest(uint64_t state,const double *samples,size_t n)
{
  const unsigned char *bytes=(const unsigned char *)samples;
  for(size_t i=0;i<n*sizeof(double);i++){
    state^=bytes[i];state*=1099511628211ULL;
  }
  return state;
}
static void bench(uint32_t hz,int profile,unsigned channels,int packed,double duration)
{
  const size_t block=4096;
  uint64_t total=(uint64_t)(hz*duration),frames=0,pcmframes=0;
  uint64_t hash=14695981039346656037ULL;
  sox_dsd_decoder_t *ctx=NULL;sox_dsd_decode_options_t opt;
  sox_sample_t *expanded=calloc(block*channels,sizeof(*expanded));
  fixture f;double *out=calloc(256*channels,sizeof(*out));
  sox_dsd_status_t rc;double t0,t1;
  CHECK((hz==high_rates[0]||hz==high_rates[1]) && channels>0 && channels<=6);
  CHECK(duration>=.001 && duration<=130. && (profile==0||profile==1));
  CHECK(expanded && out && total);
  f=make_fixture(block,channels,0,1);
  for(size_t i=0;i<block;i++)for(unsigned c=0;c<channels;c++)
    expanded[i*channels+c]=bit(i,c)?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
  sox_dsd_decode_options_init_extended(&opt);
  opt.native_hz=hz;opt.output_hz=profile?705600:176400;opt.channels=channels;
  opt.profile=profile?SOX_DSD_DECODE_WIDEBAND:SOX_DSD_DECODE_MASTERING;
  opt.kernel_fir="scalar";
  CHECK(sox_dsd_decoder_create(&opt,&ctx)==SOX_DSD_OK && ctx);
  t0=now();
  while(frames<total){
    size_t remaining=total-frames>block?block:(size_t)(total-frames);
    size_t used=0;
    /* No output gets lost if a non-default decoder SRC rate fills the queue. */
    while(used<remaining){
      size_t in=remaining-used,made=256;
      if(packed){
        f.b.frames=remaining;
        f.b.last_valid_bits=(unsigned)((remaining-1)%8+1);
        rc=sox_dsd_decoder_process_packed(ctx,&f.b,used,&in,out,&made);
      }else{
        rc=sox_dsd_decoder_process(ctx,expanded+used*channels,&in,out,&made);
      }
      CHECK(rc==SOX_DSD_NEED_INPUT || rc==SOX_DSD_NEED_OUTPUT);
      CHECK(in||made);
      used+=in;pcmframes+=made;
      hash=digest(hash,out,made*channels);
    }
    frames+=remaining;
  }
  for(;;){
    size_t made=256;
    rc=sox_dsd_decoder_finish(ctx,out,&made);
    CHECK(rc==SOX_DSD_DONE || rc==SOX_DSD_NEED_OUTPUT);
    pcmframes+=made;hash=digest(hash,out,made*channels);
    if(rc==SOX_DSD_DONE)break;
  }
  t1=now();
  {uint64_t expected;CHECK(lsx_dsd_count_convert(frames,hz,opt.output_hz,&expected));
    CHECK(pcmframes==expected);}
  printf("{\"status\":\"PASS\",\"rate_hz\":%u,\"channels\":%u,"
    "\"profile\":%d,\"packed\":%d,\"frames\":%" PRIu64 ",\"pcm_frames\":%" PRIu64 ","
    "\"wall_seconds\":%.9f,\"input_payload_bytes\":%" PRIu64 ","
    "\"pcm_digest_fnv64\":\"%016" PRIx64 "\"}\n",
    hz,channels,profile,packed,frames,pcmframes,t1-t0,
    packed?((frames+7)/8)*channels:frames*channels*4ULL,hash);
  sox_dsd_decoder_destroy(ctx);free(expanded);free(f.owned);free(out);
}

/* Streaming P17 research encoder benchmark. No file/transport writer is used.
 * Composite SRC/FIR/SDM time, not the isolated SDM microkernel cost. The
 * input source is deterministic and bounded; failure never counts as pass. */
static void bench_encode(uint32_t hz,double duration)
{
  const uint32_t source_hz=176400;
  const size_t batch=256;
  size_t total,used=0;
  double source[256];
  sox_sample_t bits[512];
  uint64_t emitted=0,hash=14695981039346656037ULL;
  lsx_pcmdsd *ctx=NULL;
  lsx_pcmdsd_report report;
  double t0,t1;
  CHECK((hz==high_rates[0] || hz==high_rates[1]) &&
        duration>=.001 && duration<=130.);
  total=(size_t)(duration*source_hz);
  CHECK(total>0);
  CHECK(lsx_pcmdsd_candidate_create(source_hz,hz,.5,0,NULL,NULL,&ctx)==SOX_DSD_OK && ctx);
  t0=now();
  while(used<total){
    size_t n=total-used<batch?total-used:batch;
    size_t accepted=0;
    for(size_t i=0;i<n;i++) {
      double t=(double)((used+i)%source_hz)/source_hz;
      source[i]=.095*sin(2.*3.14159265358979323846*1001.*t)+
                .021*cos(2.*3.14159265358979323846*3431.*t);
    }
    while(accepted<n){
      size_t in=n-accepted,out=512;
      sox_dsd_status_t rc=lsx_pcmdsd_process(ctx,source+accepted,&in,bits,&out);
      CHECK(rc==SOX_DSD_NEED_INPUT || rc==SOX_DSD_NEED_OUTPUT);
      CHECK(in||out);
      accepted+=in;
      emitted+=out;
      {const unsigned char *bytes=(const unsigned char *)bits;
       for(size_t j=0;j<out*sizeof(*bits);j++){
         hash^=bytes[j];hash*=1099511628211ULL;
       }}
    }
    used+=n;
  }
  for(;;){
    size_t out=512;
    sox_dsd_status_t rc=lsx_pcmdsd_finish(ctx,bits,&out);
    CHECK(rc==SOX_DSD_DONE || rc==SOX_DSD_NEED_OUTPUT);
    emitted+=out;
    {const unsigned char *bytes=(const unsigned char *)bits;
     for(size_t j=0;j<out*sizeof(*bits);j++){
       hash^=bytes[j];hash*=1099511628211ULL;
     }}
    if(rc==SOX_DSD_DONE)break;
  }
  t1=now();
  CHECK(lsx_pcmdsd_report_get(ctx,&report)==SOX_DSD_OK);
  CHECK(report.failure==LSX_PCMDSD_NO_ERROR);
  {uint64_t expected;CHECK(lsx_dsd_count_convert(total,source_hz,hz,&expected));
   CHECK(emitted==expected && report.committed_frames==expected);}
  printf("{\"status\":\"PASS\",\"rate_hz\":%u,\"source_hz\":%u,"
    "\"source_frames\":%zu,\"native_frames\":%" PRIu64 ","
    "\"wall_seconds\":%.9f,\"state0_peak\":%.9g,\"peak_scaled\":%.9g,"
    "\"native_digest_fnv64\":\"%016" PRIx64 "\"}\n",
    hz,source_hz,total,emitted,t1-t0,report.monitor.max_abs_state[0],
    report.peak,hash);
  lsx_pcmdsd_destroy(ctx);
}

/* Export the actual PRIVATE FIR cascade at any intermediate clock, including
 * wideband DSD1024 R=1411200 Hz (not a public PCM output promise).
 * Input is exact 0/1 bytes, output is binary64. Independent Python generates
 * source bits and mathematical FIR reference, NOT this test executable. */
static int export_fir(uint32_t hz,int profile,unsigned channels,size_t frames)
{
  lsx_dsd_reconstruction *ctx=NULL;
  sox_sample_t *bits;double *out;
  size_t used=0,written=0;
  CHECK((hz==high_rates[0]||hz==high_rates[1]) && channels>0 && channels<=6);
  CHECK((profile==0||profile==1) && frames>0 && frames<=500000);
  CHECK(frames<=SIZE_MAX/channels);
  bits=malloc(frames*channels*sizeof(*bits));out=malloc(256*channels*sizeof(*out));
  CHECK(bits && out);
  for(size_t i=0;i<frames*channels;i++){
    int c=getchar();CHECK(c==0 || c==1);
    bits[i]=c?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
  }
  CHECK(getchar()==EOF);
  CHECK(lsx_dsd_reconstruction_create_kernel(hz,
      profile?LSX_DSD_PROFILE_WIDEBAND:LSX_DSD_PROFILE_MASTERING,
      channels,"scalar",&ctx)==SOX_DSD_OK);
  while(used<frames){
    size_t take=frames-used;if(take>233)take=233;
    size_t done=0;
    while(done<take){
      size_t in=take-done,cap=256;
      sox_dsd_status_t rc=lsx_dsd_reconstruction_process(ctx,
        bits+(used+done)*channels,&in,out,&cap);
      CHECK(rc==SOX_DSD_NEED_INPUT || rc==SOX_DSD_NEED_OUTPUT);
      CHECK(in||cap);
      CHECK(fwrite(out,channels*sizeof(double),cap,stdout)==cap);
      done+=in;written+=cap;
    }
    used+=take;
  }
  for(;;){
    size_t cap=256;
    sox_dsd_status_t rc=lsx_dsd_reconstruction_finish(ctx,out,&cap);
    CHECK(rc==SOX_DSD_NEED_OUTPUT || rc==SOX_DSD_DONE);
    CHECK(fwrite(out,channels*sizeof(double),cap,stdout)==cap);
    written+=cap;
    if(rc==SOX_DSD_DONE)break;
  }
  {lsx_dsd_reconstruction_info info;uint64_t expected;
   CHECK(lsx_dsd_reconstruction_info_get(ctx,&info)==SOX_DSD_OK);
   /* Private reconstruction flushes the final incomplete decimation window.
    * The public decoder applies its independent rounded-length contract. */
   CHECK(info.factor>0);
   expected=frames/info.factor+(frames%info.factor!=0);
   CHECK(written==expected);
   fprintf(stderr,"P17_EXPORT_OK native=%u pcm=%u channels=%u frames=%zu out=%zu\n",
     hz,info.intermediate_hz,channels,frames,written);}
  lsx_dsd_reconstruction_destroy(ctx);free(bits);free(out);return 0;
}

int main(int argc,char **argv)
{
  if(argc==1 || !strcmp(argv[1],"unit")){unit();return 0;}
  if(!strcmp(argv[1],"matrix")){matrix();return 0;}
  if(!strcmp(argv[1],"encode")){encode();return 0;}
  if(!strcmp(argv[1],"encode-export")&&argc==4){
    return encode_export((uint32_t)strtoul(argv[2],NULL,10),
       (size_t)strtoull(argv[3],NULL,10));
  }
  if(!strcmp(argv[1],"export")&&argc==6){
    return export_fir((uint32_t)strtoul(argv[2],NULL,10),atoi(argv[3]),
       (unsigned)strtoul(argv[4],NULL,10),(size_t)strtoull(argv[5],NULL,10));
  }
  if(!strcmp(argv[1],"bench-encode")&&argc==4){
    bench_encode((uint32_t)strtoul(argv[2],NULL,10),atof(argv[3]));
    return 0;
  }
  if(!strcmp(argv[1],"bench")&&argc==7){
    bench((uint32_t)strtoul(argv[2],NULL,10),atoi(argv[3]),
         (unsigned)strtoul(argv[4],NULL,10),atoi(argv[5]),atof(argv[6]));
    return 0;
  }
  fputs("usage: dsd_test_p17 unit|matrix|encode|bench HZ PROFILE CHANNELS PACKED DURATION\n",stderr);
  return 2;
}
