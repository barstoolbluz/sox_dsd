/* Phase 05A: bounded, private, unchanged-rate/channel binary64 coordinator.
 * The format adapters own container parsing and I/O. This stream has no
 * knowledge of argv, signal handlers, headers, or the legacy int32 carrier. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "dsd_f64.h"
#include "pcmdsd.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

static pcm_f64_progress failure(lsx_dsd_f64_stream *s, pcm_f64_status code)
{
  pcm_f64_progress p = {0,0,code};
  if (s) p.status=pcm_f64_latch(&s->failure,code);
  return p;
}

pcm_f64_status lsx_dsd_f64_init(lsx_dsd_f64_stream *s,
    const pcm_f64_format *f, const double *gains, size_t n,
    const unsigned *map)
{
  unsigned i;
  size_t k;
  pcm_f64_status rc;
  if (!s || !f || (n && !gains) || n>SIZE_MAX/sizeof(double))
    return PCM_F64_ARGUMENT;
  memset(s,0,sizeof(*s));
  s->failure.failed=PCM_F64_OK;
  rc=pcm_f64_format_init(&s->format,f->rate_hz,f->channels,
      f->length_known,f->total_frames);
  if (rc!=PCM_F64_OK) return rc;
  for (i=0;i<f->channels;i++) {
    unsigned from=map?map[i]:i;
    unsigned j;
    if (from>=f->channels) return PCM_F64_ARGUMENT;
    for (j=0;j<i;j++) if (s->role_map[j]==from) return PCM_F64_ARGUMENT;
    s->role_map[i]=from;
    if (from!=i) s->transformed=s->permuted=true;
  }
  /* Every source gain stays in order; no factor multiplication/fusion. */
  if (n) {
    s->gains=malloc(n*sizeof(double));
    if (!s->gains) return PCM_F64_IO;
    s->gain_count=n;
    for (k=0;k<n;k++) {
      pcm_f64_word_class kind;
      if (pcm_f64_classify(&gains[k],&kind)!=PCM_F64_OK ||
          kind!=PCM_F64_WORD_FINITE) {
        lsx_dsd_f64_destroy(s);
        return PCM_F64_NUMERIC;
      }
      s->gains[k]=gains[k];
      if (gains[k]!=1.) s->transformed=true;
    }
  }
  /* A pure finite word copy is legal even under hostile arithmetic controls.
   * Actual gain arithmetic validates the environment again per block. */
  if (s->transformed && n && pcm_f64_check_dsp_env()!=PCM_F64_OK) {
    for (k=0;k<n;k++) if (gains[k]!=1.) {
      lsx_dsd_f64_destroy(s);
      return PCM_F64_NUMERIC;
    }
  }
  return PCM_F64_OK;
}

pcm_f64_progress lsx_dsd_f64_process(lsx_dsd_f64_stream *s,
    pcm_f64_input in, pcm_f64_output out)
{
  pcm_f64_progress p={0,0,PCM_F64_ARGUMENT};
  pcm_f64_status rc;
  size_t frames, words, bytes, k, frame, channel;
  uint64_t next;
  if (!s) return p;
  if (pcm_f64_is_failure(s->failure.failed))
    return failure(s,s->failure.failed);
  if (s->finished) return failure(s,PCM_F64_STATE);
  rc=pcm_f64_validate_input(&s->format,in);
  if (rc!=PCM_F64_OK) return failure(s,rc);
  rc=pcm_f64_validate_output(&s->format,out);
  if (rc!=PCM_F64_OK) return failure(s,rc);
  if (!in.frames) {p.status=PCM_F64_NEED_INPUT;return p;}
  if (!out.capacity_frames) {p.status=PCM_F64_NEED_OUTPUT;return p;}
  frames=in.frames<out.capacity_frames?in.frames:out.capacity_frames;
  rc=pcm_f64_advance(&s->format,s->input_frames,frames,&next);
  if (rc!=PCM_F64_OK) return failure(s,rc);
  rc=pcm_f64_frame_storage(frames,s->format.channels,&words,&bytes);
  if (rc!=PCM_F64_OK) return failure(s,rc);
  /* Prevalidate the *whole* block: a bad word in a later channel must not
   * commit an earlier channel to a writer. The source remains immutable. */
  rc=pcm_f64_copy_finite(out.data,in.data,words,NULL);
  if (rc!=PCM_F64_OK) return failure(s,rc);
  for (k=0;k<s->gain_count;k++) {
    if (s->gains[k]==1.) continue; /* Preserve -0 and subnormal words. */
    if (pcm_f64_check_dsp_env()!=PCM_F64_OK)
      return failure(s,PCM_F64_NUMERIC);
    rc=pcm_f64_fixed_gain(out.data,out.data,words,s->gains[k],NULL);
    if (rc!=PCM_F64_OK) return failure(s,rc);
  }
  /* Fixed-size stack scratch: no per-frame/per-sample heap operations. */
  if (s->permuted) for (frame=0;frame<frames;frame++) {
    double slots[64];
    for (channel=0;channel<s->format.channels;channel++)
      memcpy(&slots[channel],out.data+frame*s->format.channels+
          s->role_map[channel],sizeof(double));
    memcpy(out.data+frame*s->format.channels,slots,
        s->format.channels*sizeof(double));
  }
  s->input_frames=next;
  if (UINT64_MAX-s->output_frames<(uint64_t)frames)
    return failure(s,PCM_F64_LIMIT);
  s->output_frames+=(uint64_t)frames;
  p.consumed_frames=p.produced_frames=frames;
  p.status=frames<in.frames?PCM_F64_NEED_OUTPUT:PCM_F64_OK;
  return p;
}

pcm_f64_progress lsx_dsd_f64_finish(lsx_dsd_f64_stream *s,
    pcm_f64_output out)
{
  pcm_f64_progress p={0,0,PCM_F64_ARGUMENT};
  pcm_f64_status rc;
  if (!s) return p;
  if (pcm_f64_is_failure(s->failure.failed))
    return failure(s,s->failure.failed);
  if (s->finished) {p.status=PCM_F64_DONE;return p;}
  rc=pcm_f64_validate_output(&s->format,out);
  if (rc!=PCM_F64_OK) return failure(s,rc);
  /* Latch EOF even when capacity=0. This PCM-only shape has no tail. */
  s->finished=true;
  if (s->format.length_known &&
      (s->input_frames!=s->format.total_frames ||
       s->output_frames!=s->input_frames))
    return failure(s,PCM_F64_IO);
  p.status=PCM_F64_DONE;
  return p;
}

void lsx_dsd_f64_destroy(lsx_dsd_f64_stream *s)
{
  if (!s) return;
  free(s->gains);
  memset(s,0,sizeof(*s));
}

/* Source input and DSD outputs are frame-interleaved; the existing composite
 * is mono and owns its state. Keep its per-channel input and bit buffers
 * separate, then submit output only after every channel agrees on progress. */
sox_dsd_status_t lsx_dsd_f64_encode_init(lsx_dsd_f64_encoder *e,
    uint32_t source_hz, uint32_t native_hz, unsigned channels,
    double reference_scale, double attenuation, bool warn_and_clip)
{
  size_t i;
  if (!e || !source_hz || !channels || channels>64 ||
      (reference_scale!=.5 && reference_scale!=1.) ||
      !isfinite(attenuation) || attenuation<=0. || attenuation>1. ||
      (native_hz!=2822400 && native_hz!=5644800))
    return SOX_DSD_BAD_ARGUMENT;
  memset(e,0,sizeof(*e));
  e->channels=channels;e->native_hz=native_hz;e->source_hz=source_hz;
  e->planar=malloc((size_t)channels*LSX_DSD_F64_ENCODE_INPUT*sizeof(double));
  e->bits=malloc((size_t)channels*LSX_DSD_F64_ENCODE_OUTPUT*sizeof(sox_sample_t));
  if (!e->planar || !e->bits) goto failure;
  for (i=0;i<channels;i++) {
    sox_dsd_status_t rc=lsx_pcmdsd_create(source_hz,native_hz,
        reference_scale,(unsigned)i,&e->channel[i]);
    if (rc!=SOX_DSD_OK) goto failure;
    lsx_pcmdsd_set_gain(e->channel[i],attenuation);
    lsx_pcmdsd_set_clip(e->channel[i],warn_and_clip);
  }
  return SOX_DSD_OK;
failure:
  lsx_dsd_f64_encode_destroy(e);
  return SOX_DSD_UNSUPPORTED;
}

static sox_dsd_status_t encoder_failure(lsx_dsd_f64_encoder *e,
    sox_dsd_status_t status)
{
  if (!e->error) e->error=status;
  return e->error;
}

sox_dsd_status_t lsx_dsd_f64_encode_process(lsx_dsd_f64_encoder *e,
    const double *input, size_t *input_frames,
    sox_sample_t *output, size_t *output_frames)
{
  size_t available, capacity, used=0, produced=0, frame, c;
  sox_dsd_status_t rc=SOX_DSD_NEED_INPUT;
  if (!e || !input_frames || !output_frames) return SOX_DSD_BAD_ARGUMENT;
  available=*input_frames;capacity=*output_frames;
  *input_frames=*output_frames=0;
  if (e->error) return e->error;
  if (e->finishing || e->done) return encoder_failure(e,SOX_DSD_BAD_ARGUMENT);
  if (!capacity) return SOX_DSD_NEED_OUTPUT;
  if (!output || (available && !input))
    return encoder_failure(e,SOX_DSD_BAD_ARGUMENT);
  if (pcm_f64_check_dsp_env()!=PCM_F64_OK)
    return encoder_failure(e,SOX_DSD_UNSUPPORTED);
  if (available>LSX_DSD_F64_ENCODE_INPUT) available=LSX_DSD_F64_ENCODE_INPUT;
  if (capacity>LSX_DSD_F64_ENCODE_OUTPUT) capacity=LSX_DSD_F64_ENCODE_OUTPUT;
  if ((uint64_t)available>UINT64_MAX-e->source_frames)
    return encoder_failure(e,SOX_DSD_NUMERIC_ERROR);
  /* Whole-block finite admission precedes any per-channel state changes.
   * This is a metadata/word test, not a source amplitude limiter. */
  for (frame=0;frame<available;frame++) for (c=0;c<e->channels;c++) {
    pcm_f64_word_class kind;
    const double *word=input+frame*e->channels+c;
    if (pcm_f64_classify(word,&kind)!=PCM_F64_OK ||
        kind!=PCM_F64_WORD_FINITE)
      return encoder_failure(e,SOX_DSD_NUMERIC_ERROR);
    e->planar[c*LSX_DSD_F64_ENCODE_INPUT+frame]=*word;
  }
  for (c=0;c<e->channels;c++) {
    size_t n=available, m=capacity;
    sox_dsd_status_t status=lsx_pcmdsd_process(e->channel[c],
        e->planar+c*LSX_DSD_F64_ENCODE_INPUT,&n,
        e->bits+c*LSX_DSD_F64_ENCODE_OUTPUT,&m);
    if (status!=SOX_DSD_NEED_INPUT && status!=SOX_DSD_NEED_OUTPUT)
      return encoder_failure(e,status);
    if (c && (n!=used || m!=produced))
      return encoder_failure(e,SOX_DSD_NUMERIC_ERROR);
    used=n;produced=m;rc=status;
  }
  if ((uint64_t)produced>UINT64_MAX-e->encoded_frames)
    return encoder_failure(e,SOX_DSD_NUMERIC_ERROR);
  for (frame=0;frame<produced;frame++) for (c=0;c<e->channels;c++)
    output[frame*e->channels+c]=e->bits[c*LSX_DSD_F64_ENCODE_OUTPUT+frame];
  e->source_frames+=used;e->encoded_frames+=produced;
  *input_frames=used;*output_frames=produced;
  return rc;
}

sox_dsd_status_t lsx_dsd_f64_encode_finish(lsx_dsd_f64_encoder *e,
    sox_sample_t *output, size_t *output_frames)
{
  size_t capacity,produced=0,frame,c;
  sox_dsd_status_t rc=SOX_DSD_DONE;
  uint64_t expected;
  if (!e || !output_frames) return SOX_DSD_BAD_ARGUMENT;
  capacity=*output_frames;*output_frames=0;
  if (e->error) return e->error;
  if (e->done) return SOX_DSD_DONE;
  e->finishing=true; /* Latch EOF even when the caller has zero capacity. */
  if (!capacity) return SOX_DSD_NEED_OUTPUT;
  if (!output) return encoder_failure(e,SOX_DSD_BAD_ARGUMENT);
  if (pcm_f64_check_dsp_env()!=PCM_F64_OK)
    return encoder_failure(e,SOX_DSD_UNSUPPORTED);
  if (capacity>LSX_DSD_F64_ENCODE_OUTPUT) capacity=LSX_DSD_F64_ENCODE_OUTPUT;
  for (c=0;c<e->channels;c++) {
    size_t n=capacity;
    sox_dsd_status_t status=lsx_pcmdsd_finish(e->channel[c],
        e->bits+c*LSX_DSD_F64_ENCODE_OUTPUT,&n);
    if (status!=SOX_DSD_DONE && status!=SOX_DSD_NEED_OUTPUT)
      return encoder_failure(e,status);
    if (c && (n!=produced || status!=rc))
      return encoder_failure(e,SOX_DSD_NUMERIC_ERROR);
    produced=n;rc=status;
  }
  if ((uint64_t)produced>UINT64_MAX-e->encoded_frames)
    return encoder_failure(e,SOX_DSD_NUMERIC_ERROR);
  for (frame=0;frame<produced;frame++) for (c=0;c<e->channels;c++)
    output[frame*e->channels+c]=e->bits[c*LSX_DSD_F64_ENCODE_OUTPUT+frame];
  e->encoded_frames+=produced;
  *output_frames=produced;
  if (rc==SOX_DSD_DONE) {
    if (!lsx_dsd_count_convert(e->source_frames,e->source_hz,e->native_hz,&expected) ||
        expected!=e->encoded_frames)
      return encoder_failure(e,SOX_DSD_NUMERIC_ERROR);
    e->done=true;
  }
  return rc;
}

const lsx_pcmdsd *lsx_dsd_f64_encode_channel(const lsx_dsd_f64_encoder *e,
    unsigned channel)
{
  return e && channel<e->channels ? e->channel[channel] : NULL;
}

void lsx_dsd_f64_encode_observe_admitted(lsx_dsd_f64_encoder *e,
    unsigned channel, lsx_dsd_f64_admission_observer callback, void *opaque)
{
  if (e && channel<e->channels)
    lsx_pcmdsd_observe_admitted(e->channel[channel],callback,opaque);
}

void lsx_dsd_f64_encode_destroy(lsx_dsd_f64_encoder *e)
{
  unsigned channel;
  if (!e) return;
  for (channel=0;channel<64;channel++)
    lsx_pcmdsd_destroy(e->channel[channel]);
  free(e->planar);free(e->bits);
  memset(e,0,sizeof(*e));
}

/* Phase 06B coordinator. Keep the source-matched reconstruction and the
 * certified interpolation/modulator untouched. This scheduler never stores
 * more than one bounded, complete interleaved PCM block; a partially drained
 * block always has priority over further decoder input. */
static sox_dsd_status_t transcode_error(lsx_dsd_f64_transcode *t,
    sox_dsd_status_t status)
{
  if (!t->error) t->error=status;
  return t->error;
}

void lsx_dsd_f64_transcode_destroy(lsx_dsd_f64_transcode *t)
{
  if (!t) return;
  lsx_dsd_f64_decode_destroy(&t->decoder);
  lsx_dsd_f64_encode_destroy(&t->encoder);
  lsx_dsd_f64_destroy(&t->pcm);
  free(t->decoded);free(t->fifo);
  memset(t,0,sizeof(*t));
}

sox_dsd_status_t lsx_dsd_f64_transcode_init(lsx_dsd_f64_transcode *t,
    const sox_dsd_decode_options_t *options, bool known, uint64_t native_frames,
    const double *gains, size_t gain_count, const unsigned *map,
    uint32_t output_hz, double reference, double attenuation,
    bool warn_clip, bool clip_error, size_t fifo_capacity)
{
  pcm_f64_format format={0};
  sox_dsd_status_t st;
  if (!t || !options || !options->channels || options->channels>64 ||
      !fifo_capacity || fifo_capacity>LSX_DSD_F64_TRANSCODE_FIFO_MAX ||
      (gain_count && !gains) ||
      fifo_capacity>SIZE_MAX/options->channels/sizeof(double))
    return SOX_DSD_BAD_ARGUMENT;
  memset(t,0,sizeof(*t));
  t->fifo_capacity=fifo_capacity;
  t->clip_error=clip_error;
  t->adapter_volume=gain_count?gains[0]:1.;
  if (!isfinite(t->adapter_volume)) return SOX_DSD_NUMERIC_ERROR;
  t->decoded=malloc(fifo_capacity*options->channels*sizeof(double));
  t->fifo=malloc(fifo_capacity*options->channels*sizeof(double));
  if (!t->decoded || !t->fifo) goto error;
  if (lsx_dsd_f64_decode_init(&t->decoder,options,known,native_frames)!=SOX_DSD_OK)
    goto error;
  if (pcm_f64_format_init(&format,options->output_hz,options->channels,
        known,t->decoder.pcm_expected)!=PCM_F64_OK) goto error;
  if (lsx_dsd_f64_init(&t->pcm,&format,gains,gain_count,map)!=PCM_F64_OK)
    goto error;
  st=lsx_dsd_f64_encode_init(&t->encoder,options->output_hz,output_hz,
      options->channels,reference,attenuation,warn_clip);
  if (st!=SOX_DSD_OK) goto error;
  return SOX_DSD_OK;
error:
  lsx_dsd_f64_transcode_destroy(t);
  return SOX_DSD_UNSUPPORTED;
}

/* Reconstruction adapter clipping is evaluated at the exact legacy boundary:
 * after input volume, before subsequent user gains. The single multiplication
 * here is diagnostic only; the PCM stage applies the gain exactly once. */
static sox_dsd_status_t transcode_enqueue(lsx_dsd_f64_transcode *t,
    size_t frames)
{
  size_t i,words;
  pcm_f64_progress p;
  if (t->fifo_frames || t->fifo_at || frames>t->fifo_capacity)
    return transcode_error(t,SOX_DSD_BAD_ARGUMENT);
  words=frames*t->encoder.channels; /* init has already bounded this product */
  for (i=0;i<words;i++) {
    double v=t->decoded[i]*t->adapter_volume;
    if (!isfinite(v)) return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
    if (fabs(v)>t->decoder_peak) t->decoder_peak=fabs(v);
    if (v>=1. || v< -1.) {
      if (t->decoder_nominal_clips!=UINT64_MAX) ++t->decoder_nominal_clips;
      if (t->clip_error) return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
    }
  }
  p=lsx_dsd_f64_process(&t->pcm,(pcm_f64_input){t->decoded,frames},
      (pcm_f64_output){t->fifo,t->fifo_capacity});
  if (pcm_f64_is_failure(p.status) || p.consumed_frames!=frames ||
      p.produced_frames!=frames)
    return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
  if (t->pcm_observer)
    t->pcm_observer(t->pcm_observer_opaque,t->fifo,frames,t->encoder.channels);
  t->fifo_frames=frames;
  return SOX_DSD_OK;
}

/* Submit at most one qualified encoder work step per invocation. No bits from
 * a failed cross-channel work step can reach the physical writer. */
static sox_dsd_status_t transcode_drain(lsx_dsd_f64_transcode *t,
    sox_sample_t *bits, size_t *capacity, size_t *produced)
{
  size_t used=t->fifo_frames, made=*capacity;
  sox_dsd_status_t st;
  *produced=0;
  st=lsx_dsd_f64_encode_process(&t->encoder,
      t->fifo+t->fifo_at*t->encoder.channels,&used,bits,&made);
  if (st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT)
    return transcode_error(t,st);
  if (used>t->fifo_frames || made>*capacity || (!used && !made))
    return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
  t->fifo_at+=used;t->fifo_frames-=used;
  if (!t->fifo_frames) t->fifo_at=0;
  *capacity-=made;
  *produced=made;
  return st;
}

void lsx_dsd_f64_transcode_observe_pcm(lsx_dsd_f64_transcode *t,
    void (*observer)(void *, const double *, size_t, unsigned), void *opaque)
{
  if (t) {t->pcm_observer=observer;t->pcm_observer_opaque=opaque;}
}

sox_dsd_status_t lsx_dsd_f64_transcode_process(lsx_dsd_f64_transcode *t,
    const sox_sample_t *expanded, const sox_dsd_packed_block_t *packed,
    size_t start, size_t *nf, sox_sample_t *bits, size_t *bf)
{
  size_t remaining,cap,used_total=0,made_total=0;
  if (!t || !nf || !bf) return SOX_DSD_BAD_ARGUMENT;
  remaining=*nf;cap=*bf;
  *nf=*bf=0;
  if (t->error) return t->error;
  if (t->finishing || t->done) return transcode_error(t,SOX_DSD_BAD_ARGUMENT);
  if ((remaining && !expanded && !packed) || (expanded && packed) ||
      (cap && !bits)) return transcode_error(t,SOX_DSD_BAD_ARGUMENT);
  if (!cap) return SOX_DSD_NEED_OUTPUT;
  for (;;) {
    if (t->fifo_frames) {
      size_t made=0;
      sox_dsd_status_t st=transcode_drain(t,bits+made_total*t->encoder.channels,
          &cap,&made);
      if (t->error) return t->error;
      made_total+=made;
      if (!cap) break;
      if (t->fifo_frames) continue;
      (void)st;
    }
    if (!remaining) break;
    {
      size_t used=remaining, made=t->fifo_capacity;
      sox_dsd_status_t st=packed?
          lsx_dsd_f64_decode_process_packed(&t->decoder,packed,start+used_total,
              &used,t->decoded,&made):
          lsx_dsd_f64_decode_process(&t->decoder,
              expanded+used_total*t->encoder.channels,&used,t->decoded,&made);
      if (st!=SOX_DSD_NEED_INPUT && st!=SOX_DSD_NEED_OUTPUT)
        return transcode_error(t,st);
      if (used>remaining || made>t->fifo_capacity || (!used && !made))
        return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
      remaining-=used;used_total+=used;
      if (made && transcode_enqueue(t,made)!=SOX_DSD_OK) return t->error;
    }
  }
  *nf=used_total;*bf=made_total;
  return cap?SOX_DSD_NEED_INPUT:SOX_DSD_NEED_OUTPUT;
}

sox_dsd_status_t lsx_dsd_f64_transcode_finish(lsx_dsd_f64_transcode *t,
    sox_sample_t *bits,size_t *bf)
{
  size_t cap,made_total=0;
  if (!t || !bf) return SOX_DSD_BAD_ARGUMENT;
  cap=*bf;*bf=0;
  if (t->error) return t->error;
  if (t->done) return SOX_DSD_DONE;
  t->finishing=true;
  if (!cap) return SOX_DSD_NEED_OUTPUT;
  if (!bits) return transcode_error(t,SOX_DSD_BAD_ARGUMENT);
  for (;;) {
    if (t->fifo_frames) {
      size_t made=0;
      transcode_drain(t,bits+made_total*t->encoder.channels,&cap,&made);
      if (t->error) return t->error;
      made_total+=made;
      if (!cap) break;
      if (t->fifo_frames) continue;
    }
    if (!t->decoder_done) {
      size_t made=t->fifo_capacity;
      sox_dsd_status_t st=lsx_dsd_f64_decode_finish(&t->decoder,t->decoded,&made);
      if (st!=SOX_DSD_DONE && st!=SOX_DSD_NEED_OUTPUT)
        return transcode_error(t,st);
      if (made>t->fifo_capacity || (st==SOX_DSD_NEED_OUTPUT && !made))
        return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
      if (st==SOX_DSD_DONE) t->decoder_done=true;
      if (made) {
        if (transcode_enqueue(t,made)!=SOX_DSD_OK) return t->error;
        continue;
      }
    }
    if (!t->pcm_done) {
      pcm_f64_progress p=lsx_dsd_f64_finish(&t->pcm,(pcm_f64_output){NULL,0});
      if (p.status!=PCM_F64_DONE || p.produced_frames)
        return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
      t->pcm_done=true;
    }
    {
      size_t made=cap;
      sox_dsd_status_t st=lsx_dsd_f64_encode_finish(&t->encoder,
          bits+made_total*t->encoder.channels,&made);
      if (st!=SOX_DSD_DONE && st!=SOX_DSD_NEED_OUTPUT)
        return transcode_error(t,st);
      if (made>cap || (st==SOX_DSD_NEED_OUTPUT && !made))
        return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
      made_total+=made;
      if (t->encoder.source_frames!=t->pcm.output_frames && st==SOX_DSD_DONE)
        return transcode_error(t,SOX_DSD_NUMERIC_ERROR);
      if (st==SOX_DSD_DONE) {
        t->done=true;*bf=made_total;return SOX_DSD_DONE;
      }
      break;
    }
  }
  *bf=made_total;
  return SOX_DSD_NEED_OUTPUT;
}
