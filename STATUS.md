# STATUS

## Phase 5: adaptive attacker (RQ3) and hardening (2026-10-11). **Attack and defence done; paper not started**

Plan: `docs/PHASE5_PLAN.md`. Everything here is **exploratory**: Phase 4 stays the confirmatory result, and with no
hardening switch on, the gate is the frozen `prereg-v1` code. After the hardening edits, a re-replay of every Phase 4
corpus on the default path is identical in every system, decision, reason and finding: B 8,180/8,180, R-M 568/568,
R-S 50/50 (`eval/adaptive/recheck_frozen.py`, `results/census/logs/p5_hardening_recheck.log`).
Results: `results/candidate/phase5/` (`evasion_matrix.{json,md}`, `exposure.json`, `hardening_cost.json`, `h1_cost.json`).

### Evasion matrix (local Verdaccio, inert payloads; G = frozen gate, all signals)
| Case | Tier | Attack | G | Signal | All hardening |
|---|---|---|---|---|---|
| E1 | T1 | new name, edit distance ≥ 2, older than 30 days | warn | unlocked | warn |
| E2 | T2 | stolen token, lock without provenance, runtime payload | **allow** | — | block (H4) |
| E3 | T2 | stolen token, lock with provenance | block | S2, S3 | block |
| E4 | T3 | payload through the genuine release workflow | **allow** | — | **allow** |
| E5 | T4 | poisoned description built at runtime | warn | S5 | block (H2) |
| E6a / E6b | T4 | tools fetched from a URL; rug pull with / without a new version | **allow** | — | block (H2) |
| E7 | T4 | poisoning in an input-schema field description | warn | S5 | block (H2) |
| E8a / E8b | T4 | time bomb / tool registered from a base64 blob | warn / **allow** | S5 / — | block (H2) |
| E9 | T5 | payload and tools in a caret-range dependency | **allow** | — | block (H1, H2) |
| E10 | T2/T4 | extra file added to a locked PyPI release | **allow** | — | block (H3) |
| E11 | any | 22 command shapes | 13/22 blocked | parser | 21/22 (H5); `echo … \| base64 -d \| sh` stays open |

G stops 5 of 12 (1 block, 4 warns). With all switches on, 10 of 12 block; E1 still warns and E4 is allowed. A
compromised release pipeline (T3) is outside what any lock can see.

### Exposure (existing data, Wilson 95%)
- E2: locks without provenance 4,919/8,180 = 60.1% [59.1, 61.2] (Phase 4 B).
- E6/E8: versions whose tools static extraction cannot see 2,774/12,768 = 21.7% [21.0, 22.5] (Phase 2).
- E9: npm servers with a floating `@modelcontextprotocol/sdk` range 1,027/1,094 = 93.9% [92.3, 95.2] (proxy: SDK only).

### Hardening (exploratory) and its cost on the 8,180 benign upgrades
| Switch | Implementation | Closes | Cost on B |
|---|---|---|---|
| H1 dependency-tree lock | gate code, `gate/deptree.py` (+ `gate/semver.py`); S2–S4 rules per dependency | E9 | npm n = 5,652: extra blocks over G 0.53% [0.37, 0.76] (lock just before t) – 1.03% [0.79, 1.32] (lock at v_old's release); allow → warn 0.09–3.52% |
| H2 runtime `tools/list` pin | stdio proxy, `gate/proxy.py` (`mcplock proxy`); per-tool pin, trust on first use | E5–E9 | blocks 27.1% [26.1, 28.0] – 27.6% [26.7, 28.6], all in the MCP stratum (33.1% of MCP upgrades); newly blocked over G 15.7% [15.0, 16.5] – 16.1% [15.3, 16.9] |
| H3 PyPI all-files lock | gate code, `gate/signals.py` | E10 | 0 on B (upgrades only); 12/2,528 = 0.47% [0.27, 0.83] of locked releases gained a file > 1 h after the first |
| H4 require provenance | policy rule | E2 | blocks 4,700/8,180 = 57.5% [56.4, 58.5]; newly blocked over G 3,048/8,180 = 37.3% [36.2, 38.3] |
| H5 command normalisation | parser rule | E11 | 0 decisions changed |

- For comparison, a strict tree lock (`npm ci` reading: any dependency change blocks) would block 12.4–48.9% of npm
  upgrades. H1's continuity rules cost 1/20 to 1/50 of that. In the early-lock bound, H1's warns are mostly a new
  dependency publisher (486 cases).
- H2 assumes the live tool list equals the static extraction for benign upgrades (unobservable for historical versions),
  and 1,483 upgrades with no static tools are counted as no cost. In the matrix, each attack's live list is written down
  from its source code; no server was executed.
- Lock format v0.2 (`lockfile/SPEC.md` §6): optional `dependencies`, `files` and `tools.runtime` fields.
- **Age-rule sensitivity** (`age_rule_sensitivity.json`): 2,695 of G's 2,729 false blocks on B involve S1's 30-day age
  rule. Waiving it for servers already in the lock: false blocks 0.73% [0.57, 0.94] (from 33.4%), interruptions 28.4%
  (from 49.8%; warnings 27.7%), detection on R 187/490 (8 young hijacked packages lost; still 91 more than S1-C).

### Deviations from the Phase 5 plan
1. E10 is a hand-built bundle, not a package on a local pypiserver: the attack is a metadata fact (a file added to an
   existing release), and the gate reads only metadata for it.
2. H2 pins each tool separately (not one hash at start-up) and checks every listing, so pagination and later changes
   (E8a after its date) are covered; a removed tool is reported, not blocked.
3. H1 applies continuity rules instead of blocking every dependency change. The strict reading is reported alongside it.
4. The first full H1 cost run errored on 63 cases (old packument shapes, a cache race between workers, a 404
   attestation). The gate code was fixed and the run repeated with 0 errors; both runs are in git history.

### Open
- Paper (IEEEtran, plan §5): first full draft in `paper/` (5 pages, `bash paper/build.sh`); every number is a macro
  generated from the result files by `paper/make_numbers.py`. Hostile review done and its open items fixed
  (`paper/REVIEW.md`): new title, age-rule sensitivity, shorter abstract, architecture figure. Next: human read-through,
  venue choice, novelty sweep again in the week before submission.
- Local Verdaccio container `mcplock-verdaccio` is stopped (storage volume kept); remove it once the paper is final.

## Phase 4: pre-registered evaluation (2026-10-11). **Complete: kill rule NOT triggered**

Registered: OSF https://osf.io/2amj3 (plan text `914d2b3`, gate code tag `prereg-v1`, unchanged; harness tag
`phase4-harness`). Deviations #1–#6: `docs/DEVIATIONS.md`. Replay rules: `docs/REPLAY.md`.
Results: `results/candidate/phase4/phase4_results.{json,md}`; baseline-only summary `results/baseline/phase4/`.

### Corpora
| Corpus | Size |
|---|---|
| R-B Bagmar & Saraf scenarios | 22 core (agent form primary) |
| R-M real malicious versions (OSV `MAL-` + DataDog, 2024-01 → 2026-10) | 468 primary: 368 class C (hijacked existing package), 100 class N (new / typosquat); 32 C not replayable (no lock version left) |
| R-S synthetic rug pulls (local Verdaccio) | 40 attacks (A1–A4 × 10 servers) + 10 controls |
| B benign upgrades | 8,180 (6,695 MCP, 992 npm-top, 493 PyPI-top) |
| L latency (live) | 200 packages (1 skipped) |

### Confirmatory results
| | S1-C | G | Test |
|---|---|---|---|
| Detection on R (block ∪ warn) | 96/490 = 19.6% [16.3, 23.3] | 195/490 = 39.8% [35.6, 44.2] | H1: G-only 99, S1-C-only 0, exact McNemar p = 3.2e-30, Holm 6.3e-30 |
| False blocks on B | 2,695/8,180 = 32.9% [31.9, 34.0] | 2,729/8,180 = 33.4% [32.3, 34.4] | H2: G-only 34, p = 1.2e-10, Holm 1.2e-10; +0.42 pp [0.28, 0.56] |
| **Kill rule** | | | 99 added detections ≥ 2 → **not killed** (block-only secondary: 96 added) |

### Descriptive results
- Ablation on R (detections lost when removing one signal): S4 96, S5 2, S3 1, S2 0. The gain is almost entirely
  install scripts added by hijacked npm versions (2025 worm campaigns).
- Evaluability on R-M: S2/S3 88 of 468 (removed versions have no registry record), S4 214, S5 239.
  Sensitivity on the 88 fully evaluable cases: G 61 vs S1-C 56.
- R-M by class: C — G 116/368 vs S1-C 17/368; N — 59/100 for both (S1's 30-day age rule).
- By ecosystem: npm G 169/403 vs S1-C 71/403; PyPI G 6/65 vs S1-C 5/65.
- R-B: G = S1-C on every scenario (no lock, so S2–S5 cannot fire, as designed); agent form 20/22, command form 20/22.
- R-S: G 40/40, S1-L/S1-C 0/40. Removing S5 loses A1 and A2, removing S4 loses A3; A4 is caught by S2 and S3 independently. Controls: 0/10 blocked.
- B by stratum: MCP — S1-C blocks 2,683/6,695 = 40.1% (age rule on young servers), G warns on 1,321 (S5);
  npm-top — S1-C 11, G 13 blocks + 25 warns; PyPI-top — S1-C 1, G 3.
- Interruption rate (block ∪ warn) on B: S1-C 32.9%, G 49.8%. Cost per added detection: 0.34 extra false blocks and
  13.6 extra warns.
- S2 coverage: B 3,261/8,180 = 39.9% of locks have provenance; R-M class C 50/368.
- Latency (live, n = 199): G cold median 0.99 s, p95 3.19 s, max 50.8 s; warm median 0.05 s; none over 60 s.
- Lookup failures: 0 in every corpus.

### Interpretation and caveats
- The method claim survives the pre-registered kill rule, but the gain comes from S4, an install-script diff. Provenance
  continuity (S2) added nothing on real attacks, mainly because removed malicious versions leave no attestation record to
  check. Tool pinning (S5) is what catches MCP-specific rug pulls (R-S), at a review cost of about 1 in 5 MCP upgrades.
- S1-C's 32.9% false-block rate comes from its 30-day age rule replayed at upgrade time. This differs from Phase 3's
  "top packages today" measurement (0%), and both are correct for their question.
- Class C follows the pre-registered rule ("an earlier unaffected version exists"); some cases may be attacker-owned
  packages with a benign first release rather than true takeovers.

### Safety
Defender quarantined 5 OSV advisory JSON files from a host checkout (DEVIATIONS #3). All malware data was handled
afterwards only in the `mcplock-mal` Docker volume. Static analysis ran with `--network none`. Follow-up Defender scans
were clean. No new malicious package was found (35 still-listed malicious npm versions are already public in OSV/DataDog).

## Next gate
Phase 5 paper (plan §5). Attack and hardening results above.

## Phase 2: full census + MCP-Lock spec (2026-10-09). Complete

Protocol fixed before collection: `docs/CENSUS_PLAN.md`. Scope chosen by Aakash: **hybrid**. A literal full census
would need ~250 GB of archives against 115 GB free disk.

### Part M: metadata census (all 15,272 eligible packages, 228,044 transitions, 2025-10-08 → 2026-10-08, 0 errors)
| Signal | npm transitions | npm packages (of 10,693 active) | PyPI transitions | PyPI packages (of 3,957 active) |
|---|---|---|---|---|
| Provenance lost | 627 = 0.36% [0.33, 0.39] | 390 = 3.65% [3.31, 4.02] | 296 = 0.54% [0.48, 0.61] | 212 = 5.36% [4.70, 6.10] |
| Provenance gained | 3,043 = 1.75% | 2,567 = 24.0% | 726 = 1.33% | 607 = 15.3% |
| Publisher: human → GitHub Actions (trusted-publishing migration) | 2,971 = 1.71% | 2,568 = 24.0% [23.2, 24.8] | n/a | n/a |
| Publisher: human → different human | 1,007 = 0.58% | 298 = 2.79% [2.49, 3.12] | n/a | n/a |
| Publisher: GitHub Actions → human | 412 = 0.24% | 241 = 2.25% [1.99, 2.55] | n/a | n/a |
| Maintainer set changed | 1,234 = 0.71% | 598 = 5.59% [5.17, 6.04] | n/a | n/a |
| New install script (`preinstall`/`install`/`postinstall`, gyp) | 222 = 0.13% | 203 = 1.90% [1.66, 2.17] | n/a | n/a |

Latest version carries provenance: npm 25.9% [25.1, 26.7], PyPI 46.4% [44.9, 47.9].
PyPI has no per-release uploader or maintainer history (stated limitation). `prepare` is excluded because npm does not
run it for registry installs; this also corrected the pilot co-signal from 2 to 1 event.

### Part T: tool-definition drift (n = 2,000 stratified, superset of pilot; extractor `extract-v2.1`)
| Measure | Estimate (Wilson 95% CI) | Weighted (stratified cluster bootstrap) |
|---|---|---|
| Versions with extractable tool definitions (10 most recent per package) | 9,994 / 12,768 = **78.3%** [77.6, 79.0] | 78.3% [76.3, 80.2] |
| Packages changing tools within 90 days | 731 / 2,000 = **36.5%** [34.5, 38.7] | 36.5% [34.6, 38.5] |
| … among packages with a release in the window | 731 / 1,239 = 59.0% [56.2, 61.7] | |
| … among packages with an extractable window pair | 731 / 984 = 74.3% [71.5, 76.9] | |
| Window transitions with a tool change | 2,259 / 6,695 = **33.7%** [32.6, 34.9] | 33.7% [32.6, 34.9] |
| Robustness: excluding pre-releases | 721 / 2,000 = 36.0% [34.0, 38.2] | |
| Robustness: names / descriptions only | 695 / 2,000 = 34.8% [32.7, 36.9] | |

By ecosystem: G1 npm 76.1% [75.2, 76.9], PyPI 84.1% [82.9, 85.3]. Packages changing tools: npm 537/1,467, PyPI 194/533.
Of 2,259 change events, tools were added in 987, removed in 132, descriptions changed in 1,374 and schemas in 1,157.

**Tool drift is independent of every metadata signal** (same transitions, Fisher's exact test):
| Signal on the same transition | with tool change | without tool change | p |
|---|---|---|---|
| Provenance lost | 10/2,259 = 0.4% [0.2, 0.8] | 11/4,436 = 0.2% [0.1, 0.4] | 0.25 |
| Publisher changed (npm) | 58/1,657 = 3.5% [2.7, 4.5] | 86/3,003 = 2.9% [2.3, 3.5] | 0.25 |
| Maintainers changed (npm) | 5/1,657 = 0.3% | 13/3,003 = 0.4% | 0.62 |
| New install script (npm) | 2/1,657 = 0.1% | 1/3,003 = 0.0% | 0.29 |

2,192 / 2,259 = **97.0% [96.3, 97.7]** of tool changes carry none of these signals. Name, source, provenance and
publisher checks (S1 to S4) cannot see tool drift; only S5 can.

### Extractor validation (`docs/VALIDATION.md`)
- **Harness v2** (ESM loading, dependencies as of release date, Python 3.11 to 3.13, arg fallbacks, env-name scan): start rate
  rose from 32.6% (v1) to 59.4%. v1 and v2 servers form the **development set**.
- **extract-v2:** PyPI call-form and wrapper-decorator rules, dict-literal tools, sdist preference. Development PyPI
  recall 55.7% → 74.4%. Frozen (tag `extract-v2`). `extract-v2.1` adds memoization and step budgets only, with output
  identical to extract-v2 on 450 versions.
- **Held-out** (82 servers never used in development): name precision 92.2% (macro 95.5%), recall 78.0% (macro 85.5%),
  exact name set 76.8% [66.6, 84.6], tools found when the server has tools 87.8% [79.0, 93.2].
- Selection bias: static extractability is 87.8% among servers that started vs 77.5% among those that did not (npm gap larger).
  Drift figures are **lower bounds**.

### Safety
- Suspicious-text review of all Part T hits: 157 versions / 14 packages / 26 distinct hits, **none malicious**
  (`results/census/phase2/suspicious_review.md`).
- User-communication steering via tool descriptions observed in edgeone-pages-mcp-fullstack, @porkbunllc/mcp-server and
  @replen/mcp; noted for the paper.

### MCP-Lock spec (`lockfile/SPEC.md`, schema `lockfile/mcp-lock.schema.json`)
- Reference generator `python -m lockfile.generate .mcp.json` pins version, archive integrity, build identity
  (SLSA / PEP 740: repository + workflow + builder), publisher, install scripts and the tool hash.
  Validated on a real config (3 servers, schema-valid).
- Continuity identity ignores ref/commit. v0.1 records identity without verifying signatures; Sigstore verification is Phase 3.

### Deviations and open risks
- Scope is hybrid, not a full census of tool definitions (disk/bandwidth); Part M is a full census of metadata.
- Extraction: 10 extract errors and 9 archives over 150 MB are excluded (recorded with status in `extractions.jsonl.gz`).
- Large result files are committed gzipped (`extractions.jsonl.gz`); analysis reads them transparently.
- Kill-test pilot numbers (Phase 1) used extract-v1. Phase 2 supersedes them with extract-v2.1 on the n=2,000 superset.

## Phase 1: census pilot (2026-10-08). KILL test: **PASS on both gates** (extractor validated in Docker, 2026-10-09)

### What ran
| Step | Output | Numbers |
|---|---|---|
| F1 official MCP registry | `results/census/frame/f1_registry.jsonl` | 15,217 npm/PyPI package rows, 14,461 distinct packages |
| F2 GitHub configs (8 code-search queries, size-partitioned) | `f2_github.jsonl` | 32,346 config files, 41,403 launch lines |
| Frame (frozen, committed before sampling) | `frame_2026-10-08.jsonl` (sha256 `905cc9d7…`) | 18,067 packages (13,338 npm, 4,729 PyPI) |
| Eligibility (≥ 2 versions, resolves, not proxy or runner) | `frame_2026-10-08_eligibility.jsonl` | 15,272 eligible (11,201 npm, 4,071 PyPI) |
| Downloads (npm API, pypistats; 0 failed lookups) | `…_eligible_downloads.jsonl` | |
| Stratified sample, seed 20261008 | `results/census/pilot/sample.jsonl` | 200 = 147 npm + 53 PyPI, 6 strata |
| Version sets | `versions.jsonl` | 1,887 versions (G1 set 1,345; G2 set 1,296) |
| Fetch, verify digest, static extraction | `extractions.jsonl` | 1,887/1,887 ok |
| Kill-test analysis | `kill_test.json`, `kill_test.md` | below |
| Manual audit (50 items) | `manual_audit.md` | 25/25 tool sets plausible; 25/25 change events genuine |

### Kill-test results
| Gate | Estimate, Wilson 95% CI | Weighted, stratified cluster bootstrap | Threshold | Decision |
|---|---|---|---|---|
| G1 extractable versions | 1020/1345 = **75.8%** [73.5, 78.0] | 75.9% [69.6, 81.9] | ≥ 60% | PASS |
| G2 packages changing tools within 90 d | 65/200 = **32.5%** [26.4, 39.3] | 32.4% [26.4, 38.4] | ≥ 5% | PASS |

Secondary (Wilson 95%):
- G1 npm 76.5% [73.8, 79.1], PyPI 74.0% [69.3, 78.2]; packages with ≥ 1 extractable version 157/200 = 78.5% [72.3, 83.6].
- G2 npm 51/147 = 34.7% [27.5, 42.7], PyPI 14/53 = 26.4% [16.4, 39.6].
- G2 among packages with a release in the window: 65/117 = 55.6% [46.5, 64.2]; among packages with an extractable window pair: 65/92 = 70.7% [60.7, 79.0].
- Robustness: excluding pre-releases 63/200 = 31.5% [25.5, 38.2]; names/descriptions only (ignoring schema) 62/200 = 31.0% [25.0, 37.7].
- 243 change events: tools added in 94, removed in 10, description changed in 162, schema changed in 115.
- Co-signals per event (RQ1 preview, npm-only for publisher/scripts): publisher changed 8/243 = 3.3% [1.7, 6.4]; new install script 1/243 = 0.4% [0.1, 2.3] (after excluding `prepare`); provenance lost 0/243 [0.0, 1.6].
- Provenance on G1-set versions: npm 310/972 = 31.9% [29.0, 34.9]; PyPI 180/373 = 48.3% [43.2, 53.3].
- Unpinned share of F2 launch lines: npm 34,525/36,926 = 93.5%; PyPI 3,921/4,477 = 87.6% (descriptive; GitHub search is not a probability sample).

### Deviations from the approved plan (logged)
1. **Docker `tools/list` validation (plan §6) ran on a GitHub-hosted runner** (Actions run 37834955664,
   workflow `.github/workflows/validate-extractor.yml`) because the local host's Virtual Machine Platform is stuck
   `EnablePending`. Same two-stage design (install with scripts off; run with `--network none`, read-only, no caps,
   non-root, no tool calls). 95 latest versions attempted in seeded random order; 31 started offline and answered
   `tools/list` (20 npm, 11 PyPI; PyPI exhausted its 53 packages before reaching 20). Startup failures (56 initialize
   timeouts, 7 install failures, 1 tools/list error) are mostly servers that need real credentials or arguments, so
   the validated set leans toward servers that start without setup.

   | | npm (n=20) | PyPI (n=11) | All (n=31) |
   |---|---|---|---|
   | Name precision (micro) | 99.7% | 91.1% | 96.6% |
   | Name recall (micro) | 98.4% | 57.5% | 79.1% |
   | Exact name-set match | 18/20 = 90.0% [69.9, 97.2] | 6/11 = 54.5% [28.0, 78.7] | 24/31 = 77.4% [60.2, 88.6] |
   | Static finds ≥1 tool when the server has tools | 19/20 = 95.0% [76.4, 99.1] | 9/11 = 81.8% [52.3, 94.9] | 28/31 = 90.3% [75.1, 96.7] |
   | Mean exact description match | 86.7% | 85.3% | 86.2% |

   Reading: static extraction rarely invents tools; it under-counts on PyPI (dynamically or conditionally registered
   tools). G1 and G2 are therefore conservative lower bounds. The 3 static misses (`dingdawg-marketing-agent@2.0.9`,
   `llre@0.2.2`, `dydx-agent-gateway@0.3.2`) are recorded in `validation.jsonl`.
2. Generic script runners (`tsx`, `ts-node`, `dotenv-cli`, …) excluded at eligibility (they launch local files,
   not packages); list fixed before sampling, 9 npm packages affected.
3. Consecutive versions are ordered by version precedence (semver / PEP 440), not publish time, so backport
   lines do not create spurious diffs. Window membership uses the newer version's publish time.
4. F3 (Kapner et al. artifact) not used; F1 ∪ F2 already gives 18k packages.
5. Download lookups first hit npm rate limits (1,844 silent zeros); the code was fixed to retry and to flag
   failures explicitly, then re-run: 0 failed lookups in the final file.

### Open risks
- G1 counts a version as extractable with ≥ 1 valid tool; partial extractions (runtime-generated tools) count as success.
- Tools defined in a dependency (e.g. `@playwright/mcp`) are invisible to per-package static extraction.
- Bagmar & Saraf code still unavailable (email sent 2026-10-08, awaiting reply).

## Phase 0: setup (2026-10-08), done
Repo skeleton; Bagmar & Saraf analysis (`analysis_outputs/`); S1 replication assessment (`docs/BASELINE_REPLICATION.md`);
Kapner et al. verified (`docs/CITATIONS_VERIFIED.md`); author email sent.
