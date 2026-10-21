/* P06: bounded scalar cascade of factor-two FIR decimators.
 *
 * Each ring has a mirrored halo: a write to p and p+L makes the L oldest-
 * to-newest samples contiguous at ring+p+1, including wrap.  No block memmove
 * or file-sized allocation is needed.  The native index selected by the stage
 * phases is G mod D; discard G / D causal outputs and the first returned
 * intermediate sample is centered at native time zero.  At EOF, append only
 * numeric +0.0 to the first stage until ceil(N/D) centered samples exist.
 * Rounding mode is inherited.  No modification to the caller FP environment.
 */
#include "dsd_decode.h"
#include "dsd_packed.h"
#include "dsd_coeffs.h"
#include "dsd_coeffs_v2.h"
#include "dsd_kernels.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define LSX_DSD_MAX_STAGES 8
#define LSX_DSD_ALIGN 64

typedef struct {
  const double *h;
  double *ring;
  size_t taps, head;
  uint64_t samples;
  unsigned phase, halfband;
} stage_state;

typedef struct {
  const double *coeff;
  size_t taps;
  int halfband;
} bank;

struct lsx_dsd_reconstruction {
  lsx_dsd_reconstruction_info info;
  const lsx_dsd_kernel *fir; /* selected once, immutable until destroy */
  stage_state *stages; /* stage count x channels, private mutable histories */
  double *histories;   /* single aligned allocation, each ring has a halo */
  void *histories_raw;
  double *frame;       /* per-channel scratch, owned by this context */
  uint64_t real_frames, emitted, raw_outputs, wanted;
  unsigned finish_started, done;
  sox_dsd_status_t error;
};

static const bank hb = {lsx_dsd_coeff_halfband, 57, 1};
static const bank m64 = {lsx_dsd_coeff_master64_256, 117, 0};
static const bank m128 = {lsx_dsd_coeff_master128, 153, 0};
static const bank wide = {lsx_dsd_coeff_wideband, 257, 0};
static const bank master256_v2 = {lsx_dsd_coeff_master256_v2, 325, 0};
static const bank master128_v2 = {lsx_dsd_coeff_master128_v2, 377, 0};
static const bank master64_v2 = {lsx_dsd_coeff_master64_v2, 153, 0};

/* Every individual channel/stage ring begins on a 64-byte boundary. The
 * mirrored halo occupies 2*L elements; only the end padding is unused. */
static size_t ring_stride(size_t taps)
{
  return (2 * taps + 7) & ~(size_t)7;
}

/* Portable C99 64-byte alignment; allocation is freed by its original base. */
static double *allocate_aligned(size_t bytes, void **raw)
{
  uintptr_t start, aligned;
  void *allocation;
  if (bytes > SIZE_MAX - (LSX_DSD_ALIGN - 1)) return NULL;
  allocation = calloc(1, bytes + LSX_DSD_ALIGN - 1);
  if (!allocation) return NULL;
  start = (uintptr_t)allocation;
  aligned = (start + LSX_DSD_ALIGN - 1) & ~(uintptr_t)(LSX_DSD_ALIGN - 1);
  *raw = allocation;
  return (double *)aligned;
}

sox_dsd_status_t lsx_dsd_reconstruction_create_kernel(
    uint32_t rate, lsx_dsd_decode profile, unsigned channels,
    const char *kernel_fir, lsx_dsd_reconstruction **out)
{
  lsx_dsd_reconstruction *ctx;
  const bank *last;
  const lsx_dsd_frontend_profile *desc;
  size_t elements = 0, offset = 0, c;
  uint64_t G = 0;
  unsigned depth, j;
  if (!out) return SOX_DSD_BAD_ARGUMENT;
  *out = NULL;
  desc = lsx_dsd_frontend_profile_find(rate,profile);
  if (!channels) return SOX_DSD_BAD_ARGUMENT;
  if (!desc) return SOX_DSD_UNSUPPORTED;
  depth = desc->stages;
  if (depth < 1 || depth > LSX_DSD_MAX_STAGES ||
      rate % desc->intermediate_hz) return SOX_DSD_UNSUPPORTED;
  switch (desc->last_bank) {
    case LSX_DSD_BANK_MASTER64_256: last = &m64; break;
    case LSX_DSD_BANK_MASTER128: last = &m128; break;
    case LSX_DSD_BANK_WIDEBAND: last = &wide; break;
    case LSX_DSD_BANK_MASTER64_V2: last = &master64_v2; break;
    case LSX_DSD_BANK_MASTER128_V2: last = &master128_v2; break;
    case LSX_DSD_BANK_MASTER256_V2: last = &master256_v2; break;
    default: return SOX_DSD_UNSUPPORTED;
  }
  ctx = calloc(1, sizeof(*ctx));
  if (!ctx) return SOX_DSD_NUMERIC_ERROR; /* allocation failure */
  ctx->info.native_hz = rate;
  ctx->info.intermediate_hz = desc->intermediate_hz;
  ctx->info.factor = rate / desc->intermediate_hz;
  ctx->info.channels = channels;
  ctx->info.stages = depth;
  for (j = 0; j < depth; ++j) {
    const bank *b = (j == depth - 1) ? last : &hb;
    ctx->info.taps[j] = (unsigned)b->taps;
    G += ((uint64_t)(b->taps / 2)) << j;
    if (channels > (SIZE_MAX - elements) / ring_stride(b->taps))
      goto invalid_size;
    elements += (size_t)channels * ring_stride(b->taps);
  }
  if (elements > SIZE_MAX / sizeof(double)) goto invalid_size;
  if (G != desc->delay_native_frames) goto invalid_size;
  if (lsx_dsd_kernel_select(LSX_DSD_FIR,kernel_fir,&ctx->fir)) goto unsupported_kernel;
  ctx->info.delay_native_frames = G;
  ctx->info.discard_frames = G / ctx->info.factor;
  for (j = 0; j < depth; ++j)
    ctx->info.phases[j] = (unsigned)((G >> j) & 1u);
  ctx->stages = calloc((size_t)channels * depth, sizeof(*ctx->stages));
  ctx->frame = calloc(channels, sizeof(*ctx->frame));
  ctx->histories = allocate_aligned(elements * sizeof(double), &ctx->histories_raw);
  if (!ctx->stages || !ctx->frame || !ctx->histories) goto no_memory;
  for (c = 0; c < channels; ++c) {
    for (j = 0; j < depth; ++j) {
      const bank *b = j == depth - 1 ? last : &hb;
      stage_state *st = &ctx->stages[c*depth+j];
      st->h = b->coeff;
      st->taps = b->taps;
      st->ring = ctx->histories + offset;
      st->phase = ctx->info.phases[j];
      st->halfband = (unsigned)b->halfband;
      offset += ring_stride(b->taps);
    }
  }
  ctx->info.allocated_bytes = sizeof(*ctx) + channels * depth * sizeof(stage_state)
      + channels * sizeof(double) + elements * sizeof(double) + LSX_DSD_ALIGN - 1;
  *out = ctx;
  return SOX_DSD_OK;
unsupported_kernel:
  lsx_dsd_reconstruction_destroy(ctx);
  return SOX_DSD_UNSUPPORTED;
invalid_size:
  lsx_dsd_reconstruction_destroy(ctx);
  return SOX_DSD_BAD_ARGUMENT;
no_memory:
  lsx_dsd_reconstruction_destroy(ctx);
  return SOX_DSD_NUMERIC_ERROR;
}

sox_dsd_status_t lsx_dsd_reconstruction_create(
    uint32_t rate, lsx_dsd_decode profile, unsigned channels,
    lsx_dsd_reconstruction **out)
{
  return lsx_dsd_reconstruction_create_kernel(rate,profile,channels,NULL,out);
}

const char *lsx_dsd_reconstruction_kernel_name(const lsx_dsd_reconstruction *ctx)
{
  return ctx && ctx->fir ? ctx->fir->name : NULL;
}

/* scalar directly bound: feed one sample through a mono cascade.  Stage phases are common to all
 * channels, hence their output flags must agree for each interleaved frame. */
static int feed_scalar(lsx_dsd_reconstruction *ctx, unsigned channel, unsigned j,
                double x, double *result)
{
  stage_state *st = &ctx->stages[(size_t)channel * ctx->info.stages + j];
  const size_t head = st->head, L = st->taps;
  st->ring[head] = x;
  st->ring[head + L] = x; /* mirrored halo */
  st->head = head + 1 == L ? 0 : head + 1;
  if ((st->samples++ & 1u) != st->phase) return 0;
  x = st->halfband ? lsx_dsd_fir_halfband57(st->h, st->ring + head + 1)
      : lsx_dsd_fir_scalar(st->h, L, st->ring + head + 1, 0);
  if (j + 1 == ctx->info.stages) {
    *result = x;
    return 1;
  }
  return feed_scalar(ctx, channel, j + 1, x, result);
}

static int accept_frame_scalar(lsx_dsd_reconstruction *ctx, const sox_sample_t *bits,
                        int pad, double *pcm, size_t destination)
{
  unsigned c;
  int produced = 0;
  for (c = 0; c < ctx->info.channels; ++c) {
    int got;
    double x = pad ? 0.0 : (bits[c] == SOX_SAMPLE_MAX ? 1.0 : -1.0);
    got = feed_scalar(ctx, c, 0, x, &ctx->frame[c]);
    if (!c) produced = got;
    /* Each channel shares stage clocks; no channel-specific phase drift. */
  }
  if (produced) {
    uint64_t index = ctx->raw_outputs++;
    if (index >= ctx->info.discard_frames) {
      for (c = 0; c < ctx->info.channels; ++c)
        pcm[destination * ctx->info.channels + c] = ctx->frame[c];
      ++ctx->emitted;
      return 1;
    }
  }
  return 0;
}

#if defined(HAVE_DSD_SSE2)
/* sse2 directly bound: feed one sample through a mono cascade.  Stage phases are common to all
 * channels, hence their output flags must agree for each interleaved frame. */
static int feed_sse2(lsx_dsd_reconstruction *ctx, unsigned channel, unsigned j,
                double x, double *result)
{
  stage_state *st = &ctx->stages[(size_t)channel * ctx->info.stages + j];
  const size_t head = st->head, L = st->taps;
  st->ring[head] = x;
  st->ring[head + L] = x; /* mirrored halo */
  st->head = head + 1 == L ? 0 : head + 1;
  if ((st->samples++ & 1u) != st->phase) return 0;
  x = st->halfband ? lsx_dsd_fir_halfband57(st->h, st->ring + head + 1)
      : lsx_dsd_fir_sse2_direct(st->h, L, st->ring + head + 1, 0);
  if (j + 1 == ctx->info.stages) {
    *result = x;
    return 1;
  }
  return feed_sse2(ctx, channel, j + 1, x, result);
}

static int accept_frame_sse2(lsx_dsd_reconstruction *ctx, const sox_sample_t *bits,
                        int pad, double *pcm, size_t destination)
{
  unsigned c;
  int produced = 0;
  for (c = 0; c < ctx->info.channels; ++c) {
    int got;
    double x = pad ? 0.0 : (bits[c] == SOX_SAMPLE_MAX ? 1.0 : -1.0);
    got = feed_sse2(ctx, c, 0, x, &ctx->frame[c]);
    if (!c) produced = got;
    /* Each channel shares stage clocks; no channel-specific phase drift. */
  }
  if (produced) {
    uint64_t index = ctx->raw_outputs++;
    if (index >= ctx->info.discard_frames) {
      for (c = 0; c < ctx->info.channels; ++c)
        pcm[destination * ctx->info.channels + c] = ctx->frame[c];
      ++ctx->emitted;
      return 1;
    }
  }
  return 0;
}

#endif
#if defined(HAVE_DSD_AVX1)
/* avx1 directly bound: feed one sample through a mono cascade.  Stage phases are common to all
 * channels, hence their output flags must agree for each interleaved frame. */
static int feed_avx1(lsx_dsd_reconstruction *ctx, unsigned channel, unsigned j,
                double x, double *result)
{
  stage_state *st = &ctx->stages[(size_t)channel * ctx->info.stages + j];
  const size_t head = st->head, L = st->taps;
  st->ring[head] = x;
  st->ring[head + L] = x; /* mirrored halo */
  st->head = head + 1 == L ? 0 : head + 1;
  if ((st->samples++ & 1u) != st->phase) return 0;
  x = st->halfband ? lsx_dsd_fir_halfband57(st->h, st->ring + head + 1)
      : lsx_dsd_fir_avx1_direct(st->h, L, st->ring + head + 1, 0);
  if (j + 1 == ctx->info.stages) {
    *result = x;
    return 1;
  }
  return feed_avx1(ctx, channel, j + 1, x, result);
}

static int accept_frame_avx1(lsx_dsd_reconstruction *ctx, const sox_sample_t *bits,
                        int pad, double *pcm, size_t destination)
{
  unsigned c;
  int produced = 0;
  for (c = 0; c < ctx->info.channels; ++c) {
    int got;
    double x = pad ? 0.0 : (bits[c] == SOX_SAMPLE_MAX ? 1.0 : -1.0);
    got = feed_avx1(ctx, c, 0, x, &ctx->frame[c]);
    if (!c) produced = got;
    /* Each channel shares stage clocks; no channel-specific phase drift. */
  }
  if (produced) {
    uint64_t index = ctx->raw_outputs++;
    if (index >= ctx->info.discard_frames) {
      for (c = 0; c < ctx->info.channels; ++c)
        pcm[destination * ctx->info.channels + c] = ctx->frame[c];
      ++ctx->emitted;
      return 1;
    }
  }
  return 0;
}

#endif
#if defined(HAVE_DSD_AVX2)
/* avx2 directly bound: feed one sample through a mono cascade.  Stage phases are common to all
 * channels, hence their output flags must agree for each interleaved frame. */
static int feed_avx2(lsx_dsd_reconstruction *ctx, unsigned channel, unsigned j,
                double x, double *result)
{
  stage_state *st = &ctx->stages[(size_t)channel * ctx->info.stages + j];
  const size_t head = st->head, L = st->taps;
  st->ring[head] = x;
  st->ring[head + L] = x; /* mirrored halo */
  st->head = head + 1 == L ? 0 : head + 1;
  if ((st->samples++ & 1u) != st->phase) return 0;
  x = st->halfband ? lsx_dsd_fir_halfband57(st->h, st->ring + head + 1)
      : lsx_dsd_fir_avx2_direct(st->h, L, st->ring + head + 1, 0);
  if (j + 1 == ctx->info.stages) {
    *result = x;
    return 1;
  }
  return feed_avx2(ctx, channel, j + 1, x, result);
}

static int accept_frame_avx2(lsx_dsd_reconstruction *ctx, const sox_sample_t *bits,
                        int pad, double *pcm, size_t destination)
{
  unsigned c;
  int produced = 0;
  for (c = 0; c < ctx->info.channels; ++c) {
    int got;
    double x = pad ? 0.0 : (bits[c] == SOX_SAMPLE_MAX ? 1.0 : -1.0);
    got = feed_avx2(ctx, c, 0, x, &ctx->frame[c]);
    if (!c) produced = got;
    /* Each channel shares stage clocks; no channel-specific phase drift. */
  }
  if (produced) {
    uint64_t index = ctx->raw_outputs++;
    if (index >= ctx->info.discard_frames) {
      for (c = 0; c < ctx->info.channels; ++c)
        pcm[destination * ctx->info.channels + c] = ctx->frame[c];
      ++ctx->emitted;
      return 1;
    }
  }
  return 0;
}

#endif
#if defined(HAVE_DSD_AVX512)
/* P13: the AVX-512F direct FIR belongs to the same stateful decimation
 * cascade as scalar/SSE2/AVX1/AVX2. Selecting the descriptor without this
 * graph binding would accept the forced tier at creation but reject every
 * input frame. Keep stage clocks, mirrored history, padding and emission
 * accounting identical to the existing optimized paths. */
static int feed_avx512(lsx_dsd_reconstruction *ctx, unsigned channel, unsigned j,
                    double x, double *result)
{
  stage_state *st = &ctx->stages[(size_t)channel * ctx->info.stages + j];
  const size_t head = st->head, L = st->taps;
  st->ring[head] = x;
  st->ring[head + L] = x;
  st->head = head + 1 == L ? 0 : head + 1;
  if ((st->samples++ & 1u) != st->phase) return 0;
  x = st->halfband ? lsx_dsd_fir_halfband57(st->h, st->ring + head + 1)
      : lsx_dsd_fir_avx512_direct(st->h, L, st->ring + head + 1, 0);
  if (j + 1 == ctx->info.stages) {
    *result = x;
    return 1;
  }
  return feed_avx512(ctx, channel, j + 1, x, result);
}

static int accept_frame_avx512(lsx_dsd_reconstruction *ctx, const sox_sample_t *bits,
                             int pad, double *pcm, size_t destination)
{
  unsigned c;
  int produced = 0;
  for (c = 0; c < ctx->info.channels; ++c) {
    int got;
    double x = pad ? 0.0 : (bits[c] == SOX_SAMPLE_MAX ? 1.0 : -1.0);
    got = feed_avx512(ctx, c, 0, x, &ctx->frame[c]);
    if (!c) produced = got;
  }
  if (produced) {
    uint64_t index = ctx->raw_outputs++;
    if (index >= ctx->info.discard_frames) {
      for (c = 0; c < ctx->info.channels; ++c)
        pcm[destination * ctx->info.channels + c] = ctx->frame[c];
      ++ctx->emitted;
      return 1;
    }
  }
  return 0;
}
#endif
sox_dsd_status_t lsx_dsd_reconstruction_process(
    lsx_dsd_reconstruction *ctx, const sox_sample_t *bits,
    size_t *input_frames, double *pcm, size_t *output_frames)
{
  size_t avail, limit, consumed = 0, produced = 0;
  if (!ctx) return SOX_DSD_BAD_ARGUMENT;
  if (!input_frames || !output_frames) {
    ctx->error = SOX_DSD_BAD_ARGUMENT;
    return ctx->error;
  }
  avail = *input_frames;
  limit = *output_frames;
  *input_frames = *output_frames = 0;
  if (ctx->error) return ctx->error;
  if (ctx->finish_started) return SOX_DSD_BAD_ARGUMENT;
  if (!limit) return SOX_DSD_NEED_OUTPUT; /* no validation/state mutation */
  if ((avail && !bits) || !pcm) {
    ctx->error = SOX_DSD_BAD_ARGUMENT;
    return ctx->error;
  }
  /* Reserve integer headroom for the longest finite tail, even for unknown EOF. */
  if (ctx->real_frames > UINT64_MAX - ctx->info.delay_native_frames - ctx->info.factor ||
      avail > UINT64_MAX - ctx->info.delay_native_frames - ctx->info.factor - ctx->real_frames ||
      (ctx->info.channels && avail > SIZE_MAX / ctx->info.channels) ||
      (ctx->info.channels && limit > SIZE_MAX / ctx->info.channels)) {
    ctx->error = SOX_DSD_NUMERIC_ERROR;
    return ctx->error;
  }
#define LSX_DSD_STREAM_FRAMES(ACCEPT) do {                                   \
  while (consumed < avail && produced < limit) {                            \
    unsigned c;                                                             \
    const sox_sample_t *frame = bits + consumed * ctx->info.channels;       \
    for (c = 0; c < ctx->info.channels; ++c) {                               \
      if (frame[c] != SOX_SAMPLE_MAX && frame[c] != -SOX_SAMPLE_MAX) {       \
        ctx->error = SOX_DSD_BAD_ARGUMENT;                                  \
        *input_frames = consumed; *output_frames = produced;                \
        return SOX_DSD_BAD_ARGUMENT;                                        \
      }                                                                     \
    }                                                                       \
    produced += ACCEPT(ctx, frame, 0, pcm, produced);                       \
    ++consumed; ++ctx->real_frames;                                         \
  }                                                                         \
} while (0)
  if (ctx->fir == &lsx_dsd_kernel_scalar)
    LSX_DSD_STREAM_FRAMES(accept_frame_scalar);
#if defined(HAVE_DSD_SSE2)
  else if (ctx->fir == &lsx_dsd_kernel_sse2)
    LSX_DSD_STREAM_FRAMES(accept_frame_sse2);
#endif
#if defined(HAVE_DSD_AVX1)
  else if (ctx->fir == &lsx_dsd_kernel_avx1)
    LSX_DSD_STREAM_FRAMES(accept_frame_avx1);
#endif
#if defined(HAVE_DSD_AVX2)
  else if (ctx->fir == &lsx_dsd_kernel_avx2)
    LSX_DSD_STREAM_FRAMES(accept_frame_avx2);
#endif
#if defined(HAVE_DSD_AVX512)
  else if (ctx->fir == &lsx_dsd_kernel_avx512)
    LSX_DSD_STREAM_FRAMES(accept_frame_avx512);
#endif
  else return SOX_DSD_UNSUPPORTED;
#undef LSX_DSD_STREAM_FRAMES
  *input_frames = consumed;
  *output_frames = produced;
  if (consumed < avail) return SOX_DSD_NEED_OUTPUT;
  return SOX_DSD_NEED_INPUT;
}

/* P16 first-stage ingestion. The address calculation reads *one bit*
 * directly from the borrowed layout; its numerical value and selected FIR
 * function are exactly those of the existing expanded front end. There is no
 * int32 graph block, coefficient table, independent phase or output queue. */
sox_dsd_status_t lsx_dsd_reconstruction_process_packed(
    lsx_dsd_reconstruction *ctx, const sox_dsd_packed_block_t *b, size_t start,
    size_t *input_frames, double *pcm, size_t *output_frames)
{
  size_t avail, limit, consumed = 0, produced = 0;
  if (!ctx) return SOX_DSD_BAD_ARGUMENT;
  if (!input_frames || !output_frames)
    return ctx->error = SOX_DSD_BAD_ARGUMENT;
  avail = *input_frames;
  limit = *output_frames;
  *input_frames = *output_frames = 0;
  if (ctx->error) return ctx->error;
  if (ctx->finish_started) return SOX_DSD_BAD_ARGUMENT;
  if (!limit) return SOX_DSD_NEED_OUTPUT;
  if (!pcm || !b || !lsx_dsd_packed_validate(b) ||
      b->channels != ctx->info.channels || start > b->frames ||
      avail > b->frames - start ||
      (ctx->info.channels && limit > SIZE_MAX / ctx->info.channels))
    return ctx->error = SOX_DSD_BAD_ARGUMENT;
  if (ctx->real_frames > UINT64_MAX - ctx->info.delay_native_frames - ctx->info.factor ||
      avail > UINT64_MAX - ctx->info.delay_native_frames - ctx->info.factor - ctx->real_frames)
    return ctx->error = SOX_DSD_NUMERIC_ERROR;
#define LSX_DSD_STREAM_PACKED(FEED) do {                                    \
  while (consumed < avail && produced < limit) {                            \
    unsigned c;                                                             \
    int got = 0;                                                            \
    for (c = 0; c < ctx->info.channels; ++c) {                               \
      double x = lsx_dsd_packed_bit(b,start+consumed,c) ? 1.0 : -1.0;       \
      int event = FEED(ctx,c,0,x,&ctx->frame[c]);                            \
      if (!c) got = event;                                                  \
    }                                                                       \
    if (got) {                                                              \
      uint64_t index = ctx->raw_outputs++;                                  \
      if (index >= ctx->info.discard_frames) {                               \
        for (c = 0; c < ctx->info.channels; ++c)                              \
          pcm[produced * ctx->info.channels + c] = ctx->frame[c];            \
        ++ctx->emitted;                                                     \
        ++produced;                                                         \
      }                                                                     \
    }                                                                       \
    ++consumed; ++ctx->real_frames;                                         \
  }                                                                         \
} while (0)
  if (ctx->fir == &lsx_dsd_kernel_scalar)
    LSX_DSD_STREAM_PACKED(feed_scalar);
#if defined(HAVE_DSD_SSE2)
  else if (ctx->fir == &lsx_dsd_kernel_sse2)
    LSX_DSD_STREAM_PACKED(feed_sse2);
#endif
#if defined(HAVE_DSD_AVX1)
  else if (ctx->fir == &lsx_dsd_kernel_avx1)
    LSX_DSD_STREAM_PACKED(feed_avx1);
#endif
#if defined(HAVE_DSD_AVX2)
  else if (ctx->fir == &lsx_dsd_kernel_avx2)
    LSX_DSD_STREAM_PACKED(feed_avx2);
#endif
#if defined(HAVE_DSD_AVX512)
  else if (ctx->fir == &lsx_dsd_kernel_avx512)
    LSX_DSD_STREAM_PACKED(feed_avx512);
#endif
  else return SOX_DSD_UNSUPPORTED;
#undef LSX_DSD_STREAM_PACKED
  *input_frames = consumed;
  *output_frames = produced;
  return consumed < avail ? SOX_DSD_NEED_OUTPUT : SOX_DSD_NEED_INPUT;
}

sox_dsd_status_t lsx_dsd_reconstruction_finish(
    lsx_dsd_reconstruction *ctx, double *pcm, size_t *output_frames)
{
  size_t capacity, produced = 0;
  if (!ctx) return SOX_DSD_BAD_ARGUMENT;
  if (!output_frames) {
    ctx->error = SOX_DSD_BAD_ARGUMENT;
    return ctx->error;
  }
  capacity = *output_frames;
  *output_frames = 0;
  if (ctx->error) return ctx->error;
  if (ctx->done) return SOX_DSD_DONE;
  if (capacity && !pcm) {
    ctx->error = SOX_DSD_BAD_ARGUMENT;
    return ctx->error;
  }
  if (!capacity) return SOX_DSD_NEED_OUTPUT;
  if (!ctx->finish_started) {
    const uint64_t D = ctx->info.factor;
    uint64_t wanted = ctx->real_frames / D + (ctx->real_frames % D != 0);
    /* Index arithmetic for lookahead cannot wrap at the uint64 limit. */
    if (wanted && (wanted - 1 > (UINT64_MAX - ctx->info.delay_native_frames) / D ||
                   ctx->real_frames > UINT64_MAX - ctx->info.delay_native_frames - D)) {
      ctx->error = SOX_DSD_NUMERIC_ERROR;
      return SOX_DSD_NUMERIC_ERROR;
    }
    ctx->wanted = wanted;
    ctx->finish_started = 1;
  }
#define LSX_DSD_FINISH_FRAMES(ACCEPT) do {                                   \
  while (produced < capacity && ctx->emitted < ctx->wanted)                 \
    produced += ACCEPT(ctx, NULL, 1, pcm, produced);                        \
} while (0)
  if (ctx->fir == &lsx_dsd_kernel_scalar)
    LSX_DSD_FINISH_FRAMES(accept_frame_scalar);
#if defined(HAVE_DSD_SSE2)
  else if (ctx->fir == &lsx_dsd_kernel_sse2)
    LSX_DSD_FINISH_FRAMES(accept_frame_sse2);
#endif
#if defined(HAVE_DSD_AVX1)
  else if (ctx->fir == &lsx_dsd_kernel_avx1)
    LSX_DSD_FINISH_FRAMES(accept_frame_avx1);
#endif
#if defined(HAVE_DSD_AVX2)
  else if (ctx->fir == &lsx_dsd_kernel_avx2)
    LSX_DSD_FINISH_FRAMES(accept_frame_avx2);
#endif
#if defined(HAVE_DSD_AVX512)
  else if (ctx->fir == &lsx_dsd_kernel_avx512)
    LSX_DSD_FINISH_FRAMES(accept_frame_avx512);
#endif
  else return SOX_DSD_UNSUPPORTED;
#undef LSX_DSD_FINISH_FRAMES
  *output_frames = produced;
  if (ctx->emitted == ctx->wanted) {
    ctx->done = 1;
    return SOX_DSD_DONE;
  }
  return SOX_DSD_NEED_OUTPUT;
}

sox_dsd_status_t lsx_dsd_reconstruction_info_get(
    const lsx_dsd_reconstruction *ctx, lsx_dsd_reconstruction_info *out)
{
  if (!ctx || !out) return SOX_DSD_BAD_ARGUMENT;
  *out = ctx->info;
  return SOX_DSD_OK;
}

void lsx_dsd_reconstruction_destroy(lsx_dsd_reconstruction *ctx)
{
  if (!ctx) return;
  free(ctx->histories_raw);
  free(ctx->stages);
  free(ctx->frame);
  free(ctx);
}
