/* P10 composite mastering candidate.
 * All DSP between graph normalization and native decisions is binary64:
 * source -> R SRC -> centered non-decimating FIR at R -> native SRC -> scale.
 * Queues are bounded and carry no caller pointers. Native endpoints derive
 * from the original source count, never two independently rounded lengths.
 * A failure discards this call's output block and permanently latches. */
#include "sox_i.h"
#include "pcmdsd.h"
#include "dsd_stats.h"
#include "pcmdsd_coeffs.h"
#include "pcmdsd_guards.h"
#include "pcmdsd_v2_guards.h"
#include "pcmdsd_p20_guards.h"
#include "rate_internal.h"
#include "dsd_kernels.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PCMDSD_BATCH 256
#define PCMDSD_NATIVE_BATCH 512
/* The original 0.5 reference-scale limit is an interpolation overload
 * limit, not a promise of sustained stability for the P10 v1 modulator.
 * Sustained loud input tripped the state guard at DSD128/256; every rate
 * uses the same lower warn-and-clip ceiling so the default behaves alike
 * at all clocks.  Qualification paths retain their original input and
 * guards; the strict CLI path keeps the default gain at DSD512/1024 (see
 * lsx_pcmdsd_strict_keeps_default_gain). */
double lsx_pcmdsd_warn_clip_ceiling(uint32_t native_hz)
{
  (void)native_hz;
  return .45;
}
/* A one-pass stream has no programme-wide interpolated peak available before
 * it commits DSD decisions.  Use a constant linear gain rather than deforming
 * valid PCM samples at the lower clipping limit.  The residual clip-and-warn
 * path still handles larger overshoots.  This gain is specific to the
 * implicit default, not an explicit --headroom cut. */
double lsx_pcmdsd_default_warn_gain(uint32_t native_hz)
{
  return lsx_pcmdsd_warn_clip_ceiling(native_hz)/.5;
}
/* The eighth-order v1 encoder at DSD512/1024 was qualified only under the
 * default gain: at gain 1 it trips its state guard on sustained full-scale
 * DC. There --dsd-clip error keeps the default gain, so sustained input stays
 * at or below the 0.45 ceiling; --headroom DB still replaces it. */
int lsx_pcmdsd_strict_keeps_default_gain(uint32_t native_hz)
{
  return native_hz>=22579200;
}
/* qualified=1 as of 2026-10-20: the design authority recorded its P15
 * engineering acceptance on 2026-10-19 and withdrew the outstanding
 * formal-proof obligation as a release blocker. Coefficients, guards and
 * certificate digests are unchanged. */
static const lsx_pcmdsd_profile profiles[] = {
  {"encode.mastering.v1.dsd64",2822400,88200,20000,40000,
    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_guards[0],1,LSX_PCMDSD_CERTIFICATE_SHA256},
  {"encode.mastering.v1.dsd128",5644800,176400,30000,60000,
    lsx_pcmdsd_coeff_master128,77,lsx_pcmdsd_guards[1],1,LSX_PCMDSD_CERTIFICATE_SHA256},
  {"encode.mastering.v1.dsd256",11289600,176400,40000,80000,
    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_guards[2],1,LSX_PCMDSD_CERTIFICATE_SHA256},
  /* 2026-11-07: v1 (eighth order) binds DSD512 and DSD1024 again. It was
   * held back because v1.dsd512 failed the sustained nominal gate at min28 6
   * and v1.dsd1024 ran away on full-scale DC, both at the old 0.5 mapping.
   * Under the 1.1.0 default (0.9 gain, 0.45 clip) it passes both: P17 DC
   * fixtures and 60 s of DC at 0.45 complete at both clocks, and the
   * 3,600-second nominal soak passes p17_soak_assess at both clocks
   * (min28 7, max 21). The controls at 0.5 still reproduce both failures.
   * See docs/dsd/V1_HIGH_RATE_ENCODE_2026-11-07.md.
   *
   * v1 is ordered FIRST at each clock deliberately: lsx_pcmdsd_profile_find()
   * returns the first row matching a rate, so this is what binds the rate and
   * what lsx_pcmdsd_create() will build.
   *
   * The v2 CLANS-7 rows that P21 bound on 2026-10-23 stay qualified and are
   * reachable by exact id through the private test interface
   * (lsx_pcmdsd_profile_find_id). They are no longer in dsd_rates, so the
   * CLI cannot select them.
   *
   * certificate_sha256 names the coefficient manifest, not the modulator;
   * all four profiles use the already-certified 61-tap master64_256 bank. */
  {"encode.mastering.v1.dsd512",22579200,176400,40000,80000,
    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_guards[3],1,LSX_PCMDSD_CERTIFICATE_SHA256},
  {"encode.mastering.v2.dsd512",22579200,176400,40000,80000,
    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_p20_guards,1,LSX_PCMDSD_CERTIFICATE_SHA256},
  {"encode.mastering.v1.dsd1024",45158400,176400,40000,80000,
    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_guards[4],1,LSX_PCMDSD_CERTIFICATE_SHA256},
  {"encode.mastering.v2.dsd1024",45158400,176400,40000,80000,
    lsx_pcmdsd_coeff_master64_256,61,lsx_pcmdsd_v2_guards,1,LSX_PCMDSD_CERTIFICATE_SHA256}
};

struct lsx_pcmdsd {
  const lsx_pcmdsd_profile *profile;
  uint32_t input_hz;
  double scale, gain, envelope, clip_ceiling, bounds[8];
  int clip_overload, peak_only;
  unsigned guarded, finishing, done, source_done;
  lsx_rate_f64_t *source, *interpolator;
  double *ring;
  size_t head;
  uint64_t fir_received, fir_produced, working_limit, native_limit;
  double working[PCMDSD_BATCH], filtered[PCMDSD_BATCH];
  size_t working_pos, working_n, filtered_pos, filtered_n;
  sdm_normal_t sdm;
  const lsx_dsd_kernel *sdm_kernel; /* context-owned, immutable */
  lsx_pcmdsd_report report;
  sox_dsd_status_t error;
  lsx_pcmdsd_stage_observer observer;
  void *observer_opaque;
};

const lsx_pcmdsd_profile *lsx_pcmdsd_profile_of(const lsx_pcmdsd *p)
{ return p ? p->profile : NULL; }
double lsx_pcmdsd_reference_scale(const lsx_pcmdsd *p)
{ return p ? p->scale : 0.; }

const char *lsx_pcmdsd_kernel_name(const lsx_pcmdsd *p)
{
  return p && p->sdm_kernel ? p->sdm_kernel->name : NULL;
}

void lsx_pcmdsd_observe(lsx_pcmdsd *p, lsx_pcmdsd_stage_observer callback, void *opaque)
{
  if (p) {p->observer=callback;p->observer_opaque=opaque;}
}
void lsx_pcmdsd_set_clip(lsx_pcmdsd *p, int warn_and_clip)
{
  if (p) {
    p->clip_overload=!!warn_and_clip;
    p->report.clip_ceiling_applied=p->clip_overload?p->clip_ceiling:0.;
  }
}
void lsx_pcmdsd_set_gain(lsx_pcmdsd *p, double attenuation)
{
  if (p && isfinite(attenuation) && attenuation>0 && attenuation<=1) {
    p->gain=attenuation;
    p->report.applied_headroom_db=-20*log10(attenuation);
  }
}
void lsx_pcmdsd_set_peak_scan(lsx_pcmdsd *p)
{ if (p) p->peak_only=1; }
static void observe(lsx_pcmdsd *p, lsx_pcmdsd_stage stage,
    const double *samples, size_t count)
{
  if (p->observer && count) p->observer(p->observer_opaque,stage,samples,count);
}

const lsx_pcmdsd_profile *lsx_pcmdsd_profile_find(uint32_t hz)
{
  size_t i;
  for (i=0;i<array_length(profiles);++i)
    if (profiles[i].native_hz==hz) return &profiles[i];
  return NULL;
}
const lsx_pcmdsd_profile *lsx_pcmdsd_profile_find_id(uint32_t hz,
    const char *id)
{
  size_t i;
  if (!id) return NULL;
  for (i=0;i<array_length(profiles);++i)
    if (profiles[i].native_hz==hz && !strcmp(profiles[i].id,id))
      return &profiles[i];
  return NULL;
}

int lsx_pcmdsd_qualified(uint32_t hz)
{
  const lsx_pcmdsd_profile *p=lsx_pcmdsd_profile_find(hz);
  return p && p->qualified;
}

static sox_dsd_status_t fail_stream(lsx_pcmdsd *p, lsx_pcmdsd_failure why,
    double value, unsigned coordinate)
{
  if (!p->error) {
    p->report.failure=why;
    p->report.failure_value=value;
    p->report.coordinate=coordinate;
    p->report.first_bad_frame=p->sdm.frames;
    if (why==LSX_PCMDSD_INTERPOLATION_OVERLOAD)
      p->report.minimum_attenuation_db=20.*log10(fabs(value)/.5);
    p->error=SOX_DSD_NUMERIC_ERROR;
  }
  return p->error;
}

sox_dsd_status_t lsx_pcmdsd_candidate_create(uint32_t source_hz,
    uint32_t native_hz, double scale, unsigned channel,
    const sdm_profile_t *control, const double bounds[8], lsx_pcmdsd **out)
{
  lsx_pcmdsd *p;
  const lsx_pcmdsd_profile *profile=lsx_pcmdsd_profile_find(native_hz);
  lsx_rate_f64_config cfg;
  sox_dsd_status_t rc;
  unsigned i;
  if (!out) return SOX_DSD_BAD_ARGUMENT;
  *out=NULL;
  if (!source_hz || (scale!=.5 && scale!=1.)) return SOX_DSD_BAD_ARGUMENT;
  if (!profile) return SOX_DSD_UNSUPPORTED;
  if (!control) control=sdm_profile_find(profile->id,native_hz);
  if (!control || sdm_profile_rate(control)!=native_hz) return SOX_DSD_UNSUPPORTED;
  /* An explicitly named candidate chooses its matching composite definition;
   * legacy diagnostic controls retain the existing per-clock default. */
  {
    const lsx_pcmdsd_profile *named=lsx_pcmdsd_profile_find_id(
        native_hz,sdm_profile_id(control));
    if (named) profile=named;
  }
  if (bounds) for (i=0;i<8;++i)
    if (!isfinite(bounds[i]) || bounds[i]<=0) return SOX_DSD_BAD_ARGUMENT;
  p=calloc(1,sizeof(*p));
  if (!p) return SOX_DSD_NUMERIC_ERROR;
  p->profile=profile;
  p->input_hz=source_hz;
  p->scale=scale;
  p->gain=1.;
  p->clip_ceiling=lsx_pcmdsd_warn_clip_ceiling(native_hz);
  /* Two SOURCE int32 LSBs in normalized PCM, mapped by the resolved scale. */
  p->envelope=.5+scale*(2./SOX_SAMPLE_MAX);
  p->guarded=bounds!=NULL;
  if (bounds) memcpy(p->bounds,bounds,sizeof(p->bounds));
  p->report.channel=channel;
  p->report.first_bad_frame=UINT64_MAX;
  p->report.coordinate=UINT_MAX;
  p->report.effective_pass_hz=source_hz==profile->working_hz?profile->pass_hz:
      fmin(profile->pass_hz,.475*fmin(source_hz,profile->working_hz));
  p->ring=calloc(2*profile->taps,sizeof(*p->ring));
  if (!p->ring) {lsx_pcmdsd_destroy(p);return SOX_DSD_NUMERIC_ERROR;}
  cfg.input_hz=source_hz;
  cfg.output_hz=profile->working_hz;
  cfg.rejection_db=180.;cfg.bandwidth_0db_pct=95.;cfg.phase_percent=50;
  rc=lsx_rate_f64_create(&cfg,&p->source);
  if (rc!=SOX_DSD_OK) {lsx_pcmdsd_destroy(p);return rc;}
  cfg.input_hz=profile->working_hz;cfg.output_hz=native_hz;
  rc=lsx_rate_f64_create(&cfg,&p->interpolator);
  if (rc!=SOX_DSD_OK) {lsx_pcmdsd_destroy(p);return rc;}
  /* A forced unavailable ISA fails context creation, never execution. */
  {
    int sel=lsx_dsd_kernel_select_sdm_rate(NULL,native_hz,&p->sdm_kernel);
    if (sel) {
      lsx_pcmdsd_destroy(p);
      return sel==-2 ? SOX_DSD_UNSUPPORTED : SOX_DSD_BAD_ARGUMENT;
    }
  }
  sdm_normal_init(&p->sdm,control);
  sdm_normal_monitor_init(&p->report.monitor);
  sdm_normal_attach_monitor(&p->sdm,&p->report.monitor);
  *out=p;
  return SOX_DSD_OK;
}

sox_dsd_status_t lsx_pcmdsd_create(uint32_t source_hz, uint32_t native_hz,
    double scale, unsigned channel, lsx_pcmdsd **out)
{
  const lsx_pcmdsd_profile *profile=lsx_pcmdsd_profile_find(native_hz);
  if (!out) return SOX_DSD_BAD_ARGUMENT;
  *out=NULL;
  if (!profile || !profile->qualified) return SOX_DSD_UNSUPPORTED;
  return lsx_pcmdsd_candidate_create(source_hz,native_hz,scale,channel,NULL,
      profile->bounds,out);
}

/* Called on already scaled samples. No clamp, gain rescue, reset or fallback.
 * The guarded recurrence checks its next bank before committing a decision. */
sox_dsd_status_t lsx_pcmdsd_modulate(lsx_pcmdsd *p, const double *input,
    sox_sample_t *output, size_t n)
{
  size_t committed=0;
  unsigned coordinate=UINT_MAX;
  int rc;
  if (!p || (!input && n) || (!output && n)) return SOX_DSD_BAD_ARGUMENT;
  if (p->error) return p->error;
  /* A first pass for measured headroom performs the IDENTICAL SRC and FIR,
   * but never runs the SDM or writes decisions. Its maximum is the exact
   * post-interpolation, post-reference peak, including the finite EOF tail. */
  if (p->peak_only) {
    size_t i;
    if (n>UINT64_MAX-p->sdm.frames)
      return fail_stream(p,LSX_PCMDSD_STREAM_ERROR,0,UINT_MAX);
    for (i=0;i<n;++i) {
      if (!isfinite(input[i]))
        return fail_stream(p,LSX_PCMDSD_INPUT_NONFINITE,input[i],UINT_MAX);
      if (fabs(input[i])>p->report.peak) p->report.peak=fabs(input[i]);
    }
    p->sdm.frames+=n;
    return SOX_DSD_OK;
  }
  /* One immutable per-context call for the entire block. Each ISA kernel
   * owns its time recurrence, guard and monitor, not an indirect per bit. */
  rc=p->sdm_kernel->sdm_block(&p->sdm,input,n,output,&committed,
      p->guarded?p->bounds:NULL,&coordinate,p->envelope,&p->report.peak);
  if (!rc) return SOX_DSD_OK;
  if (rc==LSX_DSD_SDM_OVERLOAD)
    return fail_stream(p,LSX_PCMDSD_INTERPOLATION_OVERLOAD,input[committed],UINT_MAX);
  if (rc==LSX_DSD_SDM_FRAME_LIMIT)
    return fail_stream(p,LSX_PCMDSD_STREAM_ERROR,0,UINT_MAX);
  if (rc==LSX_DSD_SDM_NONFINITE && !isfinite(input[committed]))
    return fail_stream(p,LSX_PCMDSD_INPUT_NONFINITE,input[committed],UINT_MAX);
  return fail_stream(p,rc==LSX_DSD_SDM_BOUNDS?LSX_PCMDSD_STATE_BOUND:
      LSX_PCMDSD_STATE_NONFINITE,
      coordinate<8?p->sdm.state[p->sdm.bank^1][coordinate]:0,coordinate);
}

static int feed_fir(lsx_pcmdsd *p, double x, double *out)
{
  size_t L=p->profile->taps,head=p->head;
  p->ring[head]=p->ring[head+L]=x;
  p->head=head+1==L?0:head+1;
  if (++p->fir_received<=L/2) return 0;
  *out=lsx_dsd_fir_scalar(p->profile->prefilter,L,p->ring+head+1,0);
  ++p->fir_produced;
  return 1;
}

/* At EOF use ceil(N*R/Fsrc) for the finite working sequence. The native
 * count remains round_half_up(N*Fnative/Fsrc), never this rounded length. */
static int ceil_working(lsx_pcmdsd *p, uint64_t *out)
{
  uint64_t n=p->report.input_frames, q=n/p->input_hz, r=n%p->input_hz;
  uint64_t R=p->profile->working_hz,tail=(r*R)/p->input_hz;
  if ((r*R)%p->input_hz) ++tail;
  if (q>UINT64_MAX/R || tail>UINT64_MAX-q*R) return 0;
  *out=q*R+tail;
  return *out<=UINT64_MAX-p->profile->taps;
}

static sox_dsd_status_t pump(lsx_pcmdsd *p,const double *input,size_t *input_n,
    sox_sample_t *output,size_t *output_n,int finish)
{
  size_t available=*input_n, capacity=*output_n,used=0,produced=0;
  double native[PCMDSD_NATIVE_BATCH];
  *input_n=*output_n=0;
  if (p->error) return p->error;
  if (p->done) return finish?SOX_DSD_DONE:SOX_DSD_BAD_ARGUMENT;
  if (!capacity) return SOX_DSD_NEED_OUTPUT;
  if (!output || (!input && available)) return p->error=SOX_DSD_BAD_ARGUMENT;
  if (!finish && p->finishing) return p->error=SOX_DSD_BAD_ARGUMENT;
  if (finish && !p->finishing) {
    if (!ceil_working(p,&p->working_limit) ||
        !lsx_dsd_count_convert(p->report.input_frames,p->input_hz,
            p->profile->native_hz,&p->native_limit)) goto stream_error;
    p->finishing=1;
  }
  while (produced<capacity) {
    uint64_t allowed;
    size_t take,got;
    sox_dsd_status_t rc;
    if (finish) allowed=p->native_limit;
    else if (!lsx_dsd_count_convert(p->report.input_frames,p->input_hz,
        p->profile->native_hz,&allowed)) goto stream_error;
    if (p->sdm.frames>allowed) goto stream_error;
    if (finish && p->sdm.frames==allowed) {p->done=1;break;}

    /* Prefer draining the downstream SRC before accepting more upstream
     * input. The source-derived holdback prevents premature tail commits. */
    take=p->filtered_n-p->filtered_pos;
    got=(size_t)min((uint64_t)min(capacity-produced,(size_t)PCMDSD_NATIVE_BATCH),
        allowed-p->sdm.frames);
    if (got) {
      if (finish && p->source_done && p->fir_produced==p->working_limit && !take) {
        rc=lsx_rate_f64_finish(p->interpolator,allowed,native,&got);
        if (rc!=SOX_DSD_NEED_OUTPUT && rc!=SOX_DSD_DONE) goto stream_error;
      } else {
        rc=lsx_rate_f64_process(p->interpolator,p->filtered+p->filtered_pos,
            &take,native,&got);
        if (rc!=SOX_DSD_NEED_INPUT && rc!=SOX_DSD_NEED_OUTPUT) goto stream_error;
        p->filtered_pos+=take;
      }
      if (got) {
        size_t j;
        observe(p,LSX_PCMDSD_STAGE_NATIVE,native,got);
        for (j=0;j<got;++j) native[j]*=p->scale*p->gain;
        observe(p,LSX_PCMDSD_STAGE_SCALED,native,got);
        /* A clipped interpolated overshoot is a recoverable user-level
         * amplitude condition. Keep certified SDM state/nonfinite guards
         * fail-closed. Core clients stay strict unless the CLI enables it. */
        if (p->clip_overload && !p->peak_only)
          for (j=0;j<got;++j) if (isfinite(native[j]) &&
              fabs(native[j])>p->clip_ceiling) {
            native[j]=copysign(p->clip_ceiling,native[j]);
            if (p->report.clipped_native_samples<UINT64_MAX)
              ++p->report.clipped_native_samples;
          }
        if (lsx_pcmdsd_modulate(p,native,output+produced,got)!=SOX_DSD_OK)
          goto failed;
        produced+=got;
        continue;
      }
      if (take) continue;
    }
    if (p->filtered_pos==p->filtered_n) {
      p->filtered_pos=p->filtered_n=0;
      while (p->working_pos<p->working_n && p->filtered_n<PCMDSD_BATCH) {
        double x=p->working[p->working_pos++];
        if (!isfinite(x)) {fail_stream(p,LSX_PCMDSD_INPUT_NONFINITE,x,UINT_MAX);goto failed;}
        if (feed_fir(p,x,&p->filtered[p->filtered_n])) ++p->filtered_n;
      }
      if (finish && p->source_done && p->working_pos==p->working_n)
        while (p->fir_produced<p->working_limit && p->filtered_n<PCMDSD_BATCH)
          if (feed_fir(p,0.,&p->filtered[p->filtered_n])) ++p->filtered_n;
      if (p->filtered_n) {
        observe(p,LSX_PCMDSD_STAGE_PREFILTER,p->filtered,p->filtered_n);
        continue;
      }
    }
    if (p->working_pos==p->working_n && !p->source_done) {
      p->working_pos=p->working_n=0;
      got=PCMDSD_BATCH;
      if (finish) {
        rc=lsx_rate_f64_finish(p->source,p->working_limit,p->working,&got);
        if (rc!=SOX_DSD_NEED_OUTPUT && rc!=SOX_DSD_DONE) goto stream_error;
        if (rc==SOX_DSD_DONE) p->source_done=1;
      } else {
        size_t j;
        take=min(available-used,(size_t)PCMDSD_BATCH);
        if (take>UINT64_MAX-p->report.input_frames) goto stream_error;
        for (j=0;j<take;++j) if (!isfinite(input[used+j])) {
          fail_stream(p,LSX_PCMDSD_INPUT_NONFINITE,input[used+j],UINT_MAX);goto failed;
        }
        rc=lsx_rate_f64_process(p->source,input?input+used:NULL,&take,p->working,&got);
        if (rc!=SOX_DSD_NEED_INPUT && rc!=SOX_DSD_NEED_OUTPUT) goto stream_error;
        observe(p,LSX_PCMDSD_STAGE_SOURCE,input?input+used:NULL,take);
        used+=take;
        p->report.input_frames+=take;
      }
      p->working_n=got;
      observe(p,LSX_PCMDSD_STAGE_R,p->working,got);
      if (got || p->source_done || (!finish && used<available)) continue;
    }
    /* Every iteration must consume, produce, finish a stage, or return for
     * more source samples. A stalled finite stream is a processing error. */
    if (finish) goto stream_error;
    break;
  }
  *input_n=used;*output_n=produced;
  p->report.committed_frames+=produced;
  return p->done?SOX_DSD_DONE:(produced==capacity?SOX_DSD_NEED_OUTPUT:SOX_DSD_NEED_INPUT);
stream_error:
  fail_stream(p,LSX_PCMDSD_STREAM_ERROR,0,UINT_MAX);
failed:
  *input_n=used;*output_n=0; /* discard ALL output from this call */
  return p->error;
}

sox_dsd_status_t lsx_pcmdsd_process(lsx_pcmdsd *p,const double *in,size_t *ni,
    sox_sample_t *out,size_t *no)
{
  if (!p) return SOX_DSD_BAD_ARGUMENT;
  if (!ni || !no) return p->error=SOX_DSD_BAD_ARGUMENT;
  return pump(p,in,ni,out,no,0);
}
sox_dsd_status_t lsx_pcmdsd_finish(lsx_pcmdsd *p,sox_sample_t *out,size_t *no)
{
  size_t n=0;
  if (!p) return SOX_DSD_BAD_ARGUMENT;
  if (!no) return p->error=SOX_DSD_BAD_ARGUMENT;
  return pump(p,NULL,&n,out,no,1);
}
sox_dsd_status_t lsx_pcmdsd_report_get(const lsx_pcmdsd *p,lsx_pcmdsd_report *r)
{
  if (!p || !r) return SOX_DSD_BAD_ARGUMENT;
  *r=p->report;return SOX_DSD_OK;
}
sox_dsd_status_t lsx_pcmdsd_state_get(const lsx_pcmdsd *p,sdm_normal_t *s)
{
  if (!p || !s) return SOX_DSD_BAD_ARGUMENT;
  *s=p->sdm;s->profile=NULL;s->monitor=NULL;return SOX_DSD_OK;
}
void lsx_pcmdsd_destroy(lsx_pcmdsd *p)
{
  if (!p) return;
  lsx_rate_f64_destroy(p->source);
  lsx_rate_f64_destroy(p->interpolator);
  free(p->ring);free(p);
}

static int effect_start(sox_effect_t *e,int candidate)
{
  lsx_pcmdsd_private *p=e->priv;
  const lsx_pcmdsd_profile *profile;
  uint32_t source;
  double scale;
  sox_dsd_status_t rc;
  if (!lsx_dsd_integer_rate(e->in_signal.rate,&source)) {
    lsx_fail("pcmdsd: positive integer source Hz required; insert an explicit rate effect");
    return SOX_EOF;
  }
  profile=lsx_pcmdsd_profile_find(p->options.rate_hz);
  if (!profile || p->options.profile!=LSX_DSD_PROFILE_MASTERING ||
      (p->options.pinned_native_hz && p->options.pinned_native_hz!=p->options.rate_hz)) {
    lsx_fail("pcmdsd: no matching composite mastering profile; legacy sdm remains explicit");
    return SOX_EOF;
  }
  scale=p->options.reference==LSX_DSD_REF_PCM?.5:
      p->options.reference==LSX_DSD_REF_DSD?1.:
      p->resolved_reference?p->resolved_reference:.5;
  p->resolved_reference=scale;
  if (candidate)
    rc=lsx_pcmdsd_candidate_create(source,profile->native_hz,scale,(unsigned)e->flow,
        NULL,profile->bounds,&p->encoder);
  else
    rc=lsx_pcmdsd_create(source,profile->native_hz,scale,(unsigned)e->flow,&p->encoder);
  if (rc!=SOX_DSD_OK) {
    lsx_fail("pcmdsd: %s unqualified or unavailable (status %d); no output master produced",
        profile->id,(int)rc);
    return SOX_EOF;
  }
  p->applied_gain=p->options.headroom==LSX_DSD_HEADROOM_FIXED?
      pow(10.,-p->options.headroom_db/20.):
      !candidate && p->options.headroom==LSX_DSD_HEADROOM_NONE &&
      (p->options.clip==LSX_DSD_CLIP_WARN ||
       lsx_pcmdsd_strict_keeps_default_gain(profile->native_hz))?
      lsx_pcmdsd_default_warn_gain(profile->native_hz):1.;
  if (p->options.headroom==LSX_DSD_HEADROOM_AUTO && !candidate) {
    p->scan_file=lsx_tmpfile();
    if (!p->scan_file) {
      lsx_fail("pcmdsd: cannot create headroom scan file: %s",strerror(errno));
      lsx_pcmdsd_destroy(p->encoder);p->encoder=NULL;
      return SOX_EOF;
    }
    lsx_pcmdsd_set_peak_scan(p->encoder);
  } else {
    lsx_pcmdsd_set_gain(p->encoder,p->applied_gain);
    /* Candidate/test-only controls stay strict by default. */
    lsx_pcmdsd_set_clip(p->encoder,!candidate && p->options.clip==LSX_DSD_CLIP_WARN);
  }
  e->out_signal.rate=profile->native_hz;e->out_signal.precision=1;
  /* Never let generic precision-1 gain/dither alter the native decisions. */
  e->out_signal.mult=NULL;
  return SOX_SUCCESS;
}
int lsx_pcmdsd_start(sox_effect_t *e) {return effect_start(e,0);}
int lsx_pcmdsd_candidate_start(sox_effect_t *e) {return effect_start(e,1);}
void lsx_pcmdsd_set_reference(sox_effect_t *e,double scale)
{
  if (e && !strcmp(e->handler.name,"pcmdsd"))
    ((lsx_pcmdsd_private *)e->priv)->resolved_reference=scale;
}
static int effect_failure(sox_effect_t *e)
{
  lsx_pcmdsd_private *p=e->priv;
  lsx_pcmdsd_report r={0};
  lsx_pcmdsd_report_get(p->encoder,&r);
  static const char *const failures[]={"none","nonfinite input",
    "interpolation overload","nonfinite modulator state","state guard exceeded",
    "stream error"};
  /* No allocation, buffer or formatting work on the successful read path.
   * The FIRST rejected sample supplies a lower bound, not the attenuation
   * that would admit the rest of the stream.  Keep that distinction visible. */
  if (r.failure==LSX_PCMDSD_INTERPOLATION_OVERLOAD) {
    lsx_fail("pcmdsd: %s (failure %u) at native frame %" PRIu64
        ", channel %u, coordinate %u, value %.17g, observed peak %.17g; "
        "minimum explicit attenuation %.9g dB (lower bound from first "
        "overloaded sample; later peaks may require more); output block discarded",
        failures[r.failure],(unsigned)r.failure,r.first_bad_frame,r.channel,
        r.coordinate,r.failure_value,r.peak,r.minimum_attenuation_db);
  } else {
    lsx_fail("pcmdsd: %s (failure %u) at native frame %" PRIu64
        ", channel %u, coordinate %u, value %.17g, observed peak %.17g; "
        "no attenuation estimate for this failure; output block discarded",
        (unsigned)r.failure<array_length(failures)?failures[r.failure]:"unknown failure",
        (unsigned)r.failure,r.first_bad_frame,r.channel,r.coordinate,
        r.failure_value,r.peak);
  }
  return LSX_EFF_FATAL;
}
/* Streaming exact-peak scan over the SAME interpolation path as the actual
 * encoder. No modulator decisions are produced during this pass. A PCM-rate
 * temporary file, rather than an unbounded in-memory array or native-rate
 * spool, makes the two passes work with long albums and pipes. */
static int scan_flow(sox_effect_t *e,const sox_sample_t *in,size_t count)
{
  lsx_pcmdsd_private *p=e->priv;
  sox_sample_t discard[PCMDSD_NATIVE_BATCH];
  size_t used=0;
  if (count && fwrite(in,sizeof(*in),count,p->scan_file)!=count) {
    lsx_fail("pcmdsd: cannot spool headroom input: %s",strerror(errno));
    return LSX_EFF_FATAL;
  }
  while (used<count) {
    double input[PCMDSD_BATCH];
    size_t i,n=min(count-used,(size_t)PCMDSD_BATCH),out_n=array_length(discard);
    sox_dsd_status_t rc;
    for (i=0;i<n;++i) input[i]=(double)in[used+i]/SOX_SAMPLE_MAX;
    rc=lsx_pcmdsd_process(p->encoder,input,&n,discard,&out_n);
    if (rc!=SOX_DSD_NEED_INPUT && rc!=SOX_DSD_NEED_OUTPUT)
      return effect_failure(e);
    if (!n && !out_n) {
      fail_stream(p->encoder,LSX_PCMDSD_STREAM_ERROR,0,UINT_MAX);
      return effect_failure(e);
    }
    used+=n;
  }
  return SOX_SUCCESS;
}

/* SoX drains a scanning effect only after all channel flows received EOF.
 * Like gain -n, flow 0 can then inspect all per-channel previews and apply
 * ONE common attenuation; no stereo balance change or input reread occurs. */
static int start_headroom_replay(sox_effect_t *e)
{
  sox_effect_t *first=e-e->flow;
  size_t i;
  double peak=0., gain;
  for (i=0;i<e->flows;i++) {
    sox_effect_t *f=first+i;
    lsx_pcmdsd_private *p=f->priv;
    sox_sample_t discard[PCMDSD_NATIVE_BATCH];
    sox_dsd_status_t rc;
    lsx_pcmdsd_report r;
    do {
      size_t n=array_length(discard);
      rc=lsx_pcmdsd_finish(p->encoder,discard,&n);
      if (rc!=SOX_DSD_DONE && rc!=SOX_DSD_NEED_OUTPUT)
        return effect_failure(f);
      if (rc==SOX_DSD_NEED_OUTPUT && !n) {
        lsx_fail("pcmdsd: headroom scan could not finish");
        return LSX_EFF_FATAL;
      }
    } while (rc!=SOX_DSD_DONE);
    if (lsx_pcmdsd_report_get(p->encoder,&r)!=SOX_DSD_OK) return LSX_EFF_FATAL;
    if (r.peak>peak) peak=r.peak;
  }
  /* Use the measured peak after BOTH SRC stages and the FIR. The tiny
   * round-off allowance is < 1e-10 dB, not arbitrary programme headroom. */
  {
    double ceiling=lsx_pcmdsd_warn_clip_ceiling(((lsx_pcmdsd_private *)first->priv)->options.rate_hz);
    gain=peak>ceiling ? (ceiling*(1.-1e-12))/peak : 1.;
  }
  lsx_report("pcmdsd: measured interpolated peak %.12g; headroom cut %.9g dB across %u channel(s)",
      peak,-20.*log10(gain),e->flows);
  for (i=0;i<e->flows;i++) {
    sox_effect_t *f=first+i;
    lsx_pcmdsd_private *p=f->priv;
    lsx_pcmdsd *fresh=NULL;
    uint32_t source;
    sox_dsd_status_t rc;
    if (!lsx_dsd_integer_rate(f->in_signal.rate,&source)) return LSX_EFF_FATAL;
    lsx_pcmdsd_destroy(p->encoder);p->encoder=NULL;
    rc=lsx_pcmdsd_create(source,p->options.rate_hz,
        p->resolved_reference,(unsigned)f->flow,&fresh);
    if (rc!=SOX_DSD_OK) {
      lsx_fail("pcmdsd: cannot start headroom replay (status %d)",(int)rc);
      return LSX_EFF_FATAL;
    }
    p->encoder=fresh;
    p->applied_gain=gain;
    lsx_pcmdsd_set_gain(fresh,gain);
    lsx_pcmdsd_set_clip(fresh,p->options.clip==LSX_DSD_CLIP_WARN);
    if (fseek(p->scan_file,0,SEEK_SET)) {
      lsx_fail("pcmdsd: cannot rewind headroom input: %s",strerror(errno));
      return LSX_EFF_FATAL;
    }
    p->scan_started=1;
  }
  return SOX_SUCCESS;
}

int lsx_pcmdsd_flow(sox_effect_t *e,const sox_sample_t *in,sox_sample_t *out,
    size_t *ni,size_t *no)
{
  lsx_pcmdsd_private *p=e->priv;
  double input[PCMDSD_BATCH];
  size_t available=*ni,capacity=*no,used=0,produced=0;
  *ni=*no=0;
  if (p->scan_file) {
    if (scan_flow(e,in,available)!=SOX_SUCCESS) return LSX_EFF_FATAL;
    *ni=available;
    return SOX_SUCCESS;
  }
  if (!capacity) return SOX_SUCCESS;
  do {
    size_t i,n=min(available-used,(size_t)PCMDSD_BATCH),got=capacity;
    sox_dsd_status_t rc;
    for (i=0;i<n;++i) input[i]=(double)in[used+i]/SOX_SAMPLE_MAX;
    rc=lsx_pcmdsd_process(p->encoder,input,&n,out,&got);
    if (rc!=SOX_DSD_NEED_INPUT && rc!=SOX_DSD_NEED_OUTPUT)
      return effect_failure(e);
    used+=n;produced=got;
    /* The effects scheduler may start drain after a no-output call once the
     * upstream source reaches EOF. Consume ALL offered PCM before returning
     * without output, not just one normalization batch. Returning after the
     * first produced block also preserves the core's failure-commit boundary. */
    if (!n && !got && used<available) {
      fail_stream(p->encoder,LSX_PCMDSD_STREAM_ERROR,0,UINT_MAX);
      return effect_failure(e);
    }
  } while (!produced && used<available);
  *ni=used;*no=produced;return SOX_SUCCESS;
}

static int replay_drain(sox_effect_t *e,sox_sample_t *out,size_t *no)
{
  lsx_pcmdsd_private *p=e->priv;
  size_t capacity=*no;
  *no=0;
  if (!p->scan_started && start_headroom_replay(e)!=SOX_SUCCESS)
    return LSX_EFF_FATAL;
  while (1) {
    if (p->replay_pos<p->replay_size) {
      double input[PCMDSD_BATCH];
      size_t i,n=p->replay_size-p->replay_pos,got=capacity;
      sox_dsd_status_t rc;
      for (i=0;i<n;++i) input[i]=(double)p->replay[p->replay_pos+i]/SOX_SAMPLE_MAX;
      rc=lsx_pcmdsd_process(p->encoder,input,&n,out,&got);
      if (rc!=SOX_DSD_NEED_INPUT && rc!=SOX_DSD_NEED_OUTPUT)
        return effect_failure(e);
      if (!n && !got) {
        fail_stream(p->encoder,LSX_PCMDSD_STREAM_ERROR,0,UINT_MAX);
        return effect_failure(e);
      }
      p->replay_pos+=n;
      if (got) {*no=got;return SOX_SUCCESS;}
      continue;
    }
    if (!p->replay_eof) {
      p->replay_pos=0;
      p->replay_size=fread(p->replay,sizeof(*p->replay),array_length(p->replay),p->scan_file);
      if (ferror(p->scan_file)) {
        lsx_fail("pcmdsd: cannot replay headroom input: %s",strerror(errno));
        return LSX_EFF_FATAL;
      }
      if (p->replay_size) continue;
      p->replay_eof=1;
    }
    {
      sox_dsd_status_t rc=lsx_pcmdsd_finish(p->encoder,out,&capacity);
      if (rc!=SOX_DSD_NEED_OUTPUT && rc!=SOX_DSD_DONE)
        return effect_failure(e);
      *no=capacity;
      return rc==SOX_DSD_DONE?SOX_EOF:SOX_SUCCESS;
    }
  }
}

int lsx_pcmdsd_drain(sox_effect_t *e,sox_sample_t *out,size_t *no)
{
  lsx_pcmdsd_private *p=e->priv;
  sox_dsd_status_t rc;
  if (p->scan_file) return replay_drain(e,out,no);
  rc=lsx_pcmdsd_finish(p->encoder,out,no);
  if (rc!=SOX_DSD_NEED_OUTPUT && rc!=SOX_DSD_DONE) {*no=0;return effect_failure(e);}
  return rc==SOX_DSD_DONE?SOX_EOF:SOX_SUCCESS;
}
int lsx_pcmdsd_stop(sox_effect_t *e)
{
  lsx_pcmdsd_private *p=e->priv;
  lsx_pcmdsd_report r={0};
  if (p->encoder) {
    lsx_pcmdsd_report_get(p->encoder,&r);
    lsx_dsd_report_note_encode(p->encoder);
    lsx_pcmdsd_destroy(p->encoder);p->encoder=NULL;
  }
  if (p->scan_file) {lsx_close_tmpfile(p->scan_file);p->scan_file=NULL;}
  if (r.clipped_native_samples)
    lsx_warn("clipped %" PRIu64 " interpolated samples on channel %u at %.3g modulator ceiling; use --headroom DB or --auto-headroom to avoid clipping",
        r.clipped_native_samples,(unsigned)e->flow+1,
        lsx_pcmdsd_warn_clip_ceiling(p->options.rate_hz));
  return SOX_SUCCESS;
}
