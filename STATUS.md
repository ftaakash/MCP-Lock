# STATUS

## Phase 0: setup (2026-10-08)
- Created the repo skeleton.
- Read-only analysis of the Bagmar & Saraf 2026 hook: `analysis_outputs/SUMMARY.md`, `analysis_outputs/RISKS.md`.
  The source code is NOT publicly available (the linked repo returns 404); the analysis is based on the paper (Sec. 9.3, Appendix I).
- Census pilot sampling plan proposed in `docs/PILOT_SAMPLING_PLAN.md`; **awaiting approval**.

## Open risks
- Baseline code unavailable, so S1 must be reimplemented from the pseudocode; parity is "to spec", not "to code".
- Only Python 3.14 is installed; the project targets 3.11.

## Next gate
Phase 1 pilot KILL test: extractability >= 60% of versions AND >= 5% of packages change tools within 90 days (Wilson 95% CIs).
