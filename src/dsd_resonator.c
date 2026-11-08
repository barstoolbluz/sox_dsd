/* Rate dispatch for the certified switched-resonator modulators. */
#include "dsd_resonator.h"
#include <string.h>

#if DSD64_IQ_OK != DSD128_IQ_OK || DSD64_IQ_INPUT != DSD128_IQ_INPUT || \
    DSD64_IQ_PROOF_BREACH != DSD128_IQ_PROOF_BREACH
#  error resonator status codes must agree across rates
#endif

int lsx_dsd_resonator_supported(uint32_t native_hz)
{
  return native_hz==DSD64_IQ_RATE || native_hz==DSD128_IQ_RATE;
}

const char *lsx_dsd_resonator_identity(uint32_t native_hz)
{
  if (native_hz==DSD64_IQ_RATE) return dsd64_iq_identity();
  if (native_hz==DSD128_IQ_RATE) return dsd128_iq_identity();
  return NULL;
}

int lsx_dsd_resonator_init(lsx_dsd_resonator *r, uint32_t native_hz)
{
  if (!r) return LSX_DSD_RESONATOR_ARGUMENT;
  memset(r,0,sizeof(*r));
  r->native_hz=native_hz;
  if (native_hz==DSD64_IQ_RATE) return dsd64_iq_init(&r->u.dsd64);
  if (native_hz==DSD128_IQ_RATE) return dsd128_iq_init(&r->u.dsd128);
  return LSX_DSD_RESONATOR_ARGUMENT;
}

int lsx_dsd_resonator_process(lsx_dsd_resonator *r, const double *input,
    int8_t *output, size_t n)
{
  if (!r) return LSX_DSD_RESONATOR_ARGUMENT;
  if (r->native_hz==DSD64_IQ_RATE)
    return dsd64_iq_process(&r->u.dsd64,input,output,n);
  if (r->native_hz==DSD128_IQ_RATE)
    return dsd128_iq_process(&r->u.dsd128,input,output,n);
  return LSX_DSD_RESONATOR_ARGUMENT;
}

void lsx_dsd_resonator_counters(const lsx_dsd_resonator *r,
    uint64_t *recovery_entries, uint64_t *recovery_steps)
{
  uint64_t entries=0,steps=0;
  if (r && r->native_hz==DSD64_IQ_RATE) {
    entries=r->u.dsd64.recovery_entries;steps=r->u.dsd64.recovery_steps;
  } else if (r && r->native_hz==DSD128_IQ_RATE) {
    entries=r->u.dsd128.recovery_entries;steps=r->u.dsd128.recovery_steps;
  }
  if (recovery_entries) *recovery_entries=entries;
  if (recovery_steps) *recovery_steps=steps;
}
