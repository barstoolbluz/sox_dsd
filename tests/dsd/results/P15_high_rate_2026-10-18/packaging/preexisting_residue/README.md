# Unsubmitted residue preserved after packaging stopped

The first packaging attempt correctly refused an unexpected file outside the new evidence directory. It was absent from the submitted archive and present byte-identically in the baseline and three working/frozen trees. The 4,718,592-byte RIFF payload is preserved here; its RIFF header advertises 5644880 total bytes, so this is not a complete waveform. Its original generation provenance is not assumed. Only the extra work-tree pathname was moved; all original archive files and the other tree copies remain unchanged.

`PRESERVATION.json` records source locations, identities, metadata, and the failed partial archive. The partial archive did not pass validation and is not a deliverable. The numerical proof, source/operator bindings, and existing receipts are unchanged.
