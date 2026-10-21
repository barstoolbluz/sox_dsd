/* DSF file support
 *
 * Copyright (c) 2015 Mans Rullgard <mans@mansr.com>
 *
 * This library is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or (at
 * your option) any later version.
 *
 * This library is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser
 * General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this library; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

/* File format specification available at
 * http://dsd-guide.com/sites/default/files/white-papers/DSFFileFormatSpec_E.pdf
 */

#include "sox_i.h"
#include "dsd_layout_i.h"
#include "dsd_packed.h"
#include "id3.h"

struct dsf {
	lsx_dsd_layout_state_t layout_state;
	uint64_t file_size;
	uint64_t metadata;
	uint32_t version;
	uint32_t format_id;
	uint32_t chan_type;
	uint32_t chan_num;
	uint32_t sfreq;
	uint32_t bps;
	uint64_t scount;
	uint32_t block_size;

	uint32_t block_start;
	uint32_t block_pos;
	uint32_t bit_pos;
	uint8_t *block;
	uint64_t read_samp;
	int write_failed; /* Latched payload error; never reuse a full failed block. */
	unsigned access_mode; /* 0 untouched, 1 expanded, 2 packed; reset only by seek. */
};

#define TAG(a, b, c, d) ((a) | (b) << 8 | (c) << 16 | (d) << 24)

#define DSF_TAG  TAG('D', 'S', 'D', ' ')
#define FMT_TAG  TAG('f', 'm', 't', ' ')
#define DATA_TAG TAG('d', 'a', 't', 'a')

#define HEADER_SIZE (28 + 52 + 12)
#define DSF_MAX_BLOCK_SIZE 65536U

/* Normalize MSB-first storage only when a block is loaded, not per DSD bit. */
static uint8_t const dsf_reverse_byte[256] = {
  0x00, 0x80, 0x40, 0xc0, 0x20, 0xa0, 0x60, 0xe0, 0x10, 0x90, 0x50, 0xd0, 0x30, 0xb0, 0x70, 0xf0,
  0x08, 0x88, 0x48, 0xc8, 0x28, 0xa8, 0x68, 0xe8, 0x18, 0x98, 0x58, 0xd8, 0x38, 0xb8, 0x78, 0xf8,
  0x04, 0x84, 0x44, 0xc4, 0x24, 0xa4, 0x64, 0xe4, 0x14, 0x94, 0x54, 0xd4, 0x34, 0xb4, 0x74, 0xf4,
  0x0c, 0x8c, 0x4c, 0xcc, 0x2c, 0xac, 0x6c, 0xec, 0x1c, 0x9c, 0x5c, 0xdc, 0x3c, 0xbc, 0x7c, 0xfc,
  0x02, 0x82, 0x42, 0xc2, 0x22, 0xa2, 0x62, 0xe2, 0x12, 0x92, 0x52, 0xd2, 0x32, 0xb2, 0x72, 0xf2,
  0x0a, 0x8a, 0x4a, 0xca, 0x2a, 0xaa, 0x6a, 0xea, 0x1a, 0x9a, 0x5a, 0xda, 0x3a, 0xba, 0x7a, 0xfa,
  0x06, 0x86, 0x46, 0xc6, 0x26, 0xa6, 0x66, 0xe6, 0x16, 0x96, 0x56, 0xd6, 0x36, 0xb6, 0x76, 0xf6,
  0x0e, 0x8e, 0x4e, 0xce, 0x2e, 0xae, 0x6e, 0xee, 0x1e, 0x9e, 0x5e, 0xde, 0x3e, 0xbe, 0x7e, 0xfe,
  0x01, 0x81, 0x41, 0xc1, 0x21, 0xa1, 0x61, 0xe1, 0x11, 0x91, 0x51, 0xd1, 0x31, 0xb1, 0x71, 0xf1,
  0x09, 0x89, 0x49, 0xc9, 0x29, 0xa9, 0x69, 0xe9, 0x19, 0x99, 0x59, 0xd9, 0x39, 0xb9, 0x79, 0xf9,
  0x05, 0x85, 0x45, 0xc5, 0x25, 0xa5, 0x65, 0xe5, 0x15, 0x95, 0x55, 0xd5, 0x35, 0xb5, 0x75, 0xf5,
  0x0d, 0x8d, 0x4d, 0xcd, 0x2d, 0xad, 0x6d, 0xed, 0x1d, 0x9d, 0x5d, 0xdd, 0x3d, 0xbd, 0x7d, 0xfd,
  0x03, 0x83, 0x43, 0xc3, 0x23, 0xa3, 0x63, 0xe3, 0x13, 0x93, 0x53, 0xd3, 0x33, 0xb3, 0x73, 0xf3,
  0x0b, 0x8b, 0x4b, 0xcb, 0x2b, 0xab, 0x6b, 0xeb, 0x1b, 0x9b, 0x5b, 0xdb, 0x3b, 0xbb, 0x7b, 0xfb,
  0x07, 0x87, 0x47, 0xc7, 0x27, 0xa7, 0x67, 0xe7, 0x17, 0x97, 0x57, 0xd7, 0x37, 0xb7, 0x77, 0xf7,
  0x0f, 0x8f, 0x4f, 0xcf, 0x2f, 0xaf, 0x6f, 0xef, 0x1f, 0x9f, 0x5f, 0xdf, 0x3f, 0xbf, 0x7f, 0xff
};

static int dsf_startread(sox_format_t *ft)
{
	struct dsf *dsf = ft->priv;
	uint32_t magic;
	uint64_t csize;
	uint32_t v;
	uint64_t bytes_per_block, blocks, required_bytes, data_bytes;
	uint64_t physical_size;

	if (lsx_readdw(ft, &magic) || magic != DSF_TAG) {
		lsx_fail_errno(ft, SOX_EHDR, "DSF signature not found");
		return SOX_EHDR;
	}

	if (lsx_readqw(ft, &csize) || csize != 28) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid DSD chunk size");
		return SOX_EHDR;
	}

	if (lsx_readqw(ft, &dsf->file_size) ||
	    lsx_readqw(ft, &dsf->metadata))
		return SOX_EHDR;

	if (lsx_readdw(ft, &magic) || magic != FMT_TAG) {
		lsx_fail_errno(ft, SOX_EHDR, "fmt chunk not found");
		return SOX_EHDR;
	}

	if (lsx_readqw(ft, &csize) || csize != 52) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid fmt chunk size");
		return SOX_EHDR;
	}

	if (lsx_readdw(ft, &dsf->version)   ||
	    lsx_readdw(ft, &dsf->format_id) ||
	    lsx_readdw(ft, &dsf->chan_type) ||
	    lsx_readdw(ft, &dsf->chan_num)  ||
	    lsx_readdw(ft, &dsf->sfreq)     ||
	    lsx_readdw(ft, &dsf->bps)       ||
	    lsx_readqw(ft, &dsf->scount)    ||
	    lsx_readdw(ft, &dsf->block_size))
		return SOX_EHDR;

	if (lsx_readdw(ft, &v) || v) /* reserved */
		return SOX_EHDR;

	if (lsx_readdw(ft, &magic) || magic != DATA_TAG) {
		lsx_fail_errno(ft, SOX_EHDR, "data chunk not found");
		return SOX_EHDR;
	}

	if (lsx_readqw(ft, &csize) || csize < 12) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid data chunk size");
		return SOX_EHDR;
	}
	data_bytes = csize - 12;

	if (dsf->version != 1) {
		lsx_fail_errno(ft, SOX_EHDR, "unknown format version %d",
			       dsf->version);
		return SOX_EHDR;
	}

	if (dsf->format_id != 0) {
		lsx_fail_errno(ft, SOX_EFMT, "unknown format ID %d",
			       dsf->format_id);
		return SOX_EFMT;
	}

	if (dsf->chan_num < 1 || dsf->chan_num > 6) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid channel count %d",
			       dsf->chan_num);
		return SOX_EHDR;
	}

	if (dsf->bps != 1 && dsf->bps != 8) {
		lsx_fail_errno(ft, SOX_EFMT, "unsupported DSD bit order %d",
			       dsf->bps);
		return SOX_EFMT;
	}

	/* Required padded channel blocks, not simply one block per file.
	 * A zero-frame file has no required audio block. */
	if (!dsf->block_size || dsf->block_size > DSF_MAX_BLOCK_SIZE ||
	    !dsf->sfreq || dsf->scount > UINT64_MAX / dsf->chan_num) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid DSF format dimensions");
		return SOX_EHDR;
	}
	bytes_per_block = (uint64_t)dsf->block_size * 8;
	blocks = dsf->scount / bytes_per_block +
		(dsf->scount % bytes_per_block != 0);
	if (blocks > UINT64_MAX / ((uint64_t)dsf->block_size * dsf->chan_num)) {
		lsx_fail_errno(ft, SOX_EHDR, "DSF block count overflow");
		return SOX_EHDR;
	}
	required_bytes = blocks * dsf->block_size * dsf->chan_num;
	physical_size = lsx_filelength(ft);
	if (data_bytes < required_bytes ||
	    data_bytes > UINT64_MAX - HEADER_SIZE ||
	    dsf->file_size < HEADER_SIZE + data_bytes ||
	    (dsf->metadata && dsf->metadata >= dsf->file_size) ||
	    (physical_size &&
	     (physical_size < HEADER_SIZE + data_bytes ||
	      dsf->file_size > physical_size))) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid DSF data extent");
		return SOX_EHDR;
	}
	if (dsf->block_size != 4096)
		lsx_warn("nonstandard DSF block size %u", dsf->block_size);
	if (dsf->scount) {
		dsf->block = lsx_malloc((size_t)dsf->block_size * dsf->chan_num);
		if (!dsf->block)
			return SOX_ENOMEM;
	}

	ft->data_start = lsx_tell(ft);

	if (dsf->metadata && ft->seekable) {
		if (!lsx_seeki(ft, dsf->metadata, SEEK_SET))
			lsx_id3_read_tag(ft, sox_false);
		if (lsx_seeki(ft, ft->data_start, SEEK_SET)) {
			free(dsf->block);
			dsf->block = NULL;
			return SOX_EOF;
		}
	}

	dsf->block_pos = dsf->block_size;
	dsf->block_start = 0;

	dsf->layout_state.layout = lsx_dsd_layout_from_dsf(dsf->chan_type, dsf->chan_num);
	if (!dsf->layout_state.layout) return SOX_ENOMEM;
	dsf->layout_state.layout->physical_bit_order = dsf->bps;
	ft->signal.rate = dsf->sfreq;
	ft->signal.channels = dsf->chan_num;
	ft->signal.precision = 1;
	ft->signal.length = dsf->scount * dsf->chan_num;

	ft->encoding.encoding = SOX_ENCODING_DSD;
	ft->encoding.bits_per_sample = 1;

	return SOX_SUCCESS;
}

static void dsf_read_bits(struct dsf *dsf, sox_sample_t *buf,
                          unsigned start, unsigned len)
{
	uint8_t *dsd = dsf->block + dsf->block_pos;
	unsigned i, j;

	for (i = 0; i < dsf->chan_num; i++) {
		unsigned d = dsd[i * dsf->block_size] >> start;

		for (j = 0; j < len; j++) {
			buf[i + j * dsf->chan_num] = d & 1 ?
				SOX_SAMPLE_MAX : -SOX_SAMPLE_MAX;
			d >>= 1;
		}
	}
}

static size_t dsf_read(sox_format_t *ft, sox_sample_t *buf, size_t len)
{
	struct dsf *dsf = ft->priv;
	uint64_t left = dsf->scount - dsf->read_samp;
	if (len && dsf->access_mode == 2) {
		ft->sox_errno = SOX_EINVAL; /* no change to the logical cursor */
		return 0;
	}
	if (len) dsf->access_mode = 1;
	size_t frames = min(len / dsf->chan_num, left);
	size_t done = 0;

	while (frames) {
		unsigned bits;

		if (dsf->block_pos == dsf->block_size) {
			size_t i, n = (size_t)dsf->chan_num * dsf->block_size;
			if (lsx_read_b_buf(ft, dsf->block, n) != n)
				break;
			if (dsf->bps == 8)
				for (i = 0; i < n; ++i)
					dsf->block[i] = dsf_reverse_byte[dsf->block[i]];
			dsf->block_pos = dsf->block_start;
			dsf->block_start = 0;
		}

		bits = min(frames, 8 - dsf->bit_pos);
		dsf_read_bits(dsf, buf, dsf->bit_pos, bits);
		buf += bits * dsf->chan_num;
		frames -= bits;
		done += bits;
		dsf->bit_pos += bits;
		if (dsf->bit_pos == 8) {
			dsf->bit_pos = 0;
			++dsf->block_pos;
		}
	}

	dsf->read_samp += done;
	return done * dsf->chan_num;
}

/* Borrow from the *same* normalized planar read cache as dsf_read.
 * No second file cursor: core adds frames*channels to olength exactly once. */
sox_dsd_status_t lsx_dsf_read_packed(sox_format_t *ft, size_t requested,
    sox_dsd_packed_block_t *out)
{
  struct dsf *dsf = ft->priv;
  size_t remain, frames, n, i;
  unsigned first;
  if (dsf->access_mode == 1) return SOX_DSD_BAD_ARGUMENT;
  if (!requested || !out) return SOX_DSD_BAD_ARGUMENT;
  if (!dsf->block || dsf->read_samp >= dsf->scount) return SOX_DSD_DONE;
  /* Read failure does not commit a new mode or logical position. */
  if (dsf->block_pos == dsf->block_size) {
    n = (size_t)dsf->chan_num * dsf->block_size;
    if (lsx_read_b_buf(ft, dsf->block, n) != n) {
      ft->sox_errno = SOX_EOF;
      return SOX_DSD_IO_ERROR;
    }
    if (dsf->bps == 8)
      for (i = 0; i < n; ++i) dsf->block[i] = dsf_reverse_byte[dsf->block[i]];
    dsf->block_pos = dsf->block_start;
    dsf->block_start = 0;
  }
  remain = (size_t)dsf->block_size - dsf->block_pos;
  /* Max 4096 bits per call; don't materialize or expose padding as audio. */
  frames = remain * 8 - dsf->bit_pos;
  if (frames > dsf->scount - dsf->read_samp)
    frames = (size_t)(dsf->scount - dsf->read_samp);
  if (frames > requested) frames = requested;
  if (frames > 4096) frames = 4096;
  if (!frames) return SOX_DSD_IO_ERROR;
  first = dsf->bit_pos;
  out->data = dsf->block + dsf->block_pos;
  out->bytes = (size_t)dsf->block_size * dsf->chan_num - dsf->block_pos;
  out->frames = frames;
  out->channels = dsf->chan_num;
  out->bit_offset = first;
  out->last_valid_bits = (unsigned)((first + frames - 1) % 8 + 1);
  out->channel_stride = dsf->block_size;
  out->byte_stride = 1;
  out->bit_order = SOX_DSD_PACKED_LSB; /* normalized in owned cache */
  dsf->bit_pos = (unsigned)((first + frames) % 8);
  dsf->block_pos += (unsigned)((first + frames) / 8);
  dsf->read_samp += frames;
  dsf->access_mode = 2;
  return SOX_DSD_OK;
}

static int dsf_seek(sox_format_t * ft, sox_uint64_t offset)
{
  struct dsf *dsf = ft->priv;
  uint64_t frame, byte_offset, block_num, block_stride, physical;
  unsigned block_start;
  off_t target;

  if (!dsf->chan_num || offset % dsf->chan_num)
    return SOX_EOF;
  frame = offset / dsf->chan_num;
  if (frame > dsf->scount)
    return SOX_EOF;

  /* No block exists at the end of an empty or block-aligned stream.
   * The logical EOF can be committed without moving the underlying file. */
  if (frame != dsf->scount) {
    byte_offset = frame / 8;
    block_num = byte_offset / dsf->block_size;
    block_start = byte_offset % dsf->block_size;
    block_stride = (uint64_t)dsf->chan_num * dsf->block_size;
    if (block_num > (UINT64_MAX - (uint64_t)ft->data_start) / block_stride)
      return SOX_EOF;
    physical = (uint64_t)ft->data_start + block_num * block_stride;
    target = (off_t)physical;
    if (target < 0 || (uint64_t)target != physical ||
        lsx_seeki(ft, target, SEEK_SET) != SOX_SUCCESS)
      return SOX_EOF;
  } else
    block_start = 0;

  dsf->block_pos = dsf->block_size;
  dsf->block_start = block_start;
  dsf->bit_pos = frame % 8;
  dsf->read_samp = frame;
  dsf->access_mode = 0; /* only a successful seek resets the reader mode */
  ft->sox_errno = SOX_SUCCESS;
  return SOX_SUCCESS;
}

static int dsf_stopread(sox_format_t *ft)
{
	struct dsf *dsf = ft->priv;

	free(dsf->block);

	return SOX_SUCCESS;
}

static int dsf_writeheader(sox_format_t *ft)
{
	struct dsf *dsf = ft->priv;
	uint64_t data_size = dsf->file_size ? dsf->file_size - HEADER_SIZE : 0;

	sox_bool seekable = ft->seekable;
	int failed;

	/* Header replacement must write zeros over old placeholders rather than
	 * seek over them as sparse data. Payload I/O retains its original policy. */
	ft->seekable = sox_false;
	failed = (lsx_writedw(ft, DSF_TAG) ||
	    lsx_writeqw(ft, (uint64_t)28) ||
	    lsx_writeqw(ft, dsf->file_size) ||
	    lsx_writeqw(ft, dsf->metadata) ||
	    lsx_writedw(ft, FMT_TAG) ||
	    lsx_writeqw(ft, (uint64_t)52) ||
	    lsx_writedw(ft, dsf->version) ||
	    lsx_writedw(ft, dsf->format_id) ||
	    lsx_writedw(ft, dsf->chan_type) ||
	    lsx_writedw(ft, dsf->chan_num) ||
	    lsx_writedw(ft, dsf->sfreq) ||
	    lsx_writedw(ft, dsf->bps) ||
	    /* A finalized empty stream has zero samples, not unknown length. */
	    lsx_writeqw(ft, dsf->file_size ? dsf->scount : SOX_UNKNOWN_LEN) ||
	    lsx_writedw(ft, dsf->block_size) ||
	    lsx_writedw(ft, 0) || /* reserved */
	    lsx_writedw(ft, DATA_TAG) ||
	    lsx_writeqw(ft, data_size + 12));
	ft->seekable = seekable;
	return failed ? SOX_EOF : SOX_SUCCESS;
}

static int dsf_startwrite(sox_format_t *ft)
{
	struct dsf *dsf = ft->priv;

	dsf->version = 1;
	dsf->format_id = 0;
	dsf->chan_type = dsf->layout_state.layout ?
		lsx_dsd_layout_resolve_dsf(dsf->layout_state.layout) :
		ft->signal.channels + (ft->signal.channels > 4);
	if (!dsf->chan_type || dsf->chan_type > 7) {
		lsx_fail_errno(ft, SOX_EFMT, "DSF cannot encode this channel layout");
		return SOX_EFMT;
	}
	dsf->chan_num = ft->signal.channels;
	dsf->sfreq = ft->signal.rate;
	dsf->bps = ft->encoding.bits_per_sample;
	dsf->block_size = 4096;

	dsf->block = lsx_calloc(dsf->chan_num, (size_t)dsf->block_size);
	if (!dsf->block)
		return SOX_ENOMEM;

	return dsf_writeheader(ft);
}

static int dsf_write_buf(sox_format_t *ft)
{
	struct dsf *dsf = ft->priv;

	if (dsf->block_pos == dsf->block_size) {
		size_t wlen = dsf->chan_num * dsf->block_size;
		if (lsx_write_b_buf(ft, dsf->block, wlen) < wlen) {
			dsf->write_failed = 1;
			return SOX_EOF;
		}
		dsf->block_pos = 0;
		memset(dsf->block, 0, wlen);
	}

	return SOX_SUCCESS;
}

static void dsf_write_bits(struct dsf *dsf, const sox_sample_t *buf,
			   unsigned start_bit, unsigned len)
{
	uint8_t *dsd = dsf->block + dsf->block_pos;
	unsigned i, j;

	for (i = 0; i < dsf->chan_num; i++) {
		unsigned d = dsd[i * dsf->block_size];

		for (j = 0; j < len; j++) {
			d |= (buf[i + j * dsf->chan_num] > 0) <<
				(j + start_bit);
		}

		dsd[i * dsf->block_size] = d;
	}
}

static size_t dsf_write(sox_format_t *ft, const sox_sample_t *buf, size_t len)
{
	struct dsf *dsf = ft->priv;
	unsigned nchan = dsf->chan_num;
	size_t wsamp = 0;

	if (dsf->write_failed)
		return 0;
	len /= nchan;

	if (dsf->bit_pos) {
		unsigned pre = min(len, 8 - dsf->bit_pos);

		dsf_write_bits(dsf, buf, dsf->bit_pos, pre);
		buf += pre * nchan;
		wsamp += pre;
		len -= pre;
		dsf->bit_pos += pre;

		if (dsf->bit_pos == 8) {
			dsf->block_pos++;
			dsf->bit_pos = 0;
			if (dsf_write_buf(ft))
				return 0;
		}
	}

	while (len >= 8) {
		dsf_write_bits(dsf, buf, 0, 8);
		buf += 8 * nchan;
		dsf->block_pos++;
		wsamp += 8;
		len -= 8;

		if (dsf_write_buf(ft))
			/* Even a failed flush on the last requested bit must be short.
			 * Claiming the whole block would let the caller continue writing. */
			return 0;
	}

	if (len) {
		dsf_write_bits(dsf, buf, 0, (unsigned)len);
		wsamp += len;
		dsf->bit_pos = len;
	}

	dsf->scount += wsamp;

	return wsamp * nchan;
}

static int dsf_stopwrite(sox_format_t *ft)
{
	struct dsf *dsf = ft->priv;
	int err = SOX_SUCCESS;

	if (dsf->write_failed) {
		free(dsf->block);
		dsf->block = NULL;
		return SOX_EOF;
	}
	if (dsf->bit_pos)
		dsf->block_pos++;

	if (dsf->block_pos) {
		size_t wlen = dsf->chan_num * dsf->block_size;
		if (lsx_write_b_buf(ft, dsf->block, wlen) < wlen)
			err = SOX_EOF;
	}

	free(dsf->block);

	if (err)
		return err;

	dsf->file_size = lsx_tell(ft);

	if (lsx_seeki(ft, (off_t)0, SEEK_SET)) {
		lsx_fail_errno(ft, SOX_EOF,
			       "error rewinding output to update header");
		return SOX_EOF;
	}

	return dsf_writeheader(ft);
}

LSX_FORMAT_HANDLER(dsf)
{
	static char const * const names[] = { "dsf", NULL };
	static unsigned const write_encodings[] = {
		SOX_ENCODING_DSD, 1, 0,
		0 };
	static sox_rate_t const write_rates[] = {
		64*44100, 128*44100, 256*44100,
		0 };
	static sox_format_handler_t const handler = {
		SOX_LIB_VERSION_CODE,
		"Container for DSD data",
		names, SOX_FILE_LIT_END,
		dsf_startread, dsf_read, dsf_stopread,
		dsf_startwrite, dsf_write, dsf_stopwrite,
		dsf_seek, write_encodings, write_rates,
		sizeof(struct dsf)
	};
	return &handler;
}
