/* Phase 05B: checked count and EOF wrapper for the qualified public decoder.
 * Keep all reconstruction/SRC arithmetic and channel synchronization in
 * sox_dsd_decoder_*; do not alter sample phase or finite tail accounting. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "dsd_f64_decode.h"
#include "dsd.h"
#include <stdint.h>
#include <string.h>

static sox_dsd_status_t latch(lsx_dsd_f64_decode *d,sox_dsd_status_t st)
{
  if (d && !d->error) d->error=st;
  return d ? d->error : st;
}

sox_dsd_status_t lsx_dsd_f64_decode_init(lsx_dsd_f64_decode *d,
    const sox_dsd_decode_options_t *o,int known,uint64_t frames)
{
  if (!d || !o) return SOX_DSD_BAD_ARGUMENT;
  memset(d,0,sizeof(*d));
  d->length_known=!!known;
  if (known) {
    d->native_expected=frames;
    if (!lsx_dsd_count_convert(frames,o->native_hz,o->output_hz,
          &d->pcm_expected)) return latch(d,SOX_DSD_NUMERIC_ERROR);
  }
  return latch(d,sox_dsd_decoder_create(o,&d->api))==SOX_DSD_OK ?
      SOX_DSD_OK : d->error;
}

static sox_dsd_status_t advance(lsx_dsd_f64_decode *d,
    size_t requested,size_t consumed,size_t produced,sox_dsd_status_t st)
{
  if (st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT)
    return latch(d,st);
  if (consumed>requested || (requested && !consumed && !produced) ||
      (uint64_t)consumed>UINT64_MAX-d->native_seen ||
      (uint64_t)produced>UINT64_MAX-d->pcm_seen ||
      (d->length_known &&
       ((uint64_t)consumed>d->native_expected-d->native_seen ||
        (uint64_t)produced>d->pcm_expected-d->pcm_seen)))
    return latch(d,SOX_DSD_NUMERIC_ERROR);
  d->native_seen+=consumed;
  d->pcm_seen+=produced;
  return st;
}

sox_dsd_status_t lsx_dsd_f64_decode_process(lsx_dsd_f64_decode *d,
    const sox_sample_t *in,size_t *nf,double *pcm,size_t *pf)
{
  size_t requested,capacity;
  sox_dsd_status_t st;
  if (!d || !nf || !pf) return SOX_DSD_BAD_ARGUMENT;
  if (d->error) return d->error;
  if (d->finishing) return latch(d,SOX_DSD_BAD_ARGUMENT);
  requested=*nf;capacity=*pf;
  if (d->length_known && requested>d->native_expected-d->native_seen)
    return latch(d,SOX_DSD_NUMERIC_ERROR);
  st=sox_dsd_decoder_process(d->api,in,nf,pcm,pf);
  if (*pf>capacity) return latch(d,SOX_DSD_NUMERIC_ERROR);
  return advance(d,requested,*nf,*pf,st);
}

sox_dsd_status_t lsx_dsd_f64_decode_process_packed(lsx_dsd_f64_decode *d,
    const sox_dsd_packed_block_t *in,size_t start,
    size_t *nf,double *pcm,size_t *pf)
{
  size_t requested,capacity;
  sox_dsd_status_t st;
  if (!d || !nf || !pf) return SOX_DSD_BAD_ARGUMENT;
  if (d->error) return d->error;
  if (d->finishing) return latch(d,SOX_DSD_BAD_ARGUMENT);
  requested=*nf;capacity=*pf;
  if (d->length_known && requested>d->native_expected-d->native_seen)
    return latch(d,SOX_DSD_NUMERIC_ERROR);
  st=sox_dsd_decoder_process_packed(d->api,in,start,nf,pcm,pf);
  if (*pf>capacity) return latch(d,SOX_DSD_NUMERIC_ERROR);
  return advance(d,requested,*nf,*pf,st);
}

sox_dsd_status_t lsx_dsd_f64_decode_finish(lsx_dsd_f64_decode *d,
    double *pcm,size_t *pf)
{
  size_t capacity;
  sox_dsd_status_t st;
  if (!d || !pf) return SOX_DSD_BAD_ARGUMENT;
  if (d->error) return d->error;
  if (d->finished) {*pf=0;return SOX_DSD_DONE;}
  if (d->length_known && d->native_seen!=d->native_expected)
    return latch(d,SOX_DSD_IO_ERROR);
  capacity=*pf;
  d->finishing=1;
  st=sox_dsd_decoder_finish(d->api,pcm,pf);
  if ((st!=SOX_DSD_DONE && st!=SOX_DSD_NEED_OUTPUT) ||
      *pf>capacity || (uint64_t)*pf>UINT64_MAX-d->pcm_seen ||
      (d->length_known && (uint64_t)*pf>d->pcm_expected-d->pcm_seen))
    return latch(d,st==SOX_DSD_NEED_OUTPUT || st==SOX_DSD_DONE?
        SOX_DSD_NUMERIC_ERROR:st);
  d->pcm_seen+=*pf;
  if (st==SOX_DSD_DONE) {
    if (d->length_known && d->pcm_seen!=d->pcm_expected)
      return latch(d,SOX_DSD_NUMERIC_ERROR);
    d->finished=1;
  } else if (!*pf) return latch(d,SOX_DSD_NUMERIC_ERROR);
  return st;
}

void lsx_dsd_f64_decode_destroy(lsx_dsd_f64_decode *d)
{
  if (!d) return;
  sox_dsd_decoder_destroy(d->api);
  memset(d,0,sizeof(*d));
}
