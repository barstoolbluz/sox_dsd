/* libSoX Opus-in-Ogg sound format handler
 * Copyright (C) 2013 John Stumpo <stump@jstump.com>
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation version 2.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
 * Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * Largely based on vorbis.c:
 * libSoX Ogg Vorbis sound format handler
 * Copyright 2001, Stan Seibert <indigo@aztec.asu.edu>
 *
 * Portions from oggenc, (c) Michael Smith <msmith@labyrinth.net.au>,
 * ogg123, (c) Kenneth Arnold <kcarnold@yahoo.com>, and
 * libvorbisfile (c) Xiphophorus Company
 *
 * May 9, 2001 - Stan Seibert (indigo@aztec.asu.edu)
 * Ogg Vorbis handler initially written.
 *
 * July 5, 1991 - Skeleton file
 * Copyright 1991 Lance Norskog And Sundry Contributors
 * This source code is freely redistributable and may be used for
 * any purpose.  This copyright notice must be maintained.
 * Lance Norskog And Sundry Contributors are not responsible for
 * the consequences of using this software.
 */

#include "sox_i.h"

#include <opus/opusfile.h>

#if HAVE_OPUSENC
# include <opusenc.h>
#endif

#define DEF_BUF_LEN 4096

#define BUF_ERROR -1
#define BUF_EOF  0
#define BUF_DATA 1

typedef struct {
  /* Decoding data */
  OggOpusFile *of;
  char *buf;
  size_t buf_len;
  size_t start;
  size_t end;     /* Unsent data samples in buf[start] through buf[end-1] */
  int current_section;
  int eof;
#if HAVE_OPUSENC
  OggOpusEnc *ope;	     /* OggOpus encoder state */
  OggOpusComments *oe_comments;
  float *oe_input;           /* Somewhere to convert samples to floats */
  size_t oe_input_len;       /* Number of floats allocated to oe_input */
#endif
} priv_t;

/******** Callback functions used in op_open_callbacks ************/

static int callback_read(void* ft_data, unsigned char* ptr, int nbytes)
{
  sox_format_t* ft = (sox_format_t*)ft_data;
  return lsx_readbuf(ft, ptr, (size_t)nbytes);
}

static int callback_seek(void* ft_data, opus_int64 off, int whence)
{
  sox_format_t* ft = (sox_format_t*)ft_data;
  int ret = ft->seekable ? lsx_seeki(ft, (off_t)off, whence) : -1;

  if (ret == EBADF)
    ret = -1;
  return ret;
}

static int callback_close(void* ft_data UNUSED)
{
  /* Do nothing so sox can close the file for us */
  return 0;
}

static opus_int64 callback_tell(void* ft_data)
{
  sox_format_t* ft = (sox_format_t*)ft_data;
  return lsx_tell(ft);
}

/********************* End callbacks *****************************/


/*
 * Do anything required before you start reading samples.
 * Read file header.
 *      Find out sampling rate,
 *      size and encoding of samples,
 *      mono/stereo/quad.
 */
static int startread(sox_format_t * ft)
{
  priv_t * vb = (priv_t *) ft->priv;
  const OpusTags *ot;
  int i;

  OpusFileCallbacks callbacks = {
    callback_read,
    callback_seek,
    callback_tell,
    callback_close
  };

  /* Init the decoder */
  vb->of = op_open_callbacks(ft, &callbacks, NULL, (size_t) 0, NULL);
  if (vb->of == NULL) {
    lsx_fail_errno(ft, SOX_EHDR, "input is not an Ogg Opus audio stream");
    return (SOX_EOF);
  }

  /* Get info about the Opus stream */
  ot = op_tags(vb->of, -1);

  /* Record audio info */
  ft->signal.rate = 48000;  /* libopusfile always uses 48 kHz */
  ft->encoding.encoding = SOX_ENCODING_OPUS;
  ft->signal.channels = op_channel_count(vb->of, -1);

  /* op_pcm_total doesn't work on non-seekable files so
   * skip that step in that case.  Also, it reports
   * "frame"-ish results so we must * channels.
   */
  if (ft->seekable)
    ft->signal.length = op_pcm_total(vb->of, -1) * ft->signal.channels;

  /* Record comments */
  for (i = 0; i < ot->comments; i++)
    sox_append_comment(&ft->oob.comments, ot->user_comments[i]);

  /* Setup buffer */
  vb->buf_len = DEF_BUF_LEN;
  vb->buf_len -= vb->buf_len % (ft->signal.channels*2); /* 2 bytes per sample */
  lsx_vcalloc(vb->buf, vb->buf_len);
  vb->start = vb->end = 0;

  /* Fill in other info */
  vb->eof = 0;
  vb->current_section = -1;

  return (SOX_SUCCESS);
}


/* Refill the buffer with samples.  Returns BUF_EOF if the end of the
 * Opus data was reached while the buffer was being filled,
 * BUF_ERROR is something bad happens, and BUF_DATA otherwise */
static int refill_buffer(sox_format_t * ft)
{
  priv_t * vb = (priv_t *) ft->priv;
  int num_read;

  if (vb->start == vb->end)     /* Samples all played */
    vb->start = vb->end = 0;

  while (vb->end < vb->buf_len) {
    num_read = op_read(vb->of, (opus_int16*) (vb->buf + vb->end),
        (int) ((vb->buf_len - vb->end) / sizeof(opus_int16)),
        &vb->current_section);
    if (num_read == 0)
      return (BUF_EOF);
    else if (num_read == OP_HOLE)
      lsx_warn("hole in stream; probably harmless");
    else if (num_read < 0)
      return (BUF_ERROR);
    else
      vb->end += num_read * sizeof(opus_int16) * ft->signal.channels;
  }
  return (BUF_DATA);
}


/*
 * Read up to len samples from file.
 * Convert to signed longs.
 * Place in buf[].
 * Return number of samples read.
 */

static size_t read_samples(sox_format_t * ft, sox_sample_t * buf, size_t len)
{
  priv_t * vb = (priv_t *) ft->priv;
  size_t i;
  int ret;
  sox_sample_t l;


  for (i = 0; i < len; i++) {
    if (vb->start == vb->end) {
      if (vb->eof)
        break;
      ret = refill_buffer(ft);
      if (ret == BUF_EOF || ret == BUF_ERROR) {
        vb->eof = 1;
        if (vb->end == 0)
          break;
      }
    }

    l = (vb->buf[vb->start + 1] << 24)
        | (0xffffff & (vb->buf[vb->start] << 16));
    *(buf + i) = l;
    vb->start += 2;
  }
  return i;
}

/*
 * Do anything required when you stop reading samples.
 * Don't close input file!
 */
static int stopread(sox_format_t * ft)
{
  priv_t * vb = (priv_t *) ft->priv;

  free(vb->buf);
  op_free(vb->of);

  return (SOX_SUCCESS);
}

#if HAVE_OPUSENC

/* Opus encoding */

static int startwrite(sox_format_t * ft)
{
  priv_t * vb = (priv_t *) ft->priv;
  char **cp;
  int error;

  /* Make an empty comment structure */
  vb->oe_comments = ope_comments_create();

  /* Copy comments */
  for (cp = (char **) ft->oob.comments; *cp; cp++) {
    /* Opus only handles NAME=VALUE pairs, which excludes the default
     * "Processed by SoX" comment */
    if (strchr(*cp, '=')) {
      int retval = ope_comments_add_string(vb->oe_comments, *cp);
      if (retval < 0)
        lsx_warn("can't copy comment `%s': %s", *cp, ope_strerror(retval));
    }
  }

  /* SoX sample rate is a double but opus_encoder_create() takes an int */
  vb->ope = ope_encoder_create_pull(vb->oe_comments,
                               (opus_int32)ft->signal.rate,
                               (int)ft->signal.channels,
                               /* Mapping family (0 for mono/stereo,
                                *                 1 for surround) */
                               (int)ft->signal.channels > 2,
                               &error);
  if (!vb->ope) {
      lsx_fail("encoder creation failed");
      return SOX_EOF;
  }

  if (ft->encoding.compression != HUGE_VAL) {
    /* Like MP3, positive values are CBR in kbps and negative ones
     * VBR similarly. These correspond to opusenc's --vbr and --hard-cbr;
     * for --cvbr (constrained VBR), --music and --speech, use opusenc.
     * A fractional part, like MP3, gives the --comp option for computational
     * complexity 0-10 where 0 is fast and poor and 10 (the default) is slow
     * and good. Whole numbers default to 10, like opusenc, so quality 0 can
     * be given with 64.01 (anything less that .05)
     */
    double bitrate_kbps = fabs(trunc(ft->encoding.compression));
    double dquality = fabs(ft->encoding.compression) - bitrate_kbps;
    opus_int32 quality;
    int retval;

    if (bitrate_kbps < 6 || bitrate_kbps > 256) {
      lsx_fail("invalid bitrate per channel of %gkbps; use 6 to 256",
               bitrate_kbps);
      return SOX_EOF;
    }
    if (dquality == 0) quality = 10;
    else quality =  round(dquality * 10);
    lsx_report("encoding at %gkbps %cBR with quality %d",
               bitrate_kbps, ft->encoding.compression >= 0 ? 'C' : 'V',
               quality);
    retval = ope_encoder_ctl(vb->ope,
                          OPUS_SET_BITRATE((opus_int32)(bitrate_kbps * 1000)));
    if (retval != OPUS_OK) {
      lsx_fail("failed to set bitrate of %gkbps: %s", bitrate_kbps,
               ope_strerror(retval));
      return SOX_EOF;
    }
    retval = ope_encoder_ctl(vb->ope, OPUS_SET_COMPLEXITY(quality));
    if (retval != OPUS_OK) {
      lsx_fail("failed to set quality of %d: %s", quality,
               ope_strerror(retval));
      return SOX_EOF;
    }
    if (ft->encoding.compression >= 0) {
      retval = ope_encoder_ctl(vb->ope, OPUS_SET_VBR(0));
      if (retval != OPUS_OK) {
        lsx_fail("failed to set CBR mode: %s",
                 ope_strerror(retval));
        return SOX_EOF;
      }
    }
  }

  /* Force allocation at first use */
  vb->oe_input = NULL;
  vb->oe_input_len = 0;

  return SOX_SUCCESS;
}

static size_t write_samples(sox_format_t * ft, const sox_sample_t *buf, size_t len)
{
  priv_t * vb = (priv_t *) ft->priv;

  /* There is also ope_encode() for 16-bit samples and from
   * opusenc-1.6 ope_encode24() for 32-bit samples;
   * ope_get_abi_version() may help with this, or check for
   * ope_encode24() in configure.ac.
   */

  /* Make sure the float buffer is big enough */
  if (len > vb->oe_input_len) {
    lsx_revalloc(vb->oe_input, len);
    vb->oe_input_len = len;
  }

  /* Convert samples to floats */
  {
    const sox_sample_t *sp = buf;
    float *fp = vb->oe_input;
    size_t i;
    SOX_SAMPLE_LOCALS;

    for (i=0; i < len; i++) {
      *fp++ = SOX_SAMPLE_TO_FLOAT_32BIT_NOCLIPS(*sp);
      sp++;
    }
  }

  /* Send them to the encoder */
  {
    int retval = ope_encoder_write_float(vb->ope, vb->oe_input,
                                         len / ft->signal.channels);
    if (retval < 0) {
      lsx_fail(ope_strerror(retval));
      return 0;
    }
  }

  /* Collect any output the encoder has ready for us */
  {
    unsigned char *page;
    opus_int32 size;
    while (ope_encoder_get_page(vb->ope, &page, &size, 0)) {
      if (lsx_writebuf(ft, page, (size_t)size) != (size_t)size) {
        lsx_fail("error writing output file");
        return 0;
      }
    }
  }

  /* We always consume all the input data */
  return len;
}

static int stopwrite(sox_format_t UNUSED * ft)
{
  priv_t * vb = (priv_t *) ft->priv;
  unsigned char *page;
  opus_int32 size;

  ope_encoder_drain(vb->ope);

  while (ope_encoder_get_page(vb->ope, &page, &size, 1)) {
    if (lsx_writebuf(ft, page, (size_t)size) != (size_t)size) {
      lsx_fail("error writing output file");
      return 0;
    }
  }

  ope_comments_destroy(vb->oe_comments);
  ope_encoder_destroy(vb->ope);
  free(vb->oe_input);

  return SOX_SUCCESS;
}

#endif /* HAVE_OPUSENC */

static int seek(sox_format_t * ft, sox_uint64_t offset)
{
  priv_t * vb = (priv_t *) ft->priv;

  sox_uint64_t frame = offset / ft->signal.channels;
  if (frame > INT64_MAX || op_pcm_seek(vb->of, (opus_int64)frame))
    return SOX_EOF;

  /* op_pcm_seek moved the decoder, so discard any samples and EOF state
   * retained from its previous position.  A failed seek leaves both intact. */
  vb->start = vb->end = 0;
  vb->eof = 0;
  return SOX_SUCCESS;
}

LSX_FORMAT_HANDLER(opus)
{
  static const char *const names[] = {"opus", NULL};
  static const unsigned encodings[] = {
    SOX_ENCODING_OPUS, 0, 0,
    0};
  static sox_rate_t  const rates[] = {8000, 12000, 16000, 24000, 48000, 0};
  static sox_format_handler_t handler = {SOX_LIB_VERSION_CODE,
    "Xiph.org's Opus lossy compression", names, 0,
    startread, read_samples, stopread,
#if HAVE_OPUSENC
    startwrite, write_samples, stopwrite,
#else
    NULL, NULL, NULL,
#endif
    seek, encodings, rates, sizeof(priv_t)
  };
  return &handler;
}
