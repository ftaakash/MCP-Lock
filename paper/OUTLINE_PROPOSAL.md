# MCP-Lock paper: compliance check and proposed outline (for approval, 2026-11-04)

The current paper is `paper/main.tex` (IEEEtran `conference`, double column, 6 pages, 30 bibliography entries).
It is checked here against the 13 required sections and the deliverables. Nothing below changes any result.
Every number already comes from `paper/numbers.tex`, which is generated from the result files.

## 1. Compliance check of the current paper

| # | Required | Current paper | Status | Fix |
|---|---|---|---|---|
| 1 | Title | "MCP-Lock: Lockfiles and Pre-Launch Gating for Coding-Agent MCP Servers" | ✅ | none |
| 2 | Abstract and keywords | Abstract + 6 IEEE keywords | ✅ | light rewrite to name the objectives |
| 3 | Introduction | §I, with RQ1–RQ3 and four contributions | ✅ | shorten; move the gap paragraph to §III |
| 4 | Literature review, 2022–2026 | "Related Work" at the end (§VIII); 12 research papers from 2022–2026 | ⚠️ partial | move it to §II, organise by theme, add 6 verified 2022–2026 papers, and end with a comparison table |
| 5 | Research gap | implicit in one paragraph of the introduction | ❌ no section | new §III, gaps G1–G4, each traced to the papers that leave it open |
| 6 | Research objectives | RQ1–RQ3 and the contributions list | ⚠️ no section | new §IV, objectives O1–O4 mapped to RQs, gaps, hypotheses and the kill rule |
| 7 | Proposed methodology | split across the census method (§III) and the design (§IV) | ⚠️ partial | new §V: lockfile, the five checks, verdict logic, safe suggestion, pre-registered protocol |
| 8 | System architecture diagram | Fig. 1 (TikZ): hook → gate ← lock/registry → verdict | ✅ | none; add a separate **methodology flowchart** (Fig. 2) |
| 9 | Implementation / experimental setup | corpora inside §V; stack and replay spread around | ⚠️ partial | new §VI: implementation, datasets (R-B, R-M, R-S, B), replay, metrics, statistics, environment |
| 10 | Results and discussion | §III RQ1, §V RQ2, §VI RQ3, §VII discussion | ✅ | regroup under one §VII with RQ1/RQ2/RQ3 subsections |
| 11 | Performance comparison with existing methods | Table III (gate vs baseline); simpler alternatives in text only | ⚠️ partial | new §VIII with one **comparison table** of existing methods, all from existing result files (below) |
| 12 | Conclusion and future work | conclusion only | ⚠️ | add a future-work paragraph (from the limitations and STATUS next steps) |
| 13 | IEEE references, 15–20 papers minimum | 30 entries, of which about 16 are research papers (the rest are docs, datasets, blogs, GitHub) | ⚠️ borderline | add the 6 verified papers in §4 below → about 22 research papers and 36 entries |

| Deliverable | Status | Plan |
|---|---|---|
| IEEE double-column PDF | ✅ | rebuild after the restructure |
| Word version | ❌ | IEEE conference Word template (.docx), built from the same text, figures and tables; PDF remains the reference copy |
| Architecture diagram | ✅ Fig. 1 | keep |
| Methodology flowchart | ❌ | new Fig. 2 |
| Genuine results, graphs, comparison tables | ⚠️ 1 graph, 3 tables | add 3 graphs from existing result files (§3); add the comparison table |
| Citations and references | ✅ verified (`docs/CITATIONS_VERIFIED.md`) | verify the 6 new ones the same way and log them |
| Plagiarism / similarity report | ⚠️ self-run screen only (`PLAGIARISM_CHECK.md`) | redo the self-screen after the rewrite. **A Turnitin/iThenticate report must come from the institution**: I cannot produce one |
| Corrections from your review | pending | after approval of this outline |

## 2. Proposed outline (target 8 pages plus references; see open question A)

| § | Section | Content | Source of every number |
|---|---|---|---|
| — | Title, authors, abstract, keywords | title unchanged; authors and affiliation as now (Dept. of Data Science and Business Systems) | `numbers.tex` |
| I | Introduction | unpinned `npx -y`/`uvx` launches; rug pulls; why name/age checks are not enough; RQ1–RQ3; contributions | [Kapner], [CISA] |
| II | Literature review | A. supply-chain attacks and malicious-package detection; B. signing and provenance; C. MCP security; D. agent supply chains and tool pinning; **Table I: prior work vs. four properties** | refs only |
| III | Research gap | G1 tool-definition drift unmeasured; G2 no pre-launch tool check without running the server; G3 no continuity of build/publisher/scripts; G4 no evaluation on real attacks with a false-block cost | from §II |
| IV | Research objectives | O1 measure drift (RQ1); O2 build lockfile + gate; O3 pre-registered H1/H2 with kill rule (RQ2); O4 adaptive attacker and hardening (RQ3) | PREREG.md |
| V | Proposed methodology | threat model T1–T5; lockfile fields; checks S1–S5 (**Table II**); verdict and suggestion logic; **Fig. 1 architecture** (existing); **Fig. 2 methodology flowchart** (new) | GATE.md, SPEC.md |
| VI | Implementation and experimental setup | Python 3.11, tree-sitter static extraction, npm/PyPI APIs, Claude Code hook, Docker; census frame and sample; corpora R-B, R-M, R-S, B; offline replay as of publication time; metrics; McNemar + Holm, Wilson CIs; six logged deviations | `numbers.tex`, DEVIATIONS.md |
| VII | Results and discussion | A. RQ1 drift (**Fig. 3**, new); B. RQ2 detection and cost (**Table III** existing, **Fig. 4** new: detection; **Fig. 5** new: false blocks); ablation; C. RQ3 evasion matrix (**Table IV** existing) and hardening cost (**Fig. 6** existing); D. discussion and threats to validity | results/ |
| VIII | Performance comparison with existing methods | **Table V** (below), plus latency | `plain_baselines.json`, `numbers.tex` |
| IX | Conclusion and future work | conclusion as now; future work: independent red-team evaluation, release-pipeline (T3) attacks, review fatigue, registry-side tool versioning, more ecosystems | STATUS.md |
| — | Artifact availability, references | GitHub, OSF DOI; about 36 IEEE-style references | refs.bib |

### Table V (performance comparison): every cell already exists in the result files

| Method | Real attacks detected (R, n = 490) | Rug pulls (R-S, 40) | False blocks on benign upgrades (8,180) | Notes |
|---|---|---|---|---|
| Baseline hook, literal (S1-L) | 14.5% | from results | from results | Bagmar & Saraf as published |
| Baseline hook, charitable (S1-C) | 19.6% [16.3, 23.3] | 0/40 | 32.9% | strongest reading of the baseline |
| Exact version pinning | 78.6% of R-M (368/468) | n/a | all upgrades frozen | needs a manual edit for every upgrade |
| npm `--ignore-scripts` (npm only) | 26.6% of npm R-M (upper bound) | n/a | 2.6% of npm upgrades | |
| S1-C + `--ignore-scripts` (npm only) | 42.2% of npm R-M | n/a | — | about the same as MCP-Lock on npm (**stated plainly**) |
| **MCP-Lock (G)** | **39.8% [35.6, 44.2]**; npm R-M 42.4% | **40/40** | 33.4% (+0.42 pp) | adds tool-definition and provenance continuity, plus a diff |
| MCP-Lock, locked servers exempt from the age rule (exploratory) | 38.2% | from results | **0.73%** | |
| Latency | median cold-cache and warm values from `numbers.tex` | | | |

"From results" cells are filled from the result file or left out; no value is estimated. The honest finding is that
on npm real attacks the baseline plus `--ignore-scripts` is about as good as MCP-Lock. That stays in, together with
what MCP-Lock adds on top: rug pulls, provenance continuity, and upgrades that run unattended when nothing changed.

## 3. Methodology (summary for approval)

1. **Measure (RQ1).** Build a frame of MCP packages from the official MCP registry and GitHub configs (15,272 eligible
   packages). Draw a stratified sample of 2,000 by ecosystem and download tercile, with a fixed seed. Extract tool
   definitions statically from every version, then measure how often the canonical tool hash changes within 90 days
   and whether any metadata signal accompanies the change.
2. **Design.** `mcplock lock` writes `mcp-lock.json` (digest, provenance identity, publisher, install scripts, tool hash).
   Before every launch, the hook resolves the version the command would fetch and reads its archive without executing
   it. It then runs S1–S5 against the lock entry and returns allow, warn (with a diff) or block (with a verified safe version).
3. **Evaluate (RQ2, pre-registered on OSF before any scored run).** Replay 490 real attacks and 8,180 benign upgrades
   offline as of their publication time. Compare against the baseline hook with an exact McNemar test and Holm
   correction, using a kill rule fixed in advance. Run an ablation per check and report the synthetic rug pulls separately.
4. **Attack it (RQ3, exploratory).** Build 12 adaptive attacks that know every check, add five hardening switches D1–D5,
   and measure each switch's extra false blocks. Confirm runtime verdicts for 11 cases in sealed Docker containers.

Flowchart (Fig. 2, to be drawn in TikZ):
`Frame & sample → static tool extraction → drift census (RQ1)` ⟶ `design lockfile + checks S1–S5` ⟶
`pre-register H1, H2, kill rule (OSF)` ⟶ `offline replay: R (490), R-S (40), B (8,180)` ⟶ `McNemar/Holm, Wilson CIs` ⟶
`kill rule?` → (fail: report negative result) / (pass: ablation, comparison) ⟶ `adaptive attacks + D1–D5 cost (RQ3)`.

New graphs, all drawn from existing result files by `make_figures.py`:
- Fig. 3: RQ1 drift, share of packages whose tools changed within 90 days, by ecosystem, with 95% CIs.
- Fig. 4: detection by corpus, baseline vs. MCP-Lock (all R, class C, class N, R-S).
- Fig. 5: false-block and warning rates on B (baseline, MCP-Lock, MCP-Lock with the age-rule exemption).

## 4. References to add (each checked on its primary page on 2026-11-04)

| Paper | Venue | Identifier | Why |
|---|---|---|---|
| A. Sejfia, M. Schäfer, "Practical Automated Detection of Malicious npm Packages" | ICSE 2022 | doi 10.1145/3510003.3510104 | malicious-package detection (scanning, not continuity) |
| P. Ladisa, S. E. Ponta, N. Ronzoni, M. Martinez, O. Barais, "On the Feasibility of Cross-Language Detection of Malicious Packages in npm and PyPI" | ACSAC 2023, pp. 71–82 | doi 10.1145/3627106.3627138 | same, cross-ecosystem |
| T. R. Schorlemmer et al., "Signing in Four Public Software Package Registries: Quantity, Quality, and Influencing Factors" | IEEE S&P 2024 | doi 10.1109/SP54263.2024.00182 | signing is sparse, so provenance continuity rarely applies |
| Y. Gamage, D. Tiwari, M. Monperrus, B. Baudry, "The Design Space of Lockfiles Across Package Managers" | arXiv:2505.04834, 2025 | arXiv | lockfile design, the base MCP-Lock extends |
| S. Gaire et al., "SoK: Security and Safety in the Model Context Protocol Ecosystem" | arXiv:2512.08290, 2025 | arXiv | MCP threat taxonomy, including provenance defences |
| C. Huang, X. Huang, N. P. Tran, A. Milani Fard, "Model Context Protocol Threat Modeling and Analyzing Vulnerabilities to Prompt Injection with Tool Poisoning" | arXiv:2603.22489, 2026 | arXiv | tool poisoning tested on 7 MCP clients |

Before adding them, I read the full text of each, as was done for the existing references, and confirm what we cite
it for. A paper that does not support the sentence that cites it is dropped.

## 5. Open questions (need your answer)

A. **Target conference and page limit.** The restructure needs about 8 pages. Most IEEE conferences allow 6 pages plus
   paid extra pages, and some cap at 6. If the cap is 6, Fig. 5 and part of §VI move to an appendix or the artifact.
B. **Word version.** Option 1: write it in the IEEE Word conference template (editable, but TikZ figures become images
   and equations need re-entry). Option 2: convert the PDF. Option 1 is recommended.
C. **Anonymisation.** Double-blind venues need author names, the GitHub link and the OSF link removed.
