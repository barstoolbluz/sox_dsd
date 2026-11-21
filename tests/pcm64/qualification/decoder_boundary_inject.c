/* Qualification-only LD_PRELOAD hook: replace one public decoder output word.
 * Both ordinary dsdpcm and native PCM64 call this unchanged decoder API;
 * all downstream clip/adaptation decisions remain real production code.
 * Not installed, linked, or consulted by a production binary. */
#define _GNU_SOURCE
#include "sox_dsd.h"
#include <dlfcn.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef sox_dsd_status_t (SOX_DSD_CALL *real_process_t)(
    sox_dsd_decoder_t *, const sox_sample_t *, size_t *, double *, size_t *);

static int injected;
static int parse_value(double *value)
{
  const char *name=getenv("SOX_DSD_TEST_INJECT");
  if (!name) return 0;
  if (!strcmp(name,"positive_one")) *value=1.;
  else if (!strcmp(name,"negative_one")) *value=-1.;
  else if (!strcmp(name,"positive_inside")) *value=nextafter(1.,0.);
  else if (!strcmp(name,"positive_outside")) *value=nextafter(1.,INFINITY);
  else if (!strcmp(name,"negative_inside")) *value=nextafter(-1.,0.);
  else if (!strcmp(name,"negative_outside")) *value=nextafter(-1.,-INFINITY);
  else if (!strcmp(name,"nan")) *value=NAN;
  else if (!strcmp(name,"positive_infinity")) *value=INFINITY;
  else { fprintf(stderr,"qualification hook: invalid injection name\n"); abort(); }
  return 1;
}

sox_dsd_status_t SOX_DSD_CALL sox_dsd_decoder_process(
    sox_dsd_decoder_t *ctx, const sox_sample_t *input, size_t *native_frames,
    double *pcm, size_t *pcm_frames)
{
  static real_process_t real_process;
  sox_dsd_status_t rc;
  double value;
  if (!real_process) {
    void *sym=dlsym(RTLD_NEXT,"sox_dsd_decoder_process");
    /* POSIX guarantees the corresponding function-pointer representation
     * on the Linux/ELF host named by this qualification fixture. */
    memcpy(&real_process,&sym,sizeof(real_process));
    if (!real_process) abort();
  }
  rc=real_process(ctx,input,native_frames,pcm,pcm_frames);
  if (!injected && pcm && *pcm_frames && parse_value(&value)) {
    pcm[0]=value;
    injected=1;
    /* Explicit receipt: a broken or uncalled hook is not a passing test. */
    fprintf(stderr,"qualification hook: injected %s\n",getenv("SOX_DSD_TEST_INJECT"));
  }
  return rc;
}
