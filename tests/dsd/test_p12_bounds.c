/* P12: execute FIR at a PROT_NONE page boundary. This detects any vector
 * over-read past exactly taps samples in a 4-output stride-two window.
 * POSIX-specific; on non-POSIX hosts the gate is explicitly UNRUN. */
#include "sox_i.h"
#include "dsd_kernels.h"
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(__unix__) || defined(__APPLE__)
#include <sys/mman.h>
#include <unistd.h>
#define HAVE_GUARD_PAGE 1
#endif
#ifndef MAP_ANONYMOUS
#ifdef MAP_ANON
#define MAP_ANONYMOUS MAP_ANON
#endif
#endif
#define CHECK(c) do {if (!(c)) {fprintf(stderr,"P12 bounds FAIL line %d: %s\n",__LINE__,#c); return 1;}} while (0)

int main(void)
{
#if defined(HAVE_GUARD_PAGE) && defined(MAP_ANONYMOUS)
  static const unsigned tap_counts[]={1,3,57,61,77,117,153,257};
  static const unsigned frames[]={0,1,2,3,4,5,7,8,9,13};
  const lsx_dsd_kernel *k=NULL;
  size_t pg,t,f,stride,half,checks=0;
  unsigned char *base,*end;
  long page=sysconf(_SC_PAGESIZE);
  int rc=lsx_dsd_kernel_select(LSX_DSD_FIR,"avx2",&k);
  if (rc==-2) {puts("UNRUN: AVX2 CPU/compiler not available");return 2;}
  CHECK(rc==0 && k && k->fir_block && k->fir_single && page>512);
  pg=(size_t)page;
  base=mmap(NULL,2*pg,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
  CHECK(base!=MAP_FAILED);
  CHECK(mprotect(base+pg,pg,PROT_NONE)==0);
  end=base+pg;
  for (t=0;t<sizeof(tap_counts)/sizeof(*tap_counts);++t) {
    const size_t taps=tap_counts[t],mid=taps/2;
    double h[257];
    size_t i;
    for (i=0;i<taps;++i)h[i]=.002/(1.+fabs((double)i-(double)mid));
    for (i=0;i<mid;++i)h[taps-1-i]=h[i];
    for (half=0;half<=1;++half) {
      if (half) for (i=0;i<mid;++i) if (i&1) h[i]=h[taps-1-i]=0.;
      for (stride=1;stride<=3;++stride) {
        for (f=0;f<sizeof(frames)/sizeof(*frames);++f) {
          const size_t n=frames[f],length=n?(n-1)*stride+taps:0;
          double *s=length?(double *)(end-length*sizeof(double)):NULL;
          double out[16],reference;
          CHECK(length*sizeof(double)<=pg);
          for (i=0;i<length;++i) s[i]=.05*sin(i*.27)+.11*cos(i*.093);
          for (i=0;i<16;++i)out[i]=123.125;
          k->fir_block(h,taps,s,n,stride,(int)half,out);
          CHECK(out[n]==123.125);
          for (i=0;i<n;++i) {
            reference=lsx_dsd_fir_scalar(h,taps,s+i*stride,(int)half);
            CHECK(fabs(reference-out[i]) <=
                  16*DBL_EPSILON*taps*2.0);
            ++checks;
          }
        }
      }
      /* Direct stream at last allowed element; AVX2 reversals must not
       * look past the page on odd tap counts or unaligned sample bases. */
      {
        double *s=(double *)(end-taps*sizeof(double));
        double got;
        for (i=0;i<taps;++i) s[i]=.07*sin(i*.34);
        got=k->fir_single(h,taps,s,(int)half);
        CHECK(fabs(got-lsx_dsd_fir_scalar(h,taps,s,(int)half)) < 1e-11);
        ++checks;
      }
    }
  }
  CHECK(munmap(base,2*pg)==0);
  printf("P12 protected-page FIR spans PASS (%zu comparisons)\n",checks);
  return 0;
#else
  puts("UNRUN: guard-page mmap/mprotect not supported on this platform");
  return 2;
#endif
}
