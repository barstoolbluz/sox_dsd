/* P16 production-link qualification: native reader ownership, one cursor,
 * physical layout, partial byte and exact DSP/ISA parity. This test has its
 * own fixture chronology and bit-addressing oracle, not production helpers. */
#include "sox_dsd.h"
#include "dsd.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <limits.h>
#include <unistd.h>

static unsigned long checks, passed, skipped;
#define CHECK(x) do { ++checks; if (!(x)) { \
  fprintf(stderr,"P16 FAIL line %d: %s\n",__LINE__,#x); exit(1); \
} } while (0)

static int bit_at(size_t frame,unsigned channel)
{
  uint64_t v=((uint64_t)frame*0x9e3779b97f4a7c15ULL) ^
      ((uint64_t)(channel+1)*0xbf58476d1ce4e5b9ULL);
  v^=v>>30; v*=0xbf58476d1ce4e5b9ULL;
  v^=v>>27; v*=0x94d049bb133111ebULL;
  v^=v>>31;
  return (int)(v&1);
}
static sox_sample_t sign_bit(size_t frame,unsigned channel)
{ return bit_at(frame,channel)?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX; }

static void file_write(const char *file,unsigned channels,size_t frames,uint32_t rate)
{
  sox_signalinfo_t sig={0};
  sox_encodinginfo_t enc={0};
  sox_format_t *ft;
  sox_sample_t *bits;
  size_t j;
  sig.rate=rate;sig.channels=channels;sig.precision=1;
  sig.length=frames*channels;
  sox_init_encodinginfo(&enc);
  enc.encoding=SOX_ENCODING_DSD;enc.bits_per_sample=1;
  ft=sox_open_write(file,&sig,&enc,NULL,NULL,NULL);
  CHECK(ft);
  /* Chunk writes: large benchmark fixtures must never require an entire
   * native-rate stream of expanded int32 samples in memory. */
  {
    const size_t chunk=4096;
    bits=malloc(chunk*channels*sizeof(*bits));CHECK(bits);
    for(j=0;j<frames;) {
      size_t count=frames-j<chunk?frames-j:chunk;
      for(size_t n=0;n<count;n++)for(unsigned c=0;c<channels;c++)
        bits[n*channels+c]=sign_bit(j+n,c);
      CHECK(sox_write(ft,bits,count*channels)==count*channels);
      j+=count;
    }
  }
  CHECK(sox_close(ft)==SOX_SUCCESS);
  free(bits);
}

/* Adapt a valid LSB DSF fixture to a physically MSB-first fixture. The
 * reference bits remain unchanged, but the on-disk bytes are reversed. */
static unsigned reverse(unsigned n)
{
  unsigned v=0;
  for(unsigned i=0;i<8;i++) {v=(v<<1)|(n&1);n>>=1;}
  return v;
}
static void msb_dsf(const char *input,const char *output)
{
  FILE *a=fopen(input,"rb"),*b=fopen(output,"wb");
  long size;
  unsigned char *buf;
  CHECK(a && b);
  CHECK(!fseek(a,0,SEEK_END));size=ftell(a);CHECK(size>=92);
  CHECK(!fseek(a,0,SEEK_SET));buf=malloc((size_t)size);CHECK(buf);
  CHECK(fread(buf,1,(size_t)size,a)==(size_t)size);
  /* bps at offset 60, native little-endian uint32; data starts at 92. */
  CHECK(buf[60]==1 && buf[61]==0 && buf[62]==0 && buf[63]==0);
  buf[60]=8;
  for(long i=92;i<size;i++)buf[i]=(unsigned char)reverse(buf[i]);
  CHECK(fwrite(buf,1,(size_t)size,b)==(size_t)size);
  CHECK(!fclose(a) && !fclose(b));free(buf);
}

static int reference_bit(const sox_dsd_packed_block_t *b,size_t f,unsigned c)
{
  size_t bit=f+b->bit_offset;
  size_t address=c*b->channel_stride+(bit/8)*b->byte_stride;
  unsigned shift=b->bit_order==SOX_DSD_PACKED_MSB?7-(bit%8):bit%8;
  CHECK(address<b->bytes);
  return (b->data[address]>>shift)&1;
}
static void reader_check(const char *path,unsigned channels,size_t frames,
    int planar,unsigned physical_order)
{
  static const size_t request[]={1,2,7,8,9,17,127,512,4096,8192};
  sox_format_t *f;
  sox_dsd_packed_block_t b;
  size_t j,offset,cap;
  unsigned sample_modes=0;
  for(offset=0;offset<8;offset++)for(size_t t=0;t<sizeof(request)/sizeof(*request);t++) {
    size_t cursor=offset,iterations=0;
    cap=request[t];
    f=sox_open_read(path,NULL,NULL,NULL);CHECK(f);
    CHECK(f->signal.channels==channels);
    CHECK(f->signal.length==frames*channels);
    CHECK(sox_dsd_packed_supported(f));
    CHECK(sox_seek(f,offset*channels,SOX_SEEK_SET)==SOX_SUCCESS);
    sox_dsd_packed_block_init(&b);
    while(cursor<frames) {
      sox_dsd_status_t st=sox_dsd_read_packed(f,cap,&b);
      CHECK(st==SOX_DSD_OK && b.data && b.frames && b.frames<=cap);
      CHECK(b.channels==channels && b.size==sizeof(b) && b.version==1);
      CHECK(b.bit_offset<8 && b.last_valid_bits>=1 && b.last_valid_bits<=8);
      CHECK(b.last_valid_bits==(b.bit_offset+b.frames-1)%8+1);
      CHECK(b.bit_order==(planar?SOX_DSD_PACKED_LSB:SOX_DSD_PACKED_MSB));
      CHECK(b.channel_stride==(planar?4096u:1u));
      CHECK(b.byte_stride==(planar?1u:channels));
      for(j=0;j<b.frames;j++)for(unsigned c=0;c<channels;c++)
        CHECK(reference_bit(&b,j,c)==bit_at(cursor+j,c));
      cursor+=b.frames;
      CHECK(f->olength==cursor*channels);
      CHECK(++iterations<frames+20);
      ++passed;
    }
    CHECK(sox_dsd_read_packed(f,1,&b)==SOX_DSD_DONE);
    CHECK(f->olength==frames*channels);
    CHECK(sox_close(f)==SOX_SUCCESS);
  }
  /* A packed handle refuses the original API, preserving its position. */
  f=sox_open_read(path,NULL,NULL,NULL);CHECK(f);
  sox_dsd_packed_block_init(&b);
  CHECK(sox_dsd_read_packed(f,1,&b)==SOX_DSD_OK);
  CHECK(f->olength==channels);
  {
    sox_sample_t scratch[64];
    CHECK(sox_read(f,scratch,channels)==0);
    CHECK(f->sox_errno==SOX_EINVAL && f->olength==channels);
    CHECK(sox_seek(f,0,SOX_SEEK_SET)==SOX_SUCCESS);
    CHECK(sox_read(f,scratch,channels)==channels);
    for(unsigned c=0;c<channels;c++)CHECK(scratch[c]==sign_bit(0,c));
    CHECK(sox_dsd_read_packed(f,1,&b)==SOX_DSD_BAD_ARGUMENT);
    CHECK(f->olength==channels);
    CHECK(sox_seek(f,7*channels,SOX_SEEK_SET)==SOX_SUCCESS);
    CHECK(sox_dsd_read_packed(f,1,&b)==SOX_DSD_OK);
    CHECK(b.bit_offset==7 && b.frames==1);
    CHECK(reference_bit(&b,0,0)==bit_at(7,0));
    CHECK(sox_seek(f,0,SOX_SEEK_SET)==SOX_SUCCESS);
    CHECK(sox_dsd_read_packed(f,0,&b)==SOX_DSD_NEED_OUTPUT);
    CHECK(f->olength==0);
    CHECK(sox_read(f,scratch,channels)==channels);
    sample_modes++;
  }
  CHECK(sox_close(f)==SOX_SUCCESS);
  CHECK(sample_modes==1);
  (void)physical_order;
}

/* Pack a synthetic native stream in either legitimate physical layout with
 * every start-bit offset; this generator is independent of reader code. */
static unsigned char *make_packed(sox_dsd_packed_block_t *b,
    size_t frames,unsigned channels,unsigned offset,int planar)
{
  size_t nbytes=(offset+frames+7)/8;
  size_t count=nbytes*channels;
  unsigned char *buf=calloc(count,1); CHECK(buf);
  sox_dsd_packed_block_init(b);
  b->data=buf;b->bytes=count;b->frames=frames;b->channels=channels;
  b->bit_offset=offset;
  b->last_valid_bits=(unsigned)((offset+frames-1)%8+1);
  b->channel_stride=planar?nbytes:1;
  b->byte_stride=planar?1:channels;
  b->bit_order=planar?SOX_DSD_PACKED_LSB:SOX_DSD_PACKED_MSB;
  for(size_t f=0;f<frames;f++)for(unsigned c=0;c<channels;c++) {
    size_t n=offset+f;
    size_t at=planar?c*nbytes+n/8:(n/8)*channels+c;
    unsigned shift=planar?n%8:7-n%8;
    if(bit_at(f,c))buf[at]|=1u<<shift;
  }
  return buf;
}

typedef struct {double *pcm;size_t count;} run_result;
static run_result decode(uint32_t native,uint32_t rate,
    sox_dsd_decode_profile_t profile,unsigned channels,const char *tier,
    const sox_dsd_packed_block_t *packed, int direct_packed, int *unsupported)
{
  const size_t n=packed->frames;
  const size_t capacity=n*channels;
  size_t consumed=0,made=0,iteration=0;
  sox_dsd_decode_options_t opt;
  sox_dsd_decoder_t *ctx=NULL;
  sox_sample_t *expanded=malloc(capacity*sizeof(*expanded));
  run_result result={0};
  sox_dsd_status_t st;
  CHECK(expanded);
  result.pcm=calloc(capacity+32,sizeof(*result.pcm));CHECK(result.pcm);
  for(size_t j=0;j<n;j++)for(unsigned c=0;c<channels;c++)
    expanded[j*channels+c]=sign_bit(j,c);
  sox_dsd_decode_options_init_extended(&opt);
  opt.native_hz=native;opt.output_hz=rate;opt.channels=channels;
  opt.profile=profile;opt.kernel_fir=tier;
  st=sox_dsd_decoder_create(&opt,&ctx);
  if(st==SOX_DSD_UNSUPPORTED) {
    *unsupported=1;free(result.pcm);result.pcm=NULL;free(expanded);
    return result;
  }
  CHECK(st==SOX_DSD_OK && ctx);
  while(consumed<n) {
    size_t input=n-consumed,output=(iteration%13)+1;
    if(input>47)input=47;
    st=direct_packed ? sox_dsd_decoder_process_packed(ctx,packed,consumed,
        &input,result.pcm+made*channels,&output) :
        sox_dsd_decoder_process(ctx,expanded+consumed*channels,
            &input,result.pcm+made*channels,&output);
    CHECK(st==SOX_DSD_NEED_INPUT || st==SOX_DSD_NEED_OUTPUT);
    CHECK(input || output);
    consumed+=input;made+=output;
    CHECK(made*channels<=capacity+32);
    CHECK(++iteration<100000);
  }
  for(;;) {
    size_t output=1+iteration%13;
    st=sox_dsd_decoder_finish(ctx,result.pcm+made*channels,&output);
    CHECK(st==SOX_DSD_DONE || st==SOX_DSD_NEED_OUTPUT);
    made+=output;CHECK(made*channels<=capacity+32);
    if(st==SOX_DSD_DONE)break;
    CHECK(++iteration<100000);
  }
  result.count=made;
  {
    uint64_t expected;
    CHECK(lsx_dsd_count_convert(n,native,rate,&expected));
    CHECK(result.count==expected);
  }
  sox_dsd_decoder_destroy(ctx);
  free(expanded);
  return result;
}

/* `decode` selects packed on a non-zero byte_stride; select the conventional
 * API with a descriptor shadow that retains the frame count only. */
static void matrix_check(void)
{
  const uint32_t rates[]={2822400u,5644800u,11289600u};
  const uint32_t pcm[]={44100u,48000u,88200u,96000u,176400u,
      192000u,352800u,384000u,705600u};
  const sox_dsd_decode_profile_t profiles[]={
    SOX_DSD_DECODE_MASTERING,SOX_DSD_DECODE_WIDEBAND,SOX_DSD_DECODE_MASTERING_V2};
  const char *tiers[]={"scalar","sse2","avx1","avx2","avx512"};
  for(unsigned r=0;r<3;r++)for(unsigned pr=0;pr<3;pr++)
   for(size_t out=0;out<sizeof(pcm)/sizeof(pcm[0]);out++)for(unsigned k=0;k<5;k++)
    for(unsigned planar=0;planar<2;planar++)for(unsigned offset=0;offset<8;offset++) {
      sox_dsd_packed_block_t b;
      unsigned ch=(k%2)?6:2;
      int unavailable=0,unavailable_packed=0;
      unsigned char *raw=make_packed(&b,1031,ch,offset,planar);
      run_result first,second;
      first=decode(rates[r],pcm[out],profiles[pr],ch,tiers[k],&b,0,&unavailable);
      second=decode(rates[r],pcm[out],profiles[pr],ch,tiers[k],&b,1,&unavailable_packed);
      CHECK(unavailable==unavailable_packed);
      if(!unavailable) {
        CHECK(first.count==second.count);
        CHECK(!memcmp(first.pcm,second.pcm,first.count*ch*sizeof(double)));
        passed++;
      } else skipped++;
      free(first.pcm);free(second.pcm);free(raw);
    }
  fprintf(stdout,"P16 DSP matrix: %lu passed %lu unsupported; %lu assertions\n",
      passed,skipped,checks);
}

/* Validate the public packed decoder's structural rejection path on
 * independent malformed descriptors, without trusting native handlers. */
static void invalid_descriptor_check(void)
{
  sox_dsd_packed_block_t b,invalid;
  uint8_t *raw=make_packed(&b,19,2,7,1);
  sox_dsd_decode_options_t opt;
  double output[64]={0};
  sox_dsd_decoder_t *ctx;
  size_t consumed,capacity;
  unsigned attempt;
  for(attempt=0;attempt<10;attempt++) {
    sox_dsd_decode_options_init_extended(&opt);
    opt.native_hz=2822400;opt.output_hz=88200;opt.channels=2;
    CHECK(sox_dsd_decoder_create(&opt,&ctx)==SOX_DSD_OK);
    invalid=b;
    switch(attempt) {
    case 0: invalid.bytes=1;break;
    case 1: invalid.byte_stride=0;break;
    case 2: invalid.channel_stride=0;break;
    case 3: invalid.bit_offset=8;break;
    case 4: invalid.last_valid_bits=0;break;
    case 5: invalid.last_valid_bits=8;break;
    case 6: invalid.version=2;break;
    case 7: invalid.bit_order=0;break;
    case 8: invalid.channels=3;break;
    case 9: invalid.frames=SIZE_MAX;break;
    }
    consumed=19;capacity=32;
    CHECK(sox_dsd_decoder_process_packed(ctx,&invalid,0,
        &consumed,output,&capacity)==SOX_DSD_BAD_ARGUMENT);
    CHECK(consumed==0 && capacity==0);
    sox_dsd_decoder_destroy(ctx);
  }
  free(raw);
  fprintf(stdout,"P16 malformed descriptor gate: %u rejected\n",attempt);
}

static void reader_suite(const char *directory)
{
  char path[1024],msb[1024],name[1024];
  for(unsigned c=1;c<=6;c+=c==1?1:4) {
    size_t n=32773;
    snprintf(path,sizeof(path),"%s/p16-%u.dsf",directory,c);
    snprintf(msb,sizeof(msb),"%s/p16-msb-%u.dsf",directory,c);
    file_write(path,c,n,2822400);
    msb_dsf(path,msb);
    reader_check(path,c,n,1,1);
    reader_check(msb,c,n,1,8);
    n=32776;
    snprintf(name,sizeof(name),"%s/p16-%u.dff",directory,c);
    file_write(name,c,n,2822400);
    reader_check(name,c,n,0,8);
  }
  fprintf(stdout,"P16 physical readers: %lu packed blocks verified; %lu assertions\n",passed,checks);
}
int main(int argc,char **argv)
{
  char directory[]="/tmp/sox_p16_XXXXXX";
  if(sox_init()!=SOX_SUCCESS) {fprintf(stderr,"sox_init failed\n");return 2;}
  if(argc>=2 && !strcmp(argv[1],"matrix")) matrix_check();
  else if(argc>=2 && !strcmp(argv[1],"fixtures") && argc==3) {
    for(unsigned c=1;c<=6;c+=c==1?1:4) {
      char path[1024];
      for(unsigned r=0;r<3;r++)for(unsigned type=0;type<2;type++) {
        snprintf(path,sizeof(path),"%s/p16-%u-%u.%s",argv[2],c,
            2822400u<<r,type?"dff":"dsf");
        file_write(path,c,32776,2822400u<<r);
      }
    }
  } else if(argc==6 && !strcmp(argv[1],"fixture")) {
    char *end;
    unsigned long rate=strtoul(argv[3],&end,10);CHECK(*end=='\0');
    unsigned long ch=strtoul(argv[4],&end,10);CHECK(*end=='\0');
    unsigned long long n=strtoull(argv[5],&end,10);CHECK(*end=='\0');
    CHECK((rate==2822400ul || rate==5644800ul || rate==11289600ul) &&
        ch>=1 && ch<=6 && n>0 && n<=100000000ULL);
    CHECK(n <= SIZE_MAX / ch);
    file_write(argv[2],(unsigned)ch,(size_t)n,(uint32_t)rate);
  } else if(argc==4 && !strcmp(argv[1],"simulate")) {
    /* Simulated DSD512/1024 pack transport; not a decoder or writer test. */
    char *end;
    unsigned long rate=strtoul(argv[2],&end,10);CHECK(*end=='\0');
    unsigned long long n=strtoull(argv[3],&end,10);CHECK(*end=='\0');
    CHECK((rate==22579200ul || rate==45158400ul) && n>0 && n<=25000000ULL);
    uint64_t checksum=0;
    for(unsigned planar=0;planar<2;planar++) {
      sox_dsd_packed_block_t b;
      unsigned char *buffer=make_packed(&b,(size_t)n,2,7,(int)planar);
      for(size_t f=0;f<n;f++)for(unsigned c=0;c<2;c++) {
        CHECK(reference_bit(&b,f,c)==bit_at(f,c));
        checksum+=(unsigned)reference_bit(&b,f,c);
      }
      free(buffer);
    }
    fprintf(stdout,"P16 simulated clock %lu; frames %llu; channels 2; "
        "layouts 2; verified payload bits %llu; checksum %llu\n",
        rate,n,n*4ULL,(unsigned long long)checksum);
  } else {
    char *root=mkdtemp(directory);
    CHECK(root);
    reader_suite(root);
    invalid_descriptor_check();
  }
  CHECK(sox_quit()==SOX_SUCCESS);
  return 0;
}
