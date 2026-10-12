/* P14 native-stat streaming and independent SOS coefficient observation unit.
 * Compiles against the production library. It does not implement production
 * bit statistics or filter formulas as its oracle; the Python gate does. */
#include "sox_i.h"
#include "dsd_stats.h"
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int synthetic(unsigned frames, unsigned channels, int analysis)
{
  sox_sample_t samples[2*512];
  lsx_dsd_stats *s;
  unsigned i,ch,start;
  if (frames>512 || channels>2 || channels<1) return 2;
  for(i=0;i<frames;i++)for(ch=0;ch<channels;ch++) {
    /* deliberate 33-bit + run straddling the 17/31/64 chunk boundaries */
    unsigned bit=(ch==0?(i>=12 && i<55 ?1 : (i%5==0)):
                           (i>=29 && i<72 ?0 : (i%7<3)));
    samples[i*channels+ch]=bit?SOX_SAMPLE_MAX:-SOX_SAMPLE_MAX;
  }
  s=lsx_dsd_stats_create(channels,2822400,analysis);
  if (!s) return 1;
  for(start=0;start<frames;) {
    unsigned n=start%3==0?17:start%3==1?31:64;
    if (n>frames-start) n=frames-start;
    if (!lsx_dsd_stats_feed(s,samples+start*channels,n)) return 1;
    start+=n;
  }
  if(lsx_dsd_stats_frames(s)!=frames)return 1;
  lsx_dsd_stats_json(stdout,s);
  fputc('\n',stdout);
  lsx_dsd_stats_destroy(s);
  return 0;
}

static int sos(unsigned hz, double cutoff, int hp)
{
  lsx_dsd_sos sections[3];
  unsigned i;
  if(!lsx_dsd_butterworth5(hz,cutoff,hp,sections))return 2;
  for(i=0;i<3;i++) {
    printf("%u %.17g %.17g %.17g %.17g %.17g\n",sections[i].order,
       sections[i].b[0],sections[i].b[1],sections[i].b[2],
       sections[i].a[1],sections[i].a[2]);
  }
  return 0;
}

int main(int argc, char **argv)
{
  if(argc==5 && !strcmp(argv[1],"--sos")) {
    char *end=NULL;
    unsigned long hz=strtoul(argv[2],&end,10);
    double cutoff;
    int hp;
    if(!end || *end || hz>UINT32_MAX)return 2;
    cutoff=strtod(argv[3],&end);
    if(!end || *end || !isfinite(cutoff))return 2;
    hp=!strcmp(argv[4],"hp")?1:0;
    if(hp==0 && strcmp(argv[4],"lp"))return 2;
    return sos((unsigned)hz,cutoff,hp);
  }
  if(argc==2 && !strcmp(argv[1],"--large")) {
    lsx_dsd_stats_uint64_json(stdout,(UINT64_C(1)<<63)+UINT64_C(12345));
    fputc('\n',stdout);return 0;
  }
  if(argc==4 && !strcmp(argv[1],"--json")) {
    char *end=NULL;
    unsigned long frames=strtoul(argv[2],&end,10);
    if(!end || *end || frames>512)return 2;
    return synthetic((unsigned)frames,2,!strcmp(argv[3],"analysis"));
  }
  fprintf(stderr,"usage: test_p14 --sos hz cutoff lp|hp | --json frames basic|analysis\n");
  return 2;
}
