/* Narrow, in-tree channel-identity queries; neither adds public ABI. */
#ifndef LSX_DSD_LAYOUT_QUERY_H
#define LSX_DSD_LAYOUT_QUERY_H
#include "sox_dsd.h"
/* Indexes are zero-based source channels. */
sox_bool lsx_remix_pure_map(sox_effect_t *effp, unsigned input_channels,
    unsigned *source_indexes, unsigned capacity);
/* True only for a WAV layout with no speaker assignment at all.  Do not
 * confuse a nonzero but unrepresentable extensible mask with an absent mask. */
sox_bool lsx_dsd_layout_wav_without_assignment(const sox_dsd_layout_t *layout);
#endif
