/* P17 private full-track DSF decode instrument; uninstalled, no capability flip.
 * Streaming planar DSF blocks and independent expanded/packed input mapping.
 * Any optional F64LE output is for off-line INDEPENDENT audio comparison.
 * This executable by itself is not independent media quality evidence. */
#define _POSIX_C_SOURCE 200809L
#include "sox_dsd.h"
#include "dsd_packed.h"
#include "dsd.h"
#include <float.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <time.h>

#define OUT_FRAMES 2048u
#define FNV_OFFSET UINT64_C(14695981039346656037)
#define FNV_PRIME UINT64_C(1099511628211)
static uint32_t le32(const unsigned char *x)
{ return (uint32_t)x[0]|(uint32_t)x[1]<<8|(uint32_t)x[2]<<16|(uint32_t)x[3]<<24; }
static uint64_t le64(const unsigned char *x)
{ return (uint64_t)le32(x)|((uint64_t)le32(x+4)<<32); }
static uint64_t hash_update(uint64_t v,const void *ptr,size_t n)
{
  const unsigned char *p=ptr;
  while(n--){v^=*p++;v*=FNV_PRIME;}
  return v;
}
static void fail(const char *s)
{ fprintf(stderr,"P17_DSF_FAIL: %s\n",s); }

int main(int argc,char **argv)
{
  FILE *in=NULL,*pcm=NULL;
  unsigned char h[92],*dsf=NULL;
  sox_sample_t *expanded=NULL;
  double *a=NULL,*b=NULL;
  sox_dsd_decoder_t *d=NULL,*e=NULL;
  sox_dsd_decode_options_t opt;
  struct stat st;
  uint64_t logical,filesize,declared_data,blocks,expected,consumed=0,produced=0;
  uint64_t input_hash=FNV_OFFSET,output_hash=FNV_OFFSET;
  uint32_t native,blocksize,bps,channels,dst;
  uint64_t blockbits,bytes_per_block;
  uint64_t over_90pct=0;
  long double power[6]={0},sum[6]={0};
  double peak[6]={0};
  unsigned profile;
  const char *kind,*kernel;
  struct timespec wall_start={0},wall_finish={0};
  struct rusage usage={0};
  int status=1;
  if(argc!=6 && argc!=7){
    fail("usage: dsd_test_p17_dsf input.dsf mastering|wideband destination_hz scalar|sse2|avx1|avx2|avx512 full [pcm.f64le]");
    return 2;
  }
  kind=argv[2];kernel=argv[4];
  if(strcmp(kernel,"scalar") && strcmp(kernel,"sse2") &&
     strcmp(kernel,"avx1") && strcmp(kernel,"avx2") && strcmp(kernel,"avx512")){
    fail("unsupported explicit kernel override");return 2;
  }
  if(!strcmp(kind,"mastering"))profile=SOX_DSD_DECODE_MASTERING;
  else if(!strcmp(kind,"wideband"))profile=SOX_DSD_DECODE_WIDEBAND;
  else {fail("unsupported profile");return 2;}
  {
    char *end=NULL;unsigned long v=strtoul(argv[3],&end,10);
    if(!end||*end||v>UINT32_MAX||!lsx_dsd_pcm_rate_supported((uint32_t)v)){
      fail("invalid destination PCM rate");return 2;
    }
    dst=(uint32_t)v;
  }
  if(strcmp(argv[5],"full")){fail("fifth argument must be full");return 2;}
  in=fopen(argv[1],"rb");
  if(!in){perror("open DSF");goto done;}
  if(fstat(fileno(in),&st)||st.st_size<92||!S_ISREG(st.st_mode)){
    fail("not a regular DSF file of required size");goto done;
  }
  if(fread(h,1,92,in)!=92){fail("truncated DSF header");goto done;}
  if(memcmp(h,"DSD ",4)||le64(h+4)!=28||memcmp(h+28,"fmt ",4)||
     le64(h+32)!=52||memcmp(h+80,"data",4)){
    fail("DSF chunk layout unsupported (requires DSD/fmt/data)");goto done;
  }
  filesize=le64(h+12);native=le32(h+56);channels=le32(h+52);
  bps=le32(h+60);logical=le64(h+64);blocksize=le32(h+72);
  declared_data=le64(h+84);
  if(filesize!=(uint64_t)st.st_size||
     (native!=22579200u&&native!=45158400u)||channels<1||channels>6||
     (bps!=1&&bps!=8)||!logical||blocksize!=4096||
     le32(h+40)!=1||le32(h+44)!=0){
    fail("DSF metadata/size/rate/format unsupported");goto done;
  }
  blockbits=(uint64_t)blocksize*8;
  blocks=logical/blockbits+(logical%blockbits!=0);
  bytes_per_block=(uint64_t)blocksize*channels;
  if(blocks>(UINT64_MAX-92)/bytes_per_block||
     declared_data!=12+blocks*bytes_per_block||
     92+blocks*bytes_per_block>filesize){
    fail("DSF data length/padding inconsistent with samples");goto done;
  }
  if(!lsx_dsd_count_convert(logical,native,dst,&expected)){
    fail("PCM length overflow");goto done;
  }
  dsf=malloc((size_t)bytes_per_block);
  expanded=malloc((size_t)blockbits*channels*sizeof(*expanded));
  a=malloc(OUT_FRAMES*channels*sizeof(*a));
  b=malloc(OUT_FRAMES*channels*sizeof(*b));
  if(!dsf||!expanded||!a||!b){fail("allocation failed");goto done;}
  if(argc==7){
    const uint16_t endian=1;
    if(*(const unsigned char *)&endian!=1||sizeof(double)!=8||
       DBL_MANT_DIG!=53||DBL_MAX_EXP!=1024){
      fail("F64LE export requires IEEE-754 binary64 on little-endian host");goto done;
    }
    pcm=fopen(argv[6],"wb");
    if(!pcm){perror("open PCM output");goto done;}
  }
  sox_dsd_decode_options_init_extended(&opt);
  opt.native_hz=native;opt.output_hz=dst;opt.channels=channels;
  opt.profile=profile;opt.kernel_fir=kernel;
  if(sox_dsd_decoder_create(&opt,&d)!=SOX_DSD_OK||!d||
     sox_dsd_decoder_create(&opt,&e)!=SOX_DSD_OK||!e){
    fail("private decoder unavailable");goto done;
  }
  if(clock_gettime(CLOCK_MONOTONIC,&wall_start)) {fail("no monotonic clock");goto done;}
  for(uint64_t block=0;block<blocks;block++){
    sox_dsd_packed_block_t pk;
    size_t frames=(size_t)(logical-consumed<blockbits?logical-consumed:blockbits);
    size_t offset=0;
    if(fread(dsf,1,(size_t)bytes_per_block,in)!=bytes_per_block){
      fail("truncated DSF channel block");goto done;
    }
    input_hash=hash_update(input_hash,dsf,(size_t)bytes_per_block);
    sox_dsd_packed_block_init(&pk);
    pk.data=dsf;pk.bytes=(size_t)bytes_per_block;pk.frames=frames;
    pk.channels=channels;pk.bit_offset=0;
    pk.last_valid_bits=(unsigned)((frames-1)%8+1);
    pk.byte_stride=1;pk.channel_stride=blocksize;
    pk.bit_order=bps==1?SOX_DSD_PACKED_LSB:SOX_DSD_PACKED_MSB;
    if(!lsx_dsd_packed_validate(&pk)){
      fail("invalid packed DSF descriptor");goto done;
    }
    for(size_t n=0;n<frames;n++)for(uint32_t c=0;c<channels;c++){
      size_t at=c*blocksize+n/8;
      unsigned shift=bps==1?(unsigned)(n%8):(unsigned)(7-n%8);
      expanded[n*channels+c]=(dsf[at]&(1u<<shift))?
          SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
    }
    while(offset<frames){
      size_t take_p=frames-offset,take_e=take_p;
      size_t out_p=OUT_FRAMES,out_e=OUT_FRAMES;
      sox_dsd_status_t r1=sox_dsd_decoder_process_packed(d,&pk,offset,
          &take_p,a,&out_p);
      sox_dsd_status_t r2=sox_dsd_decoder_process(e,expanded+offset*channels,
          &take_e,b,&out_e);
      if(r1!=r2||take_p!=take_e||out_p!=out_e||
         (r1!=SOX_DSD_NEED_INPUT&&r1!=SOX_DSD_NEED_OUTPUT)||
         (!take_p&&!out_p)||memcmp(a,b,out_p*channels*sizeof(double))){
        fail("expanded/packed PCM mismatch or decoder failed");goto done;
      }
      offset+=take_p;produced+=out_p;
      if(produced>expected){fail("too many PCM frames");goto done;}
      output_hash=hash_update(output_hash,a,out_p*channels*sizeof(double));
      if(pcm&&fwrite(a,channels*sizeof(double),out_p,pcm)!=out_p){
        fail("PCM output write failed");goto done;
      }
      for(size_t n=0;n<out_p;n++)for(uint32_t c=0;c<channels;c++){
        double x=a[n*channels+c],mag=fabs(x);
        if(!isfinite(x)){fail("nonfinite PCM sample");goto done;}
        if(mag>peak[c])peak[c]=mag;
        if(mag>.9)over_90pct++;
        power[c]+=(long double)x*x;sum[c]+=x;
      }
    }
    consumed+=frames;
  }
  for(;;){
    size_t out_p=OUT_FRAMES,out_e=OUT_FRAMES;
    sox_dsd_status_t r1=sox_dsd_decoder_finish(d,a,&out_p);
    sox_dsd_status_t r2=sox_dsd_decoder_finish(e,b,&out_e);
    if(r1!=r2||out_p!=out_e||
       (r1!=SOX_DSD_DONE&&r1!=SOX_DSD_NEED_OUTPUT)||
       (r1==SOX_DSD_NEED_OUTPUT&&!out_p)||
       memcmp(a,b,out_p*channels*sizeof(double))){
      fail("expanded/packed EOF mismatch or stalled flush");goto done;
    }
    produced+=out_p;
    if(produced>expected){fail("too many tail frames");goto done;}
    output_hash=hash_update(output_hash,a,out_p*channels*sizeof(double));
    if(pcm&&fwrite(a,channels*sizeof(double),out_p,pcm)!=out_p){
      fail("PCM tail write failed");goto done;
    }
    for(size_t n=0;n<out_p;n++)for(uint32_t c=0;c<channels;c++){
      double x=a[n*channels+c],mag=fabs(x);
      if(!isfinite(x)){fail("nonfinite tail PCM sample");goto done;}
      if(mag>peak[c])peak[c]=mag;
      if(mag>.9)over_90pct++;
      power[c]+=(long double)x*x;sum[c]+=x;
    }
    if(r1==SOX_DSD_DONE)break;
  }
  if(produced!=expected||consumed!=logical){fail("incorrect output duration");goto done;}
  if(clock_gettime(CLOCK_MONOTONIC,&wall_finish)||getrusage(RUSAGE_SELF,&usage)){
    fail("resource measurement unavailable");goto done;
  }
  if(pcm&&fflush(pcm)){fail("PCM flush error");goto done;}
  printf("{\"schema\":\"P17/dsf-private-full-file/1\",\"status\":\"PASS_FUNCTIONAL_ONLY\","
      "\"rate_hz\":%u,\"channels\":%u,\"bits_per_sample\":%u,"
      "\"profile\":\"%s\",\"destination_hz\":%u,"
      "\"kernel\":\"%s\",\"native_frames\":%" PRIu64 ","
      "\"pcm_frames\":%" PRIu64 ",\"packed_expanded_equal\":true,"
      "\"input_fnv64\":\"%016" PRIx64 "\",\"pcm_fnv64\":\"%016" PRIx64 "\","
      "\"samples_over_0_9\":%" PRIu64 ","
      "\"decode_wall_seconds\":%.9g,\"process_user_cpu_seconds\":%.9g,"
      "\"process_system_cpu_seconds\":%.9g,\"max_rss_kb_platform_reported\":%ld,"
      "\"channels_numeric\":[",
      native,channels,bps,kind,dst,kernel,logical,produced,input_hash,output_hash,over_90pct,
      (double)(wall_finish.tv_sec-wall_start.tv_sec)+
        (double)(wall_finish.tv_nsec-wall_start.tv_nsec)*1e-9,
      (double)usage.ru_utime.tv_sec+usage.ru_utime.tv_usec*1e-6,
      (double)usage.ru_stime.tv_sec+usage.ru_stime.tv_usec*1e-6,
      usage.ru_maxrss);
  for(uint32_t c=0;c<channels;c++){
    if(c)putchar(',');
    if(produced)
      printf("{\"channel\":%u,\"rms\":%.17g,\"dc\":%.17g,\"absolute_peak\":%.17g}",
          c,(double)sqrtl(power[c]/produced),(double)(sum[c]/produced),peak[c]);
    else
      printf("{\"channel\":%u,\"rms\":null,\"dc\":null,\"absolute_peak\":null}",c);
  }
  puts("]}");
  status=0;
done:
  sox_dsd_decoder_destroy(d);sox_dsd_decoder_destroy(e);
  free(dsf);free(expanded);free(a);free(b);
  if(pcm&&fclose(pcm))status=1;
  if(status&&argc==7)remove(argv[6]);
  if(in)fclose(in);
  return status;
}
