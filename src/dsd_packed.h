/* P16 private native-reader dispatch and checked packed addressing. */
#ifndef LSX_DSD_PACKED_H
#define LSX_DSD_PACKED_H
#include "sox_dsd.h"

/* Internal reader entry points. The handlers own buffers and access mode. */
sox_dsd_status_t lsx_dsf_read_packed(sox_format_t *, size_t,
    sox_dsd_packed_block_t *);
sox_dsd_status_t lsx_dff_read_packed(sox_format_t *, size_t,
    sox_dsd_packed_block_t *);

/* True if every descriptor address is within [data, data + bytes).
 * Includes all channels, first/last bit and arithmetic overflow checks. */
int lsx_dsd_packed_validate(const sox_dsd_packed_block_t *);

/* Caller must validate descriptor and range before using this helper. */
static inline unsigned lsx_dsd_packed_bit(const sox_dsd_packed_block_t *b,
    size_t frame, unsigned channel)
{
  size_t bit = (size_t)b->bit_offset + frame;
  uint8_t byte = b->data[channel * b->channel_stride +
      (bit / 8) * b->byte_stride];
  return (byte >> (b->bit_order == SOX_DSD_PACKED_MSB ?
      7 - (bit & 7) : (bit & 7))) & 1u;
}
#endif
