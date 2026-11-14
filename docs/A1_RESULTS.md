# Addendum A1 results: locked-server age exemption on post-freeze data (2026-11-15)

**Code:** branch `age-x` (on `main` only the results and documents are kept).
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

## Follow-up 1 (exploratory): is there a better threshold? (`eval/adaptive/age_tradeoff.py`)

Each variant waives the age rule for a locked package only when a condition holds. It re-decides the frozen gate G's
stored findings. These data have already been seen, so none of this is confirmatory.

**Package age at upgrade time ≥ d days:**

| d (days) | Phase 4 false blocks | Phase 4 hijacked caught (of 368) | A1 false blocks | A1 hijacked caught (of 42) |
|---|---|---|---|---|
| 0 (= G-X) | 0.73% | 108 | 0.53% | 0 |
| 1 | 9.74% | 108 | 0.53% | 0 |
| 7 | 19.96% | 108 | 0.75% | 0 |
| 14 | 26.09% | 110 | 2.04% | 2 |
| 21 | 29.43% | 115 | 4.33% | 4 |
| 30 (= G) | 33.36% | 116 | 11.01% | 8 |

**Locked version's age ≥ d days:**
- In Phase 4, false blocks jump from 0.86% (d = 0) to 21.81% at d = 1.
- In A1 they jump from 0.53% to 5.01%.
- Hijacked caught rise only from 108 to 112 and from 0 to 2.

**Reading: no threshold gives a middle ground.**
- The age rule's false blocks and its hijack detections come from the same population, packages younger than 30 days,
  so any threshold trades one for the other almost linearly.
- The two datasets disagree on where the false blocks are:
  - Phase 4's benign MCP upgrades include many packages under a day old, so even d = 1 brings back about 10% false blocks.
  - In A1 the false blocks only come back from d = 14.
- A threshold tuned on one dataset would not carry over to the other. We do not recommend pre-registering any threshold
  variant.

## Follow-up 2 (exploratory): are the 8 missed cases real hijacks? (`results/candidate/a1/lost8_review.json`)

Only registry metadata and OSV record headers were read, inside Docker. GHSA's boilerplate calls every affected machine
"compromised", so that word is not evidence of an account takeover.

| Package | Age at attack (days) | Assessment | Evidence |
|---|---|---|---|
| tailwindcss-hook-forms | 13 | likely attacker-owned (typosquat) | advisory: impersonates `@tailwindcss/forms`; only a placeholder version before the malicious one |
| overarch-windows-x64-yr | 22 | likely attacker-owned | one version, then three malicious versions three weeks later |
| @adminide-stack/forms-core | 14 | likely real compromise | the same campaign hit 5 packages of the scope on 3–4 Nov, one of them published since 2017 |
| @ai-ecoverse/slicc-windows-amd64, kampodra, local-commander-agent, modelsdesk, paidwithtab | 9–26 | undetermined | active young projects (8 to 180 versions); metadata cannot tell a takeover from a long con |

- **Class rule:** at least 2 of the 8 look misclassified by the mechanical rule (a threat to validity already listed in
  the paper).
- **Sensitivity with those 2 moved to class N:**
  - They would have no lock, so G-X would keep the age rule and catch them.
  - G-X would then miss 6, not 8 (exact two-sided p = 0.031; still significant after Holm).
  - **The confirmatory conclusion does not change.**
