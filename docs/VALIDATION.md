# Static extractor validation

Ground truth comes from the MCP `tools/list` response of the real server, run in Docker with
`--network none`, a read-only root filesystem, no capabilities, as a non-root user, and with **no tool
calls**. Runs happen on GitHub-hosted runners ([workflow](../.github/workflows/validate-extractor.yml)),
because the local host's Virtual Machine Platform is stuck in `EnablePending`.

## Timeline and data sets
| Round | Harness | Extractor | Packages | Role | Files |
|---|---|---|---|---|---|
| v1 | v1 (CJS `require`, latest deps, Python 3.11 only) | extract-v1 | pilot sample, latest version | first attempt | `results/census/pilot/validation_v1.jsonl` |
| v2 | v2 (ESM-aware, deps as of release date, Python 3.11 to 3.13, arg fallbacks, env-name scan) | extract-v1 | pilot sample, then frame reserve | **development set** | `results/census/pilot/validation_{npm,pypi}.jsonl` |
| dev rescoring | | extract-v2 | the 82 v2 servers | development only, not reported as accuracy | `results/census/pilot/devset_scores.json` |
| held-out | v2 | **extract-v2 (tag `extract-v2`, frozen)** | phase-2 sample minus every v1/v2 package, separately seeded order | **reported accuracy** | `results/census/phase2/validation_heldout_*.jsonl` |

## Why the harness changed between v1 and v2
Only 31 of 95 servers started under v1. Most failures were caused by the harness, not by the servers:
- ESM entry points with top-level `await` failed under `require()`.
- Installing today's dependencies pulled MCP Python SDK v2, which breaks servers written for v1.
- Some packages need Python 3.12 or 3.13.
- Read-only `/work` broke servers that write next to themselves.

v2 fixes these without touching the extractor. Start rate: v1 32.6% → v2 59.4% [51.1, 67.3].

## Held-out accuracy (reported)
| | npm (n=41) | PyPI (n=41) | All (n=82) |
|---|---|---|---|
| Tool-name precision, micro / macro | 97.3 / 97.8% | 84.2 / 93.5% | 92.2 / 95.5% |
| Tool-name recall, micro / macro | 75.9 / 81.5% | 82.1 / 89.4% | 78.0 / 85.5% |
| Exact tool-name set | 29/41 = 70.7% [55.5, 82.4] | 34/41 = 82.9% [68.7, 91.5] | 63/82 = 76.8% [66.6, 84.6] |
| ≥ 1 tool found when the server has tools | 34/41 = 82.9% [68.7, 91.5] | 38/41 = 92.7% [80.6, 97.5] | 72/82 = 87.8% [79.0, 93.2] |
| Mean exact description match | 96.3% | 92.1% | 94.1% |
| Servers that started offline | 41/63 = 65.1% | 41/108 = 38.0% | 82/171 = 48.0% [40.6, 55.4] |

## Selection bias
Servers that start offline without real configuration may be easier for static analysis. This is checked by
comparing the static-extractability rate of servers that started against those that did not:

| | started | not started |
|---|---|---|
| Held-out, all | 87.8% [79.0, 93.2] | 77.5% [67.8, 85.0] |
| Held-out, npm | 82.9% [68.7, 91.5] | 50.0% [30.7, 69.3] |
| Held-out, PyPI | 92.7% [80.6, 97.5] | 86.6% [76.4, 92.8] |

The gap is large for npm, so the npm accuracy figures likely overstate performance on servers that need configuration.

## Error analysis (held-out; no extractor changes made from it)
- **Precision misses are mostly config-gated tools.** Example: `outlook-graph-mcp` defines 68 tools and serves 2 until
  signed in. Static extraction reports the package's *potential* tool surface, which is what a lockfile should pin.
  One genuine false positive: `freeplay-mcp` produced spurious names `name` and `object`.
- **Recall misses are all-or-nothing.** Static finds 0 tools while the server serves 10 to 68. These tools are
  generated at runtime from manifests, specs, or builder functions (e.g. `@doist/todoist-mcp`, `appcrane-mcp`,
  `mcp-ksef-pl`). Tools defined in a dependency are invisible by design.

## Consequences for RQ1
- Tool-drift estimates are **lower bounds**: missed tools can only hide changes.
- High precision plus the manual audit (25/25 change events genuine) means detected changes are real.
- A future extractor revision must be evaluated on a new held-out set; this one is now spent.
