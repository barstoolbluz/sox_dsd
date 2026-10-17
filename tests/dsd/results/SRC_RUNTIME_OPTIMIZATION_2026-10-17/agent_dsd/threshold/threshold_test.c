/* Ordered production SRC regression.  Compile the real rate.c, then instantiate
 * the exact pre-optimization headers as independent reference functions.  The
 * reference bytes and their origin hashes are retained in reference/src_optimization.
 * Compare binary64 words, output counts, phase and retained FIFO data; no epsilon.
 * This test does not certify the original SRC response or FFT4G roundoff.
 */
#define lsx_rate_effect_fn src_opt_test_effect_fn
#define lsx_rate_f64_create src_opt_test_create
#define lsx_rate_f64_process src_opt_test_process
#define lsx_rate_f64_finish src_opt_test_finish
#define lsx_rate_f64_destroy src_opt_test_destroy
#include "/workspace/scratch/4dd8292178b8/sox_ng/src/rate.c"
#undef lsx_rate_effect_fn
#undef lsx_rate_f64_create
#undef lsx_rate_f64_process
#undef lsx_rate_f64_finish
#undef lsx_rate_f64_destroy
#include <fenv.h>
#include <float.h>
#include <inttypes.h>
#include <time.h>

#define FUNCTION reference_h8
#define CONVOLVE _ _ _ _ _ _ _ _
#define COEFS half_fir_coefs_8
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_half_fir.h"
#define FUNCTION reference_h9
#define CONVOLVE _ _ _ _ _ _ _ _ _
#define COEFS half_fir_coefs_9
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_half_fir.h"
#define FUNCTION reference_h10
#define CONVOLVE _ _ _ _ _ _ _ _ _ _
#define COEFS half_fir_coefs_10
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_half_fir.h"
#define FUNCTION reference_h11
#define CONVOLVE _ _ _ _ _ _ _ _ _ _ _
#define COEFS half_fir_coefs_11
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_half_fir.h"
#define FUNCTION reference_h12
#define CONVOLVE _ _ _ _ _ _ _ _ _ _ _ _
#define COEFS half_fir_coefs_12
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_half_fir.h"
#define FUNCTION reference_h13
#define CONVOLVE _ _ _ _ _ _ _ _ _ _ _ _ _
#define COEFS half_fir_coefs_13
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_half_fir.h"
#define FUNCTION reference_vpoly0
#define FIR_LENGTH p->n
#define CONVOLVE while (j < FIR_LENGTH) _
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_poly_fir0.h"
#define FUNCTION reference_U100_0
#define FIR_LENGTH U100_l
#define CONVOLVE poly_fir_convolve_U100
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_poly_fir0.h"
#define FUNCTION reference_u100_0
#define FIR_LENGTH u100_l
#define CONVOLVE poly_fir_convolve_u100
#include "/workspace/scratch/4dd8292178b8/sox_ng/tests/dsd/reference/src_optimization/rate_poly_fir0.h"

#define FUNCTION threshold2_vpoly0
#define FIR_LENGTH p->n
#define CONVOLVE while (j < FIR_LENGTH) _
#include "threshold2.h"

/* Test-only alternative: the same scalar dot product with exact quotient and
 * remainder scheduling, without pairing. It isolates the benefit of pairing
 * in the same executable. It is never installed as a production path. */
static void recurrence_vpoly0(stage_t *p, fifo_t *output_fifo)
{
  const double *input = stage_read_p(p);
  int num_in = stage_occupancy(p), i = 0;
  int max_num_out = 1 + num_in * p->out_in_ratio;
  double *output = lsx_fifo_reserve(output_fifo, max_num_out);
  div_t at = div(p->at.parts.integer, p->L);
  const div_t step = div(p->step.parts.integer, p->L);
  while (at.quot < num_in) {
    const double *s = input + at.quot;
    const double *h = p->shared->poly_fir_coefs + (size_t)p->n * at.rem;
    double sum = 0.;
    int j, carry;
    for (j = 0; j < p->n; ++j) sum += h[j] * s[j];
    output[i++] = sum;
    carry = at.rem >= p->L - step.rem;
    at.quot += step.quot + carry;
    at.rem += step.rem - carry * p->L;
  }
  assert(i <= max_num_out);
  lsx_fifo_trim_by(output_fifo, max_num_out - i);
  lsx_fifo_read(&p->fifo, at.quot, NULL);
  p->at.parts.integer = at.rem;
}

static uint64_t checks, cases, samples_compared, stream_cases, api_cases;
static const char *family = "setup";
static int detail_n, detail_L, detail_M, detail_phase, detail_size, detail_pattern;
static int original_rounding;

static void fail(const char *condition, unsigned line)
{
  fprintf(stderr, "SRC optimization line %u: %s; %s n=%d L=%d M=%d phase=%d "
      "size=%d pattern=%d rounding=%d\n", line, condition, family, detail_n,
      detail_L, detail_M, detail_phase, detail_size, detail_pattern, fegetround());
  exit(1);
}
#define CHECK(x) do { ++checks; if (!(x)) fail(#x, __LINE__); } while (0)

static void equal_samples(const double *a, const double *b, size_t n)
{
  CHECK(!n || memcmp(a, b, n * sizeof(*a)) == 0);
  samples_compared += n;
}

/* Values are constructed by binary64 words, so fixture creation does not depend
 * on the current rounding mode. Large finite operands stay far from overflow. */
static double value_at(size_t i, unsigned pattern)
{
  uint64_t word, sign = (uint64_t)(i & 1) << 63;
  uint64_t mix = ((uint64_t)i + UINT64_C(0x937b91a2)) * UINT64_C(0x9e3779b97f4a7c15);
  double result;
  switch (pattern % 6) {
    case 0: word = sign; break; /* Both signs of zero. */
    case 1: word = sign | (i % 3 ? UINT64_C(0x3fefffffffffffff) : UINT64_C(0x3ff0000000000000)); break;
    case 2: word = sign | UINT64_C(0x3ff0000000000000) | (i % 5 == 0); break;
    case 3: word = sign | (i % 3 ? (mix & UINT64_C(0x7ff)) + 1 : UINT64_C(0x0010000000000000)); break;
    case 4: word = sign | ((uint64_t)(i % 3 ? 523 : 1423) << 52) | (mix & UINT64_C(0x000fffffffffffff)); break;
    default: word = (mix & UINT64_C(0x8000000000000000)) |
        ((mix >> 11) & UINT64_C(0x000fffffffffffff)) | UINT64_C(0x3fe0000000000000); break;
  }
  memcpy(&result, &word, sizeof(result));
  return result;
}

static void exact_fifo(fifo_t *f, size_t count, size_t offset,
                       unsigned pattern, int impulse)
{
  size_t i, allocation = count + offset;
  memset(f, 0, sizeof(*f));
  f->item_size = sizeof(double);
  /* Non-null backing for a legal zero-item call avoids unrelated null-pointer
   * arithmetic in the inherited FIFO implementation. Positive spans are exact. */
  f->allocation = (allocation ? allocation : 1) * sizeof(double);
  f->data = malloc(f->allocation);
  CHECK(f->data != NULL);
  f->begin = offset * sizeof(double);
  f->end = (offset + count) * sizeof(double);
  for (i = 0; i < allocation; ++i)
    ((double *)f->data)[i] = value_at(i + 19, 5);
  for (i = 0; i < count; ++i)
    ((double *)f->data)[offset + i] = impulse >= 0 ?
        (i == (size_t)impulse ? 1. : 0.) : value_at(i, pattern);
}

static void stage_init(stage_t *p, rate_shared_t *shared, int n,
    int pairs, int L, int M, int phase)
{
  memset(p, 0, sizeof(*p));
  p->shared = shared;
  p->n = n;
  p->L = L;
  p->step.parts.integer = M;
  p->at.parts.integer = phase;
  p->out_in_ratio = pairs ? .5 : (double)L / M;
  p->pre = pairs ? (size_t)2 * pairs : 0;
  p->pre_post = pairs ? (size_t)4 * pairs : (size_t)n - 1;
  p->preload = pairs ? p->pre : ((size_t)n - 1) / 2;
}

static void same_state(stage_t *a, stage_t *b, int exact_offsets)
{
  CHECK(a->at.all == b->at.all && a->step.all == b->step.all);
  CHECK(lsx_fifo_occupancy(&a->fifo) == lsx_fifo_occupancy(&b->fifo));
  if (exact_offsets) CHECK(a->fifo.begin == b->fifo.begin && a->fifo.end == b->fifo.end);
  equal_samples(lsx_fifo_read_ptr(&a->fifo), lsx_fifo_read_ptr(&b->fifo),
                lsx_fifo_occupancy(&a->fifo));
}

typedef struct {
  const char *name;
  stage_fn_t current, reference;
  int pairs, taps;
} kernel;

static const kernel half_kernels[] = {
  {"h8", h8, reference_h8, 8, 0}, {"h9", h9, reference_h9, 9, 0},
  {"h10", h10, reference_h10, 10, 0}, {"h11", h11, reference_h11, 11, 0},
  {"h12", h12, reference_h12, 12, 0}, {"h13", h13, reference_h13, 13, 0}
};

static void one_call(const kernel *k, rate_shared_t *shared, int n,
    int L, int M, int phase, int num_in, unsigned pattern, size_t offset, int impulse)
{
  stage_t a, b;
  fifo_t ao, bo;
  size_t expected_out, expected_read, input_count;
  const size_t prefix = 3;
  family = k->name; detail_n = n; detail_L = L; detail_M = M;
  detail_phase = phase; detail_size = num_in; detail_pattern = (int)pattern;
  stage_init(&a, shared, n, k->pairs, L, M, phase);
  stage_init(&b, shared, n, k->pairs, L, M, phase);
  input_count = (size_t)num_in + a.pre_post;
  exact_fifo(&a.fifo, input_count, offset, pattern, impulse);
  exact_fifo(&b.fifo, input_count, offset, pattern, impulse);
  exact_fifo(&ao, prefix, 0, 5, -1);
  exact_fifo(&bo, prefix, 0, 5, -1);
  k->reference(&a, &ao);
  k->current(&b, &bo);
  if (k->pairs) {
    expected_out = ((size_t)num_in + 1) / 2;
    expected_read = 2 * expected_out;
  } else {
    /* Independent closed-form integer oracle, not the optimized recurrence. */
    uint64_t limit = (uint64_t)num_in * L;
    expected_out = limit <= (unsigned)phase ? 0 :
        (size_t)((limit - (unsigned)phase + M - 1) / M);
    expected_read = (size_t)(((uint64_t)phase + expected_out * (uint64_t)M) / L);
    CHECK(b.at.parts.integer == (int)(((uint64_t)phase + expected_out * (uint64_t)M) % L));
  }
  CHECK(expected_read <= input_count);
  CHECK(b.fifo.begin == (offset + expected_read) * sizeof(double));
  CHECK(lsx_fifo_occupancy(&ao) == prefix + expected_out);
  CHECK(lsx_fifo_occupancy(&bo) == prefix + expected_out);
  equal_samples(lsx_fifo_read_ptr(&ao), lsx_fifo_read_ptr(&bo), prefix + expected_out);
  same_state(&a, &b, 1);
  lsx_fifo_delete(&a.fifo); lsx_fifo_delete(&b.fifo);
  lsx_fifo_delete(&ao); lsx_fifo_delete(&bo);
  ++cases;
}

static double *coefficients(int n, int L)
{
  size_t i, count = (size_t)n * L;
  double *h = malloc(count * sizeof(*h));
  CHECK(h != NULL);
  /* Phase-dependent and signed coefficients make phase permutations visible. */
  for (i = 0; i < count; ++i) h[i] = value_at(i + 37, 5);
  return h;
}

static void direct_matrix(void)
{
  static const int lengths[] = {0,1,2,3,4,7,8,9,15,16,17,31,32,33,65,127,257};
  static const int taps[] = {1,2,3,11,18,24,26,42,63,88};
  static const int ratios[][2] = {{1,1},{2,1},{2,3},{3,2},{3,3},{3,8},
    {40,147},{80,147},{160,147},{147,160},{2048,4095},{4096,4095}};
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  unsigned m, h, t, r, ph, z, pat;
  for (m = 0; m < array_length(modes); ++m) {
    CHECK(fesetround(modes[m]) == 0);
    for (h = 0; h < array_length(half_kernels); ++h) {
      const kernel *k = &half_kernels[h];
      for (z = 0; z < array_length(lengths); ++z)
        for (pat = 0; pat < 6; ++pat)
          one_call(k, NULL, 0, 1, 2, 0, lengths[z], pat, (z & 1) ? 3 : 0, -1);
      /* Each tap and each interleaved-output edge sees an isolated impulse. */
      for (z = 0; z < (unsigned)(4*k->pairs + 9); ++z)
        one_call(k, NULL, 0, 1, 2, 0, 9, 0, 0, (int)z);
    }
    for (t = 0; t < array_length(taps) + 2; ++t) {
      int n = t < array_length(taps) ? taps[t] : t == array_length(taps) ? U100_l : u100_l;
      kernel k = t < array_length(taps) ? (kernel){"vpoly0",vpoly0,reference_vpoly0,0,n} :
          t == array_length(taps) ? (kernel){"U100_0",U100_0,reference_U100_0,0,n} :
          (kernel){"u100_0",u100_0,reference_u100_0,0,n};
      for (r = 0; r < array_length(ratios); ++r) {
        int L = ratios[r][0], M = ratios[r][1];
        rate_shared_t shared;
        if (M > n * L) continue; /* Preserve the valid FIR halo/skip contract. */
        memset(&shared, 0, sizeof(shared));
        shared.poly_fir_coefs = coefficients(n, L);
        for (ph = 0; ph < 3; ++ph) {
          int phase = ph == 0 ? 0 : ph == 1 ? L/2 : L-1;
          for (z = 0; z < array_length(lengths); ++z) {
            one_call(&k, &shared, n, L, M, phase, lengths[z],
                (m+t+r+ph+z)%6, (z & 1) ? 1 : 0, -1);
            if (k.current == vpoly0) {
              kernel scalar_clock = {"recurrence-only", recurrence_vpoly0, reference_vpoly0, 0, n};
              one_call(&scalar_clock, &shared, n, L, M, phase, lengths[z],
                  (m+t+r+ph+z)%6, (z & 1) ? 1 : 0, -1);
            }
          }
        }
        free(shared.poly_fir_coefs);
      }
    }
  }
  CHECK(fesetround(original_rounding) == 0);
}

static void stage_stream(const kernel *k, rate_shared_t *shared, int n,
    int L, int M, int phase, unsigned pattern, unsigned schedule,
    int reference, stage_t *stage, fifo_t *output)
{
  static const size_t chunks[] = {1,3,2,7,17,1,65,511};
  const size_t count = 5003;
  size_t used = 0, serial = 0;
  double *data = malloc(count * sizeof(*data));
  CHECK(data != NULL);
  stage_init(stage, shared, n, k->pairs, L, M, phase);
  memset(&stage->fifo, 0, sizeof(stage->fifo));
  memset(output, 0, sizeof(*output));
  lsx_fifo_create(&stage->fifo, sizeof(double));
  lsx_fifo_create(output, sizeof(double));
  if (stage->preload) memset(lsx_fifo_write(&stage->fifo, stage->preload, NULL), 0,
                              stage->preload * sizeof(double));
  for (used = 0; used < count; ++used)
    data[used] = used + 160 < count ? value_at(used, pattern) : 0.;
  used = 0;
  do {
    size_t take = count - used;
    if (schedule && take > chunks[serial % array_length(chunks)])
      take = chunks[serial % array_length(chunks)];
    lsx_fifo_write(&stage->fifo, take, data + used);
    (reference ? k->reference : k->current)(stage, output);
    if (serial % 7 == 0) (reference ? k->reference : k->current)(stage, output);
    used += take; ++serial;
  } while (used < count);
  free(data);
}

static void stream_matrix(void)
{
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  static const int poly[][3] = {{18,40,147},{24,160,147},{26,80,147},
    {26,160,147},{11,147,160},{42,3,8}};
  unsigned m, index, pat;
  for (m=0; m<array_length(modes); ++m) {
    CHECK(fesetround(modes[m]) == 0);
    for (index=0; index<array_length(half_kernels)+array_length(poly); ++index) {
      kernel k;
      rate_shared_t shared;
      int n=0,L=1,M=2;
      memset(&shared,0,sizeof(shared));
      if (index<array_length(half_kernels)) k=half_kernels[index];
      else {
        unsigned p=index-array_length(half_kernels);
        n=poly[p][0];L=poly[p][1];M=poly[p][2];
        k=(kernel){"vpoly0-stream",vpoly0,reference_vpoly0,0,n};
        if (p==4) k=(kernel){"u100_0-stream",u100_0,reference_u100_0,0,n};
        if (p==5) k=(kernel){"U100_0-stream",U100_0,reference_U100_0,0,n};
        shared.poly_fir_coefs=coefficients(n,L);
      }
      for (pat=0;pat<6;++pat) {
        stage_t a,b,c; fifo_t ao,bo,co;
        family=k.name;detail_n=n;detail_L=L;detail_M=M;
        detail_phase=L-1;detail_size=5003;detail_pattern=pat;
        stage_stream(&k,&shared,n,L,M,L-1,pat,0,1,&a,&ao);
        stage_stream(&k,&shared,n,L,M,L-1,pat,1,1,&b,&bo);
        stage_stream(&k,&shared,n,L,M,L-1,pat,1,0,&c,&co);
        CHECK(lsx_fifo_occupancy(&ao)==lsx_fifo_occupancy(&bo));
        CHECK(lsx_fifo_occupancy(&bo)==lsx_fifo_occupancy(&co));
        equal_samples(lsx_fifo_read_ptr(&ao),lsx_fifo_read_ptr(&bo),lsx_fifo_occupancy(&ao));
        equal_samples(lsx_fifo_read_ptr(&bo),lsx_fifo_read_ptr(&co),lsx_fifo_occupancy(&bo));
        same_state(&a,&b,0);same_state(&b,&c,1);
        lsx_fifo_delete(&a.fifo);lsx_fifo_delete(&b.fifo);lsx_fifo_delete(&c.fifo);
        lsx_fifo_delete(&ao);lsx_fifo_delete(&bo);lsx_fifo_delete(&co);
        ++stream_cases;
      }
      free(shared.poly_fir_coefs);
    }
  }
  CHECK(fesetround(original_rounding)==0);
}

static unsigned select_reference(lsx_rate_f64_t *ctx)
{
  unsigned mask=0,i,h;
  if (ctx->identity) return 0;
  for (i=0;i<ctx->rate.num_stages;++i) {
    stage_t *s=ctx->rate.stages+i;
    for (h=0;h<array_length(half_kernels);++h)
      if (s->fn==half_kernels[h].current) {s->fn=half_kernels[h].reference;mask|=1;break;}
    if (s->fn==vpoly0) {s->fn=reference_vpoly0;mask|=2;}
    if (s->fn==U100_0) {s->fn=reference_U100_0;mask|=2;}
    if (s->fn==u100_0) {s->fn=reference_u100_0;mask|=2;}
  }
  return mask;
}

static double *api_stream(unsigned input_hz, unsigned output_hz, size_t count,
    unsigned pattern, unsigned schedule, size_t *total, unsigned *mask)
{
  const size_t chunks[]={1,3,31,257,2,65}, caps[]={1,7,2,127,13};
  lsx_rate_f64_config cfg={input_hz,output_hz,180.,95.,50};
  lsx_rate_f64_t *a=NULL,*b=NULL;
  size_t used=0,made=0,serial=0;
  size_t wanted=(size_t)(((uint64_t)count*output_hz+input_hz/2)/input_hz);
  double *input=malloc((count+1)*sizeof(double));
  double *result=malloc((wanted+1)*sizeof(double)),ao[127],bo[127];
  CHECK(input&&result);
  CHECK(src_opt_test_create(&cfg,&a)==SOX_DSD_OK);
  CHECK(src_opt_test_create(&cfg,&b)==SOX_DSD_OK);
  *mask|=select_reference(a);
  for (used=0;used<count;++used) input[used]=value_at(used,pattern);
  used=0;
  do {
    size_t ni=count-used,no=schedule?caps[serial%array_length(caps)]:127,ai,bi,ac,bc;
    sox_dsd_status_t as,bs;
    if (schedule&&ni>chunks[serial%array_length(chunks)])ni=chunks[serial%array_length(chunks)];
    if (serial%11==0) {
      size_t ai0=ni,bi0=ni,az=0,bz=0;
      CHECK(src_opt_test_process(a,NULL,&ai0,NULL,&az)==SOX_DSD_NEED_OUTPUT);
      CHECK(src_opt_test_process(b,NULL,&bi0,NULL,&bz)==SOX_DSD_NEED_OUTPUT);
      CHECK(!ai0&&!bi0&&!az&&!bz);
    }
    ai=bi=ni;ac=bc=no;
    as=src_opt_test_process(a,input+used,&ai,ao,&ac);
    bs=src_opt_test_process(b,input+used,&bi,bo,&bc);
    CHECK(as==bs&&(as==SOX_DSD_NEED_INPUT||as==SOX_DSD_NEED_OUTPUT));
    CHECK(ai==bi&&ac==bc&&ai<=ni&&ac<=no);
    equal_samples(ao,bo,ac);
    CHECK(made+ac<=wanted);
    memcpy(result+made,bo,ac*sizeof(double));
    used+=ai;made+=ac;++serial;
    CHECK(a->accepted==b->accepted&&a->delivered==b->delivered);
    CHECK(ai||ac||!count);
  } while (used<count);
  for (;;) {
    size_t ac=schedule?caps[serial++%array_length(caps)]:127,bc=ac;
    sox_dsd_status_t as=src_opt_test_finish(a,wanted,ao,&ac);
    sox_dsd_status_t bs=src_opt_test_finish(b,wanted,bo,&bc);
    CHECK(as==bs&&ac==bc&&made+ac<=wanted);
    equal_samples(ao,bo,ac);
    memcpy(result+made,bo,ac*sizeof(double));made+=ac;
    if(as==SOX_DSD_DONE)break;
    CHECK(as==SOX_DSD_NEED_OUTPUT&&ac);
  }
  CHECK(made==wanted);
  {
    size_t ac=1,bc=1;
    CHECK(src_opt_test_finish(a,wanted,ao,&ac)==SOX_DSD_DONE&&ac==0);
    CHECK(src_opt_test_finish(b,wanted,bo,&bc)==SOX_DSD_DONE&&bc==0);
  }
  src_opt_test_destroy(a);src_opt_test_destroy(b);free(input);
  *total=made;return result;
}

static void api_matrix(void)
{
  static const unsigned rates[][2]={{44100,48000},{48000,44100},{176400,44100},
    {352800,48000},{88200,192000},{176400,384000},{352800,88200},
    {384000,88200},{96000,88200},{96000,96000}};
  static const size_t sizes[]={0,1,31,257,4099};
  unsigned r,z,mask=0;
  CHECK(fesetround(FE_TONEAREST)==0);
  for(r=0;r<array_length(rates);++r)for(z=0;z<array_length(sizes);++z) {
    size_t na,nb;double *a,*b;
    family="f64-adapter";detail_L=rates[r][1];detail_M=rates[r][0];
    detail_size=(int)sizes[z];detail_pattern=(r+z)%6;
    a=api_stream(rates[r][0],rates[r][1],sizes[z],(r+z)%6,0,&na,&mask);
    b=api_stream(rates[r][0],rates[r][1],sizes[z],(r+z)%6,1,&nb,&mask);
    CHECK(na==nb);equal_samples(a,b,na);free(a);free(b);++api_cases;
  }
  CHECK(mask==3); /* Real initialization reached rational stages and halfband controls. */
  CHECK(fesetround(original_rounding)==0);
}

static int effective_ordered(void)
{
#if defined(LSX_RATE_ORDERED_OPT) && LSX_RATE_ORDERED_OPT && !defined(__FAST_MATH__) && FLT_EVAL_METHOD == 0
  return 1;
#else
  return 0;
#endif
}

#if defined(CLOCK_MONOTONIC) && defined(CLOCK_PROCESS_CPUTIME_ID)
typedef struct {
  const char *name;
  stage_fn_t fn;
  stage_t stage;
  fifo_t output;
  size_t input_end;
} timing_arm;
typedef struct {
  double wall, cpu;
  uint64_t outputs, checksum;
  int final_phase;
} timing;
static volatile uint64_t benchmark_sink;

static double seconds(clockid_t which)
{
  struct timespec t;
  CHECK(clock_gettime(which, &t) == 0);
  return (double)t.tv_sec + (double)t.tv_nsec * 1.e-9;
}

static timing time_arm(timing_arm *a, unsigned iterations)
{
  unsigned k;
  size_t input_allocation = a->stage.fifo.allocation;
  size_t output_allocation = a->output.allocation;
  timing t = {0, 0, 0, 0, 0};
  double wall, cpu;
  a->stage.at.parts.integer = 0;
  wall = seconds(CLOCK_MONOTONIC);
  cpu = seconds(CLOCK_PROCESS_CPUTIME_ID);
  for (k = 0; k < iterations; ++k) {
    size_t made;
    uint64_t word;
    /* Reuse a fixed real input window while carrying the exact phase between
     * calls. Keep one pending output so FIFO reserve can reuse its allocation. */
    a->stage.fifo.begin = 0;
    a->stage.fifo.end = a->input_end;
    a->output.begin = 0;
    a->output.end = sizeof(double);
    a->fn(&a->stage, &a->output);
    made = lsx_fifo_occupancy(&a->output) - 1;
    t.outputs += made;
    if (made) {
      memcpy(&word, (double *)a->output.data + made, sizeof(word));
      t.checksum ^= word;
    }
  }
  t.cpu = seconds(CLOCK_PROCESS_CPUTIME_ID) - cpu;
  t.wall = seconds(CLOCK_MONOTONIC) - wall;
  t.final_phase = a->stage.at.parts.integer;
  CHECK(a->stage.fifo.allocation == input_allocation);
  CHECK(a->output.allocation == output_allocation);
  benchmark_sink ^= t.checksum;
  return t;
}

static int benchmark(void)
{
  static const int spec[][4] = {
    {26,80,147,0},{26,80,147,1},{26,80,147,2},{26,80,147,3},
    {26,80,147,4},{26,80,147,8},{26,80,147,4096},
    {11,80,147,2},{11,80,147,3},{11,80,147,4096},
    {88,80,147,2},{88,80,147,3},{88,80,147,4},{88,80,147,4096},
    {26,160,147,1},{26,160,147,2},{26,160,147,3}
  };
  unsigned c, v, repeat;
  uint32_t rng = UINT32_C(0x5ac17);
  CHECK(fesetround(FE_TONEAREST) == 0);
  for (c=0;c<array_length(spec);++c) {
    int n=spec[c][0],L=spec[c][1],M=spec[c][2],num_in=spec[c][3];
    timing_arm arms[3];
    rate_shared_t shared;
    timing calibration;
    unsigned iterations=1;
    double setup_wall=seconds(CLOCK_MONOTONIC),setup_cpu=seconds(CLOCK_PROCESS_CPUTIME_ID);
    memset(&shared,0,sizeof(shared));shared.poly_fir_coefs=coefficients(n,L);
    memset(arms,0,sizeof(arms));
    arms[0].name="original";arms[0].fn=reference_vpoly0;
    arms[1].name="threshold2";arms[1].fn=threshold2_vpoly0;
    arms[2].name="threshold1";arms[2].fn=vpoly0;
    family="benchmark";detail_n=n;detail_L=L;detail_M=M;detail_size=num_in;
    for (v=0;v<3;++v) {
      stage_init(&arms[v].stage,&shared,n,0,L,M,0);
      exact_fifo(&arms[v].stage.fifo,(size_t)num_in+n-1,0,5,-1);
      arms[v].input_end=arms[v].stage.fifo.end;
      exact_fifo(&arms[v].output,1,0,5,-1);
      arms[v].fn(&arms[v].stage,&arms[v].output); /* Reserve before timing. */
      if (v) {
        CHECK(lsx_fifo_occupancy(&arms[0].output)==lsx_fifo_occupancy(&arms[v].output));
        equal_samples(lsx_fifo_read_ptr(&arms[0].output),lsx_fifo_read_ptr(&arms[v].output),
            lsx_fifo_occupancy(&arms[0].output));
        same_state(&arms[0].stage,&arms[v].stage,1);
      }
    }
    setup_cpu=seconds(CLOCK_PROCESS_CPUTIME_ID)-setup_cpu;
    setup_wall=seconds(CLOCK_MONOTONIC)-setup_wall;
    do {
      calibration=time_arm(arms,iterations);
      if(calibration.cpu<.004)iterations*=2;
    } while(calibration.cpu<.004&&iterations<(1u<<22));
    iterations*=5;
    for (repeat=0;repeat<17;++repeat) {
      unsigned order[3]={0,1,2},j;
      timing rows[3];
      for(j=2;j>0;--j) {
        unsigned other,temp;
        rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;
        other=rng%(j+1);temp=order[j];order[j]=order[other];order[other]=temp;
      }
      for(j=0;j<3;++j)rows[order[j]]=time_arm(arms+order[j],iterations);
      for(v=1;v<3;++v) {
        CHECK(rows[v].outputs==rows[0].outputs&&rows[v].checksum==rows[0].checksum);
        CHECK(rows[v].final_phase==rows[0].final_phase);
      }
      for(j=0;j<3;++j) {
        v=order[j];
        printf("{\"schema\":\"production-src-opt/real-fifo-timing/1\","
            "\"case\":%u,\"variant\":\"%s\",\"taps\":%d,\"L\":%d,\"M\":%d,"
            "\"num_in\":%d,\"repeat\":%u,\"warmup\":%s,\"order\":%u,"
            "\"iterations\":%u,\"outputs\":%"PRIu64",\"cpu_seconds\":%.9g,"
            "\"wall_seconds\":%.9g,\"setup_cpu_seconds\":%.9g,\"setup_wall_seconds\":%.9g,"
            "\"checksum\":\"%016"PRIx64"\",\"allocation_changed\":false,\"effective_ordered\":%d}\n",
            c,arms[v].name,n,L,M,num_in,repeat,repeat<2?"true":"false",j,iterations,
            rows[v].outputs,rows[v].cpu,rows[v].wall,setup_cpu,setup_wall,rows[v].checksum,effective_ordered());
      }
      fflush(stdout);
    }
    for(v=0;v<3;++v) {lsx_fifo_delete(&arms[v].stage.fifo);lsx_fifo_delete(&arms[v].output);}
    free(shared.poly_fir_coefs);
  }
  CHECK(fesetround(original_rounding)==0);
  return 0;
}
#else
static int benchmark(void)
{
  fputs("Monotonic and process CPU clocks are unavailable; benchmark UNRUN.\n",stderr);
  return 77;
}
#endif

int main(int argc, char **argv)
{
  original_rounding=fegetround();
  CHECK(original_rounding!=-1);
  CHECK(sizeof(double)==sizeof(uint64_t)&&DBL_MANT_DIG==53&&DBL_MAX_EXP==1024);
  if(argc==2&&!strcmp(argv[1],"--benchmark"))return benchmark();
  if(argc!=1) {fputs("Usage: test_src_optimization [--benchmark]\n",stderr);return 2;}
  direct_matrix();stream_matrix();api_matrix();
  printf("{\"schema\":\"production-src-opt/exact-regression/1\",\"status\":\"PASS\","
      "\"checks\":%"PRIu64",\"direct_cases\":%"PRIu64",\"stream_cases\":%"PRIu64","
      "\"api_cases\":%"PRIu64",\"sample_words_compared\":%"PRIu64","
      "\"rounding_modes\":4,\"flt_eval_method\":%d,\"effective_ordered\":%d,\"ordered_opt\":%d}\n",
      checks,cases,stream_cases,api_cases,samples_compared,FLT_EVAL_METHOD,effective_ordered(),
#if defined(LSX_RATE_ORDERED_OPT)
      LSX_RATE_ORDERED_OPT
#else
      0
#endif
      );
  return 0;
}
