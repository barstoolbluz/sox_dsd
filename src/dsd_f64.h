/* Phase 04 private precision-policy vocabulary. No native runner exists yet. */
#ifndef LSX_DSD_F64_H
#define LSX_DSD_F64_H
#include "sox_ng.h"
typedef enum {
  LSX_PRECISION_AUTO = 0, LSX_PRECISION_64, LSX_PRECISION_32
} lsx_precision_policy;
/* Query only the getopts-populated state. Does not run the gain effect. */
int lsx_gain_plain_fixed(const sox_effect_t *effect, double *factor);
#endif
