/* P20 candidate DSD512 v2, independent exact-clock identity.
 * The seven-order CLANS-7 binary64 coefficient words come unchanged from
 * the historical DSD256 recurrence. P19's DSD1024 candidate remains frozen.
 * A new DSD512 rate binding requires separate qualification; this is not
 * a production profile or authorization to enable writing. */
#ifndef LSX_SDM_P20_CANDIDATES_H
#define LSX_SDM_P20_CANDIDATES_H
static const sdm_filter_t lsx_sdm_p20_dsd512 = {
  {0x1.1b366e8f27ddap+0, 0x1.b04456dc422ccp-2, 0x1.35151cf8c016fp-4, 0x1.cf72919034587p-8, 0x1.723e910875961p-12, 0x1.2a85751a0c7fep-17, 0x1.f1efaf5000004p-25, 0x0.0p+0},
  {0x0.0p+0, 0x1.a02758c7c8842p-16, 0x0.0p+0, 0x1.5b5129d78fd7ep-14, 0x0.0p+0, 0x1.1c7c78184b489p-13, 0x0.0p+0, 0x0.0p+0},
  7, 22579200u, "clans-7-p20-dsd512", 0, 0, 0
};
#endif
