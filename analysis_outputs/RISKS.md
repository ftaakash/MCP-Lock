# Risks and suspicious patterns (heuristics, unverified against code)

All items come from the pseudocode in Appendix I. They are **not** confirmed bugs, because the code
is unavailable.

| # | Observation | Why it matters | Confidence |
|---|---|---|---|
| R1 | Source trust uses `t in u` substring matching | `https://pypi.org.attacker.example/simple` or `https://evil.example/?pypi.org` would pass. This is a candidate adaptive attack for RQ3 against S1, if the real code matches the pseudocode. | Medium (pseudocode may simplify) |
| R2 | Name proximity is limited to distance 1 / transposition / separator normalization | Distance-2 squats, homoglyphs, combosquats (`requests-toolbelt-pro`) and scope confusion on npm (`@scope/x` vs `x`) are uncovered. | High (stated explicitly) |
| R3 | Any warning blocks, with no warn tier | The false-block rate is the same thing as the flag rate. A fair comparison with our allow/warn/block gate must report both "block-only" and "block+warn" operating points. | High |
| R4 | Evaluation equals construction set (R1–R11) | Their 10/11 is not a generalization estimate. Our corpora (OSV MAL-, synthetic rug pulls) are the real test, and S1 may drop sharply there. That would be a finding, not unfairness. | High (authors say so) |
| R5 | Popular set P is unspecified | The false-positive rate depends heavily on the size of P. We must choose P and report sensitivity (for example top-1k / 5k / 10k). | High |
| R6 | Check 3 (age < 30 d) blocks every brand-new legitimate package | Likely a major driver of false blocks on MCP servers, many of which are young. Measure separately. | Medium |
| R7 | Check 7 needs `p==v` | Unpinned and range specs (`>=`) are skipped, which is the dominant form in MCP launch lines. | High |
| R8 | Hook mediates the command string only | `npx -y pkg` resolves to "latest" at run time, so a version published after the check (TOCTOU) is not covered. MCP-Lock must pin the resolved version. | High |

## Process risks for us
- **Baseline unavailable**: parity cannot be bit-exact. Mitigation: implement from the spec, list
  deviations, ask the authors for code.
- **Paper version**: v1 (16 Jul 2026). Re-check arXiv for v2 or a code release before Phase 3.
