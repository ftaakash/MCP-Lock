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
