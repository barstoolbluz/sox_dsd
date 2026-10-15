/* P07 explicit DSD to PCM graph boundary.  This wrapper is per-channel:
 * effects.c copies the parsed option prefix, then each clone owns its decoder.
 * The binary64 result is intentionally saturated at SoX's int32 boundary. */
#include "sox_i.h"
#include "dsd.h"
#include "dsd_stats.h"
#include <inttypes.h>
#include <math.h>
#include <string.h>

#define DSDPCM_BATCH 256

int lsx_dsdpcm_start(sox_effect_t *effect)
{
  lsx_dsdpcm_private *priv=effect->priv;
  sox_dsd_decode_options_t opts;
  const lsx_dsd_frontend_profile *profile;
  uint32_t input_hz, output_hz;
  sox_dsd_status_t rc;
  if (!lsx_dsd_integer_rate(effect->in_signal.rate, &input_hz)) {
    lsx_fail("dsdpcm: native input sample rate must be integer Hz");
    return SOX_EOF;
  }
  if (priv->options.pinned_native_hz && priv->options.pinned_native_hz!=input_hz) {
    lsx_fail("dsdpcm: versioned decoder ID is for a different native DSD clock");
    return SOX_EOF;
  }
  profile=lsx_dsd_frontend_profile_find(input_hz,priv->options.profile);
  if (!profile) {
    lsx_fail("dsdpcm: unsupported reconstruction rate/profile");
    return SOX_EOF;
  }
  output_hz=priv->options.rate_hz ? priv->options.rate_hz : profile->intermediate_hz;
  sox_dsd_decode_options_init(&opts);
  opts.native_hz=input_hz;
  opts.output_hz=output_hz;
  opts.channels=1;
  opts.profile=(sox_dsd_decode_profile_t)priv->options.profile;
  opts.level=(sox_dsd_decode_level_t)priv->options.level;
  opts.bandwidth=(sox_dsd_decode_bandwidth_t)priv->options.bandwidth;
  rc=sox_dsd_decoder_create(&opts,&priv->decoder);
  if (rc!=SOX_DSD_OK) {
    lsx_fail("dsdpcm: cannot initialize %.0f Hz -> %u Hz reconstruction: %d",
        effect->in_signal.rate,output_hz,(int)rc);
    return SOX_EOF;
  }
  effect->out_signal.rate=output_hz;
  effect->out_signal.precision=SOX_SAMPLE_PRECISION;
  priv->graph_clips=0;
  priv->max_preclip=0;
  return SOX_SUCCESS;
}

/* An entire effect block must fail before graph interleaving on clip-error. */
static int pcm_convert(sox_effect_t *effect,const double *in,
    sox_sample_t *out,size_t count)
{
  lsx_dsdpcm_private *priv=effect->priv;
  size_t i;
  SOX_SAMPLE_LOCALS;
  for (i=0;i<count;i++) {
    double magnitude=fabs(in[i]);
    if (!isfinite(magnitude)) {
      lsx_fail("dsdpcm: nonfinite reconstructed sample (channel %lu)",
          (unsigned long)effect->flow);
      return LSX_EFF_FATAL;
    }
    if (magnitude>priv->max_preclip) priv->max_preclip=magnitude;
    if (in[i] >= 1. || in[i] < -1.) {
      ++priv->graph_clips;
      if (priv->options.clip==LSX_DSD_CLIP_ERROR) {
        lsx_fail("dsdpcm: --dsd-clip error: channel %lu, sample magnitude %.9g",
            (unsigned long)effect->flow,magnitude);
        return LSX_EFF_FATAL;
      }
    }
    out[i]=SOX_FLOAT_64BIT_TO_SAMPLE(in[i],effect->clips);
  }
  return SOX_SUCCESS;
}

int lsx_dsdpcm_flow(sox_effect_t *effect,const sox_sample_t *input,
    sox_sample_t *output,size_t *in_count,size_t *out_count)
{
  lsx_dsdpcm_private *priv=effect->priv;
  double temp[DSDPCM_BATCH];
  size_t in_cap=*in_count, out_cap=*out_count;
  size_t produced=out_cap<DSDPCM_BATCH?out_cap:DSDPCM_BATCH;
  sox_dsd_status_t rc;
  *in_count=*out_count=0;
  if (!produced) return SOX_SUCCESS;
  rc=sox_dsd_decoder_process(priv->decoder,input,&in_cap,temp,&produced);
  if (rc!=SOX_DSD_NEED_OUTPUT && rc!=SOX_DSD_NEED_INPUT) {
    lsx_fail("dsdpcm: binary64 stream failed (%d)",(int)rc);
    return LSX_EFF_FATAL;
  }
  if (pcm_convert(effect,temp,output,produced)==LSX_EFF_FATAL)
    return LSX_EFF_FATAL;
  *in_count=in_cap;
  *out_count=produced;
  return SOX_SUCCESS;
}

int lsx_dsdpcm_drain(sox_effect_t *effect,sox_sample_t *output,size_t *out_count)
{
  lsx_dsdpcm_private *priv=effect->priv;
  double temp[DSDPCM_BATCH];
  size_t n=*out_count<DSDPCM_BATCH?*out_count:DSDPCM_BATCH;
  sox_dsd_status_t rc;
  *out_count=0;
  if (!n) return SOX_EOF;
  rc=sox_dsd_decoder_finish(priv->decoder,temp,&n);
  if (rc!=SOX_DSD_NEED_OUTPUT && rc!=SOX_DSD_DONE) {
    lsx_fail("dsdpcm: binary64 finalization failed (%d)",(int)rc);
    return LSX_EFF_FATAL;
  }
  if (pcm_convert(effect,temp,output,n)==LSX_EFF_FATAL)
    return LSX_EFF_FATAL;
  *out_count=n;
  return rc==SOX_DSD_DONE ? SOX_EOF : SOX_SUCCESS;
}

int lsx_dsdpcm_stop(sox_effect_t *effect)
{
  lsx_dsdpcm_private *priv=effect->priv;
  if (priv->graph_clips)
    lsx_warn("dsdpcm: clipped %" PRIu64 " graph samples (channel %lu, max magnitude %.9g)",
        priv->graph_clips,(unsigned long)effect->flow,priv->max_preclip);
  lsx_dsd_report_note_decode(priv->decoder,priv->options.profile,
      priv->options.level,priv->graph_clips,priv->max_preclip);
  sox_dsd_decoder_destroy(priv->decoder);
  priv->decoder=NULL;
  return SOX_SUCCESS;
}
