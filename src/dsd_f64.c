/* Phase 05A: bounded, private, unchanged-rate/channel binary64 coordinator.
 * The format adapters own container parsing and I/O. This stream has no
 * knowledge of argv, signal handlers, headers, or the legacy int32 carrier. */
#ifdef HAVE_CONFIG_H
#include "soxconfig.h"
#endif
#include "dsd_f64.h"
#include <stdlib.h>
#include <string.h>

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
          kind!=PCM_F64_WORD_FINITE || gains[k]<0) {
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
