/* DSD exact-rate descriptors and explicit effect-option frontends (P05).
 * Scalar reconstruction and composite modulation are separate later phases.
 */
#include "sox_i.h"
#include "dsd.h"
#include <math.h>
#include <errno.h>
#include <limits.h>

#define CAPS_QUALIFIED (LSX_DSD_READ_NATIVE | LSX_DSD_WRITE_NATIVE | LSX_DSD_RECONSTRUCT | LSX_DSD_MODULATE | LSX_DSD_DOP)
static lsx_dsd_rate const dsd_rates[] = {
  {2822400, 64, "DSD64", CAPS_QUALIFIED,
   "decode.mastering.v1.dsd64", "decode.wideband.v1.dsd64", "encode.mastering.v1.dsd64"},
  {5644800, 128, "DSD128", CAPS_QUALIFIED,
   "decode.mastering.v1.dsd128", "decode.wideband.v1.dsd128", "encode.mastering.v1.dsd128"},
  {11289600, 256, "DSD256", CAPS_QUALIFIED,
   "decode.mastering.v1.dsd256", "decode.wideband.v1.dsd256", "encode.mastering.v1.dsd256"},
  {22579200, 512, "DSD512", 0, NULL, NULL, NULL},
  {45158400, 1024, "DSD1024", 0, NULL, NULL, NULL}
};

lsx_dsd_rate const *lsx_dsd_rate_find(uint64_t hz)
{
  size_t i;
  for (i = 0; i < sizeof(dsd_rates)/sizeof(dsd_rates[0]); ++i)
    if (dsd_rates[i].hz == hz) return &dsd_rates[i];
  return NULL;
}

int lsx_dsd_integer_rate(double value, uint32_t *out)
{
  if (!out || !isfinite(value) || value <= 0 || value > UINT32_MAX || floor(value) != value)
    return 0;
  *out = (uint32_t)value;
  return 1;
}

int lsx_dsd_checked_interleaved(uint64_t frames, unsigned channels, uint64_t *out)
{
  if (!out || !channels || frames > UINT64_MAX / channels) return 0;
  *out = frames * channels;
  return 1;
}

/* Rounding is exact even at UINT64_MAX: quotient/remainder, no double path. */
int lsx_dsd_count_convert(uint64_t frames, uint32_t input_hz,
    uint32_t output_hz, uint64_t *out)
{
  uint64_t q, r, scaled, fractional;
  if (!out || !input_hz || !output_hz) return 0;
  q = frames / input_hz;
  r = frames % input_hz;
  if (q > UINT64_MAX / output_hz) return 0;
  scaled = q * output_hz;
  /* Two uint32_t operands fit within uint64_t; use a quotient and remainder
   * to avoid an overflow when rounding a 64-bit product upward. */
  fractional = (r * output_hz) / input_hz;
  if ((r * output_hz) % input_hz >= ((uint64_t)input_hz + 1) / 2)
    ++fractional;
  if (fractional > UINT64_MAX - scaled) return 0;
  *out = scaled + fractional;
  return 1;
}

/* P06 coefficients are versioned by these immutable rate/profile choices.
 * These values are derived from the actual emitted bank lengths in the
 * separate P06 coefficient manifest, not the earlier feasibility probe. */
static const lsx_dsd_frontend_profile dsd_frontends[] = {
  { 2822400,  88200, LSX_DSD_PROFILE_MASTERING,  20000,  40000, 5, LSX_DSD_BANK_MASTER64_256, 1348},
  { 5644800, 176400, LSX_DSD_PROFILE_MASTERING,  30000,  60000, 5, LSX_DSD_BANK_MASTER128, 1636},
  {11289600, 176400, LSX_DSD_PROFILE_MASTERING,  40000,  80000, 6, LSX_DSD_BANK_MASTER64_256, 2724},
  { 2822400,  88200, LSX_DSD_PROFILE_WIDEBAND,  35280,  44100, 5, LSX_DSD_BANK_WIDEBAND, 2468},
  { 5644800, 176400, LSX_DSD_PROFILE_WIDEBAND,  70560,  88200, 5, LSX_DSD_BANK_WIDEBAND, 2468},
  {11289600, 352800, LSX_DSD_PROFILE_WIDEBAND, 141120, 176400, 5, LSX_DSD_BANK_WIDEBAND, 2468}
};

const lsx_dsd_frontend_profile *lsx_dsd_frontend_profile_find(
    uint32_t rate, lsx_dsd_decode profile)
{
  size_t i;
  for (i = 0; i < sizeof(dsd_frontends)/sizeof(dsd_frontends[0]); ++i)
    if (dsd_frontends[i].native_hz == rate && dsd_frontends[i].kind == profile)
      return &dsd_frontends[i];
  return NULL;
}

int lsx_dsd_profile_edges(uint32_t rate, lsx_dsd_decode profile,
    double *pass, double *stop, double *intermediate)
{
  const lsx_dsd_frontend_profile *desc;
  if (!pass || !stop || !intermediate) return 0;
  desc = lsx_dsd_frontend_profile_find(rate, profile);
  if (!desc) return 0;
  *pass = desc->pass_hz;
  *stop = desc->stop_hz;
  *intermediate = desc->intermediate_hz;
  return 1;
}

double lsx_dsd_effective_bandwidth(double pass, double intermediate, double output)
{
  if (intermediate == output) return pass;
  return fmin(pass, .475 * fmin(intermediate, output));
}

int lsx_dsd_pcm_rate_supported(uint32_t hz)
{
  static uint32_t const rates[] = {
    44100,48000,88200,96000,176400,192000,352800,384000,705600
  };
  size_t i;
  for (i=0; i<sizeof(rates)/sizeof(rates[0]); ++i)
    if (hz == rates[i]) return 1;
  return 0;
}

char const *lsx_dsd_domain_name(lsx_dsd_domain d)
{
  switch(d) {
    case LSX_DSD_NATIVE: return "DSD_NATIVE";
    case LSX_PCM_AUDIO: return "PCM_AUDIO";
    case LSX_DOP_TRANSPORT: return "DOP_TRANSPORT";
    default: return "INVALID";
  }
}

/* Getopts has no stateful start, no allocations, and only records intent. */
static int parse_profile(char const *text, int encode, int *out, uint32_t *native)
{
  size_t i;
  for (i=0;i<sizeof(dsd_rates)/sizeof(dsd_rates[0]);i++) {
    char const *master=encode?dsd_rates[i].encode_mastering_id:dsd_rates[i].decode_mastering_id;
    char const *w=dsd_rates[i].decode_wideband_id;
    if (master && !strcmp(text,master)) {*out=0;*native=dsd_rates[i].hz;return 1;}
    if (!encode && w && !strcmp(text,w)) {*out=1;*native=dsd_rates[i].hz;return 1;}
  }

  if (!strcmp(text,"mastering")) { *out=0; return 1; }
  if (!encode && !strcmp(text,"wideband")) { *out=1; return 1; }
  if (!strcmp(text,"legacy")) { *out=encode?1:2; return 1; }
  if (encode && !strcmp(text,"experimental")) { *out=2; return 1; }
  return 0;
}
static int parse_rate(char const *text, uint32_t *rate)
{
  char *end;
  double v;
  errno=0;
  v=strtod(text,&end);
  return end != text && !*end && !errno && lsx_dsd_integer_rate(v,rate);
}
static int dsd_getopts(sox_effect_t *eff, int argc, char **argv)
{
  lsx_dsd_effect_options *opt=eff->priv;
  int i, is_encode=!strcmp(eff->handler.name,"pcmdsd"), profile;
  int seen_profile=0, seen_level=0, seen_reference=0, seen_rate=0;
  memset(opt,0,sizeof(*opt));
  opt->profile=LSX_DSD_PROFILE_MASTERING;
  opt->level=LSX_DSD_LEVEL_PRESERVE;
  opt->reference=LSX_DSD_REF_AUTO;
  opt->clip=LSX_DSD_CLIP_WARN;
  opt->bandwidth=LSX_DSD_BANDWIDTH_ADAPT;
  for (i=1;i<argc;++i) {
    if (!strcmp(argv[i],"-p") && i+1<argc) {
      if (seen_profile++ || !parse_profile(argv[++i],is_encode,&profile,&opt->pinned_native_hz)) goto invalid;
      opt->profile=(lsx_dsd_decode)profile; opt->profile_specified=1;
    } else if (!is_encode && !strcmp(argv[i],"-l") && i+1<argc) {
      if (seen_level++ || (strcmp(argv[++i],"preserve") && strcmp(argv[i],"sacd"))) goto invalid;
      opt->level=!strcmp(argv[i],"sacd")?LSX_DSD_LEVEL_SACD:LSX_DSD_LEVEL_PRESERVE;
      opt->level_specified=1;
    } else if (is_encode && !strcmp(argv[i],"--reference") && i+1<argc) {
      char const *s=argv[++i];
      if (seen_reference++) goto invalid;
      if (!strcmp(s,"auto")) opt->reference=LSX_DSD_REF_AUTO;
      else if (!strcmp(s,"pcm")) opt->reference=LSX_DSD_REF_PCM;
      else if (!strcmp(s,"dsd")) opt->reference=LSX_DSD_REF_DSD;
      else goto invalid;
      opt->reference_specified=1;
    } else if (argv[i][0]!='-' && !seen_rate++) {
      if (!parse_rate(argv[i],&opt->rate_hz)) goto invalid;
    } else goto invalid;
  }
  if (is_encode && !seen_rate) goto invalid;
  if (opt->rate_hz) eff->out_signal.rate=opt->rate_hz;
  if (is_encode) eff->out_signal.precision=1;
  else eff->out_signal.precision=SOX_SAMPLE_PRECISION;
  return SOX_SUCCESS;
invalid:
  lsx_fail("invalid %s options; see --help-effect %s",eff->handler.name,eff->handler.name);
  return SOX_EOF;
}

static int dsd_unavailable(sox_effect_t *eff)
{
  lsx_fail("%s: composite DSD DSP is not implemented in P05",eff->handler.name);
  return SOX_EOF;
}
static int dsdstat_getopts(sox_effect_t *eff, int argc, char **argv)
{
  (void)eff;(void)argv;
  return argc == 1 ? SOX_SUCCESS : SOX_EOF;
}

lsx_dsd_effect_options lsx_dsd_effect_get_options(sox_effect_t const *effect)
{
  lsx_dsd_effect_options defaults={0};
  defaults.profile=LSX_DSD_PROFILE_MASTERING;
  defaults.level=LSX_DSD_LEVEL_PRESERVE;
  defaults.reference=LSX_DSD_REF_AUTO;
  if (effect && (!strcmp(effect->handler.name,"dsdpcm") ||
                 !strcmp(effect->handler.name,"pcmdsd")))
    return *(lsx_dsd_effect_options const *)effect->priv;
  return defaults;
}

/* CLI policy is injected after option parsing, before effects are cloned. */
void lsx_dsd_effect_apply_policy(sox_effect_t *effect, const lsx_dsd_policy *policy)
{
  lsx_dsd_effect_options *opt;
  if (!effect || !policy || strcmp(effect->handler.name,"dsdpcm")) return;
  opt=effect->priv;
  opt->clip=policy->clip;
  opt->bandwidth=policy->bandwidth;
}

const sox_effect_handler_t *lsx_dsdpcm_effect_fn(void)
{
  static sox_effect_handler_t h={"dsdpcm", "[-p mastering|wideband|legacy] [-l preserve|sacd] [rate]",
    SOX_EFF_RATE | SOX_EFF_PREC, dsd_getopts, lsx_dsdpcm_start,
    lsx_dsdpcm_flow, lsx_dsdpcm_drain, lsx_dsdpcm_stop, NULL, sizeof(lsx_dsdpcm_private), NULL, NULL, NULL};
  return &h;
}
const sox_effect_handler_t *lsx_pcmdsd_effect_fn(void)
{
  static sox_effect_handler_t h={"pcmdsd", "[-p mastering|legacy|experimental] [--reference auto|pcm|dsd] rate",
    SOX_EFF_RATE | SOX_EFF_PREC, dsd_getopts, dsd_unavailable,
    NULL, NULL, NULL, NULL, sizeof(lsx_dsd_effect_options), NULL, NULL, NULL};
  return &h;
}
const sox_effect_handler_t *lsx_dsdstat_effect_fn(void)
{
  static sox_effect_handler_t h={"dsdstat", "(DSD native pass-through statistics, available in P14)",
    SOX_EFF_MCHAN, dsdstat_getopts, dsd_unavailable,
    NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL};
  return &h;
}
