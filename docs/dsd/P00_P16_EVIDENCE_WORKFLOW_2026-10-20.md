# P00 → P15 → P16: handling routine edits without rewriting history

**Status:** engineering workflow guidance, 2026-10-20. Not a release
certificate or a replacement for a P16 acceptance contract.

## Three different objects

1. **P00 is the historical index** at
   `tests/dsd/results/P00/P00_SHA256SUMS.txt`, SHA-256
   `f3b06a48cae0e0bb451c8bac0a476364dea3017d82c66d9dd1b2abaf2b9aac4f`.
   It describes a particular evidence snapshot, including missing bulk payload
   digests. The accompanying `REVIEWED_P00_INDEX_SHA256` protects its identity.
   Do **not** regenerate either one for ordinary P16 development.
2. **The P15 operator rebind is an exact, reviewed exception**, anchored to
   original P00 preimages and the 2026-10-20 C exporter recapture. Its
   32 admitted current revisions have a fixed meaning, not a general
   `--approve-drift` bypass. The subsequent sixteenth-test amendment is one
   more review decision covering one different digest of *the same test*.
3. **The P16 working tree is a moving engineering revision.** Its changes do
   not retroactively change P00 or expand the P15 admission. They must not be
   labeled certified merely because old tests, snapshots, or interval receipts
   still exist.

## Normal P16 iteration

Edit, build, test, and commit normally. You do **not** need a new audit directory
for every developer edit. To see P00-indexed drift relative to the P15 admitted
baseline without granting acceptance, run:

```sh
python3 scripts/p16_dev_input_drift.py
python3 scripts/p16_dev_input_drift.py --include path/to/new/P16/file.c
```

For a **review checkpoint**, use `--out
P16_DEV_CHECKPOINT_YYYY-MM-DD.json` and commit the generated report along with
source changes. The tool records SHA-256 and absent-file states, identifies
in-scope P00-indexed drift, and can be rerun idempotently. The report explicitly
**does not** certify a complete input closure, qualify P16, or grant exceptions
to the historical P15 current-source gate. List new/non-P00 inputs with
`--include` or in the reviewed P16 input manifest; otherwise they are not
covered by the drift report. Git commit identity is useful provenance but is
not a mathematical proof.

## At P16 acceptance / new evidence production

Freeze the exact source and toolchain revision. Create a distinct P16 manifest
with an externally reviewed digest, a complete input closure (including any
new files, build options, generated artifacts and toolchain relevant to the
claim), a version link back to P00/P15, and the new tests and obligations to
re-run. Check which P15 theorems and measurements are reusable, which need
fresh qualification, and which have materially changed semantics. A stage
snapshot matching byte-for-byte alone does *not* establish all full-chain DSP
behavior. Never reassign old 11,516 historical certificates to a new source
identity without adequate independent evidence.

If the workflow requires historical **P15** certification, verify that evidence
against the **frozen historical P15 revision**, rather than running the
`p15_current_closeout` source-identity check against an actively modified P16
tree. `p15_current_closeout` must continue to refuse unadmitted P00-indexed
changes in a current working tree; its refusal is a valid warning, not a
reason to bless arbitrary edits. `--approve-drift` in the operator tool only
approves exact, inspected changes to the *35 operator source pins*, subject to
stage recapture, and has no authority over arbitrary P00-indexed sources.

## When an existing P15 admission itself must change

A genuinely reviewed replacement of an already admitted P15 file needs an
**explicit successor admission**, preserving its prior admitted digest and
frozen historical P00 preimage. For this one-off:

```sh
python3 scripts/verify_p15_sixteenth_readmission.py --inventory
```

The predecessor ledger is preserved verbatim in
`tests/dsd/results/P15_SIXTEENTH_READMISSION_2026-10-20/BEFORE_ADMISSION.json`.
The original 32-entry admission remains in its original dated directory,
but its one current digest was changed under the separately recorded decision.
An independent `verify_p15_sixteenth_readmission.py` pins both revisions and
refuses unrelated changes. This repair must not become a template for
unreviewed self-approval or repeated mutation of the P15 ledger. More P15
admissions should instead be handled as separately anchored successor records
with a generalized, independently reviewed gate at the next planned review.

**Prohibited shortcut:** recomputing `P00_SHA256SUMS.txt` and changing
`REVIEWED_P00_INDEX_SHA256` in lockstep. Two mutually self-updated local hashes
have no continuity of the originally reviewed evidence.
