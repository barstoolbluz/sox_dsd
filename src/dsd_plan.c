/* Domain planning is a pure, pre-output operation.  In particular, it does not
 * call an effect's start(): those functions can allocate state and change I/O.
 * The returned plan owns only its arrays and borrows static effect names.
 */
#include "dsd.h"
#include "dsd_kernels.h"
#include "pcmdsd.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <stdarg.h>

static int fail(char *dst, size_t n, char const *fmt, ...)
{
  va_list ap;
  if (dst && n) {
    va_start(ap,fmt);
    vsnprintf(dst,n,fmt,ap);
    va_end(ap);
  }
  return 0;
}

static int is(char const *x, char const *y) {return x && !strcmp(x,y);}
static int is_parallel(lsx_dsd_combine c) {return c >= LSX_DSD_COMBINE_MIX;}

static int native_identity(lsx_dsd_effect_spec const *e, unsigned channels)
{
  return (is(e->name,"channels") && e->out_channels == channels) ||
         (is(e->name,"remix") && e->native_permutation &&
          e->out_channels == channels);
}

static int native_step(lsx_dsd_effect_spec const *e, unsigned channels)
{
  return is(e->name,"trim") || is(e->name,"dsdstat") ||
         native_identity(e,channels);
}

static int append(lsx_dsd_plan *p, char const *name, lsx_dsd_domain before,
    lsx_dsd_domain after, double inrate, double outrate,
    unsigned inchan, unsigned outchan, int implicit, int input_index, double ref)
{
  lsx_dsd_plan_step *s;
  if (p->step_count >= p->step_capacity) return 0;
  s=&p->steps[p->step_count++];
  s->name=name; s->before=before; s->after=after;
  s->rate_before=inrate; s->rate_after=outrate;
  s->channels_before=inchan; s->channels_after=outchan;
  s->implicit=implicit; s->input_index=input_index; s->reference=ref;
  return 1;
}

void lsx_dsd_plan_free(lsx_dsd_plan *p)
{
  if (p) {
    free(p->inputs); free(p->steps);
    memset(p,0,sizeof(*p));
  }
}

static int resolve_decode(lsx_dsd_plan *p, const lsx_dsd_policy *policy,
    uint32_t native_rate,
    lsx_dsd_decode profile, lsx_dsd_level level,
    double destination, lsx_dsd_bandwidth bandwidth,
    char *error, size_t n)
{
  double pass, stop, intermediate, effective;
  lsx_dsd_rate const *rate=lsx_dsd_rate_find(native_rate);
  if (policy->decode_pinned_native_hz && policy->decode_pinned_native_hz != native_rate)
    return fail(error,n,"versioned --dsd-decode ID is for a different native DSD clock (%u Hz, expected %u Hz)",
        native_rate,policy->decode_pinned_native_hz);
  if (!rate || !(rate->capabilities & LSX_DSD_RECONSTRUCT))
    return fail(error,n,"no qualified decoder rate for native DSD %u Hz",native_rate);
  if (profile == LSX_DSD_PROFILE_LEGACY) {
    /* Generic legacy reconstruction is explicitly unqualified.  It must not
     * acquire a made-up mastering passband or filter identity.  A mastering R
     * is only an interoperable default PCM working clock. */
    if (!lsx_dsd_profile_edges(native_rate,LSX_DSD_PROFILE_MASTERING,
          &pass,&stop,&intermediate))
      return fail(error,n,"no PCM working rate for legacy decoder");
    pass=stop=0;
    if (bandwidth == LSX_DSD_BANDWIDTH_STRICT)
      return fail(error,n,"strict bandwidth cannot certify the legacy decoder");
  } else if (!lsx_dsd_profile_edges(native_rate,profile,&pass,&stop,&intermediate))
    return fail(error,n,"no decoder profile for %u Hz",native_rate);
  if (destination && destination != intermediate) {
    uint32_t requested;
    if (!lsx_dsd_integer_rate(destination,&requested) ||
        !lsx_dsd_pcm_rate_supported(requested))
      return fail(error,n,"new-profile PCM rate must be an exact supported integer Hz (got %.9g)",destination);
  }
  effective=destination ? lsx_dsd_effective_bandwidth(pass,intermediate,destination) : pass;
  if (bandwidth == LSX_DSD_BANDWIDTH_STRICT && effective + 1e-9 < pass)
    return fail(error,n,"strict bandwidth rejects %.0f Hz PCM output: %.0f Hz profile passband reduces to %.3f Hz",
        destination,pass,effective);
  p->decoder_pass_hz=pass;
  p->decoder_stop_hz=stop;
  p->decoder_intermediate_hz=intermediate;
  p->effective_bandwidth_hz=effective;
  p->decoder_gain=level==LSX_DSD_LEVEL_SACD?2.:1.;
  p->decoder_id=profile==LSX_DSD_PROFILE_LEGACY?"decode.legacy.generic":
      lsx_dsd_frontend_profile_find(native_rate,profile)->canonical_id;
  p->needs_unimplemented_dsp=1;
  p->unavailable_reason="DSD reconstruction is scheduled for P06/P07/P08";
  return 1;
}

static int resolve_encode(lsx_dsd_plan *p, const lsx_dsd_policy *policy,
    uint32_t hz,
    lsx_dsd_encode profile, char *error, size_t n)
{
  lsx_dsd_rate const *r=lsx_dsd_rate_find(hz);
  if (policy->encode_pinned_native_hz && policy->encode_pinned_native_hz != hz)
    return fail(error,n,"versioned --dsd-encode ID is for a different native DSD clock (%u Hz, expected %u Hz)",
        hz,policy->encode_pinned_native_hz);
  if (!r || !(r->capabilities & LSX_DSD_MODULATE))
    return fail(error,n,"no supported composite DSD encoder at %u Hz",hz);
  if (profile == LSX_DSD_ENCODE_MASTERING) p->encoder_id=r->encode_mastering_id;
  else if (profile == LSX_DSD_ENCODE_LEGACY) p->encoder_id="encode.legacy.explicit";
  else p->encoder_id="encode.experimental.explicit";
  if (profile!=LSX_DSD_ENCODE_MASTERING || !lsx_pcmdsd_qualified(hz)) {
    p->needs_unimplemented_dsp=1;
    p->unavailable_reason=profile==LSX_DSD_ENCODE_MASTERING?
        "P10 mastering profile is unqualified; qualification evidence blocks activation":
        "no qualified composite for legacy/experimental selection; explicit sdm remains available";
  }
  return 1;
}

/* A force is checked only for a family whose P11 context will exist. Use
 * the SAME dispatcher as context creation, including runtime CPU capability
 * and documented/compatibility environment precedence. */
static int check_kernel(enum lsx_dsd_kernel_family family, char const *requested,
    char *error, size_t n)
{
  const lsx_dsd_kernel *selected=NULL;
  int rc=lsx_dsd_kernel_select(family,requested,&selected);
  if (!rc) return 1;
  return fail(error,n,"requested DSD %s kernel tier is %s",
      family==LSX_DSD_FIR?"FIR":"SDM",
      rc==-2?"unavailable on this CPU/build":"unknown or unimplemented");
}

/* An explicit leading decoder is a configuration for per-input reconstruction
 * whenever file gain or the combiner makes that reconstruction mandatory.
 * Check precedence once, before choosing the common PCM clock. */
static int decoder_selection(lsx_dsd_plan_spec const *spec,
    lsx_dsd_effect_spec const *e, lsx_dsd_decode *decoder,
    lsx_dsd_level *level, char *error, size_t n)
{
  if (e->dsd.profile_specified && spec->policy.decode_specified &&
      e->dsd.profile!=spec->policy.decode)
    return fail(error,n,"conflicting --dsd-decode and dsdpcm -p selections");
  if (e->dsd.pinned_native_hz && spec->policy.decode_pinned_native_hz &&
      e->dsd.pinned_native_hz != spec->policy.decode_pinned_native_hz)
    return fail(error,n,"conflicting versioned --dsd-decode and dsdpcm -p native clocks");
  if (e->dsd.level_specified && spec->policy.level_specified &&
      e->dsd.level!=spec->policy.level)
    return fail(error,n,"conflicting --dsd-level and dsdpcm -l selections");
  *decoder=e->dsd.profile_specified?e->dsd.profile:spec->policy.decode;
  *level=e->dsd.level_specified?e->dsd.level:spec->policy.level;
  return 1;
}

/* Place automatically requested normalization in PCM, ahead of terminal
 * modulation.  Guard (-G) alone is conditional at runtime and does not imply
 * an unconditional gain effect. */
static int append_norm(lsx_dsd_plan_spec const *spec, lsx_dsd_plan *p,
    lsx_dsd_domain *domain, double *rate, double *ref, unsigned channels,
    lsx_dsd_decode decoder, lsx_dsd_level level, char *error, size_t n)
{
  if (*domain==LSX_DOP_TRANSPORT)
    return fail(error,n,"normalization cannot follow terminal DoP");
  if (*domain==LSX_DSD_NATIVE) {
    double before=*rate;
    if (spec->policy.mode==LSX_DSD_MODE_NATIVE)
      return fail(error,n,"native mode forbids PCM normalization");
    if (p->encode_count)
      return fail(error,n,"normalization after modulation requires an explicit dsdpcm boundary");
    if (!resolve_decode(p,&spec->policy,(uint32_t)*rate,decoder,level,0,
          spec->policy.bandwidth,error,n)) return 0;
    *rate=p->decoder_intermediate_hz;
    *domain=LSX_PCM_AUDIO;
    *ref=1./p->decoder_gain;
    ++p->graph_decode_count;
    p->trim_native_seek=0;
    if (!append(p,"implicit_dsdpcm",LSX_DSD_NATIVE,LSX_PCM_AUDIO,
          before,*rate,channels,channels,1,-1,*ref))
      return fail(error,n,"preflight step capacity exceeded");
  }
  if (!append(p,"auto_normalize",LSX_PCM_AUDIO,LSX_PCM_AUDIO,
        *rate,*rate,channels,channels,1,-1,*ref))
    return fail(error,n,"preflight step capacity exceeded");
  return 1;
}

int lsx_dsd_plan_build(lsx_dsd_plan_spec const *spec, lsx_dsd_plan *p,
    char *error, size_t n)
{
  size_t i, pending_explicit_decodes=0;
  int any_native=0, any_pcm=0, any_scaling=0, differing_native=0;
  int all_native=1, per_input_decode=0, leading_consumed=0;
  uint32_t native_rate=0, output_hz=0;
  unsigned channels=0;
  double rate=0, common_pcm_rate=0, largest_r=0, ref=.5;
  lsx_dsd_domain domain, requested_domain;
  lsx_dsd_decode decoder;
  lsx_dsd_level level;
  int explicit_encode=0, has_dop=0, norm_inserted=0;
  int explicit_dither_seen=0, norm_sdm_unavailable=0;
  int native_chain_only=1;
  if (error && n) error[0]=0;
  if (!spec || !p || !spec->inputs || !spec->input_count)
    return fail(error,n,"missing planner input");
  memset(p,0,sizeof(*p));
  decoder=spec->policy.decode;
  level=spec->policy.level;
  if (spec->input_count > (SIZE_MAX / sizeof(*p->inputs)) ||
      spec->effect_count > (SIZE_MAX - spec->input_count - 12) / 3)
    return fail(error,n,"planner input exceeds allocation bounds");
  p->inputs=calloc(spec->input_count,sizeof(*p->inputs));
  p->step_capacity=spec->effect_count*3+spec->input_count+12;
  p->steps=calloc(p->step_capacity,sizeof(*p->steps));
  if (!p->inputs || !p->steps) {
    lsx_dsd_plan_free(p);
    return fail(error,n,"out of memory allocating preflight plan");
  }
  p->input_count=spec->input_count;
  p->executable=1;
  p->layout_identity_preserved=1;
  p->trim_native_seek=1;
  for (i=0;i<spec->input_count;i++) {
    lsx_dsd_plan_input *in=&p->inputs[i];
    lsx_dsd_input_spec const *src=&spec->inputs[i];
    uint32_t exact;
    double pass,stop,r;
    in->native_rate=src->native_signal.rate;
    in->effective_rate=in->native_rate;
    in->channels=src->native_signal.channels;
    in->native_domain=src->encoding==SOX_ENCODING_DSD? LSX_DSD_NATIVE: LSX_PCM_AUDIO;
    in->effective_domain=in->native_domain;
    in->reference=in->native_domain==LSX_DSD_NATIVE?1.:.5;
    in->volume=src->input_volume;
    if (!isfinite(in->volume)) return fail(error,n,"invalid input gain at input %lu",(unsigned long)i);
    if (!in->channels || !isfinite(in->native_rate) || in->native_rate<=0)
      return fail(error,n,"invalid input signal at index %lu",(unsigned long)i);
    if (in->native_domain==LSX_DSD_NATIVE) {
      lsx_dsd_rate const *d;
      if (!lsx_dsd_integer_rate(in->native_rate,&exact) ||
          !(d=lsx_dsd_rate_find(exact)) || !(d->capabilities & LSX_DSD_READ_NATIVE))
        return fail(error,n,"native DSD rate %.9g Hz has no enabled profile",in->native_rate);
      /* A native-only path does not require a decoder profile.  In
       * particular, selecting the legacy decoder must not inhibit repacking. */
      if (!lsx_dsd_profile_edges(exact,spec->policy.decode,&pass,&stop,&r) &&
          spec->policy.decode==LSX_DSD_PROFILE_LEGACY)
        lsx_dsd_profile_edges(exact,LSX_DSD_PROFILE_MASTERING,&pass,&stop,&r);
      largest_r=fmax(largest_r,r);
      any_native=1;
      if (!native_rate) native_rate=exact;
      if (native_rate!=exact) {
        differing_native=1;
        if (spec->combine==LSX_DSD_COMBINE_CONCAT)
          return fail(error,n,"native DSD clocks differ in a concatenation");
      }
    } else {
      all_native=0; any_pcm=1;
      if (!common_pcm_rate) common_pcm_rate=in->native_rate;
      else if (common_pcm_rate != in->native_rate)
        return fail(error,n,"PCM input rates differ: %.9g and %.9g Hz",common_pcm_rate,in->native_rate);
    }
    if (in->volume != 1) any_scaling=1;
    if (!src->layout_known) p->layout_identity_preserved=0;
  }

  if (differing_native && spec->output_native_capable &&
      !spec->requested_output_rate)
    return fail(error,n,"multiple native DSD clocks require an explicit native output rate");
  if (spec->combine==LSX_DSD_COMBINE_CONCAT && any_native) {
    for (i=1;i<spec->input_count;i++)
      if (p->inputs[i].native_domain!=p->inputs[0].native_domain ||
          p->inputs[i].channels!=p->inputs[0].channels ||
          p->inputs[i].native_rate!=p->inputs[0].native_rate)
        return fail(error,n,"native concatenation needs identical domains, rates and channels");
    if (!p->layout_identity_preserved)
      return fail(error,n,"native concatenation has unknown or conflicting channel identities");
  }
  /* Sequence segments are independently planned by the caller before output. */
  if (any_native && spec->policy.mode == LSX_DSD_MODE_NATIVE &&
      (any_scaling || is_parallel(spec->combine)))
    return fail(error,n,"native mode cannot scale/combine DSD pulses before the effects chain");

  for (i=0;i<spec->effect_count;i++) {
    lsx_dsd_effect_spec const *e=&spec->effects[i];
    if (is(e->name,"dop")) {
      if (has_dop++ || i+1!=spec->effect_count)
        return fail(error,n,"dop must occur exactly once, as the terminal effect");
    } else if (is(e->name,"dsdpcm")) {
      /* A reconstruction boundary makes an earlier trim PCM processing. */
      native_chain_only=0;
      ++pending_explicit_decodes;
    } else if (is(e->name,"pcmdsd") || is(e->name,"sdm") ||
               e->dither_precision_one) {
      ++explicit_encode;
      native_chain_only=0;
    } else if (!native_step(e,p->inputs[0].channels)) {
      native_chain_only=0;
    }
  }
  if (has_dop && !spec->output_dop_capable)
    return fail(error,n,"dop needs a lossless 24-bit PCM-capable transport destination");
  if (spec->output_is_null) requested_domain=has_dop?LSX_DOP_TRANSPORT:LSX_PCM_AUDIO;
  else if (spec->output_native_capable) requested_domain=LSX_DSD_NATIVE;
  else requested_domain=has_dop?LSX_DOP_TRANSPORT:LSX_PCM_AUDIO;
  if (has_dop && requested_domain!=LSX_DOP_TRANSPORT)
    return fail(error,n,"DoP requires a PCM transport output, not a native DSD container");
  if (!spec->output_native_capable && !spec->output_pcm_capable && !spec->output_is_null)
    return fail(error,n,"destination cannot encode the selected DSD/PCM format");
  if (requested_domain==LSX_PCM_AUDIO || spec->policy.normalizing ||
      (requested_domain==LSX_DSD_NATIVE && all_native &&
       ((spec->requested_output_rate && spec->requested_output_rate!=native_rate) ||
        (spec->requested_output_channels &&
         spec->requested_output_channels!=p->inputs[0].channels))))
    native_chain_only=0;
  if (spec->requested_output_rate &&
      !lsx_dsd_integer_rate(spec->requested_output_rate,&output_hz) && any_native)
    return fail(error,n,"DSD-related output rate must be an exact integer Hz");
  if (requested_domain == LSX_DSD_NATIVE) {
    if (!all_native && !output_hz) output_hz=2822400;
    if (all_native && !output_hz) output_hz=native_rate;
    if (!lsx_dsd_rate_find(output_hz) ||
        !(lsx_dsd_rate_find(output_hz)->capabilities & LSX_DSD_WRITE_NATIVE))
      return fail(error,n,"native DSD writer is disabled or unsupported at %u Hz",output_hz);
    p->native_output_hz=output_hz;
  } else if (requested_domain==LSX_DOP_TRANSPORT) {
    if (!all_native && !explicit_encode)
      return fail(error,n,"DoP requires native DSD or a terminal explicit modulator");
    /* The native clock is the one immediately before dop, not the original
     * source clock.  Resolve it when the terminal effect is visited. */
  }

  /* The input combiner operates before add_effects. Native DSD in parallel or
   * under file gain must be reconstructed into each input, not after mixing. */
  per_input_decode=any_native && (any_scaling || is_parallel(spec->combine) || any_pcm);
  if (any_pcm && any_native && !is_parallel(spec->combine))
    return fail(error,n,"serial concatenation cannot combine native DSD and PCM");
  if (any_native && per_input_decode) {
    if (spec->policy.mode==LSX_DSD_MODE_NATIVE)
      return fail(error,n,"native mode forbids per-input reconstruction");
    if (spec->effect_count && is(spec->effects[0].name,"dsdpcm")) {
      lsx_dsd_effect_spec const *e=&spec->effects[0];
      if (!decoder_selection(spec,e,&decoder,&level,error,n)) return 0;
      if (level==LSX_DSD_LEVEL_SACD &&
          (spec->policy.guarded || spec->policy.normalizing))
        return fail(error,n,"sacd reconstruction cannot be combined with automatic guard or normalization");
      if (e->dsd.pinned_native_hz) for (i=0;i<spec->input_count;i++)
        if (p->inputs[i].native_domain==LSX_DSD_NATIVE &&
            p->inputs[i].native_rate!=e->dsd.pinned_native_hz)
          return fail(error,n,"versioned decoder ID is for a different native DSD clock at input %lu",
              (unsigned long)i);
      if (any_pcm && e->dsd.rate_hz && e->dsd.rate_hz!=common_pcm_rate)
        return fail(error,n,"leading dsdpcm rate conflicts with the mixed PCM input clock");
      leading_consumed=1;
      --pending_explicit_decodes;
      if (!any_pcm && !e->dsd.rate_hz) {
        largest_r=0;
        for (i=0;i<spec->input_count;i++) {
          double pass,stop,r;
          if (!lsx_dsd_profile_edges((uint32_t)p->inputs[i].native_rate,
                decoder,&pass,&stop,&r) &&
              !(decoder==LSX_DSD_PROFILE_LEGACY &&
                lsx_dsd_profile_edges((uint32_t)p->inputs[i].native_rate,
                    LSX_DSD_PROFILE_MASTERING,&pass,&stop,&r)))
            return fail(error,n,"no PCM working rate for leading dsdpcm");
          largest_r=fmax(largest_r,r);
        }
      }
    }
    rate=any_pcm?common_pcm_rate:leading_consumed && spec->effects[0].dsd.rate_hz?
        spec->effects[0].dsd.rate_hz:largest_r;
    { uint32_t common_rate;
    if (!lsx_dsd_integer_rate(rate,&common_rate) || !lsx_dsd_pcm_rate_supported(common_rate))
      return fail(error,n,"common DSD/PCM working rate must be a supported integer PCM Hz");
    }
    for (i=0;i<spec->input_count;i++) if (p->inputs[i].native_domain==LSX_DSD_NATIVE) {
      lsx_dsd_plan_input *in=&p->inputs[i];
      if (!resolve_decode(p,&spec->policy,(uint32_t)in->native_rate,decoder,level,rate,
          spec->policy.bandwidth,error,n)) return 0;
      in->effective_rate=rate;
      in->effective_domain=LSX_PCM_AUDIO;
      in->decoder_before_combiner=1;
      in->volume_consumed_by_decoder=1;
      in->decoder_gain=p->decoder_gain;
      in->decoder_id=p->decoder_id;
      in->decoder_pass_hz=p->decoder_pass_hz;
      in->decoder_stop_hz=p->decoder_stop_hz;
      in->effective_bandwidth_hz=p->effective_bandwidth_hz;
      in->reference=1./p->decoder_gain;
      ++p->input_decode_count;
      append(p,"input_dsdpcm",LSX_DSD_NATIVE,LSX_PCM_AUDIO,
          in->native_rate,rate,in->channels,in->channels,1,(int)i,in->reference);
    }
    domain=LSX_PCM_AUDIO;
    ref=any_pcm?.5:1./p->decoder_gain;

  } else {
    domain=p->inputs[0].native_domain;
    rate=p->inputs[0].native_rate;
    ref=domain==LSX_DSD_NATIVE?1.:.5;
  }
  channels=is_parallel(spec->combine) && spec->combine==LSX_DSD_COMBINE_MERGE ? 0:p->inputs[0].channels;
  for (i=0;i<spec->input_count;i++) if (is_parallel(spec->combine)) {
    if (spec->combine==LSX_DSD_COMBINE_MERGE) channels+=p->inputs[i].channels;
    else if (p->inputs[i].channels>channels) channels=p->inputs[i].channels;
  }
  if (is_parallel(spec->combine)) {
    if (any_pcm) ref=.5;
    p->layout_identity_preserved=0;
  }
  p->combiner_domain=domain;
  p->combiner_rate=rate;
  p->combiner_channels=channels;
  p->processing_rate=rate;
  if (per_input_decode) p->trim_native_seek=0;

  /* Leading explicit dsdpcm chooses the working rate. An ordinary 'rate'
   * never replaces an implicit DSD reconstruction and keeps its own options. */
  for (i=0;i<spec->effect_count;i++) {
    lsx_dsd_effect_spec const *e=&spec->effects[i];
    double before=rate;
    unsigned old_channels=channels;
    lsx_dsd_domain old_domain=domain;
    if (i==0 && leading_consumed) continue;
    /* SoX inserts automatic gain before explicit dither.  A modulator which
     * will not be followed by explicit reconstruction must also see the
     * requested PCM normalization before converting to one-bit samples.
     * Native-safe trailing effects do not delay that gain. */
    if (spec->policy.normalizing && !norm_inserted &&
        (is(e->name,"dither") ||
         ((is(e->name,"pcmdsd") || is(e->name,"sdm")) &&
          !pending_explicit_decodes))) {
      if (!append_norm(spec,p,&domain,&rate,&ref,channels,decoder,level,
            error,n)) return 0;
      norm_inserted=1;
      before=rate;old_domain=domain;
    }
    /* add_effects() inserts automatic gain before the first explicit dither,
     * but not before low-level sdm.  Until that placement is supported, an
     * opt-in plan that normalizes ahead of sdm must not execute a different
     * graph with the gain applied to one-bit samples after modulation. */
    if (is(e->name,"sdm") && spec->policy.normalizing &&
        norm_inserted && !explicit_dither_seen)
      norm_sdm_unavailable=1;
    if (is(e->name,"dsdpcm")) {
      if (domain!=LSX_DSD_NATIVE)
        return fail(error,n,"dsdpcm at effect %lu duplicates reconstruction or follows PCM",(unsigned long)(i+1));
      if (spec->policy.mode==LSX_DSD_MODE_NATIVE)
        return fail(error,n,"native mode forbids explicit dsdpcm");
      if (!decoder_selection(spec,e,&decoder,&level,error,n)) return 0;
      if (e->dsd.pinned_native_hz && e->dsd.pinned_native_hz!=(uint32_t)rate)
        return fail(error,n,"versioned decoder ID is for a different native DSD clock");
      if (level==LSX_DSD_LEVEL_SACD &&
          (spec->policy.guarded || spec->policy.normalizing))
        return fail(error,n,"sacd reconstruction cannot be combined with automatic guard or normalization");
      if (!e->dsd.rate_hz) {
        double pass,stop,intermediate;
        if (!lsx_dsd_profile_edges((uint32_t)rate,decoder,&pass,&stop,&intermediate) &&
            !(decoder==LSX_DSD_PROFILE_LEGACY &&
              lsx_dsd_profile_edges((uint32_t)rate,LSX_DSD_PROFILE_MASTERING,
                  &pass,&stop,&intermediate)))
          return fail(error,n,"no PCM working rate for explicit dsdpcm");
        rate=intermediate;
      } else rate=e->dsd.rate_hz;
      if (!resolve_decode(p,&spec->policy,(uint32_t)before,decoder,level,rate,
          spec->policy.bandwidth,error,n)) return 0;
      domain=LSX_PCM_AUDIO;ref=1./p->decoder_gain;
      ++p->graph_decode_count;
      p->trim_native_seek=0;
      append(p,e->name,old_domain,domain,before,rate,old_channels,channels,0,-1,ref);
      --pending_explicit_decodes;
    } else if (is(e->name,"pcmdsd") || is(e->name,"sdm") ||
               e->dither_precision_one) {
      int lowlevel=is(e->name,"sdm") || e->dither_precision_one;
      uint32_t target=e->dsd.rate_hz?e->dsd.rate_hz:
          (p->native_output_hz?p->native_output_hz:2822400);
      if (domain!=LSX_PCM_AUDIO)
        return fail(error,n,"%s at effect %lu duplicates modulation or follows native DSD",e->name,(unsigned long)(i+1));
      if (spec->policy.mode==LSX_DSD_MODE_NATIVE)
        return fail(error,n,"native mode forbids PCM-to-DSD modulation");
      if (e->dsd.pinned_native_hz && e->dsd.pinned_native_hz!=target)
        return fail(error,n,"versioned encoder ID is for a different native DSD clock");
      if (is(e->name,"pcmdsd") && e->dsd.pinned_native_hz &&
          spec->policy.encode_pinned_native_hz &&
          e->dsd.pinned_native_hz != spec->policy.encode_pinned_native_hz)
        return fail(error,n,"conflicting versioned --dsd-encode and pcmdsd -p native clocks");
      if (is(e->name,"pcmdsd") && e->dsd.profile_specified &&
          spec->policy.encode_specified && (lsx_dsd_encode)e->dsd.profile!=spec->policy.encode)
        return fail(error,n,"conflicting --dsd-encode and pcmdsd -p selections");
      if (lowlevel) {
        uint32_t current;
        if (!lsx_dsd_integer_rate(rate,&current) || current!=target)
          return fail(error,n,"%s is a rate-preserving one-bit modulator: input %.9g Hz differs from native %u Hz; use an explicit rate effect",
              e->name,rate,target);
        if (!lsx_dsd_rate_find(target) ||
            !(lsx_dsd_rate_find(target)->capabilities & LSX_DSD_MODULATE))
          return fail(error,n,"unsupported native clock for low-level %s: %u Hz",e->name,target);
        if (is(e->name,"sdm") && !lsx_sdm_filter_valid_for_rate(e->sdm_filter_name,target))
          return fail(error,n,"sdm filter is not available at %u Hz",target);
        /* Neither legacy effect has a rate converter or mastering profile.
         * Both are already implemented; unlike composite pcmdsd they must
         * not manufacture a missing DSP stage or a mastering certificate. */
        p->encoder_id=is(e->name,"sdm")?"encode.legacy.sdm":
            "encode.legacy.dither-p1";
        p->encoder_filter_name=is(e->name,"sdm")?
            lsx_sdm_filter_selected_name(e->sdm_filter_name,target):
            lsx_sdm_filter_selected_name(NULL,target);
      } else {
        uint32_t integer_source;
        if (!lsx_dsd_integer_rate(rate,&integer_source))
          return fail(error,n,"pcmdsd requires integer source Hz; insert an explicit rate effect");
        if (!resolve_encode(p,&spec->policy,target,
          e->dsd.profile_specified?(lsx_dsd_encode)e->dsd.profile:spec->policy.encode,
          error,n)) return 0;
      }
      domain=LSX_DSD_NATIVE;
      rate=target;
      p->modulator_input_scale=lowlevel?1.:
          e->dsd.reference==LSX_DSD_REF_PCM?.5:
          e->dsd.reference==LSX_DSD_REF_DSD?1.:ref;
      ++p->encode_count;
      p->trim_native_seek=0;
      append(p,e->name,old_domain,domain,before,rate,old_channels,channels,0,-1,p->modulator_input_scale);
    } else if (is(e->name,"dop")) {
      if (spec->policy.normalizing && !norm_inserted && domain==LSX_DSD_NATIVE) {
        /* DoP is transport, so a requested PCM normalization cannot be
         * discarded at the native-to-transport boundary.  If no explicit
         * terminal modulator precedes it, schedule decode/normalize/encode
         * at this *current* DSD clock before packaging. */
        uint32_t target=(uint32_t)rate;
        if (!append_norm(spec,p,&domain,&rate,&ref,channels,decoder,level,
              error,n)) return 0;
        norm_inserted=1;
        if (!resolve_encode(p,&spec->policy,target,spec->policy.encode,error,n)) return 0;
        append(p,"implicit_pcmdsd",domain,LSX_DSD_NATIVE,rate,target,
            channels,channels,1,-1,ref);
        domain=LSX_DSD_NATIVE;
        rate=target;
        ++p->encode_count;
        p->modulator_input_scale=ref;
        p->trim_native_seek=0;
      }
      if (domain!=LSX_DSD_NATIVE)
        return fail(error,n,"dop requires native DSD at effect %lu",(unsigned long)(i+1));
      if (!lsx_dsd_integer_rate(rate,&p->native_output_hz) ||
          !lsx_dsd_rate_find(p->native_output_hz) ||
          !(lsx_dsd_rate_find(p->native_output_hz)->capabilities & LSX_DSD_DOP))
        return fail(error,n,"DoP requires a supported current native DSD clock");
      if (spec->requested_output_rate && spec->requested_output_rate!=rate/16)
        return fail(error,n,"DoP output rate mismatch: native %.0f Hz needs %.0f Hz output",rate,rate/16);
      output_hz=p->native_output_hz/16;
      rate/=16;
      domain=LSX_DOP_TRANSPORT;
      ++p->dop_count;
      p->trim_native_seek=0;
      append(p,e->name,old_domain,domain,before,rate,old_channels,channels,0,-1,ref);
    } else if (is(e->name,"dsdstat")) {
      if (domain!=LSX_DSD_NATIVE)
        return fail(error,n,"dsdstat is a native DSD pass-through only");
      append(p,e->name,old_domain,domain,before,rate,old_channels,channels,0,-1,ref);
    } else if (domain==LSX_DSD_NATIVE && native_step(e,channels) &&
        (native_chain_only || native_identity(e,channels))) {
      if (is(e->name,"remix") && !e->native_permutation)
        return fail(error,n,"native remix must be a pure channel permutation");
      append(p,e->name,domain,domain,rate,rate,channels,channels,0,-1,ref);
    } else {
      if (domain==LSX_DOP_TRANSPORT)
        return fail(error,n,"PCM effects cannot follow terminal DoP");
      if (domain==LSX_DSD_NATIVE) {
        if (p->encode_count)
          return fail(error,n,"PCM effect '%s' after modulation requires an explicit dsdpcm boundary",e->name);
        if (spec->policy.mode==LSX_DSD_MODE_NATIVE)
          return fail(error,n,"native mode forbids PCM effect '%s'",e->name);
        if (!resolve_decode(p,&spec->policy,(uint32_t)rate,decoder,level,0,
            spec->policy.bandwidth,error,n)) return 0;
        old_domain=domain;
        rate=p->decoder_intermediate_hz;
        domain=LSX_PCM_AUDIO;
        ref=1./p->decoder_gain;
    
        ++p->graph_decode_count;
        p->trim_native_seek=0;
        append(p,"implicit_dsdpcm",old_domain,domain,before,rate,old_channels,channels,1,-1,ref);
        before=rate;
        old_domain=domain;
      }
      if ((e->out_rate || (is(e->name,"rate") && spec->requested_output_rate)) &&
          (e->flags & SOX_EFF_RATE)) {
        double selected=e->out_rate?e->out_rate:spec->requested_output_rate;
        if (!isfinite(selected) || selected <= 0)
          return fail(error,n,"invalid effect rate for %s",e->name);
        rate=selected;
        if (any_native) {
          uint32_t pcm_rate;
          if (!lsx_dsd_integer_rate(rate,&pcm_rate) || !lsx_dsd_pcm_rate_supported(pcm_rate))
            return fail(error,n,"noninteger or unsupported PCM rate for %s: %.9g Hz",e->name,rate);
        }
      }
      if (e->out_channels && (e->flags & SOX_EFF_CHAN))
        channels=e->out_channels;
      if (((e->flags & SOX_EFF_MCHAN) && !e->native_permutation) ||
          ((e->flags & SOX_EFF_CHAN) && !native_identity(e,old_channels)))
        p->layout_identity_preserved=0;
      if (is(e->name,"synth")) ref=.5;
      append(p,e->name,old_domain,domain,before,rate,old_channels,channels,0,-1,ref);
    }
    if (is(e->name,"dither")) explicit_dither_seen=1;
  }

  /* Endpoint negotiation is independent of graph precision.  No synthetic
   * 1-bit 'PCM' destination is accepted as a native DSD writer. */
  if (requested_domain==LSX_DSD_NATIVE) {
    if (domain==LSX_DOP_TRANSPORT)
      return fail(error,n,"DoP transport cannot be written as native DSD");
    if (spec->policy.normalizing && !norm_inserted) {
      if (!append_norm(spec,p,&domain,&rate,&ref,channels,decoder,level,
            error,n)) return 0;
      norm_inserted=1;
    }
    if (domain==LSX_DSD_NATIVE && (rate != output_hz || channels !=
        (spec->requested_output_channels?spec->requested_output_channels:channels))) {
      double before=rate;
      if (p->encode_count) return fail(error,n,
          "explicit modulator output conflicts with the native output clock or channels; use matching -r/-c or an explicit dsdpcm boundary");
      if (spec->policy.mode==LSX_DSD_MODE_NATIVE)
        return fail(error,n,"native mode cannot change DSD rate or channels without reconstruction");
      if (!resolve_decode(p,&spec->policy,(uint32_t)rate,decoder,level,0,
          spec->policy.bandwidth,error,n)) return 0;
      rate=p->decoder_intermediate_hz;
      append(p,"implicit_dsdpcm",domain,LSX_PCM_AUDIO,before,
          rate,channels,channels,1,-1,1./p->decoder_gain);
      domain=LSX_PCM_AUDIO;
      ref=1./p->decoder_gain;
      ++p->graph_decode_count;p->trim_native_seek=0;
    }
    if (domain==LSX_PCM_AUDIO) {
      if (spec->policy.mode==LSX_DSD_MODE_NATIVE)
        return fail(error,n,"native mode forbids DSD modulation");
      /* The normal channels effect is PCM-only; encode the transformed
       * channels, never silently copy source DSD channel roles. */
      if (spec->requested_output_channels && spec->requested_output_channels!=channels) {
        append(p,"implicit_pcm_channels",domain,domain,rate,rate,channels,
            spec->requested_output_channels,1,-1,ref);
        channels=spec->requested_output_channels;
        p->layout_identity_preserved=0;
        p->trim_native_seek=0;
      }
      { uint32_t integer_source;
        if (!lsx_dsd_integer_rate(rate,&integer_source))
          return fail(error,n,"pcmdsd requires integer source Hz; insert an explicit rate effect");
      }
      if (!resolve_encode(p,&spec->policy,output_hz,spec->policy.encode,error,n)) return 0;
      append(p,"implicit_pcmdsd",domain,LSX_DSD_NATIVE,rate,output_hz,
          channels,channels,1,-1,ref);
      domain=LSX_DSD_NATIVE;rate=output_hz;
      ++p->encode_count;
      p->modulator_input_scale=ref;
      p->trim_native_seek=0;
    }
    if (rate!=output_hz)
      return fail(error,n,"terminal DSD clock disagrees with output: %.0f vs %u Hz",rate,output_hz);
    p->output_rate=output_hz;
    p->output_bits=1;
    p->output_encoding=SOX_ENCODING_DSD;
  } else if (requested_domain==LSX_DOP_TRANSPORT) {
    if (domain!=LSX_DOP_TRANSPORT)
      return fail(error,n,"terminal DoP effect was not resolved");
    p->output_rate=rate;
    p->output_bits=24;
    p->output_encoding=SOX_ENCODING_SIGN2;
  } else {
    if (domain==LSX_DSD_NATIVE) {
      double dest=spec->requested_output_rate;
      if (p->encode_count) return fail(error,n,
          "PCM output after modulation requires an explicit dsdpcm boundary");
      if (spec->policy.mode==LSX_DSD_MODE_NATIVE)
        return fail(error,n,"native mode cannot write reconstructed PCM");
      if (!dest) {
        double pa,st,inter;
        if (!lsx_dsd_profile_edges((uint32_t)rate,decoder,&pa,&st,&inter) &&
            !(decoder==LSX_DSD_PROFILE_LEGACY &&
              lsx_dsd_profile_edges((uint32_t)rate,LSX_DSD_PROFILE_MASTERING,
                  &pa,&st,&inter)))
          return fail(error,n,"no reconstruction working rate for %.0f Hz",rate);
        dest=inter;
      }
      if (!resolve_decode(p,&spec->policy,(uint32_t)rate,decoder,level,dest,
          spec->policy.bandwidth,error,n)) return 0;
      append(p,"implicit_dsdpcm",domain,LSX_PCM_AUDIO,rate,dest,
          channels,channels,1,-1,1./p->decoder_gain);
      domain=LSX_PCM_AUDIO;rate=dest;
      ref=1./p->decoder_gain;
      ++p->graph_decode_count;
      p->trim_native_seek=0;
    } else if (domain==LSX_DOP_TRANSPORT)
      return fail(error,n,"DoP output requires a lossless transport endpoint");
    if (spec->requested_output_rate && rate != spec->requested_output_rate) {
      if (any_native) {
        uint32_t pcm_rate;
        if (!lsx_dsd_integer_rate(spec->requested_output_rate,&pcm_rate) ||
            !lsx_dsd_pcm_rate_supported(pcm_rate))
          return fail(error,n,"requested PCM output rate is not a supported integer Hz");
      }
      append(p,"implicit_pcm_rate",domain,domain,rate,
          spec->requested_output_rate,channels,channels,1,-1,ref);
      rate=spec->requested_output_rate;
      p->trim_native_seek=0;
    }
    if (spec->requested_output_channels && spec->requested_output_channels!=channels) {
      append(p,"implicit_pcm_channels",domain,domain,rate,rate,channels,
          spec->requested_output_channels,1,-1,ref);
      channels=spec->requested_output_channels;
      p->layout_identity_preserved=0;
    }
    if (spec->policy.normalizing && !norm_inserted) {
      if (!append_norm(spec,p,&domain,&rate,&ref,channels,decoder,level,
            error,n)) return 0;
      norm_inserted=1;
    }
    p->output_rate=rate;
    p->output_bits=spec->requested_encoding.bits_per_sample?
        spec->requested_encoding.bits_per_sample:
        ((any_native || p->encode_count || p->graph_decode_count)?spec->fallback_bits:0);
    p->output_encoding=spec->requested_encoding.encoding?
        spec->requested_encoding.encoding:
        ((any_native || p->encode_count || p->graph_decode_count)?
            spec->fallback_encoding:SOX_ENCODING_SIGN2);
    if (p->output_bits==1)
      return fail(error,n,"one-bit PCM is not a native DSD output or DoP transport");
  }
  if (requested_domain==LSX_DOP_TRANSPORT &&
      spec->requested_output_channels && spec->requested_output_channels!=channels) {
    if (domain==LSX_DSD_NATIVE || domain==LSX_DOP_TRANSPORT)
      return fail(error,n,"native/DoP output channel count disagrees with planned graph");
  }
  if (spec->requested_encoding.encoding &&
      spec->requested_encoding.encoding != p->output_encoding)
    return fail(error,n,"explicit output encoding conflicts with %s endpoint",lsx_dsd_domain_name(domain));
  if (spec->requested_encoding.bits_per_sample &&
      p->output_bits && spec->requested_encoding.bits_per_sample != p->output_bits)
    return fail(error,n,"explicit output precision conflicts with %s endpoint",lsx_dsd_domain_name(domain));
  if (spec->policy.mode==LSX_DSD_MODE_NATIVE && p->needs_unimplemented_dsp)
    return fail(error,n,"native mode does not permit DSD reconstruction/modulation");
  p->output_channels=channels;
  p->output_domain=domain;
  p->processing_rate=p->combiner_domain==LSX_DSD_NATIVE && p->graph_decode_count?
      p->decoder_intermediate_hz:p->combiner_rate;
  p->dsd_amplitude_per_pcm_unit=ref;
  if (p->encode_count && !p->modulator_input_scale)
    p->modulator_input_scale=ref;
  /* P08 activates the existing P07 decoder at either graph boundary.  The
   * private composite encoder, legacy decoder and diagnostic pass-through
   * remain unavailable; none may be mistaken for a mastering implementation. */
  if (p->needs_unimplemented_dsp) {
    int unsupported_encoder=p->encoder_id &&
        strcmp(p->encoder_id,"encode.legacy.sdm") &&
        strcmp(p->encoder_id,"encode.legacy.dither-p1") &&
        !(p->native_output_hz && lsx_pcmdsd_qualified(p->native_output_hz) &&
          !strcmp(p->encoder_id,lsx_pcmdsd_profile_find(p->native_output_hz)->id));
    int unsupported_decoder=p->decoder_id &&
        !strcmp(p->decoder_id,"decode.legacy.generic");
    if (!unsupported_encoder && !unsupported_decoder && !p->dop_count &&
        p->executable) {
      p->needs_unimplemented_dsp=0;
      p->unavailable_reason=NULL;
    } else p->executable=0;
  }
  if (norm_sdm_unavailable) {
    p->executable=0;
    p->unavailable_reason="automatic normalization before low-level sdm is not supported by the current effects pipeline";
  }
  if (p->executable &&
      (p->input_decode_count || p->graph_decode_count) &&
      (!p->decoder_id || strcmp(p->decoder_id,"decode.legacy.generic")) &&
      !check_kernel(LSX_DSD_FIR,spec->policy.kernel_fir,error,n)) return 0;
  /* Legacy low-level sdm and precision-one dither never instantiate the
   * composite P11 SDM kernel; their overrides must remain inert. */
  if (p->executable) for (i=0;i<p->step_count;++i)
    if (is(p->steps[i].name,"pcmdsd") ||
        is(p->steps[i].name,"implicit_pcmdsd")) {
      if (!check_kernel(LSX_DSD_SDM,spec->policy.kernel_sdm,error,n)) return 0;
      break;
    }
  return 1;
}

static void json_string(FILE *fp, char const *s)
{
  unsigned char const *c=(unsigned char const *)(s?s:"");
  fputc('"',fp);
  while (*c) {
    if (*c=='"'||*c=='\\') {fputc('\\',fp);fputc(*c,fp);}
    else if (*c<32) fprintf(fp,"\\u%04x",*c);
    else fputc(*c,fp);
    ++c;
  }
  fputc('"',fp);
}

void lsx_dsd_plan_json(FILE *fp, lsx_dsd_plan_spec const *spec, lsx_dsd_plan const *p)
{
  size_t i;
  char const *mode=spec->policy.mode==LSX_DSD_MODE_NATIVE?"native":
      spec->policy.mode==LSX_DSD_MODE_AUTO?"auto":"legacy";
  fprintf(fp,"{\n  \"schema\": \"sox.dsd.plan.v1\",\n  \"mode\": ");
  json_string(fp,mode);
  fprintf(fp,",\n  \"executable\": %s,\n  \"needs_unimplemented_dsp\": %s,\n  \"unavailable_reason\": ",
      p->executable?"true":"false",p->needs_unimplemented_dsp?"true":"false");
  if (p->unavailable_reason) json_string(fp,p->unavailable_reason); else fputs("null",fp);
  fprintf(fp,",\n  \"policy\": {\"decode\": ");
  json_string(fp,spec->policy.decode==LSX_DSD_PROFILE_WIDEBAND?"wideband":
      spec->policy.decode==LSX_DSD_PROFILE_LEGACY?"legacy":
      spec->policy.decode==LSX_DSD_PROFILE_MASTERING_V2?"mastering-v2-candidate":"mastering");
  fprintf(fp,", \"encode\": ");
  json_string(fp,spec->policy.encode==LSX_DSD_ENCODE_LEGACY?"legacy":
      spec->policy.encode==LSX_DSD_ENCODE_EXPERIMENTAL?"experimental":"mastering");
  fprintf(fp,", \"level\": ");
  json_string(fp,spec->policy.level==LSX_DSD_LEVEL_SACD?"sacd":"preserve");
  fprintf(fp,", \"clip\": ");
  json_string(fp,spec->policy.clip==LSX_DSD_CLIP_ERROR?"error":"warn");
  fprintf(fp,", \"bandwidth\": ");
  json_string(fp,spec->policy.bandwidth==LSX_DSD_BANDWIDTH_STRICT?"strict":"adapt");
  fprintf(fp,", \"layout_loss\": ");
  json_string(fp,spec->policy.layout_loss_warn?"warn":"error");
  fprintf(fp,", \"kernel_fir\": ");
  json_string(fp,spec->policy.kernel_fir?spec->policy.kernel_fir:"auto");
  fprintf(fp,", \"kernel_sdm\": ");
  json_string(fp,spec->policy.kernel_sdm?spec->policy.kernel_sdm:"auto");
  fprintf(fp,", \"guarded\": %s, \"normalizing\": %s, \"dither_disabled\": %s},\n",
      spec->policy.guarded?"true":"false",spec->policy.normalizing?"true":"false",
      spec->policy.dither_disabled?"true":"false");
  fprintf(fp,"  \"combiner\": {\"domain\": ");
  json_string(fp,lsx_dsd_domain_name(p->combiner_domain));
  fprintf(fp,", \"rate_hz\": %.9g, \"channels\": %u},\n",p->combiner_rate,p->combiner_channels);
  fprintf(fp,"  \"output\": {\"domain\": ");
  json_string(fp,lsx_dsd_domain_name(p->output_domain));
  fprintf(fp,", \"rate_hz\": %.9g, \"channels\": %u, \"bits_per_sample\": %u, \"encoding\": %d, \"requested_rate_hz\": ",
      p->output_rate,p->output_channels,p->output_bits,(int)p->output_encoding);
  if (spec->requested_output_rate) fprintf(fp,"%.9g",spec->requested_output_rate);
  else fputs("null",fp);
  fputs("},\n",fp);
  fprintf(fp,"  \"decoder\": {\"id\": ");
  if (p->decoder_id) json_string(fp,p->decoder_id); else fputs("null",fp);
  fprintf(fp,", \"gain\": %.17g, \"pass_hz\": %.9g, \"stop_hz\": %.9g, \"intermediate_hz\": %.9g, \"effective_bandwidth_hz\": %.9g},\n",
      p->decoder_gain,p->decoder_pass_hz,p->decoder_stop_hz,p->decoder_intermediate_hz,p->effective_bandwidth_hz);
  fprintf(fp,"  \"encoder\": {\"id\": ");
  if (p->encoder_id) json_string(fp,p->encoder_id); else fputs("null",fp);
  fprintf(fp,", \"modulator_input_scale\": %.17g, \"lowlevel_filter\": ",p->modulator_input_scale);
  /* Current low-level SDM/dither filters have no certified mastering ID. */
  if (p->encoder_filter_name) json_string(fp,p->encoder_filter_name);
  else fputs("null",fp);
  if (p->encoder_id && p->native_output_hz) {
    const lsx_pcmdsd_profile *enc=lsx_pcmdsd_profile_find(p->native_output_hz);
    if (enc && !strcmp(enc->id,p->encoder_id)) {
      fprintf(fp,", \"qualified\": %s, \"working_hz\": %u, \"prefilter_design_hz\": %u, \"pass_hz\": %.9g, \"stop_hz\": %.9g, \"certificate_sha256\": ",
          enc->qualified?"true":"false",enc->working_hz,enc->working_hz,enc->pass_hz,enc->stop_hz);
      json_string(fp,enc->certificate_sha256);
    }
  }
  fputs("},\n",fp);
  fprintf(fp,"  \"level_reference\": %.17g,\n",p->dsd_amplitude_per_pcm_unit);
  fprintf(fp,"  \"native_trim_seek\": %s,\n  \"layout_identity_preserved\": %s,\n",
      p->trim_native_seek?"true":"false",p->layout_identity_preserved?"true":"false");
  fprintf(fp,"  \"input_decoder_count\": %d,\n  \"graph_decoder_count\": %d,\n  \"encoder_count\": %d,\n  \"dop_count\": %d,\n",
      p->input_decode_count,p->graph_decode_count,p->encode_count,p->dop_count);
  fputs("  \"inputs\": [\n",fp);
  for (i=0;i<p->input_count;i++) {
    lsx_dsd_plan_input const *in=&p->inputs[i];
    fprintf(fp,"    {\"index\": %lu, \"native_domain\": ",(unsigned long)i);
    json_string(fp,lsx_dsd_domain_name(in->native_domain));
    fprintf(fp,", \"effective_domain\": ");
    json_string(fp,lsx_dsd_domain_name(in->effective_domain));
    fprintf(fp,", \"native_rate_hz\": %.9g, \"effective_rate_hz\": %.9g, \"channels\": %u, \"volume\": %.17g, \"reference\": %.17g, \"decoder_gain\": %.17g, \"decoder_id\": ",
        in->native_rate,in->effective_rate,in->channels,in->volume,in->reference,in->decoder_gain);
    if (in->decoder_id) json_string(fp,in->decoder_id); else fputs("null",fp);
    fprintf(fp,", \"decoder_pass_hz\": %.9g, \"decoder_stop_hz\": %.9g, \"effective_bandwidth_hz\": %.9g, \"decoder_before_combiner\": %s, \"volume_consumed_by_decoder\": %s}%s\n",
        in->decoder_pass_hz,in->decoder_stop_hz,in->effective_bandwidth_hz,
        in->decoder_before_combiner?"true":"false",
        in->volume_consumed_by_decoder?"true":"false",i+1==p->input_count?"":",");
  }
  fputs("  ],\n  \"steps\": [\n",fp);
  for (i=0;i<p->step_count;i++) {
    lsx_dsd_plan_step const *s=&p->steps[i];
    fputs("    {\"name\": ",fp);json_string(fp,s->name);
    fputs(", \"before\": ",fp);json_string(fp,lsx_dsd_domain_name(s->before));
    fputs(", \"after\": ",fp);json_string(fp,lsx_dsd_domain_name(s->after));
    fprintf(fp,", \"rate_in_hz\": %.9g, \"rate_out_hz\": %.9g, \"channels_in\": %u, \"channels_out\": %u, \"implicit\": %s, \"input_index\": %d, \"reference\": %.17g}%s\n",
        s->rate_before,s->rate_after,s->channels_before,s->channels_after,
        s->implicit?"true":"false",s->input_index,s->reference,
        i+1==p->step_count?"":",");
  }
  fputs("  ]\n}\n",fp);
}
