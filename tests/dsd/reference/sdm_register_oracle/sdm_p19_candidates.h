/* P19 exact-rate experimental DSD1024 SDM correction: profile v2 only.
 * Source coefficients: historical sdm_filters[6] (CLANS-7, DSD256);
 * identical binary64 words, re-keyed to 45158400 Hz. The reduced order
 * changes the quantizer recurrence and requires independent qualification.
 * The v1 eight-order candidate and qualified <=DSD256 paths are unchanged.
 */
#ifndef LSX_SDM_P19_CANDIDATES_H
#define LSX_SDM_P19_CANDIDATES_H
static const sdm_filter_t lsx_sdm_p19_dsd1024 = {
  {0x1.1b366e8f27ddap+0, 0x1.b04456dc422ccp-2, 0x1.35151cf8c016fp-4, 0x1.cf72919034587p-8, 0x1.723e910875961p-12, 0x1.2a85751a0c7fep-17, 0x1.f1efaf5000004p-25, 0x0.0p+0},
  {0x0.0p+0, 0x1.a02758c7c8842p-16, 0x0.0p+0, 0x1.5b5129d78fd7ep-14, 0x0.0p+0, 0x1.1c7c78184b489p-13, 0x0.0p+0, 0x0.0p+0},
  7, 45158400u, "clans-7-p19-dsd1024", 0, 0, 0
};
#endif
