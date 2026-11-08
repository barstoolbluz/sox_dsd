/* SoX DSD 2.0.0 certified switched-resonator modulators.
 * A thin rate dispatch over the frozen reference sources in resonator/,
 * which are vendored byte for byte with their certificates. Their
 * recurrences, coefficients, admission bound and recovery mode are used
 * unchanged; nothing here alters a decision. Not an installed ABI. */
#ifndef LSX_DSD_RESONATOR_H
#define LSX_DSD_RESONATOR_H
#include <stddef.h>
#include <stdint.h>
#include "resonator/dsd64/src/dsd64_iq.h"
#include "resonator/dsd128/src/dsd128_iq.h"

typedef struct {
  uint32_t native_hz;
  union {dsd64_iq dsd64; dsd128_iq dsd128;} u;
} lsx_dsd_resonator;

/* Status codes are the kernels' own; both rates share one numbering. */
enum {
  LSX_DSD_RESONATOR_OK = DSD64_IQ_OK,
  LSX_DSD_RESONATOR_ARGUMENT = DSD64_IQ_ARGUMENT,
  LSX_DSD_RESONATOR_ENVIRONMENT = DSD64_IQ_ENVIRONMENT,
  LSX_DSD_RESONATOR_INPUT = DSD64_IQ_INPUT,
  LSX_DSD_RESONATOR_STATE = DSD64_IQ_STATE,
  LSX_DSD_RESONATOR_OVERFLOW = DSD64_IQ_OVERFLOW,
  LSX_DSD_RESONATOR_PROOF_BREACH = DSD64_IQ_PROOF_BREACH
};

int lsx_dsd_resonator_supported(uint32_t native_hz);
/* Exact certificate SHA-256 the kernel was generated from, or NULL. */
const char *lsx_dsd_resonator_identity(uint32_t native_hz);
int lsx_dsd_resonator_init(lsx_dsd_resonator *, uint32_t native_hz);
/* Unchecked production entry point, as certified: one signed bit per
 * native binary64 sample. All-or-nothing rejection of invalid input. */
int lsx_dsd_resonator_process(lsx_dsd_resonator *, const double *input,
    int8_t *output, size_t n);
void lsx_dsd_resonator_counters(const lsx_dsd_resonator *,
    uint64_t *recovery_entries, uint64_t *recovery_steps);
#endif
