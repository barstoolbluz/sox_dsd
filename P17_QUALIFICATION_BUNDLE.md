# P17 qualification bundle — 2026-10-21

Entry point: `docs/dsd/handoffs/P17_QUALIFICATION_2026-10-21.md`.

Resume and replay: `docs/dsd/handoffs/P17_QUALIFICATION_RESUME_2026-10-21.md`.

Base source `sox_dsd/main` 2bda0491 (asserted in supplied manifest; no `.git`), input tar.zst SHA-256 `8a0f2ccbbdb3534b101880c5eebc25c5690259347513933ac67a49b8cc6ea377`.

This is a **source working-set qualification bundle**, not a build with enabled high-rate capabilities. First three P10 bound rows, original P10 certificate, and all twelve P18 high-rate deny rows preserved. DSD512 encode holdout passes but no sustained qualification. DSD1024 encode contains real nonfinite/guard-bound failures and remains blocked. Four reconstructors need licensed whole-file and independent reference audio.

This bundle intentionally excludes the licensed 23 GB DSD512 media and the 49,662 historically omitted paths (including 1,351 `.npz`). Original inventory manifests retained in `input-manifests/`. Byte-bound test receipts are under `tests/dsd/results/P17_qualification_2026-10-21/` and the six candidate hashes under `tests/dsd/reference/p17_qualification_certificates.json`. Linux training and holdout executables are carried strictly as evidence.

See `P17_BUNDLE_SHA256SUMS.txt` for SHA-256 of every packaged file except that self-referential manifest. A separate outer `.sha256` verifies the compressed archive.
