/* Private contract and primitive probe; never installed. Tests direct source
 * (not the historical int32 SoX engine), with an independent Python oracle. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "pcm_f64.h"
#include <float.h>
#include <fenv.h>
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(HAVE_PTHREAD_H)
#include <pthread.h>
#endif
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
#include <xmmintrin.h>
#endif

static unsigned checks = 0;
#define CHECK(x) do { ++checks; if (!(x)) { \
  fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; \
} } while (0)

static double from_bits(uint64_t u)
{
  double d;
  memcpy(&d, &u, sizeof(d));
  return d;
}
static uint64_t to_bits(const double *d)
{
  uint64_t u;
  memcpy(&u, d, sizeof(u));
  return u;
}

static int selftest(void)
{
  pcm_f64_format f;
  pcm_f64_failure latch = { PCM_F64_OK };
  size_t n = 0, b = 0, bad = SIZE_MAX;
  uint64_t cumulative = 0;
  double in[5], out[5], dst_copy[5], norm;
  int32_t q;
  bool sat, excursion;
  pcm_f64_word_class kind;
  unsigned bits;

  CHECK(pcm_f64_format_init(NULL, 44100, 2, false, 0)==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_format_init(&f, 0, 2, false, 0)==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_format_init(&f, 44100, 0, false, 0)==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_format_init(&f, 44100, 65, false, 0)==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_format_init(&f, 44100, 2, true, 0)==PCM_F64_OK);
  CHECK(f.length_known && f.total_frames == 0);
  CHECK(pcm_f64_advance(&f,0,0,&cumulative)==PCM_F64_OK && cumulative==0);
  CHECK(pcm_f64_advance(&f,0,1,&cumulative)==PCM_F64_LIMIT);
  CHECK(pcm_f64_validate_input(&f,(pcm_f64_input){NULL,0})==PCM_F64_OK);
  CHECK(pcm_f64_validate_input(&f,(pcm_f64_input){in,1})==PCM_F64_LIMIT);
  CHECK(pcm_f64_validate_output(&f,(pcm_f64_output){NULL,0})==PCM_F64_OK);
  CHECK(pcm_f64_validate_output(&f,(pcm_f64_output){NULL,1})==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_format_init(&f, 44100, 2, false, UINT64_MAX)==PCM_F64_OK);
  CHECK(!f.length_known && f.total_frames==0);
  CHECK(pcm_f64_validate_input(&f,(pcm_f64_input){in,1})==PCM_F64_OK);
  CHECK(pcm_f64_validate_input(&f,(pcm_f64_input){NULL,1})==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_frame_storage(3,2,&n,&b)==PCM_F64_OK && n==6 && b==48);
  CHECK(pcm_f64_frame_storage(SIZE_MAX,2,&n,&b)==PCM_F64_LIMIT);
  CHECK(pcm_f64_frame_storage(SIZE_MAX/sizeof(double)+1,1,&n,&b)==PCM_F64_LIMIT);
  CHECK(pcm_f64_frame_storage(0,64,&n,&b)==PCM_F64_OK && n==0 && b==0);
  CHECK(pcm_f64_frame_storage(0,0,&n,&b)==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_count_samples(UINT64_MAX,2,&cumulative)==PCM_F64_LIMIT);
  CHECK(pcm_f64_count_samples(7,3,&cumulative)==PCM_F64_OK && cumulative==21);
  CHECK(pcm_f64_advance(&f,UINT64_MAX,1,&cumulative)==PCM_F64_LIMIT);
  CHECK(pcm_f64_advance(&f,UINT64_MAX-2,2,&cumulative)==PCM_F64_OK && cumulative==UINT64_MAX);
  CHECK(pcm_f64_latch(&latch,PCM_F64_NEED_OUTPUT)==PCM_F64_OK);
  CHECK(pcm_f64_latch(&latch,PCM_F64_IO)==PCM_F64_IO);
  CHECK(pcm_f64_latch(&latch,PCM_F64_OK)==PCM_F64_IO);
  CHECK(pcm_f64_latch(&latch,PCM_F64_ARGUMENT)==PCM_F64_IO);
  CHECK(pcm_f64_is_failure(PCM_F64_IO));
  CHECK(!pcm_f64_is_failure(PCM_F64_DONE));
  CHECK(!strcmp(pcm_f64_status_name(PCM_F64_NEED_INPUT),"NEED_INPUT"));
  CHECK(!strcmp(pcm_f64_status_name(PCM_F64_NEED_OUTPUT),"NEED_OUTPUT"));
  CHECK(!strcmp(pcm_f64_status_name(PCM_F64_DONE),"DONE"));
  CHECK(!strcmp(pcm_f64_status_name(PCM_F64_NUMERIC),"NUMERIC"));

  CHECK(pcm_f64_check_ieee_storage()==PCM_F64_OK);
  in[0]=from_bits(UINT64_C(0x8000000000000000)); /* negative zero */
  in[1]=from_bits(UINT64_C(0x0000000000000001)); /* min subnormal */
  in[2]=from_bits(UINT64_C(0xffefffffffffffff)); /* finite, -DBL_MAX */
  in[3]=from_bits(UINT64_C(0x3ff4000000000000)); /* +1.25 */
  in[4]=from_bits(UINT64_C(0x7fefffffffffffff)); /* +DBL_MAX */
  memset(out,0x5a,sizeof(out));
  memcpy(dst_copy,out,sizeof(out));
  CHECK(pcm_f64_copy_finite(out,in,5,&bad)==PCM_F64_OK && bad==SIZE_MAX);
  CHECK(!memcmp(in,out,sizeof(in)));
  CHECK(pcm_f64_copy_finite(in,in,5,&bad)==PCM_F64_OK);
  CHECK(to_bits(&in[0])==UINT64_C(0x8000000000000000));
  in[3]=from_bits(UINT64_C(0x7ff8000000000001)); /* qNaN */
  memcpy(out,dst_copy,sizeof(out));
  CHECK(pcm_f64_copy_finite(out,in,5,&bad)==PCM_F64_NUMERIC && bad==3);
  CHECK(!memcmp(out,dst_copy,sizeof(out)));
  CHECK(pcm_f64_classify(&in[3],&kind)==PCM_F64_OK && kind==PCM_F64_WORD_QNAN);
  in[3]=from_bits(UINT64_C(0x7ff0000000000001)); /* sNaN, do not evaluate */
  CHECK(pcm_f64_classify(&in[3],&kind)==PCM_F64_OK && kind==PCM_F64_WORD_SNAN);
  CHECK(pcm_f64_copy_finite(out,in,5,&bad)==PCM_F64_NUMERIC && bad==3);
  in[3]=from_bits(UINT64_C(0xfff0000000000000));
  CHECK(pcm_f64_classify(&in[3],&kind)==PCM_F64_OK && kind==PCM_F64_WORD_INFINITY);
  CHECK(pcm_f64_copy_finite(NULL,NULL,0,&bad)==PCM_F64_OK);
  in[3]=from_bits(UINT64_C(0x3ff4000000000000));

  CHECK(pcm_f64_fixed_gain(out,in,5,1.0,&bad)==PCM_F64_OK);
  CHECK(!memcmp(out,in,sizeof(in)) && bad==SIZE_MAX);
  CHECK(pcm_f64_fixed_gain(out,in,5,0.0,&bad)==PCM_F64_OK);
  CHECK(to_bits(&out[0])==UINT64_C(0x8000000000000000));
  CHECK(to_bits(&in[0])==UINT64_C(0x8000000000000000));
  CHECK(pcm_f64_fixed_gain(out,in,5,2.0,&bad)==PCM_F64_NUMERIC && bad==2);
  CHECK(pcm_f64_fixed_gain(NULL,NULL,0,1.0,&bad)==PCM_F64_OK);
  CHECK(pcm_f64_fixed_gain(out,in,5,from_bits(UINT64_C(0x7ff0000000000001)),&bad)==PCM_F64_NUMERIC);
  CHECK(pcm_f64_nominal_excursion(-1.0,&excursion)==PCM_F64_OK && !excursion);
  CHECK(pcm_f64_nominal_excursion(-1.01,&excursion)==PCM_F64_OK && excursion);
  CHECK(pcm_f64_nominal_excursion(1.0,&excursion)==PCM_F64_OK && excursion);
  CHECK(pcm_f64_nominal_excursion(0.999,&excursion)==PCM_F64_OK && !excursion);

  for (bits=8;bits<=32;bits+=8) {
    int32_t one = (int32_t)(1u<<(bits-2));
    CHECK(pcm_f64_normalize_signed(-one,bits,&norm)==PCM_F64_OK && norm==-0.5);
    CHECK(pcm_f64_normalize_signed(one,bits,&norm)==PCM_F64_OK && norm==0.5);
    CHECK(pcm_f64_quantize_int(norm,bits,&q,&sat)==PCM_F64_OK && !sat);
    CHECK(q==INT32_C(0x40000000));
    CHECK(pcm_f64_quantize_int(-1.0,bits,&q,&sat)==PCM_F64_OK && !sat && q==INT32_MIN);
    CHECK(pcm_f64_quantize_int(1.0,bits,&q,&sat)==PCM_F64_OK && sat &&
          q==(int32_t)(((INT64_C(1) << (bits-1))-1) * (INT64_C(1) << (32-bits))));
  }
  CHECK(pcm_f64_normalize_signed(128,8,&norm)==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_normalize_signed(-129,8,&norm)==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_normalize_signed(1,12,&norm)==PCM_F64_ARGUMENT);
  CHECK(pcm_f64_normalize_u8(0,&norm)==PCM_F64_OK && norm==-1.0);
  CHECK(pcm_f64_normalize_u8(255,&norm)==PCM_F64_OK && norm==127.0/128.0);
  CHECK(pcm_f64_normalize_aligned32(INT32_MIN,&norm)==PCM_F64_OK && norm==-1.0);
  CHECK(pcm_f64_normalize_aligned32(INT32_MAX,&norm)==PCM_F64_OK && norm==(double)INT32_MAX/2147483648.0);
  CHECK(pcm_f64_quantize_int(nextafter(ldexp(1.0,-24),0.0),24,&q,&sat)==PCM_F64_OK && q==0);
  CHECK(pcm_f64_quantize_int(-ldexp(1.0,-24),24,&q,&sat)==PCM_F64_OK && q==-256);
  CHECK(pcm_f64_quantize_int(nextafter(ldexp(1.0,-32),0.0),32,&q,&sat)==PCM_F64_OK && q==0);
  CHECK(pcm_f64_quantize_int(nextafter(-1.0,-INFINITY),32,&q,&sat)==PCM_F64_OK && q==INT32_MIN && !sat);
  CHECK(pcm_f64_quantize_int(-1.0-ldexp(1.0,-32),32,&q,&sat)==PCM_F64_OK && q==INT32_MIN && sat);
  printf("SELFTEST assertions=%u status=PASS\n",checks);
  return 0;
}

/* Test control refusal without implicitly changing the controls. The FP mode
 * changed in this test is restored after the guard has returned. */
static int verify_environment_here(void)
{
  pcm_f64_status initial = pcm_f64_check_dsp_env();
  fenv_t saved;
  int original_round;
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
  unsigned int csr_original = _mm_getcsr(), csr;
  unsigned short cw_original, cw;
  __asm__ __volatile__("fnstcw %0" : "=m"(cw_original));
#endif
  CHECK(fegetenv(&saved)==0);
  original_round = fegetround();
#if PCM_F64_NATIVE_ENABLED
  CHECK(initial==PCM_F64_OK);
#else
  CHECK(initial==PCM_F64_UNSUPPORTED);
#endif
  CHECK(fesetround(FE_UPWARD)==0);
  CHECK(pcm_f64_check_dsp_env()!=PCM_F64_OK);
  CHECK(fegetround()==FE_UPWARD);
  CHECK(fesetround(FE_DOWNWARD)==0);
  CHECK(pcm_f64_check_dsp_env()!=PCM_F64_OK);
  CHECK(fegetround()==FE_DOWNWARD);
  CHECK(fesetround(FE_TOWARDZERO)==0);
  CHECK(pcm_f64_check_dsp_env()!=PCM_F64_OK);
  CHECK(fegetround()==FE_TOWARDZERO);
  CHECK(fesetenv(&saved)==0);
  CHECK(fegetround()==original_round);
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
  /* Tests are host-specific; skip direct register mutations elsewhere rather
   * than pretending that portable fenv exposes FTZ/DAZ/trap-enable bits. */
  csr = csr_original | 0x8000u;  /* flush-to-zero */
  _mm_setcsr(csr);
  CHECK(pcm_f64_check_dsp_env()!=PCM_F64_OK);
  CHECK(_mm_getcsr()==csr);
  _mm_setcsr(csr_original);
  csr = csr_original | 0x0040u;  /* denormals-are-zero */
  _mm_setcsr(csr);
  CHECK(pcm_f64_check_dsp_env()!=PCM_F64_OK);
  CHECK(_mm_getcsr()==csr);
  _mm_setcsr(csr_original);
  csr = csr_original & ~0x0080u; /* unmask invalid exception */
  _mm_setcsr(csr);
  CHECK(pcm_f64_check_dsp_env()!=PCM_F64_OK);
  CHECK(_mm_getcsr()==csr);
  _mm_setcsr(csr_original);
  cw = cw_original & (unsigned short)~0x0001u; /* x87 invalid trap */
  __asm__ __volatile__("fldcw %0" : : "m"(cw));
  CHECK(pcm_f64_check_dsp_env()!=PCM_F64_OK);
  __asm__ __volatile__("fnstcw %0" : "=m"(cw));
  CHECK(cw==(unsigned short)(cw_original & ~0x0001u));
  __asm__ __volatile__("fldcw %0" : : "m"(cw_original));
  CHECK(_mm_getcsr()==csr_original);
#endif
  /* Acquired exception flags are permitted when traps remain masked. */
  CHECK(feclearexcept(FE_ALL_EXCEPT)==0);
  CHECK(feraiseexcept(FE_INEXACT | FE_UNDERFLOW)==0);
  CHECK(pcm_f64_check_dsp_env()==initial);
  CHECK(fesetenv(&saved)==0);
#if (defined(__i386__) || defined(__x86_64__)) && defined(__SSE2__)
  CHECK(_mm_getcsr()==csr_original);
  __asm__ __volatile__("fnstcw %0" : "=m"(cw));
  CHECK(cw==cw_original);
#endif
  /* Bitwise copies are unaffected even when DSP controls are rejected. */
  {
    double v=from_bits(UINT64_C(0x8000000000000001)), out=0.0;
    int old=fegetround();
    CHECK(fesetround(FE_DOWNWARD)==0);
    CHECK(pcm_f64_copy_finite(&out,&v,1,NULL)==PCM_F64_OK);
    CHECK(to_bits(&out)==to_bits(&v));
    CHECK(fegetround()==FE_DOWNWARD);
    CHECK(fesetround(old)==0);
  }
  CHECK(pcm_f64_check_dsp_env()==initial);
  return 0;
}

#if defined(HAVE_PTHREAD_H)
static void *worker(void *arg)
{
  int *rc = (int *)arg;
  *rc = verify_environment_here();
  return NULL;
}
#endif

static int environment_test(void)
{
  int rc;
  CHECK(verify_environment_here()==0);
#if defined(HAVE_PTHREAD_H)
  {
    pthread_t worker_ids[3];
    int worker_rc[3]={-1,-1,-1};
    unsigned i;
    /* Serialize test threads: the assertion counter is not synchronized,
     * and worker FENV isolation is the property under examination. */
    for (i=0;i<3;++i) {
      CHECK(pthread_create(&worker_ids[i],NULL,worker,&worker_rc[i])==0);
      CHECK(pthread_join(worker_ids[i],NULL)==0 && worker_rc[i]==0);
    }
    printf("ENV workers=3 ");
  }
#else
  printf("ENV workers=UNSUPPORTED ");
#endif
  rc=pcm_f64_check_dsp_env();
  printf("status=%s assertions=%u\n",pcm_f64_status_name(rc),checks);
  return 0;
}

static int stream(void)
{
  char line[256], word[32];
  unsigned bits;
  unsigned long long uword;
  int signed_value;
  unsigned unsigned_value;
  unsigned long iterations = 0;
  while (fgets(line,sizeof(line),stdin)) {
    double value, gain, result;
    int32_t q;
    bool saturated, nominal;
    pcm_f64_status status = PCM_F64_ARGUMENT;
    pcm_f64_word_class kind;
    if (line[0]=='Q' && sscanf(line,"Q %u %31s",&bits,word)==2) {
      uword=strtoull(word,NULL,16); value=from_bits((uint64_t)uword);
      status=pcm_f64_quantize_int(value,bits,&q,&saturated);
      if (status==PCM_F64_OK) status=pcm_f64_nominal_excursion(value,&nominal);
      if (status==PCM_F64_OK) printf("Q %08" PRIx32 " %u %u\n",(uint32_t)q,(unsigned)saturated,(unsigned)nominal);
    } else if (line[0]=='N' && sscanf(line,"N %u %d",&bits,&signed_value)==2) {
      status=pcm_f64_normalize_signed((int32_t)signed_value,bits,&result);
      if (status==PCM_F64_OK) printf("N %016" PRIx64 "\n",to_bits(&result));
    } else if (line[0]=='U' && sscanf(line,"U %u",&unsigned_value)==1 && unsigned_value<256) {
      status=pcm_f64_normalize_u8((uint8_t)unsigned_value,&result);
      if (status==PCM_F64_OK) printf("U %016" PRIx64 "\n",to_bits(&result));
    } else if (line[0]=='A' && sscanf(line,"A %d",&signed_value)==1) {
      status=pcm_f64_normalize_aligned32((int32_t)signed_value,&result);
      if (status==PCM_F64_OK) printf("A %016" PRIx64 "\n",to_bits(&result));
    } else if (line[0]=='C' && sscanf(line,"C %31s",word)==1) {
      value=from_bits((uint64_t)strtoull(word,NULL,16));
      status=pcm_f64_classify(&value,&kind);
      if (status==PCM_F64_OK) printf("C %u\n",(unsigned)kind);
    } else if (line[0]=='G' && sscanf(line,"G %31s",word)==1) {
      /* gain and PCM payload are two exact hex words, not text floats. */
      char *second=strchr(line+2,' ');
      if (second) {
        unsigned long long g = strtoull(word,NULL,16);
        while (*second==' ') ++second;
        if (sscanf(second,"%llx",&uword)==1) {
          gain=from_bits((uint64_t)g);
          value=from_bits((uint64_t)uword);
          status=pcm_f64_fixed_gain(&result,&value,1,gain,NULL);
          if (status==PCM_F64_OK) printf("G %016" PRIx64 "\n",to_bits(&result));
        }
      }
    }
    if (status!=PCM_F64_OK) printf("ERR %s\n",pcm_f64_status_name(status));
    ++iterations;
  }
  if (ferror(stdin) || !iterations) {
    fprintf(stderr,"No input probes or a read error\n");
    return 2;
  }
  return 0;
}

int main(int argc, char **argv)
{
  if (argc!=2) {
    fprintf(stderr,"usage: pcm64_probe --selftest|--environment|--stream\n");
    return 2;
  }
  if (!strcmp(argv[1],"--selftest")) return selftest();
  if (!strcmp(argv[1],"--environment")) return environment_test();
  if (!strcmp(argv[1],"--stream")) return stream();
  fprintf(stderr,"Unknown probe command: %s\n",argv[1]);
  return 2;
}
