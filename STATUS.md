# STATUS

## Phase 3: gate + baseline (2026-10-10). **Complete: gate built, S1 parity reproduced; awaiting go-ahead for Phase 4 (PREREG)**

No reply from Bagmar & Saraf (email sent 2026-10-08), so S1 is reimplemented from Appendix I in two variants.
Docker now works locally (Virtual Machine Platform enabled after the Windows repair).

### Built
| Component | Files | What it does |
|---|---|---|
| Command parser | `gate/command.py` | pip / `python -m pip` / `uv pip` / npm / pnpm / yarn / bun installs, `npx` / `uvx` launches, env prefixes, `export`, `make` |
| S1 baseline | `gate/s1.py`, `gate/data/` | Appendix I's 7 checks for PyPI **and** npm; `literal` and `charitable` variants as recorded switches |
| S2 to S5 | `gate/signals.py` | provenance continuity, publisher change (human → CI migration ignored), new install script, tool-definition drift with diff; integrity check on the same version |
| Policy | `gate/core.py` | allow / warn / block with a one-line reason |
| Claude Code hook | `gate/hook.py` | PreToolUse on `Bash` and on `Write` to MCP configs; block → deny, warn → ask; fails closed |
| CLI | `gate/cli.py` (`mcplock`) | `mcplock check -- <cmd>`, `mcplock lock <config>`; installable (`pip install -e .`) |
| Docs | `docs/GATE.md` | signals, variants, hook setup, limitations |

End-to-end check against a real lock: older pinned filesystem server → `npx -y` resolves 2026.8.31 → **WARN S5 tool_drift**;
unchanged `mcp-server-fetch` → ALLOW; unlocked server → WARN; untrusted index → BLOCK. The hook gives the same answers
from real PreToolUse JSON.

### S1 parity with Bagmar & Saraf Table 8 (`results/baseline/parity_2026-10-10/`)
| S1 variant | PyPI, command form | PyPI, agent form | npm port, command form | npm port, agent form |
|---|---|---|---|---|
| literal | **10/11 (R7 missed) = Table 8** | 8/11 (misses R3, R10) | 7/11 | 4/11 |
| charitable | 10/11 = Table 8 | 10/11 = Table 8 | 10/11 | 10/11 |

The literal reading reproduces Table 8 exactly on explicit install lines. Its misses on `pip install -e .` and `make setup`
indicate that the paper scored command lines, or that the real code does more than Appendix I.

### S1 false positives on popular packages (`results/baseline/s1_fp_2026-10-10/`)
| | top-1,000 PyPI | top-1,000 npm |
|---|---|---|
| literal (P = top-1,000) | 52 = 5.2% [4.0, 6.8] | 35 = 3.5% [2.5, 4.8] |
| charitable | 0 = 0.0% [0.0, 0.38] | 0 = 0.0% [0.0, 0.38] |
| paper | 5 = 0.5% | n/a |

The paper's 5/1,000 is reproduced by the literal name rule only with P of about the top-100 to 150 (3 at 100, 8 at 150).
The charitable variant is at least as good as the paper on false positives, so it is not a strawman.

### Fixed during Phase 3
- Parser bug: `npm install https-proxy-agent` was read as a URL install (name starts with "http"). Fixed with a regression
  test; npm literal false positives were 33/1,000 before the fix and 35/1,000 after. The buggy run was discarded.
- Registry lookups for the age check made cheap (PyPI JSON simple API; npm abbreviated document plus a downloads
  probe), because full npm packuments of popular packages are tens of MB.

### Open risks for Phase 4
- S5 recall equals the extractor's held-out recall (78.0%), so runtime-generated tools escape it.
- Build identity is recorded, not signature-verified (Sigstore verification not implemented).
- Latency: a cold PyPI lookup for very large projects (boto3) takes about 14 s; Phase 4 must report latency per install.

## Next gate
Phase 4: write `PREREG.md` (corpora, metrics, statistics, kill rule) and **stop for Aakash to register it** before any
evaluation run.

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
