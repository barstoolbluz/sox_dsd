# P15 — final scoped engineering acceptance of ideal-operator spectral transfer

**Decision record:** P15-SPECTRAL-ENGINEERING-2026-10-19  
**Decision date (America/New_York):** 2026-10-19  
**Target authority:** `sox_ng-P15-adjudicate-cc399928.tar.gz` (SHA-256 `d058b3908817e01e937f49e0dfeee7194d847aae74f625043e881d8b8f0e9210`)  
**Governing specification:** `docs/dsd/DSD_DESIGN.md` §8.6.1, SHA-256 `458537dbe9a2ea1e687b68f998f43a90de10c369b604f809c78cf80c2389b94b`  
**Decision:** **ACCEPT the completed ideal-operator spectral evidence for ENGINEERING purposes at the explicitly stated, source-audited computational-interval assurance tier. STOP further routine spectral proof campaigns.**

## 1. What this acceptance actually does

For the exact captured source/operator/profile/rate configurations represented by the original campaign, treat the **spectral-transfer engineering review as closed with accepted and documented computational trusted-base/provenance risks**. No further full-band re-campaign, additional independent per-interval replay, or formal transcendental theorem is required *for this chosen engineering assurance tier* in the absence of a specific defect or changed operator.

This is a **scoped acceptance-method decision**, not a claim of an unconditional theorem. Section 8.6.1's original quantitative criteria are unchanged:

- Passband absolute gain error: **at most 0.0001 dB** across the complete effective band, including applicable coherent aliases.
- Unwanted composite source-stop/folded-alias transfer: **at most -160 dB** relative to unity, including potentially coherent folding families (the original campaign uses a strict `< 1e-8` amplitude pass condition).
- Applicable `adapt`/`strict` passband intersection, operator source identity, and all original eligibility conditions remain unchanged.

The §8.6.1 requirement for independent complete-chain transfer certification is **accepted at a source-audited engineering computation tier**, based on the original interval campaign plus independent adversarial mathematical source audit and the R6–R9 exact-arithmetic cross-checks. If “independent certification” is instead required to mean an *entirely separate, universally qualified, mpmath-free certifier for all 11,516 intervals*, **that stronger formal interpretation is NOT discharged**; the present decision is a narrowly recorded acceptance-policy variance for engineering review, *not* a retroactive assertion of formal proof.

No numeric tolerance, capture, source, production DSP, runtime acceptance requirement, or historical result is waived or altered.

## 2. Evidence accepted

1. **Complete original inventory.** All 11,516 canonical jobs in 72 SRC-active cells are present in a single original archive, with 2,850 reported passband PASS and 8,666 reported source-stop PASS certificates; zero OPEN and zero missing, with the original 0.0001-dB/1e-8 criteria. Every receipt is byte-identical to the authenticated compressed source archive. Source/operator/design bindings and recorded inequalities were independently checked. Inventory SHA-256: `b72841ffb59e5016e12db4360458895223f454271e9d4504e74aa6ee39d34e99`.
2. **Adversarial original-prover audit.** Evaluated exact dyadic coefficient conversion; directed complex interval arithmetic and mpmath's actual implementation; rational alias branch boundaries and multiplicity; composite triangle recurrence; conservative subtree/pruning, halfband, finite-difference majorants, terminal saturation and cache identities. No demonstrated source-level numerical false-PASS defect. Full argument and limits: `docs/dsd/P15_FINAL_ORIGINAL_PROVER_SOURCE_AUDIT_2026-10-19.md`.
3. **Independent exact numerical corroboration.** R6–R9 qualify **1,023 distinct** canonical intervals: 981 source-stop and 42 passband. R9 independently replays **all 958 DSD256 mastering-v2 source-stop jobs** across eight output rates, from a whole-native-cover + SRC branch-norm proof. R7 and R8 intervals are counted with the 23-job R7/R9 overlap removed. Verified R9 replay JSON SHA-256: `4d73a7edbc304bb154ac5fb66cf739e777e0cc5a37a95b49472d6cdd23c6d003`.
4. **Adversarial regression verification.** Existing targeted tests: **41 successful/expected-skip results (2 skipped; zero failures)**. Newly authored source-audit suite: **17 passed, zero skipped**. Historical receipt reader weakness (it accepts a fabricated PASS label with a contradictory numeric upper) is reproduced and contained by an independent **read-only** receipt checker; the actual archived receipts pass that checker. No mathematical false PASS from the certifier has been demonstrated.

**Do not misinterpret (1) as independent mathematical recomputation of 11,516 theorems, or (3) as proof of all passband jobs or other profiles.** The engineering assurance derives from the original source-level correctness argument, directed numerical backend accepted as trusted, complete receipt consistency, and substantial exact-arithmetic independent corroboration together.

## 3. Two explicitly accepted residual risks

**A. Third-party numerical trusted base.** For the original un-recomputed intervals, the source-audited `mpmath.iv` transcendental argument reduction and outward error guard are assumed to enclose the mathematical values at the encountered anchors. Elementary directed arithmetic and the recurrence are separately justified, and independent exact arithmetic supports representative and structurally difficult cases. Universal proof of the transcendental guard for all possible anchors has **not** been established. This is an explicit engineering assumption, not a finding of incorrect enclosure.

**B. Historical execution identity.** The immutable campaign receipts demonstrably belong byte-for-byte to the SHA-verified original archive and match its recorded method/source/operator identities. The archives do **not** cryptographically prove the complete historical Python/`mpmath` runtime/code/host used to compute each certificate. Accept this bounded provenance limitation as engineering evidence; do not falsely report historical execution attestation.

Under either assumption becoming false, the affected claim must be reopened, not silently grandfathered.

## 4. Final gate classification: do not collapse categories

| Item | Final classification at this decision | Meaning |
| --- | --- | --- |
| Original full-band spectral receipt inventory | **PASS as historical coverage/integrity inventory** | Reports, not 11,516 independent math replays |
| Independent exact spectral claims | **PASS within their R6–R9 demonstrated scopes** | 1,023 unique intervals; R9 eight-cell source-stop factorization |
| Global ideal-operator **unconditional mathematical proof** | **CONDITIONAL** | `mpmath.iv` universal transcendental enclosure and historical process correspondence not demonstrated |
| Ideal-operator **engineering spectral acceptance** | **ACCEPTED — SCOPED ASSURANCE/RISK DECISION** | Completed work; no continuing interval campaigns authorized by this review |
| Actual release's arbitrary-input FFT4G roundoff and same-operator finite transfer | **NOT DISCHARGED** | Independent, mandatory §8.6.1 release-execution requirements |
| Source/build/final ELF/host transferability, other P15 release checks | **NOT GRANTED BY THIS DECISION** | Review each existing receipt/gate separately |
| **Overall P15 release authorization** | **OPEN / NOT AUTHORIZED** | Do not promote release or v2 default based on this spectral record |

This record **supersedes earlier recommendations to keep generating spectral proofs** for these unchanged, audited operators, *at this accepted engineering assurance tier*. It does not rewrite the historical R9 mathematical-gate classification or §8.6.1 release-execution contract.

## 5. Reopen criteria: specific, not speculative

Reopen the spectral engineering gate only on (a) a reproducible false-PASS numerical counterexample or broken source-level invariant; (b) verified failure of the relevant `mpmath.iv` trusted-base assumption; (c) changed binary64 FIR taps, SRC stage topology, ratios, governing design or acceptance bounds; (d) demonstrably incorrect historical receipt/source correspondence; or (e) an **explicit, authorized policy change** demanding a stronger assurance tier. A hypothetical possibility of constructing additional proofs, alone, is not a reopen criterion.

**Disposition:** End the spectral certification campaign for this immutable source. Preserve the evidence and route release work only to the already-separate, unsatisfied execution/binary/host obligations. Do not claim the *whole project* is release-ready.
