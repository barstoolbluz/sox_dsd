/* Production high-rate mastering SDM-8 tables, selected 2026-11-13.
 * SDM256 feedback coefficients a are unchanged. Rate-specific zeros g use
 * (k/m)^2, with k=1.75 for DSD512 and k=2 for DSD1024 relative to DSD256.
 * Coefficient provenance: observed/round03/tables/tables.diff in the
 * 2026-11-13 one-encoder handoff. No P17 generator or historical
 * qualification certificate is rewritten by this selection. */
#ifndef LSX_SDM_MASTERING_HIGHRATE_H
#define LSX_SDM_MASTERING_HIGHRATE_H
static const sdm_filter_t lsx_sdm_mastering_highrate[2] = {
  {
    {0x1.7c12a0afe3005p-1, 0x1.170ca689a451ap-2, 0x1.06ba2f75adc4ep-4, 0x1.590b8c91dea79p-7, 0x1.42e781a5ecd18p-10, 0x1.a153b43db31a0p-14, 0x1.5861db5c3affbp-18, 0x1.02b31c1effff5p-23},
    {0x1.045e7add55492p-18, 0x0.0p+0, 0x1.0b20f18f227f8p-15, 0x0.0p+0, 0x1.32ed6143a4873p-14, 0x0.0p+0, 0x1.bdf1b3c55cfdap-14, 0x0.0p+0},
    8, 22579200u, "sdm-8-dsd512", 0, 0, 0
  },
  {
    {0x1.7c12a0afe3005p-1, 0x1.170ca689a451ap-2, 0x1.06ba2f75adc4ep-4, 0x1.590b8c91dea79p-7, 0x1.42e781a5ecd18p-10, 0x1.a153b43db31a0p-14, 0x1.5861db5c3affbp-18, 0x1.02b31c1effff5p-23},
    {0x1.5412e99e79d7bp-20, 0x0.0p+0, 0x1.5ce71c28aa725p-17, 0x0.0p+0, 0x1.90e274970b238p-16, 0x0.0p+0, 0x1.233a94bf958b8p-15, 0x0.0p+0},
    8, 45158400u, "sdm-8-dsd1024", 0, 0, 0
  }
};
#endif
