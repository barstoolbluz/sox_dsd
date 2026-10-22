# DSD512: comparative noise-transfer-function study (2026-10-22)

**Disposition: RESEARCH PASS / NOT A PRODUCT QUALIFICATION.** Eight separately designed order-4–7 NTFs were evaluated using the real DSD512 encoder, followed by seven constrained seventh-order resonator sweeps. The current P20 CLANS-7 remains unchanged. One SDM-7 variant merits independent qualification; none is authorized for production.

## Design question and method

At 22,579,200 native bits/s, can an order-4, -5, -6, or -7 modulator reduce quantization residual over an extended ultrasonic band while retaining low-band fidelity, finite states, an admissible 28-bit-window population and reasonable computational cost?

All candidates use the **existing scalar `sdm_normal_step_impl` recurrence**, input SRC, 176,400-Hz working rate, 61-tap mastering prefilter and final scale 0.5. The experimental filters exist only in disposable instrumented builds, never as enabled product profiles. The unmodified P20 v2 CLANS-7 was rerendered as the reference, reproducing the archived F64 bitstream SHA-256 exactly.

The linearized NTF for the frozen recurrence is

```
s[n] = M s[n-1] + e0 (x[n] - y[n-1])
v[n] = x[n] + a^T s[n]
y[n] = Q(v[n])
NTF(z) = det(zI-M) / det(zI-M+e0 a^T)
```

The signs and feedback delay follow `src/sdm.c`; `M` contains the original alternating resonator terms `g`. The derivation assumes an *additive quantizer error* and does not describe nonlinear one-bit overload or idle cycles. The NTF pole radius and `H_inf` are screening heuristics, **not stability proofs**. Reference methodology: Schreier-style NTF synthesis and the Lee peak-gain heuristic (see `https://python-deltasigma.readthedocs.io/en/latest/_modules/deltasigma/_synthesizeNTF.html` and `https://pydsm.readthedocs.io/latest/generated/pydsm.NTFdesign.delsig.ntf_schreier.html`). This study does not use those packages to generate or realize a different topology.

Starting at the historical DSD256 `sdm-4` ... `sdm-7` coefficient banks, a bounded log-space optimizer adjusted the positive feedforward `a` terms and the existing nonzero resonator `g` terms. Separate objectives minimized integrated *linearized* NTF power on 0–100 kHz or 0–150 kHz at DSD512. Parameters stayed within [0.6, 1.6] times the seed `a`, and [0.3, 28] times the seed nonzero `g`; sampled peak NTF gain had to remain <=1.61 and pole radius <=0.981. There are three deterministic optimizer starts per objective. Complete binary64 coefficient words, loss traces and analytic metrics are in `designs.json`; `design_ntf.py` can independently redo the search. This bounded search does **not** establish global optimality.

After the initial tests, a separate, explicitly recorded SDM-7 *Pareto sweep* held `a` exactly unchanged and scaled **all nonzero `g`** by 1.25, 1.5, 1.75, 2.0, 2.25, 2.5 or 3.0. It is a fixed-topology resonator-placement sweep, not a new optimization of every coefficient. Exact hex coefficients are in `designs-sweep.json`.

## Reconstruction and measurement validity

- Training signal: the *exact prequantization binary64* 1.6-second 997-Hz P10 stimulus, with 0.4–1.2-second analysis window. The 32-bit equivalent was already shown to have a ~-200.4-dBFS scaled source-quantization floor; all new comparisons avoid that source floor.
- Native bitstreams: all 13 initial candidates and all seven sweep candidates completed the 1.6-second training render (36,126,720 native frames each), with no nonfinite states and zero 28-bit excursions. **This result alone was not used for selection.**
- Reconstruction: frozen 57-tap halfbands for five 2:1 stages; a separately designed 401-tap Kaiser beta=22 final 2:1 FIR from 705.6 to 352.8 kHz. Its response is essentially unity to 150 kHz, with >200 dB attenuation at 200 kHz. A 601-tap/beta=25 alternative changes the integrated comparisons by <=0.13 dB in tested bands. The unchanged 176.4-kHz P20 reconstruction separately reproduces its frozen diagnostic.
- Spectral analysis: fit and remove fundamental and DC; apply a 30-beta Kaiser window to the residual, normalize by window RMS, then integrate disjoint Parseval-checked FFT bands. **A rectangular window was experimentally rejected** because 150–176.4-kHz noise leaked numerically into the extremely quiet lower bands. Both raw counterexample and corrected evidence are retained. All quoted residual values use sine-equivalent RMS dBFS (`20 log10(sqrt(2)*RMS)`), not a certified AES17 noise-floor specification. Narrowband spectral peaks are also recorded for inspection.
- **Input limitation:** the existing source working rate is 176.4 kHz (Nyquist 88.2 kHz). Its mastering prefilter is flat at 40 kHz, -6.0206 dB at 60 kHz and about -209.5 dB at 80 kHz. Thus 100–150-kHz comparisons measure shaped noise, not transmission fidelity of ultrasonic source content. No conclusion about reproduction of source frequencies above 88.2 kHz is possible from this pipeline.

## Results: primary 997-Hz, binary64 stimulus

| Candidate | Residual 0–40 kHz | Residual 40–100 kHz | Residual 100–150 kHz |
|---|---:|---:|---:|
| **P20 CLANS-7 reference** | **-198.30** | **-123.51** | **-99.21** |
| Historical SDM-4 at DSD512 | -166.97 | -122.38 | -105.52 |
| Historical SDM-5 at DSD512 | -189.44 | -133.45 | -112.83 |
| Historical SDM-6 at DSD512 | -211.90 | -144.50 | -120.10 |
| Historical SDM-7 at DSD512 | -221.93 | -152.22 | -123.98 |
| Optimized order 4 / 100 kHz | -143.66 | -138.09 | -113.61 |
| Optimized order 5 / 100 kHz | -157.59 | -154.17 | -121.74 |
| Optimized order 6 / 100 kHz | -174.76 | -170.41 | -130.59 |
| Optimized order 7 / 100 kHz | -189.15 | -184.04 | -137.15 |
| Optimized order 7 / 150 kHz | -164.94 | -163.36 | -161.08 |
| **Balanced SDM-7, g x3** | **-200.93** | **-162.20** | **-127.80** |

All values are dBFS in the explicitly stated diagnostic, **not** intrinsic DSD noise specifications. Other optimized 150-kHz variants and seven sweep variants are recorded in the JSON evidence, including those omitted from this compact table.

The initial NTF optimizer optimized *integrated wideband noise* without a nonlinear stability or low-band preservation constraint. This gave large ultrasonic improvements but sacrificed low-band rejection. In particular, the order-7/100k design improved 40–100 kHz by ~60.5 dB relative to P20 while degrading 0–40 kHz by ~9.2 dB. That was a screening observation, not a satisfactory design conclusion.

The **SDM-7 g x3** candidate improves the P20 baseline under the main diagnostic by ~2.63 dB at 0–40 kHz, ~38.69 dB at 40–100 kHz, and ~28.59 dB at 100–150 kHz. This is a *measured same-stimulus comparison*. It has exactly the same computational topology and order as the baseline, so no additional per-bit filter terms are required. It has **not** been proven to be an optimal NTF or a universally better audio encoder.

## Adversarial holdouts and acceptance screening

Eight separately generated 1.2-second source programs: silence, bipolar +/-0.7 DC step, 0.95-peak 997-Hz tone, 0.02-peak 997-Hz tone, 20-kHz and 40-kHz tones, a four-tone program and deterministic bounded random noise. The original 0.7-scale random program produced the **same upstream interpolation-overload failure** (first bad native frame 13,314,649) in baseline and all NTFs, and is retained as a **source rejection control**, not an NTF failure. A new 0.4-scale random program was generated and every shortlisted candidate completed it without failure.

**Critical nonlinear result:** At the 0.95-peak 997-Hz source, *seven of eight optimized order-4–7 designs* became nonfinite after long constant-bit runs: both fourth-order, both fifth-order, sixth-order/150k, and both seventh-order designs. The optimized sixth-order/100k alone completed, but its 0–40-kHz residual on the primary stimulus was -174.76 dBFS, substantially worse than P20. This shows conclusively that sampled pole and Hinf limits do **not** guarantee one-bit robustness.

The balanced **SDM-7 g x3** completed each of the holdouts including the 0.95-peak tone. The P20 baseline also completed them except the common upstream-overload control. The hot 997-Hz case produced a minimum 28-bit one population of **6 in both**; it therefore cannot be used to extend the separate min-7 sustained-gate claim. The balanced candidate did not show the unstable long-run behavior of the aggressively optimized filters.

Independent held-out tone reconstructions (same high-rate FIR, 0.25–0.95-second fit window) corroborated the balanced SDM-7 trend:

| Source | Baseline 0–40 | Balanced 0–40 | Baseline 40–100 | Balanced 40–100 |
|---|---:|---:|---:|---:|
| 997 Hz at 0.95 peak | -194.00 | -201.05 | -123.95 | -162.83 |
| 997 Hz at 0.02 peak | -196.60 | -202.44 | -125.48 | -163.74 |
| 20 kHz at 0.60 peak | -187.70 | -201.09 | -123.35 | -162.48 |
| 40 kHz at 0.60 peak | -191.66 | -201.03 | -123.24 | -162.32 |

All numerical values are dBFS. The input tone fundamentals had matching reconstructed gains for each baseline/candidate pair (0.475 for the hot 997-Hz tone; 0.300 at 20 and 40 kHz after expected source scaling).

### Continuous 32-second mixed-signal screen

The same 32-second signal (4 s each: silence, +0.7 DC, -0.7 DC, four tones, 0.4-scale seeded noise, 0.8-amplitude 997-Hz sine, 0.6-amplitude 20-kHz sine, silence) was rendered in one uninterrupted call per filter: **722,534,400 native frames** each.

| Statistic | P20 CLANS-7 | Balanced SDM-7 g x3 |
|---|---:|---:|
| Result | completed | completed |
| 28-bit min/max one population | 7 / 21 | 7 / 21 |
| 28-bit excursions | 0 | 0 |
| Nonfinite states | 0 | 0 |
| Longest constant-bit run | 5 | 9 |
| Largest seventh state (absolute, dimensionless) | 2,178,440 | 128,906 |
| Host CPU time | 23.73 s | 23.94 s |

The one-run CPU times are **not** a reproducible speed benchmark; the recurrence and per-bit operation count are unchanged. The lower seventh-state magnitude for g x3 is an observation, not a bound across all stimuli. Both remain unqualified candidates.

## Assessment, design implications and handoff

1. **The lower-order premise is not established for these objectives.** Seventh order substantially outperformed tested order-4–6 designs for most extended-band residual comparisons; merely lowering order at DSD512 was not a fidelity improvement. Given the earlier seventh-order stability success, a seventh-order NTF specifically designed for DSD512 is credible.
2. **The current CLANS-7 is not an ultrasonic noise optimum.** The controlled SDM-7 g x3 test shows that redistribution within the same seventh-order recurrence can improve measured 40–150-kHz noise substantially, without sacrificing the original 0–40-kHz integrated performance on the tested sources.
3. **Avoid the seemingly superior unconstrained optimized designs.** Seven of eight fail a modest short-duration high-level signal. Do not deliver, promote or use them as replacement mastering filters.
4. **Candidate for independent next-phase qualification:** SDM-7 g x3. Preserve its exact binary64 coefficient words from `designs-sweep.json`; do not rebuild them from decimal strings. It needs the *full* candidate-specific nominal and adverse-duration soak, independently trained finite-state bounds, adversarial-source validation, media-spectrum and playback-filter review, and a real throughput comparison before authorization. The already closed P20 CLANS-7 soak cannot be transferred.
5. **Separate future architectural question:** if the goal is genuine source fidelity to 100–150 kHz, the 176.4-kHz source working rate and current mastering prefilter must be revisited. That is outside the present NTF-only experiment. It should not be changed merely to improve the study's noise figures.

**No production changes, P00/P15/P17/P18 gate changes, capability enablement, waiver updates, frozen receipts or historic amendments are included.** This study is additive and reproducible; all results preserve failure data rather than filtering it away. The original source archive lacked authenticated Git history, so original revision labels are source-provenance labels, not verified commits.

## Exact materials

- `designs.json` / `designs-sweep.json`: frozen exact hexadecimal coefficient words, optimization traces, reference comparisons, sampled NTF metrics.
- `evidence/renders*/`: each actual 1.6-second native encoder status, packed-bitstream SHA-256, source and disposable-binary digest.
- `evidence/spectrum*/`: Parseval spectra, FIR control comparisons and strongest narrowband FFT bins.
- `evidence/holdouts/`: finite/nonfinite statuses, first failure offsets, source digests, independent tone spectra and 32-second receipts.
- `test_ntf_study.py`: ten standalone integrity and numerical tests.
- `instrument_candidates.py`: inserts experimental-only profiles into a **disposable copied source tree** for native rendering; never alters the delivered original `sdm.c`.
- `REPLAY.md`, `NTF_STUDY_CHECKPOINT_2026-10-22.json`: rerun and resumption information.

See `NTF_STUDY_SHA256SUMS.txt` for all added study files and the existing P20 manifests for the preserved original source/evidence. The packed bitstreams are omitted from the distribution to keep it small; regenerate them from the documented F64 programs and validate their receipt hashes.
