# Extractor v3 validation plan (written 2026-11-14, before the run)

**Purpose:** measure extractor v3 (v2 + fixes A, B1, C, E; see `EXTRACTOR_MISS_ANALYSIS.md`) on servers that played no
part in building it. The 85.3% recall on the first held-out set is in-sample and is not reported as a recall estimate.

**Status:** exploratory, and not part of the OSF pre-registration. Paper numbers stay on extractor v2.

## Frozen inputs

- **Extractor:** tag `extract-v3`. The run checks out this tag. Static results are computed in the run by
  `census.run_extract.extract_one`, as in the first held-out run.
- **Harness:** `census/dynamic.py` harness v2, unchanged. Same images, sandbox flags (`--network none`, read-only, no
  capabilities, non-root), timeouts and argument fallbacks. No tool is ever called.
- **Environment:** GitHub Actions `ubuntu-24.04`, workflow `validate-extractor.yml`, as in the first run.

## Sample

- **Pool `heldout2`:** packages of the phase-2 sample (`results/census/phase2/sample.jsonl`) never attempted before,
  neither in development (`results/census/pilot/validation_*.jsonl`) nor in the first held-out run. That leaves 1,347 npm
  and 344 PyPI packages.
- **Order:** a new seeded permutation (seed 20261010 = `SEED + 2`); the latest version of each package.
- **Size:** target 40 validated servers per ecosystem, maximum 160 attempts each, 3 workers. These are the same settings as
  the first held-out run.

## Analysis (fixed before the run)

| | Measure |
|---|---|
| Primary | v3 tool-name **recall** and **precision** (micro: matched names / runtime names, matched / static names) over validated servers, with a 95% interval from a server-level bootstrap (10,000 resamples, seed 20261114) |
| Secondary | v2 on the same servers (extractor at tag `extract-v2.1`, run offline on the same archives), and v3 minus v2 with a paired server-level bootstrap interval |
| Secondary | macro recall and precision; share of servers with identical name sets (Wilson 95% CI) |
| Secondary | per-category attribution of v3's remaining misses, using the categories of `EXTRACTOR_MISS_ANALYSIS.md`, with any new pattern reported as new |
| Reported, not tested | start rate; static extractability among servers that started vs. did not (selection bias, as in the first run) |

- **No tuning:** no extractor change is made in response to this run before its results are reported. Any later fix is a
  new version and needs new servers.

## Outputs

- `results/census/phase2/validation_heldout2_{npm,pypi}.jsonl`
- `validation_heldout2_summary.json`
- `extractor_v3_heldout2.json`

---

## Results (added 2026-11-14, after the run)

**Run:** GitHub Actions run 43597225133, from tag `extract-v3` (commit `c8e4f53`). Its provenance marks the checkout
"-dirty", as in the first held-out run, because the job writes its output files into the working tree. The analysis is
`scripts/heldout2_analysis.py`, committed before the results.

| | Value |
|---|---|
| Attempted / started | 161 / 80 (40 npm, 40 PyPI); start rate 49.7% [42.1, 57.3] |
| Runtime tools on the 80 servers | 1,081 |
| **v3 recall (micro)** | **79.4% [66.8, 89.9]** |
| **v3 precision (micro)** | **99.4% [98.6, 100]** |
| v2 recall / precision on the same servers | 79.4% / 99.4% (identical) |
| v3 − v2 recall | 0.0 pp [0.0, 0.0]: no server changed |
| Servers with identical name sets | 60 of 80, 75.0% [64.5, 83.2] |
| Selection check: servers with static tools, started vs not started | npm 85% vs 82%, PyPI 88% vs 83% |

**What this means:**
- **The fixes did not show up on new servers.** None of the patterns behind A, B1, C and E occurred among the 80 fresh
  servers, so v3 and v2 give the same result. The 78.0% → 85.3% gain on the first set was specific to the servers it was
  built from.
- **The extractor's out-of-sample recall is about 79%,** consistent with the paper's 78.0%. Precision on new servers is
  higher (99.4%) than on the first set (92.2%), where one configuration-gated server dominated.

**Remaining misses: 223 names on 18 servers.** Categories were assigned by brief inspection after the run:

| Category | Servers | Missed |
|---|---|---|
| Tools outside the package source (JSON contract, native binary, wheel without code) | 4 | 73 |
| Tool names built at runtime (no literal occurrence in the source) | 6 | 48 |
| Project-specific registration helper (`defineTool`, `registerStall`, `registerValidator`, ...) | 5 | 47 |
| Programmatic catalogue (hand-written JSON-RPC handler, generated registration) | 2 | 36 |
| Call form over a function-local list of module attributes (variant of A that v3 does not cover) | 1 | 19 |

- **Out of reach of static analysis:** 157 of 223 (70%) are in the first, second and fourth rows, which no source-pattern
  rule can reach. The rest are a long tail of project-specific helpers, each seen once.
- **Conclusion:** further pattern work on the extractor has low expected value. Recording the real `tools/list` once at
  lock time in a sandbox is the fix that addresses most misses.
- **For the paper:** report extractor recall with its interval, about 78–79% on two independent held-out sets, and do not
  claim a v3 improvement.
