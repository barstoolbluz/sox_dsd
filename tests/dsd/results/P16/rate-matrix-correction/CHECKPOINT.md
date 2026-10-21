# P16 correction checkpoint — October 20, 2026

Status: implementation and focused qualification COMPLETE; delivery packaging external to the source tree.

## Corrected source

- Original test SHA-256: `102865ded3920ba6c660943360cbd6017e14a329162fa00591d8f3cf983ad037`
- Corrected test SHA-256: `fa2164e986c262d27edd4c03cc373d6d40c68dd6795d192cc5261695c40d87f9`
- Only this test and the P16 handoff changed among 28 inventoried source inputs. Production reader, decoder, CLI, and writer files are unchanged from the supplied P16 bundle. The P00 index and P15 admissions are unchanged.

## Executed gates

- `make -C test dsd_test_p16`: exit 0
- `./test/dsd_test_p16 matrix`: exit 0; 6,480 cases, 1,480,320 assertions, 0 unsupported
- `./test/dsd_test_p16`: exit 0; 4,695,450 blocks, 183,833,677 assertions, 10 malformed descriptors rejected
- `make check-dsd DSD_PHASE=P16`: exit 0; runner 38 pass, CLI 219 pass
- `make check`: exit 0
- `make check-rename`: exit 0
- Original five-part archive: verify-only, fresh assembly, repeat-assembly all exit 0; SHA-256 `68f600ae039df9a53aabd54512dea853ba268c4e31fb4c2a4b44f8eb834ac839` (500,770,021 bytes)
- Corrected 28-input source inventory: PASS; historical P00 index unchanged

## Interruption recovery and delivery

This source tree is the corrected implementation. `CORRECTION_QUALIFICATION.json`, raw command logs and the small test patch in this directory are authoritative local qualification artifacts. Both the original self-generated P16 source inventory and the new post-correction inventory are retained separately. The original source archive is not modified; delivery may use a newly assembled, separately checksummed complete archive or apply the small test/evidence overlay to the original P16 archive. The packaging manifest is an **external sidecar** and must accompany parts and the byte-identical `reassemble.py`. Do not mix manifests or parts from different deliveries.

Two standing P15 proof obligations remain open, as before. No new writer capability is authorized or enabled.
