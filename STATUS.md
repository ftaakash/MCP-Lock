# STATUS

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
- Co-signals per event (RQ1 preview, npm-only for publisher/scripts): publisher changed 8/243 = 3.3% [1.7, 6.4]; new install script 2/243 = 0.8% [0.2, 3.0]; provenance lost 0/243 [0.0, 1.6].
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

## Next gate
- Improve PyPI extraction recall (dynamic/conditional registration) before the full census.
- Phase 2: full census (RQ1 publishable alone) + MCP-Lock spec (`lockfile/mcp-lock.schema.json` draft exists).

## Phase 0: setup (2026-10-08), done
Repo skeleton; Bagmar & Saraf analysis (`analysis_outputs/`); S1 replication assessment (`docs/BASELINE_REPLICATION.md`);
Kapner et al. verified (`docs/CITATIONS_VERIFIED.md`); author email sent.
