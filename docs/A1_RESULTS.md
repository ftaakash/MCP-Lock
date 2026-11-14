# Addendum A1 results: locked-server age exemption on post-freeze data (2026-11-15)

**Plan:** `docs/PREREG_ADDENDUM_AGE.md`, filed on OSF as an update to osf.io/2amj3 on 2026-11-15, before this run.
**Scored code:** `age-x-v1.1`, run from commit `271a14e`. **Scoring:** `eval/scoring/a1.py`.
**Outputs:** `results/{baseline,candidate}/a1/runs/`, `results/candidate/a1/a1_results.{json,md}`.

**Corpora:** versions published 2026-10-09 to 2026-11-07.
- B′: 2,653 benign upgrades (2,209 MCP, 230 npm top, 214 PyPI top).
- R-M′: 199 primary real attacks (42 hijacked existing packages, 157 new or typosquatted names).
- Lookup failures: 0 in every system.

## Confirmatory tests (G-X vs S1-charitable)

| Test | Corpus | G-X | S1-C | Discordant (G-X only / S1-C only) | p (Holm) |
|---|---|---|---|---|---|
| **A-H2** false blocks | B′ | **0.53%** [0.31, 0.88] (14) | 10.48% [9.37, 11.70] (278) | 14 / 278 | 1.4 × 10⁻⁶⁴ |
| **A-H1** detection | R-M′ | **52.3%** [45.3, 59.1] (104) | 56.3% [49.3, 63.0] (112) | 0 / 8 | 0.0078 |

**Paired differences, G-X minus S1-C (Newcombe 95% interval):**
- false blocks: −9.95 pp [−11.20, −8.78]
- detection: −4.02 pp [−6.72, −1.30]

**Claim rule: not met.**
- A-H2 is significant with G-X lower.
- A-H1 is significant in the **wrong direction**: G-X detects 8 fewer attacks than S1-C.
- Under the registered rule, the exemption is **not confirmed as a deployable default**.

## What happened

- **The 8 lost detections:**
  - All 8 are hijacked packages (class C).
  - The baseline caught each one **only** through the 30-day age rule (`new_package`): the package was young when it
    was hijacked, and the lock had already been made.
  - G-X waives exactly that rule for locked packages, so it misses them.
- **Hijacked packages overall:**

  | System | Hijacked packages caught (of 42) |
  |---|---|
  | S1-C | 8 |
  | G | 8 |
  | G-X | 0 |

  - The checks S2–S5 added nothing on these 42.
  - Only 1 of the 42 had every signal evaluable, because the malicious versions were removed from the registries, as in
    Phase 4.
- **New or typosquatted names:** all systems detect 104/157. The exemption does not touch them: there is no lock entry,
  so the age rule stays on.
- **Benign cost:**
  - G-X removes 278 of the 292 false blocks G makes (both directions: 278 G only, 0 G-X only).
  - It also raises warnings from 23.1% to 27.8%; interruptions are 28.4% vs 34.1% for G.
  - Nearly all warnings come from tool-definition drift (S5): without S5, G-X interrupts 0.68% of upgrades.
  - By stratum, G-X false blocks are 13/2,209 MCP, 0/230 npm and 1/214 PyPI.
- **Cluster bootstrap** (MCP stratum by package, seed 20261114), G-X false blocks: [0.27%, 0.83%].

## Reading

- **The trade-off is now measured, not assumed.** On fresh data, the exemption removes about 95% of false blocks
  (10.5% → 0.5% against the baseline). The cost is the attacks that only the age rule catches: young packages hijacked
  soon after a user locked them. Here those were 8 of 42 hijacked cases (19%).
- **Detection of hijacked packages depends almost entirely on the age rule in both new and old data,** because removed
  malicious versions leave the provenance, publisher, install-script and tool checks nothing to compare.
- **For the paper:**
  - Report A1 as a pre-registered test whose claim rule failed.
  - Present the exemption as an explicit trade-off, not a default.
  - A narrower variant (for example, waive the age rule only after the lock is older than N days) would be new
    exploratory work and would need new data.
- **Descriptive, not tested:** S1-C's false-block rate on B′ (10.5%) is lower than on the Phase 4 corpus (32.9%).
  B′ covers 30 days instead of 90, and has fewer young MCP servers at upgrade time.
