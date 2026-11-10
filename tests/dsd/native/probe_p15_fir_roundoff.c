/* Deterministic native-DSD reconstruction probe, no external audio.
 * Compare raw pre-graph doubles for scalar and SSE2 at all native clocks,
 * with both released decoder profile families. This does not test the
 * proprietary P10 commercial recording or establish P15 release eligibility.
 */
#include "sox_i.h"
#include "dsd_decode.h"
#include "dsd_coeffs.h"
#include <float.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FRAMES 262144
static uint32_t seed=UINT32_C(0xcacf3e85);
static uint32_t next(void) {
  seed ^= seed<<13;
  seed ^= seed>>17;
  seed ^= seed<<5;
  return seed;
}
static void die(const char *what) { fprintf(stderr,"FAIL: %s\n",what); exit(1); }
static uint64_t render(lsx_dsd_reconstruction *ctx, const sox_sample_t *src,
                       double *dst, unsigned channels) {
  size_t in=FRAMES, out=FRAMES; 
  sox_dsd_status_t rc;
  if (channels!=1) die("invalid channel count");
  rc=lsx_dsd_reconstruction_process(ctx,src,&in,dst,&out);
  if (rc!=SOX_DSD_NEED_INPUT || in!=FRAMES) die("process completeness");
  {
    size_t extra=FRAMES-out;
    rc=lsx_dsd_reconstruction_finish(ctx,dst+out,&extra);
    if (rc!=SOX_DSD_DONE) die("finalize completeness");
    return out+extra;
  }
}
static void profile_run(uint32_t native, lsx_dsd_decode profile, const char *name,
                        const sox_sample_t *src) {
  lsx_dsd_reconstruction *a=NULL,*b=NULL;
  lsx_dsd_reconstruction_info ia,ib;
  double *x=calloc(FRAMES,sizeof(*x)),*y=calloc(FRAMES,sizeof(*y));
  double max_abs=0.0,product=1.0,raw_bound,graph_lsb;
  uint64_t na,nb,i,diff=0;
  unsigned j;
  if (!x || !y) die("allocation");
  if (lsx_dsd_reconstruction_create_kernel(native,profile,1,"scalar",&a)!=SOX_DSD_OK ||
      lsx_dsd_reconstruction_create_kernel(native,profile,1,"sse2",&b)!=SOX_DSD_OK)
    die("context creation / unsupported SSE2");
  if (lsx_dsd_reconstruction_info_get(a,&ia)!=SOX_DSD_OK ||
      lsx_dsd_reconstruction_info_get(b,&ib)!=SOX_DSD_OK ||
      ia.native_hz!=ib.native_hz || ia.intermediate_hz!=ib.intermediate_hz ||
      ia.channels!=ib.channels || ia.stages!=ib.stages || ia.factor!=ib.factor ||
      ia.delay_native_frames!=ib.delay_native_frames ||
      ia.discard_frames!=ib.discard_frames)
    die("context description changed");
  for (j=0;j<6;++j)
    if (ia.taps[j]!=ib.taps[j] || ia.phases[j]!=ib.phases[j])
      die("context tap/phase description changed");
  na=render(a,src,x,1);nb=render(b,src,y,1);
  if (na!=nb || na!=(FRAMES+ia.factor-1)/ia.factor) die("frame count differs");
  for (j=0;j<ia.stages;++j) {
    double l1=0.0;
    const double *h=j+1==ia.stages ?
      (profile==LSX_DSD_PROFILE_WIDEBAND ? lsx_dsd_coeff_wideband :
       native==5644800 ? lsx_dsd_coeff_master128 : lsx_dsd_coeff_master64_256)
      : lsx_dsd_coeff_halfband;
    size_t k;
    for (k=0;k<ia.taps[j];++k) l1+=fabs(h[k]);
    product*=l1;
  }
  {
    double total_taps=0.0;
    for(j=0;j<ia.stages;++j) total_taps+=(double)ia.taps[j];
    raw_bound=16.0*DBL_EPSILON*total_taps*product;
  }
  for(i=0;i<na;++i) {
    double delta=fabs(x[i]-y[i]);
    if (!isfinite(x[i]) || !isfinite(y[i])) die("nonfinite raw decode");
    if (memcmp(&x[i],&y[i],sizeof(double))) ++diff;
    if (delta>max_abs)max_abs=delta;
    if (delta>raw_bound) die("raw FIR roundoff contract exceeded");
  }
  graph_lsb=max_abs*(double)SOX_SAMPLE_MAX;
  if (graph_lsb>1.) die("graph absolute LSB bound exceeded");
  printf("{\"native_hz\":%u,\"profile\":\"%s\",\"samples\":%"PRIu64","
         "\"raw_double_mismatches\":%"PRIu64",\"max_abs_delta\":%.17g,"
         "\"roundoff_bound\":%.17g,\"max_delta_in_graph_lsb\":%.17g}\n",
         native,name,na,diff,max_abs,raw_bound,graph_lsb);
  lsx_dsd_reconstruction_destroy(a);
  lsx_dsd_reconstruction_destroy(b);
  free(x);free(y);
}
int main(void) {
  const uint32_t rates[]={2822400,5644800,11289600};
  const char *names[]={"mastering","wideband"};
  sox_sample_t *src=malloc(FRAMES*sizeof(*src));
  unsigned i,p,k;
  if (!src) die("source allocation");
  for(k=0;k<sizeof(rates)/sizeof(*rates);++k) {
    for(i=0;i<FRAMES;++i) src[i]=(next()&1)?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
    for(p=0;p<2;++p) profile_run(rates[k], (lsx_dsd_decode)p,names[p],src);
  }
  free(src);
  return 0;
}
