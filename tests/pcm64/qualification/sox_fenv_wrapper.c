/* Phase 08 diagnostic-only SoX entry/exit IEEE-754 FENV witness.
 * This module is built ONLY into the uninstalled qualification CLI, never
 * the normal SoX or shared library; it performs no work in the sample loop.
 * FENV is observed at entry and exit, not claimed at every sample boundary.
 */
#if defined(main)
# undef main
#endif
#include <fenv.h>
#include <stdio.h>
#include <stdlib.h>

extern int sox_p08_original_main(int argc,char **argv);

static const char *round_name(int mode)
{
  if (mode==FE_TONEAREST)return "FE_TONEAREST";
  if (mode==FE_DOWNWARD)return "FE_DOWNWARD";
  if (mode==FE_UPWARD)return "FE_UPWARD";
  if (mode==FE_TOWARDZERO)return "FE_TOWARDZERO";
  return "UNKNOWN";
}

int main(int argc,char **argv)
{
  const char *path=getenv("SOX_P08_FENV_PATH");
  int before=fegetround(), before_exceptions=fetestexcept(FE_ALL_EXCEPT);
  int after,after_exceptions,rc;
  FILE *out;
  rc=sox_p08_original_main(argc,argv);
  after=fegetround();after_exceptions=fetestexcept(FE_ALL_EXCEPT);
  if (path && *path) {
    out=fopen(path,"wb");
    if (!out)return 1;
    if (fprintf(out,
          "{\"schema\":\"sox-p08-inprocess-fenv/1\","
          "\"entry_round\":\"%s\",\"exit_round\":\"%s\","
          "\"entry_exceptions\":%d,\"exit_exceptions\":%d,"
          "\"sox_exit\":%d}\n",
          round_name(before),round_name(after),before_exceptions,
          after_exceptions,rc)<0) {
      (void)fclose(out);
      return 1;
    }
    if (fclose(out)!=0)return 1;
  }
  return rc;
}
