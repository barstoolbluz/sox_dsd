#ifndef DSD128_IQ_H
#define DSD128_IQ_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define DSD128_IQ_RATE 5644800u
/* Version 2 snapshots are deliberately incompatible with version 1. */
#define DSD128_IQ_SNAPSHOT_SIZE 164u
#define DSD128_IQ_INPUT_BOUND 0x1.0000002000000p-1
/* Research-only C ABI. Context fields must not be modified directly by callers.
   Mode is part of the state and is serialized, including its counters. */
typedef struct {
    double state[8];
    uint64_t samples, interventions, checks, recovery_steps, recovery_entries, mode, magic;
} dsd128_iq;
enum { DSD128_IQ_OK=0, DSD128_IQ_ARGUMENT=-1, DSD128_IQ_ENVIRONMENT=-2,
       DSD128_IQ_INPUT=-3, DSD128_IQ_STATE=-4, DSD128_IQ_OVERFLOW=-5,
       DSD128_IQ_PROOF_BREACH=-6, DSD128_IQ_SNAPSHOT=-7 };
/* Native mono binary64 -> signed one-bit samples, no resampling, gain, clipping,
   hard reset or alternate output bit representation. Input/context/output must
   not overlap and must designate accessible objects. All-or-nothing rejection
   for invalid blocks, but PROOF_BREACH (unreachable under proved assumptions)
   may leave a published prefix. The caller must not concurrently mutate
   context or rounding mode. -ffp-contract=off, no fast-math, direct IEEE binary64. */
int dsd128_iq_init(dsd128_iq *ctx);
int dsd128_iq_process(dsd128_iq *ctx,const double *input,int8_t *output,size_t n);
int dsd128_iq_process_checked(dsd128_iq *ctx,const double *input,int8_t *output,size_t n);
int dsd128_iq_export(const dsd128_iq *ctx,unsigned char output[DSD128_IQ_SNAPSHOT_SIZE]);
int dsd128_iq_import(dsd128_iq *ctx,const unsigned char input[DSD128_IQ_SNAPSHOT_SIZE]);
double dsd128_iq_energy(const dsd128_iq *ctx);
const char *dsd128_iq_identity(void);
#ifdef __cplusplus
}
#endif
#endif
