/* Private DSD capability and CLI preflight contract.  Not an installed ABI. */
#ifndef LSX_DSD_H
#define LSX_DSD_H
#ifndef LSX_EFF_FATAL
#define LSX_EFF_FATAL (-0x5D50)
#endif

#include "sox_ng.h"
#include "sox_dsd.h"
#include <stdint.h>
#include <stdio.h>

typedef enum {
  LSX_DSD_NATIVE, LSX_PCM_AUDIO, LSX_DOP_TRANSPORT
} lsx_dsd_domain;

enum lsx_dsd_capability {
  LSX_DSD_READ_NATIVE = 1u << 0,
  LSX_DSD_WRITE_NATIVE = 1u << 1,
  LSX_DSD_RECONSTRUCT = 1u << 2,
  LSX_DSD_MODULATE = 1u << 3,
  LSX_DSD_DOP = 1u << 4
};

typedef struct {
  uint32_t hz;
  unsigned multiplier;
  char const *name;
  unsigned capabilities;
  char const *decode_mastering_id, *decode_wideband_id;
  char const *encode_mastering_id;
} lsx_dsd_rate;

typedef enum {LSX_DSD_MODE_LEGACY, LSX_DSD_MODE_AUTO, LSX_DSD_MODE_NATIVE} lsx_dsd_mode;
typedef enum {LSX_DSD_PROFILE_MASTERING, LSX_DSD_PROFILE_WIDEBAND,
              LSX_DSD_PROFILE_LEGACY} lsx_dsd_decode;
typedef enum {LSX_DSD_ENCODE_MASTERING, LSX_DSD_ENCODE_LEGACY,
              LSX_DSD_ENCODE_EXPERIMENTAL} lsx_dsd_encode;
typedef enum {LSX_DSD_LEVEL_PRESERVE, LSX_DSD_LEVEL_SACD} lsx_dsd_level;
typedef enum {LSX_DSD_CLIP_WARN, LSX_DSD_CLIP_ERROR} lsx_dsd_clip;
typedef enum {LSX_DSD_BANDWIDTH_ADAPT, LSX_DSD_BANDWIDTH_STRICT} lsx_dsd_bandwidth;
typedef enum {LSX_DSD_REF_AUTO, LSX_DSD_REF_PCM, LSX_DSD_REF_DSD} lsx_dsd_reference;
typedef enum {LSX_DSD_COMBINE_SEQUENCE, LSX_DSD_COMBINE_CONCAT,
              LSX_DSD_COMBINE_MIX, LSX_DSD_COMBINE_MIX_POWER,
              LSX_DSD_COMBINE_MERGE, LSX_DSD_COMBINE_MULTIPLY} lsx_dsd_combine;

typedef struct {
  lsx_dsd_decode profile;
  lsx_dsd_level level;
  uint32_t rate_hz;
  lsx_dsd_reference reference;
  int profile_specified, level_specified, reference_specified;
  uint32_t pinned_native_hz; /* Versioned profile ID, or 0 for alias. */
  lsx_dsd_clip clip;
  lsx_dsd_bandwidth bandwidth;
} lsx_dsd_effect_options;

typedef struct {
  lsx_dsd_mode mode;
  lsx_dsd_decode decode;
  lsx_dsd_encode encode;
  lsx_dsd_level level;
  lsx_dsd_clip clip;
  lsx_dsd_bandwidth bandwidth;
  int layout_loss_warn;
  int guarded;
  int normalizing;             /* --norm always inserts an automatic PCM gain. */
  int dither_disabled;
  int decode_specified, encode_specified, level_specified;
  /* Explicit versioned CLI selections are tied to a native clock.  Zero
   * denotes a human profile alias, not a versioned selection. */
  uint32_t decode_pinned_native_hz, encode_pinned_native_hz;
  char const *kernel_fir, *kernel_sdm;
} lsx_dsd_policy;

typedef struct {
  sox_signalinfo_t native_signal; /* Unmodified reader signal. */
  sox_encoding_t encoding;
  double input_volume;            /* Includes -v and replay-gain, pre-combiner. */
  int layout_known;
} lsx_dsd_input_spec;

typedef struct {
  char const *name;
  unsigned flags;                 /* Parsed effect handler flags, never start(). */
  double out_rate;                /* getopts hint, may be zero. */
  unsigned out_channels;          /* getopts hint, may be zero. */
  int native_permutation;         /* Verified private remix map. */
  int dither_precision_one;       /* Query of getopts state, not start(). */
  char const *sdm_filter_name;    /* Borrowed low-level -f option (nullable). */
  lsx_dsd_effect_options dsd;     /* Parsed and validated explicit options. */
} lsx_dsd_effect_spec;

typedef struct {
  lsx_dsd_policy policy;
  lsx_dsd_combine combine;
  lsx_dsd_input_spec const *inputs;
  size_t input_count;
  lsx_dsd_effect_spec const *effects;
  size_t effect_count;
  double requested_output_rate;   /* Zero if not supplied, no rounding. */
  unsigned requested_output_channels;
  sox_encodinginfo_t requested_encoding;
  char const *output_path;
  char const *output_type;
  int output_native_capable;
  int output_pcm_capable;
  int output_dop_capable;
  int output_is_null;
  int output_has_explicit_encoding;
  sox_encoding_t fallback_encoding;
  unsigned fallback_bits;
} lsx_dsd_plan_spec;

typedef struct {
  double native_rate, effective_rate, volume, reference;
  unsigned channels;
  lsx_dsd_domain native_domain, effective_domain;
  int decoder_before_combiner;
  int volume_consumed_by_decoder;
  char const *decoder_id;
  double decoder_pass_hz, decoder_stop_hz, effective_bandwidth_hz;
  double decoder_gain;
} lsx_dsd_plan_input;

typedef struct {
  char const *name;
  lsx_dsd_domain before, after;
  double rate_before, rate_after;
  unsigned channels_before, channels_after;
  int implicit;
  int input_index; /* -1 for chain nodes */
  double reference;
} lsx_dsd_plan_step;

typedef struct {
  lsx_dsd_plan_input *inputs;
  lsx_dsd_plan_step *steps;
  size_t input_count, step_count, step_capacity;
  lsx_dsd_domain combiner_domain, output_domain;
  double combiner_rate, processing_rate, output_rate;
  unsigned combiner_channels, output_channels, output_bits;
  sox_encoding_t output_encoding;
  double decoder_pass_hz, decoder_stop_hz, decoder_intermediate_hz;
  double effective_bandwidth_hz, decoder_gain, dsd_amplitude_per_pcm_unit;
  double modulator_input_scale;
  uint32_t native_output_hz;
  int input_decode_count, graph_decode_count, encode_count, dop_count;
  int trim_native_seek, layout_identity_preserved;
  int executable, needs_unimplemented_dsp;
  char const *unavailable_reason;
  char const *decoder_id, *encoder_id;
  char const *encoder_filter_name; /* Low-level SDM selection; not mastering. */
} lsx_dsd_plan;

lsx_dsd_rate const *lsx_dsd_rate_find(uint64_t hz);
int lsx_dsd_integer_rate(double value, uint32_t *out);
int lsx_dsd_checked_interleaved(uint64_t frames, unsigned channels, uint64_t *out);
int lsx_dsd_count_convert(uint64_t frames, uint32_t input_hz, uint32_t output_hz, uint64_t *out);
/* Certified P06 front-end profiles. Private immutable metadata; P07 may
 * compose these with a separate final-rate adapter. Bank codes are immutable
 * internal identities, never user-selectable kernel implementations. */
typedef enum {LSX_DSD_BANK_MASTER64_256, LSX_DSD_BANK_MASTER128,
              LSX_DSD_BANK_WIDEBAND} lsx_dsd_last_bank;
typedef struct {
  uint32_t native_hz, intermediate_hz;
  lsx_dsd_decode kind;
  double pass_hz, stop_hz;
  unsigned stages;
  lsx_dsd_last_bank last_bank;
  uint64_t delay_native_frames;
} lsx_dsd_frontend_profile;
const lsx_dsd_frontend_profile *lsx_dsd_frontend_profile_find(
    uint32_t native_hz, lsx_dsd_decode profile);

int lsx_dsd_profile_edges(uint32_t native_hz, lsx_dsd_decode profile,
    double *pass, double *stop, double *intermediate);
double lsx_dsd_effective_bandwidth(double pass, double intermediate, double output);
int lsx_dsd_pcm_rate_supported(uint32_t hz);
char const *lsx_dsd_domain_name(lsx_dsd_domain domain);

int lsx_dsd_plan_build(lsx_dsd_plan_spec const *, lsx_dsd_plan *, char *error, size_t error_len);
void lsx_dsd_plan_free(lsx_dsd_plan *);
void lsx_dsd_plan_json(FILE *, lsx_dsd_plan_spec const *, lsx_dsd_plan const *);

/* Per-channel adapter owns its decoder only after start, since effects.c
 * copies the pre-start private struct to every channel before start(). */
typedef struct {
  lsx_dsd_effect_options options; /* Must remain first for P05 parser. */
  sox_dsd_decoder_t *decoder;
  uint64_t graph_clips;
  double max_preclip;
} lsx_dsdpcm_private;
int lsx_dsdpcm_start(sox_effect_t *);
int lsx_dsdpcm_flow(sox_effect_t *, const sox_sample_t *, sox_sample_t *,
    size_t *, size_t *);
int lsx_dsdpcm_drain(sox_effect_t *, sox_sample_t *, size_t *);
int lsx_dsdpcm_stop(sox_effect_t *);
int lsx_dsd_profile_parse(const char *name, int encode, int *profile, uint32_t *native_hz);
void lsx_dsd_effect_apply_policy(sox_effect_t *, const lsx_dsd_policy *);
/* P07 implements explicit reconstruction only; other composites remain future DSP. */
const sox_effect_handler_t *lsx_dsdpcm_effect_fn(void);
const sox_effect_handler_t *lsx_pcmdsd_effect_fn(void);
const sox_effect_handler_t *lsx_dsdstat_effect_fn(void);
int lsx_dsdstat_getopts(sox_effect_t *,int,char **);
int lsx_dsdstat_start(sox_effect_t *);
int lsx_dsdstat_flow(sox_effect_t *,const sox_sample_t *,sox_sample_t *,size_t *,size_t *);
int lsx_dsdstat_stop(sox_effect_t *);
lsx_dsd_effect_options lsx_dsd_effect_get_options(sox_effect_t const *effect);
int lsx_dither_explicit_one_bit(sox_effect_t const *effect);
char const *lsx_sdm_effect_filter_name(sox_effect_t const *effect);
int lsx_sdm_filter_valid_for_rate(char const *filter_name, uint32_t rate);
char const *lsx_sdm_filter_selected_name(char const *filter_name, uint32_t rate);

#endif
