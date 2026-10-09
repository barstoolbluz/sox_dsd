/* P06 allocation-failure injection, compiled against the unchanged
 * production decoder source, with only calloc intercepted. The private code
 * is included as in the inherited P01 writer fault-injection test. */
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static unsigned calls, fail_at;
static void *fault_calloc(size_t n,size_t sz)
{
  if (++calls == fail_at) return NULL;
  return calloc(n,sz);
}
#define calloc fault_calloc
#include "../../src/dsd_decode.c"
#undef calloc

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr,"P06 allocation test line %d: %s\n",__LINE__,#x); return 1; \
  } ++checks; } while (0)
int main(void)
{
  unsigned checks=0;
  lsx_dsd_reconstruction *ctx=NULL;
  for (unsigned f=1;f<=4;f++) {
    calls=0;fail_at=f;
    CHECK(lsx_dsd_reconstruction_create(11289600,LSX_DSD_PROFILE_MASTERING,6,&ctx)
          ==SOX_DSD_NUMERIC_ERROR);
    CHECK(ctx==NULL);
    CHECK(calls==(f==1 ? 1u : 4u));
    /* Sanitizers detect leaked partial allocations after every injected failure. */
  }
  calls=0;fail_at=0;
  CHECK(lsx_dsd_reconstruction_create(11289600,LSX_DSD_PROFILE_MASTERING,6,&ctx)==SOX_DSD_OK);
  CHECK(ctx!=NULL);
  CHECK(calls==4);
  CHECK((uintptr_t)ctx->histories % LSX_DSD_ALIGN == 0);
  for (unsigned c=0;c<6;c++)for (unsigned j=0;j<ctx->info.stages;j++)
    CHECK((uintptr_t)ctx->stages[c*ctx->info.stages+j].ring % LSX_DSD_ALIGN == 0);
  lsx_dsd_reconstruction_destroy(ctx);
  printf("P06 allocation cleanup/alignment PASS (%u assertions; 4 injected failures)\n",checks);
  return 0;
}
