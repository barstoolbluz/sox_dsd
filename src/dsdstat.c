/* P14 bit-exact native statistic effect. Observes the original DSD samples.
 * The default path is integer-only; -a adds observational SOS processing. */
#include "sox_i.h"
#include "dsd_stats.h"
#include <inttypes.h>
#include <string.h>

typedef struct {
  int analysis;
  lsx_dsd_stats *stats; /* owned only after start, not cloned from getopts */
} dsdstat_private;

int lsx_dsdstat_getopts(sox_effect_t *e,int argc,char **argv)
{
  dsdstat_private *p=e->priv;
  if (argc==1) {p->analysis=0;return SOX_SUCCESS;}
  if (argc==2 && !strcmp(argv[1],"-a")) {
    p->analysis=1;return SOX_SUCCESS;
  }
  lsx_fail("dsdstat accepts only -a (optional native spectral analysis)");
  return SOX_EOF;
}
int lsx_dsdstat_start(sox_effect_t *e)
{
  dsdstat_private *p=e->priv;
  uint32_t hz;
  if (e->in_signal.precision!=1 ||
      !lsx_dsd_integer_rate(e->in_signal.rate,&hz) ||
      !lsx_dsd_rate_find(hz) || !e->in_signal.channels) {
    lsx_fail("dsdstat: requires native DSD bits, not reconstructed PCM");
    return SOX_EOF;
  }
  p->stats=lsx_dsd_stats_create(e->in_signal.channels,hz,p->analysis);
  if (!p->stats) {
    lsx_fail("dsdstat: cannot allocate native statistics");
    return SOX_EOF;
  }
  e->out_signal=e->in_signal;
  return SOX_SUCCESS;
}
int lsx_dsdstat_flow(sox_effect_t *e,const sox_sample_t *in,sox_sample_t *out,
    size_t *isamp,size_t *osamp)
{
  dsdstat_private *p=e->priv;
  size_t n=*isamp<*osamp?*isamp:*osamp;
  unsigned channels=e->in_signal.channels;
  n-=n%channels;
  if (n && !lsx_dsd_stats_feed(p->stats,in,n/channels)) {
    *isamp=*osamp=0;
    lsx_fail("dsdstat: invalid native bit or 64-bit counter overflow");
    return LSX_EFF_FATAL;
  }
  if (n && in!=out) memmove(out,in,n*sizeof(*out));
  *isamp=*osamp=n;
  return SOX_SUCCESS;
}
int lsx_dsdstat_stop(sox_effect_t *e)
{
  dsdstat_private *p=e->priv;
  if (!p->stats) return SOX_SUCCESS;
  lsx_dsd_report_note_stat(p->stats);
  lsx_dsd_stats_text(stderr,p->stats);
  lsx_dsd_stats_destroy(p->stats);
  p->stats=NULL;
  return SOX_SUCCESS;
}

const sox_effect_handler_t *lsx_dsdstat_effect_fn(void)
{
  static sox_effect_handler_t h={"dsdstat",
    "[-a]  (native DSD bit counters; optional original-bit filter analysis)",
    SOX_EFF_MCHAN, lsx_dsdstat_getopts, lsx_dsdstat_start,
    lsx_dsdstat_flow, NULL, lsx_dsdstat_stop, NULL,
    sizeof(dsdstat_private), NULL, NULL, NULL};
  return &h;
}
