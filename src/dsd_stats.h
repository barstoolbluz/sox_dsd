/* P14 observational DSD statistics and conversion-report interface.
 * No sample path or DSP coefficient state is owned by this collector. */
#ifndef LSX_DSD_STATS_H
#define LSX_DSD_STATS_H
#include "dsd.h"
#include "pcmdsd.h"
#include <stdint.h>
#include <stdio.h>

typedef struct lsx_dsd_stats lsx_dsd_stats;
typedef struct lsx_dsd_report_context lsx_dsd_report_context;

/* Canonical native bits are +/- SOX_SAMPLE_MAX, interleaved by channel.
 * A count failure is latched; frames/counters never wrap. */
lsx_dsd_stats *lsx_dsd_stats_create(unsigned channels, uint32_t hz, int analysis);
int lsx_dsd_stats_feed(lsx_dsd_stats *, const sox_sample_t *bits, size_t frames);
void lsx_dsd_stats_destroy(lsx_dsd_stats *);
uint64_t lsx_dsd_stats_frames(const lsx_dsd_stats *);
void lsx_dsd_stats_json(FILE *, const lsx_dsd_stats *);
void lsx_dsd_stats_text(FILE *, const lsx_dsd_stats *);
/* Private formatting probe for the full u64 (including values > 2^53). */
void lsx_dsd_stats_uint64_json(FILE *, uint64_t);

/* This process-local observer is opt-in by the sox_ng CLI. Effect stop calls
 * record immutable snapshots; recording cannot change the audio graph. */
lsx_dsd_report_context *lsx_dsd_report_create(void);
void lsx_dsd_report_enable(lsx_dsd_report_context *);
void lsx_dsd_report_disable(void);
void lsx_dsd_report_destroy(lsx_dsd_report_context *);
void lsx_dsd_report_note_stat(const lsx_dsd_stats *);
void lsx_dsd_report_note_decode(const sox_dsd_decoder_t *,
    lsx_dsd_decode profile, lsx_dsd_level level, uint64_t graph_clips,
    double peak);
void lsx_dsd_report_note_encode(const lsx_pcmdsd *);
/* This is a private CLI JSON renderer, not an installed ABI. */
void lsx_dsd_report_json(FILE *, const lsx_dsd_report_context *,
    const lsx_dsd_plan *, const lsx_dsd_stats *const *sources, size_t nsrc,
    const sox_dsd_stream_info_t *infos, const sox_dsd_layout_t *const *layouts,
    const sox_format_t *const *source_formats,
    uint64_t output_frames, uint64_t output_clips,
    uint64_t adapter_clips, uint64_t mixing_clips,
    const char *status, const char *version);
/* Individual filter routines are exposed privately for independent test. */
typedef struct {double b[3], a[3], z[2]; unsigned order;} lsx_dsd_sos;
int lsx_dsd_butterworth5(uint32_t sample_hz, double cutoff_hz, int highpass,
    lsx_dsd_sos sections[3]);
double lsx_dsd_sos_tick(lsx_dsd_sos sections[3], double x);
#endif
