/* P07 public binary64 reconstruction: one P06 front-end and independent
 * private SRC contexts per channel.  Every channel owns its FIFO/histories;
 * only immutable coefficients are shared.  The intermediate timebase is
 * finite ceil(N/D); the final output uses native N (not rounded R twice).
 */
#include "dsd_decode.h"
#include "rate_internal.h"
#include "dsd.h"
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define DSD_QUEUE 64
#define DSD_MAX_CHANNELS 64
struct sox_dsd_decoder {
  sox_dsd_decode_options_t cfg;
  lsx_dsd_reconstruction *front;
  lsx_rate_f64_t **src;
  double *queue, *intermediate;
  unsigned qhead, qlen, front_done, src_done, finishing, done;
  uint64_t native_frames, intermediate_frames, delivered, target;
  uint64_t native_limit; /* same finite-tail reserve as the reconstruction */
  uint32_t intermediate_hz;
  double pass_hz, gain;
  sox_dsd_status_t error;
};

/* The original initializer is an existing ABI entry point. It cannot know
 * whether the caller allocated the P07 version-1 prefix or P11's extension:
 * do NOT clear/write past the original size. The extended initializer is
 * explicit so an existing binary never receives a larger write. */
static void init_options_defaults(sox_dsd_decode_options_t *options)
{
  options->version = 1;
  options->profile = SOX_DSD_DECODE_MASTERING;
  options->level = SOX_DSD_LEVEL_PRESERVE;
  options->bandwidth = SOX_DSD_BANDWIDTH_ADAPT;
}

void sox_dsd_decode_options_init(sox_dsd_decode_options_t *options)
{
  if (!options) return;
  memset(options, 0, offsetof(sox_dsd_decode_options_t,kernel_fir));
  options->size = offsetof(sox_dsd_decode_options_t,kernel_fir);
  init_options_defaults(options);
}

void sox_dsd_decode_options_init_extended(sox_dsd_decode_options_t *options)
{
  if (!options) return;
  memset(options, 0, sizeof(*options));
  options->size = sizeof(*options);
  init_options_defaults(options);
}

const char *lsx_dsd_decoder_kernel_name(const sox_dsd_decoder_t *ctx)
{
  return ctx ? lsx_dsd_reconstruction_kernel_name(ctx->front) : NULL;
}

void sox_dsd_decoder_destroy(sox_dsd_decoder_t *ctx)
{
  unsigned c;
  if (!ctx) return;
  if (ctx->src)
    for (c = 0; c < ctx->cfg.channels; ++c)
      lsx_rate_f64_destroy(ctx->src[c]);
  lsx_dsd_reconstruction_destroy(ctx->front);
  free(ctx->src);
  free(ctx->queue);
  free(ctx->intermediate);
  free(ctx);
}

sox_dsd_status_t sox_dsd_decoder_create(
    const sox_dsd_decode_options_t *options, sox_dsd_decoder_t **out)
{
  sox_dsd_decoder_t *ctx;
  sox_dsd_decode_options_t resolved;
  const lsx_dsd_frontend_profile *profile;
  lsx_rate_f64_config rc;
  sox_dsd_status_t st;
  unsigned c;
  if (!out) return SOX_DSD_BAD_ARGUMENT;
  *out = NULL;
  /* Version 1 accepts its original record prefix without reading beyond the
   * caller's advertised size. New fields default to NULL/automatic. */
  if (!options || options->size < offsetof(sox_dsd_decode_options_t,kernel_fir) ||
      options->version != 1) return SOX_DSD_BAD_ARGUMENT;
  sox_dsd_decode_options_init_extended(&resolved);
  memcpy(&resolved,options,options->size < sizeof(resolved) ?
      options->size : sizeof(resolved));
  resolved.size = sizeof(resolved);
  if (!resolved.channels || resolved.channels > DSD_MAX_CHANNELS ||
      !lsx_dsd_pcm_rate_supported(resolved.output_hz) ||
      resolved.profile > SOX_DSD_DECODE_WIDEBAND ||
      resolved.level > SOX_DSD_LEVEL_SACD ||
      resolved.bandwidth > SOX_DSD_BANDWIDTH_STRICT)
    return SOX_DSD_BAD_ARGUMENT;
  profile = lsx_dsd_frontend_profile_find(resolved.native_hz,
      (lsx_dsd_decode)resolved.profile);
  if (!profile) return SOX_DSD_UNSUPPORTED;
  if (resolved.bandwidth == SOX_DSD_BANDWIDTH_STRICT &&
      profile->intermediate_hz != resolved.output_hz &&
      .475 * fmin((double)profile->intermediate_hz,
                  (double)resolved.output_hz) + 1e-9 < profile->pass_hz)
    return SOX_DSD_UNSUPPORTED;
  ctx = calloc(1, sizeof(*ctx));
  if (!ctx) return SOX_DSD_NUMERIC_ERROR;
  ctx->cfg = resolved;
  ctx->native_limit = UINT64_MAX - profile->delay_native_frames -
      resolved.native_hz / profile->intermediate_hz;
  ctx->intermediate_hz = profile->intermediate_hz;
  ctx->pass_hz = lsx_dsd_effective_bandwidth(profile->pass_hz,
      profile->intermediate_hz, resolved.output_hz);
  ctx->gain = resolved.level == SOX_DSD_LEVEL_SACD ? 2. : 1.;
  ctx->src = calloc(resolved.channels, sizeof(*ctx->src));
  ctx->queue = calloc((size_t)resolved.channels * DSD_QUEUE, sizeof(double));
  ctx->intermediate = calloc(resolved.channels, sizeof(double));
  if (!ctx->src || !ctx->queue || !ctx->intermediate) goto fail;
  st=lsx_dsd_reconstruction_create_kernel(resolved.native_hz,
      (lsx_dsd_decode)resolved.profile, resolved.channels,
      resolved.kernel_fir,&ctx->front);
  if (st!=SOX_DSD_OK) {
    sox_dsd_decoder_destroy(ctx);
    return st; /* Preserve UNSUPPORTED, do not disguise it as NUMERIC_ERROR. */
  }
  rc.input_hz = profile->intermediate_hz;
  rc.output_hz = resolved.output_hz;
  rc.bandwidth_0db_pct = 95.;
  rc.rejection_db = 180.;
  rc.phase_percent = 50;
  for (c = 0; c < resolved.channels; ++c)
    if (lsx_rate_f64_create(&rc, &ctx->src[c]) != SOX_DSD_OK)
      goto fail;
  *out = ctx;
  return SOX_DSD_OK;
fail:
  sox_dsd_decoder_destroy(ctx);
  return SOX_DSD_NUMERIC_ERROR;
}

/* Push one intermediate frame to every private SRC. Each frontend frame can
 * produce at most eight PCM frames at the admitted output clocks. */
static sox_dsd_status_t push_mid(sox_dsd_decoder_t *ctx)
{
  unsigned c;
  size_t count = (size_t)-1;
  for (c = 0; c < ctx->cfg.channels; ++c) {
    double tmp[DSD_QUEUE];
    size_t consumed = 1, produced = DSD_QUEUE - ctx->qlen;
    sox_dsd_status_t st;
    st = lsx_rate_f64_process(ctx->src[c], &ctx->intermediate[c],
                              &consumed, tmp, &produced);
    if ((st != SOX_DSD_NEED_INPUT && st != SOX_DSD_NEED_OUTPUT) ||
        consumed != 1 || (c && produced != count))
      return ctx->error = SOX_DSD_NUMERIC_ERROR;
    if (!c) count = produced;
    /* qhead + qlen may wrap; each channel is otherwise independent. */
    {
      size_t j;
      for (j = 0; j < produced; ++j)
        ctx->queue[(size_t)c * DSD_QUEUE +
            (ctx->qhead + ctx->qlen + j) % DSD_QUEUE] = tmp[j];
    }
  }
  ctx->qlen += (unsigned)count;
  ++ctx->intermediate_frames;
  return SOX_DSD_OK;
}

static int pop(sox_dsd_decoder_t *ctx, double *output)
{
  unsigned c;
  if (!ctx->qlen || ctx->delivered >= ctx->target) return 0;
  for (c = 0; c < ctx->cfg.channels; ++c)
    output[c] = ctx->gain * ctx->queue[(size_t)c * DSD_QUEUE + ctx->qhead];
  ctx->qhead = (ctx->qhead + 1) % DSD_QUEUE;
  --ctx->qlen;
  ++ctx->delivered;
  return 1;
}

sox_dsd_status_t sox_dsd_decoder_process(sox_dsd_decoder_t *ctx,
    const sox_sample_t *input, size_t *input_frames, double *output,
    size_t *output_frames)
{
  size_t avail, cap, used = 0, made = 0;
  if (!ctx) return SOX_DSD_BAD_ARGUMENT;
  if (!input_frames || !output_frames) return ctx->error = SOX_DSD_BAD_ARGUMENT;
  avail = *input_frames;
  cap = *output_frames;
  *input_frames = *output_frames = 0;
  if (ctx->error) return ctx->error;
  if (ctx->finishing) return ctx->error = SOX_DSD_BAD_ARGUMENT;
  if (!cap) return SOX_DSD_NEED_OUTPUT;
  if ((avail && !input) || !output ||
      (avail && avail > SIZE_MAX / ctx->cfg.channels) ||
      cap > SIZE_MAX / ctx->cfg.channels ||
      avail > UINT64_MAX - ctx->native_frames)
    return ctx->error = SOX_DSD_BAD_ARGUMENT;
  while (made < cap) {
    if (ctx->qlen && ctx->delivered < ctx->target) {
      pop(ctx, output + made * ctx->cfg.channels);
      ++made;
      continue;
    }
    if (used == avail) break;
    {
      size_t consumed = 1, produced = 1;
      sox_dsd_status_t st;
      /* With no held PCM, the first new intermediate output is the next
       * possible release event. Let the existing reconstruction consume up
       * to that event, without any new buffering or lookahead. A held frame
       * still advances one native clock at a time. Preserve the old valid
       * prefix at the tail-reserve boundary instead of rejecting the whole
       * offered input span early. At the limit, the one-frame call below
       * triggers the reconstruction's unchanged sticky overflow error. */
      if (!ctx->qlen && ctx->native_frames < ctx->native_limit) {
        uint64_t remaining = ctx->native_limit - ctx->native_frames;
        consumed = avail - used;
        if (consumed > remaining) consumed = (size_t)remaining;
      }
      st = lsx_dsd_reconstruction_process(ctx->front,
          input + used * ctx->cfg.channels, &consumed,
          ctx->intermediate, &produced);
      /* Invalid native data can follow an accepted prefix. Account for
       * that prefix exactly as the former one-frame loop did, even though
       * the public error return still exposes zero consumed/produced counts. */
      ctx->native_frames += consumed;
      used += consumed;
      if (!lsx_dsd_count_convert(ctx->native_frames,
           ctx->cfg.native_hz, ctx->cfg.output_hz, &ctx->target))
        return ctx->error = SOX_DSD_NUMERIC_ERROR;
      if ((st != SOX_DSD_NEED_INPUT && st != SOX_DSD_NEED_OUTPUT) ||
          !consumed) return ctx->error = SOX_DSD_NUMERIC_ERROR;
      if (produced && push_mid(ctx) != SOX_DSD_OK)
        return ctx->error;
    }
  }
  *input_frames = used;
  *output_frames = made;
  return used < avail ? SOX_DSD_NEED_OUTPUT : SOX_DSD_NEED_INPUT;
}

sox_dsd_status_t sox_dsd_decoder_finish(sox_dsd_decoder_t *ctx,
    double *output, size_t *output_frames)
{
  size_t cap, made = 0;
  if (!ctx) return SOX_DSD_BAD_ARGUMENT;
  if (!output_frames) return ctx->error = SOX_DSD_BAD_ARGUMENT;
  cap = *output_frames;
  *output_frames = 0;
  if (ctx->error) return ctx->error;
  if (ctx->done) return SOX_DSD_DONE;
  if (!cap) return SOX_DSD_NEED_OUTPUT;
  if (!output) return ctx->error = SOX_DSD_BAD_ARGUMENT;
  if (!ctx->finishing) {
    if (!lsx_dsd_count_convert(ctx->native_frames,
          ctx->cfg.native_hz, ctx->cfg.output_hz, &ctx->target))
      return ctx->error = SOX_DSD_NUMERIC_ERROR;
    ctx->finishing = 1;
  }
  while (made < cap && ctx->delivered < ctx->target) {
    if (ctx->qlen) {
      pop(ctx, output + made * ctx->cfg.channels);
      ++made;
    } else if (!ctx->front_done) {
      size_t produced = 1;
      sox_dsd_status_t st = lsx_dsd_reconstruction_finish(ctx->front,
          ctx->intermediate, &produced);
      if (st == SOX_DSD_DONE) ctx->front_done = 1;
      else if (st != SOX_DSD_NEED_OUTPUT) return ctx->error = st;
      if (produced && push_mid(ctx) != SOX_DSD_OK) return ctx->error;
    } else {
      unsigned c;
      size_t count = (size_t)-1;
      for (c = 0; c < ctx->cfg.channels; ++c) {
        double tmp[DSD_QUEUE];
        size_t produced = DSD_QUEUE;
        sox_dsd_status_t st = lsx_rate_f64_finish(ctx->src[c],
            ctx->target, tmp, &produced);
        size_t j;
        if (st != SOX_DSD_NEED_OUTPUT && st != SOX_DSD_DONE)
          return ctx->error = st;
        if (c && count != produced) return ctx->error = SOX_DSD_NUMERIC_ERROR;
        if (!c) count = produced;
        for (j = 0; j < produced; ++j)
          ctx->queue[(size_t)c * DSD_QUEUE + j] = tmp[j];
      }
      ctx->qhead = 0;
      ctx->qlen = (unsigned)count;
      if (!count) return ctx->error = SOX_DSD_NUMERIC_ERROR;
    }
  }
  *output_frames = made;
  if (ctx->delivered == ctx->target) {
    ctx->done = 1;
    return SOX_DSD_DONE;
  }
  return SOX_DSD_NEED_OUTPUT;
}

sox_dsd_status_t sox_dsd_decoder_report(const sox_dsd_decoder_t *ctx,
    sox_dsd_report_t *out)
{
  if (!ctx || !out || out->size < sizeof(*out) || out->version != 1)
    return SOX_DSD_BAD_ARGUMENT;
  out->native_frames = ctx->native_frames;
  out->intermediate_frames = ctx->intermediate_frames;
  out->output_frames = ctx->delivered;
  out->native_hz = ctx->cfg.native_hz;
  out->intermediate_hz = ctx->intermediate_hz;
  out->output_hz = ctx->cfg.output_hz;
  out->channels = ctx->cfg.channels;
  out->applied_gain = ctx->gain;
  out->effective_passband_hz = ctx->pass_hz;
  out->status = ctx->error ? ctx->error : ctx->done ? SOX_DSD_DONE :
                ctx->finishing ? SOX_DSD_NEED_OUTPUT : SOX_DSD_NEED_INPUT;
  return SOX_DSD_OK;
}
