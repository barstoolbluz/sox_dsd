/* DSDIFF file support
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
 * http://dsd-guide.com/sites/default/files/white-papers/DSDIFF_1.5_Spec.pdf
 */

#include "sox_i.h"
#include "dsd_layout_i.h"
#include "dsd_packed.h"

struct dsdiff {
	lsx_dsd_layout_state_t metadata;
	uint64_t data_size;
	uint8_t *buf;
	uint32_t bit_pos;
	sox_bool cluster_valid;
	int write_error;
	unsigned access_mode; /* 0 pristine, 1 expanded, 2 packed */
	uint8_t *packed_buf; /* allocated lazily, borrowed until next packed call */
};

#define ID(a, b, c, d) ((a) << 24 | (b) << 16 | (c) << 8 | (d))

/* All DFF sizes are payload sizes; physical child spans include the
 * 12-byte header and an external pad for odd payloads. */
static int dff_span(uint64_t payload, uint64_t *span)
{
	if (payload > UINT64_MAX - 12 - (payload & 1))
		return SOX_EHDR;
	*span = 12 + payload + (payload & 1);
	return SOX_SUCCESS;
}

/* Unknown metadata can be skipped on regular files or forward-only input.
 * Unlike a blind seek past EOF, the extent check verifies a real file's
 * physical bytes; pipes consume and verify each skipped byte. */
static int dff_skip(sox_format_t *ft, uint64_t bytes)
{
	if (ft->seekable) {
		off_t pos = lsx_tell(ft);
		uint64_t physical = lsx_filelength(ft);
		if (pos < 0 || bytes > INT64_MAX ||
		    bytes > (uint64_t)INT64_MAX - (uint64_t)pos ||
		    (physical && ((uint64_t)pos > physical ||
		                  bytes > physical - (uint64_t)pos)))
			return SOX_EHDR;
		return lsx_seeki(ft, (off_t)bytes, SEEK_CUR);
	}
	while (bytes) {
		uint8_t trash[4096];
		size_t count = (size_t)min(bytes, sizeof(trash));
		if (lsx_read_b_buf(ft, trash, count) != count)
			return SOX_EHDR;
		bytes -= count;
	}
	return SOX_SUCCESS;
}

/* Parse exactly the PROP/SND payload. Never interpret children as FRM8
 * siblings or accept required fields from outside PROP. */
static int dff_read_prop(sox_format_t *ft, uint64_t bytes,
	uint32_t *rate, uint16_t *channels, struct dsdiff *dff)
{
	uint32_t type, id;
	uint64_t size, span, left;
	sox_bool seen_fs = sox_false, seen_chnl = sox_false;
	sox_bool seen_cmpr = sox_false, seen_lsco = sox_false;
	uint16_t lsco = 0;

	if (bytes < 4 || lsx_readdw(ft, &type) ||
	    type != ID('S', 'N', 'D', ' '))
		return SOX_EHDR;
	left = bytes - 4;
	while (left) {
		uint64_t consumed = 0;
		if (left < 12 || lsx_readdw(ft, &id) ||
		    lsx_readqw(ft, &size) || dff_span(size, &span) ||
		    span > left)
			return SOX_EHDR;

		switch (id) {
		case ID('F', 'S', ' ', ' '):
			if (seen_fs || size != 4 || lsx_readdw(ft, rate) || !*rate)
				return SOX_EHDR;
			seen_fs = sox_true;
			consumed = 4;
			break;
		case ID('C', 'H', 'N', 'L'):
			if (seen_chnl || size < 2 || lsx_readw(ft, channels) ||
			    !*channels || size < 2 + 4 * (uint64_t)*channels)
				return SOX_EHDR;
			if (!(dff->metadata.layout = sox_dsd_layout_new(*channels)))
				return SOX_ENOMEM;
			dff->metadata.layout->origin = SOX_DSD_CONTAINER_DFF;
			dff->metadata.layout->physical_bit_order = 8;
			if (seen_lsco) {
				dff->metadata.layout->lsco_present = sox_true;
				dff->metadata.layout->lsco = lsco;
			}
			{
				unsigned ch;
				for (ch = 0; ch < *channels; ++ch) {
					unsigned char bytes[4];
					if (lsx_read_b_buf(ft, bytes, 4) != 4)
						return SOX_EHDR;
					memcpy(dff->metadata.layout->channel[ch].dff_id, bytes, 4);
					dff->metadata.layout->channel[ch].dff_id_valid = sox_true;
					id = ((uint32_t)bytes[0]<<24)|((uint32_t)bytes[1]<<16)|
					     ((uint32_t)bytes[2]<<8)|bytes[3];
					dff->metadata.layout->channel[ch].role = lsx_dsd_role_from_dff_id(id);
                    /* A single explicit centre channel is monophonic; in a
                     * multichannel vector it remains FC, not DSF mono. */
                    if (*channels==1 && dff->metadata.layout->channel[ch].role==SOX_DSD_ROLE_FC)
                        dff->metadata.layout->channel[ch].role=SOX_DSD_ROLE_MONO;
				}
			}
			seen_chnl = sox_true;
			consumed = 2 + 4 * (uint64_t)*channels;
			break;
		case ID('L', 'S', 'C', 'O'):
			if (seen_lsco || size != 2 || lsx_readw(ft, &lsco))
				return SOX_EHDR;
			seen_lsco = sox_true;
			if (dff->metadata.layout) {
				dff->metadata.layout->lsco_present = sox_true;
			dff->metadata.layout->lsco = lsco;
			}
			consumed = 2;
			break;
		case ID('C', 'M', 'P', 'R'):
			if (seen_cmpr || size < 5 || lsx_readdw(ft, &type) ||
			    type != ID('D', 'S', 'D', ' '))
				return SOX_EHDR;
			{
				uint8_t name_len;
				if (lsx_readb(ft, &name_len) || name_len > size - 5)
					return SOX_EHDR;
			}
			seen_cmpr = sox_true;
			consumed = 5;
			break;
		}
		if (dff_skip(ft, size - consumed + (size & 1)))
			return SOX_EHDR;
		left -= span;
	}
	if (seen_fs && seen_chnl && seen_cmpr &&
	    !lsx_dsd_lsco_consistent(dff->metadata.layout))
		lsx_warn("DSDIFF LSCO contradicts CHNL channel IDs; preserving CHNL audio order");
	return seen_fs && seen_chnl && seen_cmpr ? SOX_SUCCESS : SOX_EHDR;
}

static int dff_startread(sox_format_t *ft)
{
	struct dsdiff *dff = ft->priv;
	uint32_t id, type, version;
	uint64_t frame_size, chunk_size, span, remaining;
	uint32_t rate = 0;
	uint16_t channels = 0;
	sox_bool seen_version = sox_false, seen_prop = sox_false;

	if (lsx_readdw(ft, &id) || id != ID('F', 'R', 'M', '8') ||
	    lsx_readqw(ft, &frame_size) || frame_size < 4 ||
	    frame_size > UINT64_MAX - 12 ||
	    lsx_readdw(ft, &type) || type != ID('D', 'S', 'D', ' ')) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid DSDIFF FRM8 header");
		return SOX_EHDR;
	}
	remaining = frame_size - 4;
	while (remaining) {
		uint64_t consumed = 0;
		if (remaining < 12 || lsx_readdw(ft, &id) ||
		    lsx_readqw(ft, &chunk_size) ||
		    dff_span(chunk_size, &span) || span > remaining)
			break;
		remaining -= span;

		switch (id) {
		case ID('F', 'V', 'E', 'R'):
			if (seen_version || chunk_size != 4 ||
			    lsx_readdw(ft, &version) || version >> 24 != 1)
				goto invalid;
			seen_version = sox_true;
			consumed = 4;
			break;
		case ID('P', 'R', 'O', 'P'):
			if (seen_prop || dff_read_prop(ft, chunk_size, &rate, &channels, dff))
				goto invalid;
			seen_prop = sox_true;
			consumed = chunk_size;
			break;
		case ID('D', 'S', 'D', ' '):
			if (!seen_version || !seen_prop || !channels ||
			    chunk_size % channels || chunk_size > UINT64_MAX / 8)
				goto invalid;
			{
				uint64_t physical = lsx_filelength(ft);
				off_t start = lsx_tell(ft);
				/* The only tolerated missing byte is the legacy odd
				 * audio pad at the physical end of the file. */
				if (start < 0 ||
				    (physical && ((uint64_t)start > physical ||
				                  chunk_size > physical - (uint64_t)start)) ||
				    (physical && (physical < 12 || frame_size > physical - 12) &&
				     !(chunk_size & 1 && remaining == 0 &&
				       physical >= 12 && frame_size - (physical - 12) == 1)))
					goto invalid;
				if (physical && frame_size > physical - 12)
					lsx_warn("legacy DSDIFF audio chunk is missing its required external pad byte at EOF");
			}
			dff->data_size = chunk_size;
			dff->buf = lsx_malloc(channels);
			if (!dff->buf)
				return SOX_ENOMEM;
			dff->bit_pos = 0;
			dff->cluster_valid = sox_false;
			ft->data_start = lsx_tell(ft);
			ft->signal.rate = rate;
			ft->signal.channels = channels;
			ft->signal.precision = 1;
			ft->signal.length = chunk_size * 8;
			ft->encoding.encoding = SOX_ENCODING_DSD;
			ft->encoding.bits_per_sample = 1;
			return SOX_SUCCESS;
		default:
			/* Unknown top-level chunks are legal if their span fits. */
			break;
		}
		if (dff_skip(ft, chunk_size - consumed + (chunk_size & 1)))
			goto invalid;
	}
invalid:
	lsx_fail_errno(ft, SOX_EHDR, "invalid DSDIFF chunk layout");
	return SOX_EHDR;
}

/* The six-channel small-buffer reader is sensitive to link-time placement:
 * a change in an unrelated failure-message object has moved this code by
 * 256 bytes, with a repeatable throughput change on prepared hardware.
 * Page-offset alignment pins its L1-I cache set mapping independently of
 * preceding object sizes, without changing any read/bit/sample operation.
 * Only compilers supporting function alignment take this non-ABI hint. */
#if (defined(__GNUC__) || defined(__clang__)) && defined(__x86_64__)
#define LSX_DFF_READ_ALIGN __attribute__((aligned(4096)))
#else
#define LSX_DFF_READ_ALIGN
#endif

/* Retain partially consumed clusters for small reads and non-byte-aligned
 * seeks. This path is not used by the aligned eight-frame hot loop. */
static unsigned LSX_DFF_READ_ALIGN dff_read_fragment(sox_format_t *ft, sox_sample_t *buf,
                                  unsigned frames)
{
    struct dsdiff *dff = ft->priv;
    size_t nc = ft->signal.channels;
    unsigned i, j, bits = min(frames, 8 - dff->bit_pos);

    if (!dff->cluster_valid) {
        if (lsx_read_b_buf(ft, dff->buf, nc) != nc)
            return 0;
        dff->cluster_valid = sox_true;
    }
    /* Six-channel, sub-byte reads are the hot path with --buffer 32.
     * Write interleaved destination frames in address order.  The saved
     * channel-byte cluster still owns bits across partial read calls. */
    if (nc == 6) {
        sox_sample_t *dst = buf;
        for (j = 0; j < bits; ++j) {
            const unsigned mask = 0x80u >> (dff->bit_pos + j);
            for (i = 0; i < 6; ++i)
                *dst++ = (dff->buf[i] & mask) ?
                    SOX_SAMPLE_MAX : -SOX_SAMPLE_MAX;
        }
    } else {
        for (i = 0; i < nc; ++i) {
            unsigned d = dff->buf[i] << dff->bit_pos;
            for (j = 0; j < bits; ++j) {
                buf[i + j * nc] = d & 128 ?
                    SOX_SAMPLE_MAX : -SOX_SAMPLE_MAX;
                d <<= 1;
            }
        }
    }
    dff->bit_pos += bits;
    if (dff->bit_pos == 8) {
        dff->bit_pos = 0;
        dff->cluster_valid = sox_false;
    }
    return bits;
}

static size_t LSX_DFF_READ_ALIGN dff_read(sox_format_t *ft, sox_sample_t *buf, size_t len)
{
    struct dsdiff *dff = ft->priv;
    size_t nc = ft->signal.channels;
    size_t frames = len / nc, done = 0;
    if (frames && dff->access_mode == 2) {
        ft->sox_errno = SOX_EINVAL;
        return 0;
    }
    if (frames) dff->access_mode = 1;

    /* The generic reader uses length == 0 for unknown-length formats. */
    if (!dff->data_size || !frames)
        return 0;

    /* A prior small read, or a non-byte-aligned seek, may have left a
     * cluster partially consumed. Finish it before taking the fast path. */
    if (dff->cluster_valid || dff->bit_pos) {
        unsigned bits = dff_read_fragment(ft, buf, (unsigned)min(frames, 8));
        if (!bits)
            return 0;
        buf += bits * nc;
        frames -= bits;
        done += bits;
    }

    /* Aligned full clusters need no per-cluster retained-state bookkeeping.
     * The expansion order is the same as P01's eight-frame reader. */
    while (frames >= 8) {
        unsigned i, j;
        if (lsx_read_b_buf(ft, dff->buf, nc) != nc)
            return done * nc;
        for (i = 0; i < nc; ++i) {
            unsigned d = dff->buf[i];
            for (j = 0; j < 8; ++j) {
                buf[i + j * nc] = d & 128 ?
                    SOX_SAMPLE_MAX : -SOX_SAMPLE_MAX;
                d <<= 1;
            }
        }
        buf += 8 * nc;
        frames -= 8;
        done += 8;
    }

    if (frames)
        done += dff_read_fragment(ft, buf, (unsigned)frames);
    return done * nc;
}

/* DFF has channel-clustered bytes (one chronological byte per channel).
 * Use the retained partial cluster first; batch aligned clusters into a
 * bounded owned buffer. Reading ahead is not an independent logical cursor:
 * every exposed bit is committed to the single core olength once only. */
#define LSX_DFF_PACKED_CLUSTERS 1024u
sox_dsd_status_t lsx_dff_read_packed(sox_format_t *ft, size_t requested,
    sox_dsd_packed_block_t *out)
{
  struct dsdiff *dff = ft->priv;
  unsigned nc = ft->signal.channels;
  size_t frames, bytes;
  if (dff->access_mode == 1) return SOX_DSD_BAD_ARGUMENT;
  if (!requested || !out || !nc) return SOX_DSD_BAD_ARGUMENT;
  if (dff->cluster_valid || dff->bit_pos || requested < 8) {
    unsigned first = dff->bit_pos;
    if (!dff->cluster_valid) {
      if (lsx_read_b_buf(ft, dff->buf, nc) != nc) {
        ft->sox_errno = SOX_EOF;
        return SOX_DSD_IO_ERROR;
      }
      dff->cluster_valid = sox_true;
    }
    frames = min(requested, (size_t)(8 - first));
    out->data = dff->buf;
    out->bytes = nc;
    out->bit_offset = first;
    out->last_valid_bits = (unsigned)(first + frames);
    dff->bit_pos += (unsigned)frames;
    if (dff->bit_pos == 8) {
      dff->bit_pos = 0;
      dff->cluster_valid = sox_false;
    }
    out->byte_stride = nc;
  } else {
    size_t clusters = requested / 8;
    if (clusters > LSX_DFF_PACKED_CLUSTERS)
      clusters = LSX_DFF_PACKED_CLUSTERS;
    if (clusters > SIZE_MAX / nc) return SOX_DSD_BAD_ARGUMENT;
    bytes = clusters * nc;
    if (!dff->packed_buf) {
      dff->packed_buf = lsx_malloc(LSX_DFF_PACKED_CLUSTERS * (size_t)nc);
      if (!dff->packed_buf) return SOX_DSD_NUMERIC_ERROR;
    }
    if (lsx_read_b_buf(ft, dff->packed_buf, bytes) != bytes) {
      ft->sox_errno = SOX_EOF;
      return SOX_DSD_IO_ERROR;
    }
    frames = clusters * 8;
    out->data = dff->packed_buf;
    out->bytes = bytes;
    out->bit_offset = 0;
    out->last_valid_bits = 8;
    out->byte_stride = nc;
  }
  out->frames = frames;
  out->channels = nc;
  out->channel_stride = 1;
  out->bit_order = SOX_DSD_PACKED_MSB;
  dff->access_mode = 2;
  return SOX_DSD_OK;
}

static int dff_seek(sox_format_t * ft, sox_uint64_t offset)
{
  struct dsdiff *dff = ft->priv;
  uint64_t frame, byte_offset, data_offset, physical;
  off_t target;

  if (!ft->signal.channels || offset % ft->signal.channels || offset > ft->signal.length)
    return SOX_EOF;
  frame = offset / ft->signal.channels;
  byte_offset = frame / 8;
  if (byte_offset > UINT64_MAX / ft->signal.channels)
    return SOX_EOF;
  data_offset = byte_offset * ft->signal.channels;
  if (data_offset > dff->data_size ||
      data_offset > UINT64_MAX - (uint64_t)ft->data_start)
    return SOX_EOF;
  physical = (uint64_t)ft->data_start + data_offset;
  target = (off_t)physical;
  if (target < 0 || (uint64_t)target != physical ||
      lsx_seeki(ft, target, SEEK_SET) != SOX_SUCCESS)
    return SOX_EOF;

  dff->bit_pos = frame % 8;
  dff->cluster_valid = sox_false;
  dff->access_mode = 0;
  ft->sox_errno = SOX_SUCCESS;
  return SOX_SUCCESS;
}

static int dff_stopread(sox_format_t *ft)
{
	struct dsdiff *dff = ft->priv;

	free(dff->buf);
	free(dff->packed_buf);

	return SOX_SUCCESS;
}

#define DFF_MAX_CHANNELS	1000
#define DFF_CMPR_NAME		"not compressed"

/* Chunk sizes exclude their headers and external even-byte padding. */
static int dff_chunk_span(uint64_t size, uint64_t *span)
{
	if (size > UINT64_MAX - 12 - (size & 1))
		return SOX_EOF;
	*span = 12 + size + (size & 1);
	return SOX_SUCCESS;
}

static int dff_write_data_size(sox_format_t *ft, uint64_t size)
{
	sox_bool seekable = ft->seekable;
	int err;

	/* A sparse zero write would skip over the old unknown-length sentinel
	 * when finalizing an empty file. This field must be overwritten. */
	ft->seekable = sox_false;
	err = lsx_writeqw(ft, size);
	ft->seekable = seekable;
	return err;
}

static int dff_writeheader(sox_format_t *ft, sox_bool final)
{
	struct dsdiff *dff = ft->priv;
	uint64_t chnl_size = 2 + 4 * (uint64_t)ft->signal.channels;
	const sox_dsd_layout_t *layout = dff->metadata.layout;
	sox_bool lsco = layout && layout->lsco_present;
	uint64_t cmpr_size = 4 + 1 + sizeof(DFF_CMPR_NAME) - 1;
	uint64_t chnl_span, cmpr_span, prop_size, prop_span;
	uint64_t audio_span, frm8_size, frm8_span;
	uint64_t lsco_span = lsco ? 14 : 0;

	if (dff_chunk_span(chnl_size, &chnl_span) ||
	    dff_chunk_span(cmpr_size, &cmpr_span))
		return SOX_EOF;
	prop_size = 4 + 16 + chnl_span + cmpr_span + lsco_span; /* SND, FS, CHNL, LSCO?, CMPR */
	if (dff_chunk_span(prop_size, &prop_span) ||
	    dff_chunk_span(dff->data_size, &audio_span) ||
	    audio_span > UINT64_MAX - 4 - 16 - prop_span ||
	    dff_chunk_span(frm8_size = 4 + 16 + prop_span + audio_span,
			   &frm8_span)) {
		lsx_fail_errno(ft, SOX_EOF, "DSDIFF file size overflow");
		return SOX_EOF;
	}

	if (lsx_writedw(ft, ID('F', 'R', 'M', '8')) ||
	    lsx_writeqw(ft, final ? frm8_size : SOX_UNKNOWN_LEN) ||
            lsx_writedw(ft, ID('D', 'S', 'D', ' ')))
		return SOX_EOF;

	if (lsx_writedw(ft, ID('F', 'V', 'E', 'R')) ||
	    lsx_writeqw(ft, 4) ||
            lsx_writedw(ft, 0x01050000))
		return SOX_EOF;

	if (lsx_writedw(ft, ID('P', 'R', 'O', 'P')) ||
	    lsx_writeqw(ft, prop_size) ||
	    lsx_writedw(ft, ID('S', 'N', 'D', ' ')))
		return SOX_EOF;

	if (lsx_writedw(ft, ID('F', 'S', ' ', ' ')) ||
	    lsx_writeqw(ft, 4) ||
            lsx_writedw(ft, ft->signal.rate))
		return SOX_EOF;

	if (lsx_writedw(ft, ID('C', 'H', 'N', 'L')) ||
            lsx_writeqw(ft, chnl_size) ||
            lsx_writew(ft, ft->signal.channels))
		return SOX_EOF;

	if (layout) {
		unsigned i;
		for (i = 0; i < ft->signal.channels; ++i)
			if (lsx_writedw(ft, lsx_dsd_dff_id(layout,i)))
				return SOX_EOF;
	} else if (ft->signal.channels == 2) {
		if (lsx_writedw(ft, ID('S', 'L', 'F', 'T')) ||
		    lsx_writedw(ft, ID('S', 'R', 'G', 'T')))
			return SOX_EOF;
	} else {
		char ch[8];
		unsigned i;
		for (i = 0; i < ft->signal.channels; i++) {
			snprintf(ch, sizeof(ch), "C%03d", i);
			if (lsx_writedw(ft, ID(ch[0], ch[1], ch[2], ch[3])))
				return SOX_EOF;
		}
	}
	if (lsco && (lsx_writedw(ft, ID('L', 'S', 'C', 'O')) ||
	             lsx_writeqw(ft, 2) || lsx_writew(ft, layout->lsco)))
		return SOX_EOF;

	if (lsx_writedw(ft, ID('C', 'M', 'P', 'R')) ||
	    lsx_writeqw(ft, cmpr_size) ||
	    lsx_writedw(ft, ID('D', 'S', 'D', ' ')) ||
	    lsx_writeb(ft, sizeof(DFF_CMPR_NAME) - 1) ||
	    lsx_writes(ft, DFF_CMPR_NAME) ||
	    lsx_writeb(ft, 0)) /* external pad for the odd CMPR payload */
		return SOX_EOF;

	if (lsx_writedw(ft, ID('D', 'S', 'D', ' ')) ||
	    dff_write_data_size(ft, final ? dff->data_size : SOX_UNKNOWN_LEN))
		return SOX_EOF;

	return SOX_SUCCESS;
}

static int dff_startwrite(sox_format_t *ft)
{
	struct dsdiff *dff = ft->priv;
	int err;

	if (ft->signal.channels > DFF_MAX_CHANNELS) {
		lsx_fail_errno(ft, SOX_EOF, "too many channels");
		return SOX_EOF;
	}

	dff->data_size = 0;
	dff->bit_pos = 0;
	dff->write_error = SOX_SUCCESS;
	dff->buf = lsx_calloc(ft->signal.channels, 1);
	if (!dff->buf)
		return SOX_ENOMEM;

	err = dff_writeheader(ft, sox_false);
	if (err) {
		free(dff->buf);
		dff->buf = NULL;
	}
	return err;
}

static int dff_write_buf(sox_format_t *ft)
{
	struct dsdiff *dff = ft->priv;
	size_t wlen = ft->signal.channels;

	if (dff->data_size > UINT64_MAX - wlen) {
		lsx_fail_errno(ft, SOX_EOF, "DSDIFF audio size overflow");
		return dff->write_error = SOX_EOF;
	}
	if (lsx_write_b_buf(ft, dff->buf, wlen) < wlen)
		return dff->write_error = SOX_EOF;

	dff->data_size += wlen;
	memset(dff->buf, 0, wlen);

	return SOX_SUCCESS;
}

static void dff_write_bits(struct dsdiff *dff, const sox_sample_t *buf,
                           unsigned channels, unsigned start_bit, unsigned len)
{
	unsigned i, j;

	for (i = 0; i < channels; i++) {
		unsigned d = dff->buf[i];

		for (j = 0; j < len; j++) {
			d |= (buf[i + j * channels] > 0) <<
				(7 - j - start_bit);
		}

		dff->buf[i] = d;
	}
}

static size_t dff_write(sox_format_t *ft, const sox_sample_t *buf, size_t len)
{
	struct dsdiff *dff = ft->priv;
	unsigned nchan = ft->signal.channels;
	size_t wsamp = 0;

	if (dff->write_error)
		return 0;

	len /= nchan;

	if (dff->bit_pos) {
		unsigned pre = min(len, 8 - dff->bit_pos);

		dff_write_bits(dff, buf, nchan, dff->bit_pos, pre);

		dff->bit_pos += pre;
		if (dff->bit_pos == 8) {
			if (dff_write_buf(ft))
				return 0;

			dff->bit_pos = 0;
		}
		buf += pre * nchan;
		wsamp += pre;
		len -= pre;
	}

	while (len >= 8) {
		dff_write_bits(dff, buf, nchan, 0, 8);

		if (dff_write_buf(ft))
			return wsamp * nchan;

		buf += 8 * nchan;
		wsamp += 8;
		len -= 8;
	}

	if (len) {
		dff_write_bits(dff, buf, nchan, 0, len);

		dff->bit_pos = len;
		wsamp += len;
	}

	return wsamp * nchan;
}

static int dff_stopwrite(sox_format_t *ft)
{
	struct dsdiff *dff = ft->priv;
	unsigned i;
	int err = dff->write_error;

	if (!err && dff->bit_pos) {
		unsigned silence = 0x69 & (0xff >> dff->bit_pos);
		for (i = 0; i < ft->signal.channels; i++)
			dff->buf[i] |= silence;

		err = dff_write_buf(ft);
	}

	free(dff->buf);
	dff->buf = NULL;

	if (err)
		return err;

	if ((dff->data_size & 1) && lsx_writeb(ft, 0))
		return SOX_EOF;

	if (lsx_seeki(ft, 0, SEEK_SET)) {
		lsx_fail_errno(ft, SOX_EOF,
			       "error rewinding output to update header");
		return SOX_EOF;
	}

	if (dff_writeheader(ft, sox_true))
		return SOX_EOF;
	if (lsx_flush(ft)) {
		lsx_fail_errno(ft, SOX_EOF, "error flushing DSDIFF output");
		return SOX_EOF;
	}
	return SOX_SUCCESS;
}

LSX_FORMAT_HANDLER(dsdiff)
{
	static char const * const names[] = { "dff", NULL };
	static unsigned const write_encodings[] = {
		SOX_ENCODING_DSD, 1, 0,
		0
        };
	static sox_rate_t const write_rates[] = {
		64*44100, 128*44100, 256*44100,
		0 };
	static sox_format_handler_t const handler = {
		SOX_LIB_VERSION_CODE,
		"Direct Stream Digital Interchange File Format (DSDIFF)",
		names, SOX_FILE_BIG_END,
		dff_startread, dff_read, dff_stopread,
		dff_startwrite, dff_write, dff_stopwrite,
		dff_seek, write_encodings, write_rates,
		sizeof(struct dsdiff)
	};
	return &handler;
}

/*
 * The WSD format uses the same data layout as DSDIFF with a different
 * file header.
 *
 * http://1bitcons.acoust.ias.sci.waseda.ac.jp/pdf/wsd_file_format_ver1_1.pdf
 */

#define WSD_MAGIC ID('1', 'b', 'i', 't')

static int wsd_startread(sox_format_t *ft)
{
	struct dsdiff *dff = ft->priv;
	uint32_t magic;
	uint32_t res32;
	uint8_t version;
	uint8_t res8;
	uint32_t file_sz_l;
	uint32_t file_sz_h;
	uint64_t file_sz;
	uint32_t text_sp;
	uint32_t data_sp;
	uint32_t pb_tm;
	uint32_t fs;
	uint8_t ch_n;
	uint32_t ch_asn;
	uint32_t emph;

	if (lsx_readdw(ft, &magic) || magic != WSD_MAGIC) {
		lsx_fail_errno(ft, SOX_EHDR, "signature not found");
		return SOX_EHDR;
	}

	if (lsx_readdw(ft, &res32) || res32 != 0 ||
	    lsx_readb(ft, &version) ||
	    lsx_readb(ft, &res8) || res8 != 0 ||
	    lsx_readb(ft, &res8) || res8 != 0 ||
	    lsx_readb(ft, &res8) || res8 != 0 ||
	    lsx_readdw(ft, &file_sz_l) ||
	    lsx_readdw(ft, &file_sz_h) ||
	    lsx_readdw(ft, &text_sp) ||
	    lsx_readdw(ft, &data_sp) ||
	    lsx_readdw(ft, &res32) || res32 != 0) {
		lsx_fail_errno(ft, SOX_EHDR, "error reading header");
		return SOX_EHDR;
	}

	if (version != 0x10 && version != 0x11) {
		lsx_fail_errno(ft, SOX_EHDR, "unknown format version 0x%02x",
			       version);
		return SOX_EHDR;
	}

	if (text_sp != 0x80 || data_sp != 0x800) {
		lsx_fail_errno(ft, SOX_EHDR, "incorrect data offset");
		return SOX_EHDR;
	}

	file_sz = (uint64_t)file_sz_h << 32 | file_sz_l;

	if (file_sz < data_sp) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid file size");
		return SOX_EHDR;
	}

	if (lsx_readdw(ft, &pb_tm) ||
	    lsx_readdw(ft, &fs) ||
	    lsx_readdw(ft, &res32) || res32 != 0 ||
	    lsx_readb(ft, &ch_n) ||
	    lsx_readb(ft, &res8) || res8 != 0 ||
	    lsx_readb(ft, &res8) || res8 != 0 ||
	    lsx_readb(ft, &res8) || res8 != 0 ||
	    lsx_readdw(ft, &ch_asn) ||
	    lsx_readdw(ft, &res32) || res32 != 0 ||
	    lsx_readdw(ft, &res32) || res32 != 0 ||
	    lsx_readdw(ft, &res32) || res32 != 0 ||
	    lsx_readdw(ft, &emph) ||
	    lsx_readdw(ft, &res32) || res32 != 0) {
		lsx_fail_errno(ft, SOX_EHDR, "error reading header");
		return SOX_EHDR;
	}

	if (emph) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid emphasis value");
		return SOX_EHDR;
	}

	if (!ch_n || !fs || (file_sz - data_sp) % ch_n ||
	    file_sz - data_sp > UINT64_MAX / 8 ||
	    (lsx_filelength(ft) && file_sz > lsx_filelength(ft))) {
		lsx_fail_errno(ft, SOX_EHDR, "invalid WSD audio extent");
		return SOX_EHDR;
	}
	{
		off_t pos = lsx_tell(ft);
		if (pos < 0 || (uint64_t)pos > data_sp ||
		    dff_skip(ft, data_sp - (uint64_t)pos))
			return SOX_EOF;
	}

	dff->buf = lsx_malloc(ch_n);
	if (!dff->buf)
		return SOX_ENOMEM;

	dff->data_size = file_sz - data_sp;
	dff->bit_pos = 0;
	dff->cluster_valid = sox_false;
	ft->data_start = data_sp;

	dff->metadata.layout = sox_dsd_layout_new(ch_n);
	if (!dff->metadata.layout) return SOX_ENOMEM;
	dff->metadata.layout->origin = SOX_DSD_CONTAINER_WSD;
	dff->metadata.layout->wsd_present = sox_true;
	dff->metadata.layout->wsd_assignment = ch_asn;
	ft->signal.rate = fs;
	ft->signal.channels = ch_n;
	ft->signal.precision = 1;
	ft->signal.length = (file_sz - data_sp) * 8;

	ft->encoding.encoding = SOX_ENCODING_DSD;
	ft->encoding.bits_per_sample = 1;

	return SOX_SUCCESS;
}

LSX_FORMAT_HANDLER(wsd)
{
	static char const * const names[] = { "wsd", NULL };
	static sox_format_handler_t const handler = {
		SOX_LIB_VERSION_CODE,
		"Wideband Single-bit Data (WSD)",
		names, SOX_FILE_BIG_END,
		wsd_startread, dff_read, dff_stopread,
		NULL, NULL, NULL,
		dff_seek, NULL, NULL,
		sizeof(struct dsdiff)
	};
	return &handler;
}
