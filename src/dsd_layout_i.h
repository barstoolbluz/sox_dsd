/* Private DSD layout representation.  Handler private structures supporting
 * layouts start with lsx_dsd_layout_state_t; never cast unrelated handlers. */
#ifndef LSX_DSD_LAYOUT_I_H
#define LSX_DSD_LAYOUT_I_H
#include "sox_dsd.h"

typedef struct { sox_dsd_layout_t *layout; } lsx_dsd_layout_state_t;
struct sox_dsd_layout {
  unsigned channels;
  sox_dsd_container_t origin;
  unsigned dsf_type;
  unsigned physical_bit_order;
  sox_bool lsco_present;
  unsigned lsco;
  sox_bool wsd_present;
  uint32_t wsd_assignment;
  sox_bool wav_mask_nonzero; /* A supplied, but unrepresentable WAV mask is not absent. */
  sox_dsd_channel_info_t channel[];
};

lsx_dsd_layout_state_t *lsx_dsd_layout_state(const sox_format_t *ft);
sox_dsd_layout_t *lsx_dsd_layout_from_dsf(unsigned type, unsigned count);
sox_dsd_layout_t *lsx_dsd_layout_from_wav(unsigned count, uint32_t mask);
unsigned lsx_dsd_layout_resolve_dsf(const sox_dsd_layout_t *layout);
uint32_t lsx_dsd_dff_id(const sox_dsd_layout_t *layout, unsigned index);
sox_dsd_role_t lsx_dsd_role_from_dff_id(uint32_t id);
sox_bool lsx_dsd_lsco_consistent(const sox_dsd_layout_t *layout);
sox_bool lsx_dsd_layout_has_identity(const sox_dsd_layout_t *layout);
#endif
