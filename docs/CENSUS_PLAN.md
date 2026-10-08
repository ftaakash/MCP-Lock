# Phase 2 census protocol (fixed 2026-10-09, before any Phase 2 data collection)

Scope chosen by Aakash on 2026-10-09: **hybrid**. A literal full census (every package × every
version) would need ~250 GB of archives, more than the 115 GB free disk.

## Part M: metadata census (all eligible packages)
- **Population:** all 15,272 eligible packages of the frozen frame (`frame_2026-10-08`, sha256 `905cc9d7…`).
- **Data:** full npm packuments; PyPI JSON plus the PyPI integrity API (per-file provenance). No archives.
- **Unit:** a *transition*, i.e. a consecutive pair (v_{i-1}, v_i) in version-precedence order, with v_i
  published in the **12-month window 2025-10-08 → 2026-10-08**.
- **Signals per transition:**
  - provenance lost (attested → not attested), npm and PyPI;
  - provenance gained;
  - publisher account changed (npm `_npmUser`);
  - maintainer set changed (npm `maintainers`);
  - new install script (npm `preinstall` / `install` / `postinstall` / `prepare`).
  PyPI exposes no per-release uploader or maintainer history, so S3-type signals are npm-only (stated limitation).
- **Estimates:**
  - share of transitions with each signal;
  - share of packages with ≥ 1 such transition;
  - per ecosystem, with Wilson 95% CIs.
  This is a census of the frame, so the CIs describe sampling variability only for generalization beyond the frame.

## Part T: tool-definition drift (stratified sample, n = 2,000)
- **Sample:** `census.sample` with n = 2,000 and the same seed (20261008) and strata. The per-stratum permutations are
  identical, so the pilot's 200 packages are an exact subset. Allocation: npm 1,467, PyPI 533, equal terciles.
- **Versions:** as in the pilot. G1 uses the 10 most recent versions; G2 uses versions in the 90-day window
  2026-07-10 → 2026-10-08 plus each one's predecessor (cap 40).
- **Archives** are streamed: fetched, digest-verified, extracted, then deleted. Only extraction records and digests are kept.
- **Primary RQ1 estimates (weighted to the frame, stratified cluster bootstrap 95% CI, plus Wilson):**
  1. share of packages with ≥ 1 tool-definition change in the 90-day window;
  2. share of window transitions with a tool change, among extractable pairs;
  3. co-occurrence of tool changes with each Part M signal on the same transition: rates, and
     Fisher's exact test against transitions without tool change.
- **Robustness:** exclude pre-releases; count name/description changes only; npm only.

## Extractor revision and held-out validation
1. **Development set:** validation harness v1 + v2 results (all packages attempted there).
2. Revise PyPI extraction (dynamically and conditionally registered tools) using **only** development-set failures.
3. Freeze extractor version `extract-v2` (git tag) **before** running Part T.
4. **Held-out validation (harness v2):** packages from the n = 2,000 sample that were never attempted in v1 or v2,
   in seeded order, target 40 per ecosystem. Report precision / recall / exact-set / detection with Wilson CIs
   and the started-vs-not-started bias check. Development-set accuracy is reported separately and labelled as such.

## Stop conditions
- Live malicious drift: stop and report to Aakash.
- A measurement error that invalidates the pilot's kill-test numbers: stop and report.
