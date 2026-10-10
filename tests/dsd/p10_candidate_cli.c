/* GNU-linker qualification driver ONLY. Not installed and no production
 * environment/CLI override exists. Its sole purpose is exercising the real
 * CLI graph before a profile can be considered for promotion. */
#include "pcmdsd.h"
int __wrap_lsx_pcmdsd_qualified(uint32_t hz)
{ return lsx_pcmdsd_profile_find(hz)!=NULL; }
int __wrap_lsx_pcmdsd_start(sox_effect_t *effect)
{ return lsx_pcmdsd_candidate_start(effect); }
