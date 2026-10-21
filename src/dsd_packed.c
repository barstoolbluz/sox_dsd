/* P16: optional packed native DSD access, separate from sox_read.
 * Dispatch by the actual handler function, not file extensions or metadata.
 * Ownership, mode and native cache state remain entirely format-private. */
#include "sox_i.h"
#include "dsd_packed.h"
#include <stdint.h>
#include <string.h>

sox_format_handler_t const *lsx_dsf_format_fn(void);
sox_format_handler_t const *lsx_dsdiff_format_fn(void);

void sox_dsd_packed_block_init(sox_dsd_packed_block_t *b)
{
  if (!b) return;
  memset(b, 0, sizeof(*b));
  b->size = sizeof(*b);
  b->version = 1;
}

/* Validate the final addressed byte of every channel, independent of layout.
 * Frame and stride bounds are checked before addition or multiplication. */
int lsx_dsd_packed_validate(const sox_dsd_packed_block_t *b)
{
  size_t last_byte, max_channel, byte_offset, last_bit;
  if (!b || b->size < sizeof(*b) || b->version != 1 || !b->data ||
      !b->bytes || !b->frames || !b->channels || !b->byte_stride ||
      (b->channels > 1 && !b->channel_stride) ||
      b->bit_offset >= 8 || b->last_valid_bits < 1 ||
      b->last_valid_bits > 8 ||
      (b->bit_order != SOX_DSD_PACKED_LSB &&
       b->bit_order != SOX_DSD_PACKED_MSB) ||
      b->frames > SIZE_MAX - b->bit_offset)
    return 0;
  last_bit = b->bit_offset + (b->frames - 1);
  if (b->last_valid_bits != last_bit % 8 + 1) return 0;
  last_byte = last_bit / 8;
  if (last_byte > SIZE_MAX / b->byte_stride ||
      b->channels - 1 > SIZE_MAX / (b->channel_stride ? b->channel_stride : 1))
    return 0;
  max_channel = (b->channels - 1) * b->channel_stride;
  byte_offset = last_byte * b->byte_stride;
  return max_channel < b->bytes && byte_offset < b->bytes - max_channel;
}

static int kind(const sox_format_t *ft)
{
  if (!ft || ft->mode != 'r' || ft->encoding.encoding != SOX_ENCODING_DSD)
    return 0;
  if (ft->handler.read == lsx_dsf_format_fn()->read) return 1;
  if (ft->handler.read == lsx_dsdiff_format_fn()->read &&
      ft->handler.startread == lsx_dsdiff_format_fn()->startread) return 2;
  return 0;
}

sox_bool sox_dsd_packed_supported(const sox_format_t *ft)
{
  return kind(ft) != 0 ? sox_true : sox_false;
}

sox_dsd_status_t sox_dsd_read_packed(sox_format_t *ft,
    size_t max_frames, sox_dsd_packed_block_t *b)
{
  sox_dsd_status_t st;
  sox_dsd_packed_block_t tmp;
  size_t rem;
  int k;
  if (!b || b->size < sizeof(*b) || b->version != 1 || !ft)
    return SOX_DSD_BAD_ARGUMENT;
  /* Keep the passed record well-formed even on an error. */
  sox_dsd_packed_block_init(b);
  k = kind(ft);
  if (!k) return SOX_DSD_UNSUPPORTED;
  if (!max_frames) return SOX_DSD_NEED_OUTPUT;
  if (!ft->signal.channels ||
      ft->signal.length == SOX_UNSPEC ||
      ft->signal.length == SOX_UNKNOWN_LEN ||
      ft->olength > ft->signal.length ||
      ft->olength % ft->signal.channels)
    return SOX_DSD_BAD_ARGUMENT;
  rem = (size_t)min((uint64_t)SIZE_MAX,
      (ft->signal.length - ft->olength) / ft->signal.channels);
  if (!rem) return SOX_DSD_DONE;
  if (max_frames > rem) max_frames = rem;
  sox_dsd_packed_block_init(&tmp);
  st = k == 1 ? lsx_dsf_read_packed(ft,max_frames,&tmp) :
      lsx_dff_read_packed(ft,max_frames,&tmp);
  if (st != SOX_DSD_OK) return st;
  if (!lsx_dsd_packed_validate(&tmp) || tmp.frames > max_frames ||
      tmp.channels != ft->signal.channels ||
      tmp.frames > (UINT64_MAX - ft->olength) / tmp.channels)
    return SOX_DSD_IO_ERROR;
  ft->olength += tmp.frames * tmp.channels;
  *b = tmp;
  return SOX_DSD_OK;
}
