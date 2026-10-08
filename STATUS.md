# STATUS

## Phase 0: setup (2026-10-08), done
- Created the repo skeleton.
- Read-only analysis of the Bagmar & Saraf 2026 hook: `analysis_outputs/SUMMARY.md`, `analysis_outputs/RISKS.md`.
  The source code is NOT publicly available (the linked repo returns 404); the analysis is based on the paper (Sec. 9.3, Appendix I).
- Census pilot sampling plan **approved** (`docs/PILOT_SAMPLING_PLAN.md`), including the decision rule
  (point estimate; extend once to n=400 if the 95% CI straddles the threshold) and the two-stage dynamic check.
- Python 3.11.9 installed (user scope, via winget).
- Kapner et al. verified (arXiv:2609.07360v3): 9.8% (260/2,660) setups unpinned. See `docs/CITATIONS_VERIFIED.md`.

## Open risks
- Baseline code unavailable, so S1 must be reimplemented from the pseudocode; parity is "to spec", not "to code".
  Email to the corresponding author sent 2026-10-08 (code, scenarios, P list, Table 8 scoring); awaiting reply.
- Static extraction from bundled/minified npm `dist/` may push G1 toward the 60% kill line.

## Next gate
Phase 1 pilot KILL test: G1 extractability >= 60% of versions AND G2 >= 5% of packages change tools within 90 days (Wilson 95% CIs).
