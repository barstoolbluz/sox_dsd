/* P15 test-only source-bound rate stage exporter.  Compiles the same rate.c
 * source in a separate test executable, without adding a production API or
 * changing production DSP.  Its coefficient/clock dump is NOT an independent
 * arithmetic or spectral certificate; Python must reconstruct and compare. */
#include <stddef.h>
/* Interpose only the test build's LPF-design call.  Preserve the *original*
 * double taps before rate.c transforms them to FFT4G packed coefficients;
 * their exact binary64 identity is needed to define the intended convolution.
 * No production library symbol or its DSP implementation is touched. */
static double *p15_original_dft[2];
static size_t p15_original_dft_length[2];
static unsigned p15_dft_captured;
static double *p15_capture_design_lpf(double, double, double, double, int *, int, double);
#define lsx_design_lpf p15_capture_design_lpf
#define lsx_rate_effect_fn p15_local_rate_effect_fn
#define lsx_rate_f64_create p15_local_rate_f64_create
#define lsx_rate_f64_process p15_local_rate_f64_process
#define lsx_rate_f64_finish p15_local_rate_f64_finish
#define lsx_rate_f64_destroy p15_local_rate_f64_destroy
#include "../../src/rate.c"
#undef lsx_design_lpf
#include <inttypes.h>
#include <errno.h>

/* Real design symbol, linked from the independently built library. */
extern double *lsx_design_lpf(double, double, double, double, int *, int, double);
static double *p15_capture_design_lpf(double fp,double fs,double fn,double att,
                                      int *ntaps,int phases,double beta)
{
  double *result=lsx_design_lpf(fp,fs,fn,att,ntaps,phases,beta);
  if (fn > 0 && phases < 0 && beta == -1. && result) {
    if (p15_dft_captured < 2 && *ntaps > 0 && *ntaps < 200000) {
      size_t n=(size_t)*ntaps;
      double *copy=malloc(n*sizeof(*copy));
      if (!copy) return result;
      memcpy(copy,result,n*sizeof(*copy));
      p15_original_dft_length[p15_dft_captured]=n;
      p15_original_dft[p15_dft_captured++]=copy;
    }
  }
  return result;
}

static int kind(const stage_t *s, int *order, const double **coefs,
                size_t *count, unsigned *phases)
{
  unsigned i;
  if (s->fn == dft_stage_fn) {
    const dft_filter_t *f = &s->shared->dft_filter[s->dft_filter_num];
    *order = -1; *coefs = f->coefs; *count = (size_t)f->dft_length;
    *phases = 0; return 2;
  }
  for (i = 0; i < array_length(half_firs); ++i)
    if (s->fn == half_firs[i].fn) {
      static const double *const arrays[] = {
          half_fir_coefs_8,half_fir_coefs_9,half_fir_coefs_10,
          half_fir_coefs_11,half_fir_coefs_12,half_fir_coefs_13};
      *order = -1; *coefs = arrays[i];
      *count = (size_t)half_firs[i].num_coefs;
      *phases = 0; return 1;
    }
  if (s->fn == vpoly0 || s->fn == U100_0 || s->fn == u100_0)
    *order = 0;
  else if (s->fn == vpoly1 || s->fn == u100_1) *order = 1;
  else if (s->fn == vpoly2 || s->fn == u100_2) *order = 2;
  else if (s->fn == vpoly3) *order = 3;
  else return 0;
  if (s->n < 1 || s->n > 100000) return 0;
  if (*order == 0) *phases = (unsigned)s->L;
  else if (s->phase_bits < 0 || s->phase_bits > 22) return 0;
  else *phases = 1u << s->phase_bits;
  *count = (size_t)s->n * *phases * (unsigned)(*order + 1);
  if (*count > 8000000) return 0;
  *coefs = s->shared->poly_fir_coefs;
  return 3;
}

static int output_stage(FILE *out, const stage_t *s, int index)
{
  int order, type;
  size_t n, j;
  unsigned phases;
  const double *coefs;
  const dft_filter_t *f = NULL;
  type=kind(s,&order,&coefs,&n,&phases);
  if (!type || !coefs) return 0;
  if (type==2) {
    unsigned actual=s->dft_filter_num==0 ? 0u : p15_dft_captured-1;
    f=&s->shared->dft_filter[s->dft_filter_num];
    if (p15_dft_captured==0 || actual>=p15_dft_captured ||
        p15_original_dft_length[actual]!=f->num_taps) return 0;
    coefs=p15_original_dft[actual]; n=f->num_taps;
  }
  fprintf(out,"%s{\"index\":%d,\"kind\":%d,\"order\":%d,"
          "\"n\":%d,\"phases\":%u,\"phase_bits\":%d,"
          "\"L\":%d,\"M\":%d,\"pre\":%zu,\"pre_post\":%zu,"
          "\"preload\":%zu,\"remL\":%d,\"remM\":%d,"
          "\"at_i64\":\"%" PRId64 "\",\"step_i64\":\"%" PRId64 "\","
          "\"use_hi_prec_clock\":%s,\"dft_taps\":%zu,\"dft_length\":%zu,"
          "\"dft_post_peak\":%zu,\"coefficients\":[",
          index?",":"",index,type,order,s->n,phases,s->phase_bits,
          s->L,s->step.parts.integer,s->pre,s->pre_post,s->preload,
          s->remL,s->remM,s->at.all,s->step.all,
          s->use_hi_prec_clock?"true":"false",
          f?f->num_taps:0,f?f->dft_length:0,f?f->post_peak:0);
  for (j=0;j<n;j++) {
    if (!isfinite(coefs[j])) return 0;
    fprintf(out,"%s\"%a\"",j?",":"",coefs[j]);
  }
  fputs("]",out);
  if (f) {
    fputs(",\"fft4g_realized_bins\":[",out);
    for (j=0;j<f->dft_length;j++)
      fprintf(out,"%s\"%a\"",j?",":"",f->coefs[j]);
    fputs("]",out);
  }
  fputs("}",out);
  return !ferror(out);
}

static int parse_rate(const char *value, uint32_t *result)
{
  char *end;
  unsigned long long rate;
  if (!value || !*value || *value == '-' || *value == '+') return 0;
  errno=0;
  rate=strtoull(value,&end,10);
  if (errno || *end || rate < 8000 || rate > 1000000) return 0;
  *result=(uint32_t)rate;
  return 1;
}

int main(int argc,char **argv)
{
  rate_t p={0}; rate_shared_t shared={0};
  uint32_t in,out;
  double bits;
  FILE *fp;
  int err, i;
  if (argc!=4 || !parse_rate(argv[1],&in) ||
      !parse_rate(argv[2],&out) || in==out) return 2;
  bits=180. / (20. * log10(2.)) - 1.;
  err=rate_init(&p,&shared,in,out,bits,50.,95.,100.,rolloff_none,
                sox_false,sox_false,-1,400,sox_false,sox_true);
  if (err || p.num_stages<1 || p.num_stages>10) return 3;
  fp=fopen(argv[3],"wb");
  if (!fp) { rate_close(&p); return 4; }
  fprintf(fp,"{\"schema\":\"P15/source-rate-stage-snapshot/1\","
             "\"input_hz\":%u,\"output_hz\":%u,\"stage_count\":%d,"
             "\"stages\":[",in,out,p.num_stages);
  for (i=0;i<p.num_stages;i++) if (!output_stage(fp,p.stages+i,i)) {
    fclose(fp); remove(argv[3]);rate_close(&p);return 5;
  }
  fputs("]}\n",fp);
  err=fclose(fp);
  if (err) remove(argv[3]);
  rate_close(&p);
  for (i=0;i<(int)p15_dft_captured;i++) free(p15_original_dft[i]);
  return err?6:0;
}
