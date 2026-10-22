/* Frozen P19 DSD1024 v2 clock-specific training bounds. NOT qualification.
 * Distinct from immutable P10/P17 guard rows. Holdout cannot retune them. */
#ifndef LSX_PCMDSD_V2_GUARDS_H
#define LSX_PCMDSD_V2_GUARDS_H
static const double lsx_pcmdsd_v2_guards[8] = {
  0x1.0000000000000p+5, 0x1.0000000000000p+6, 0x1.0000000000000p+9, 0x1.0000000000000p+12, 0x1.0000000000000p+16, 0x1.0000000000000p+20, 0x1.0000000000000p+26, 0x1.0000000000000p+4
};
#endif
