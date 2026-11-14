# Why the static extractor misses tools (held-out validation, 2026-11-14)

No reported result changes. Every paper number uses extractor v2 (tags `extract-v2.1` and `prereg-v1`). Re-running v2
reproduces every miss below exactly. Fixes A, B1, C and E were then added to `main` as extractor v3 (see "Extractor v3" below).

- Input: `results/census/phase2/validation_heldout_{npm,pypi}.jsonl` (82 servers that started; 1,385 runtime tools)
- Re-run: `scripts/miss_rerun.py` (archives fetched with digest checks into a scratch folder, never executed)
- Output: `results/census/phase2/miss_analysis.json`, `results/census/phase2/extractor_v3_insample.json`
- Categories were assigned by reading each package's source.

## Where recall is lost

The paper's recall (78.0%, micro) means 305 of 1,385 runtime tool names were not found statically.

- **Concentration:** all 305 come from 14 of the 82 servers. The other 68 have no misses.
- **Whole-server failures:** 284 of the 305 (93%) come from 10 servers where static extraction found no tools at all.
- **Size effect:** a few large servers dominate the micro figure, which is why macro recall is higher (85.5%).

| Cat. | Pattern the extractor does not handle | Servers | Missed | Example |
|---|---|---|---|---|
| A | Python call form `mcp.tool()(fn)`, including in a loop | 3 | 23 | mcp-ksef-pl (12 of 56), freeplay-mcp, mcp-monumenten |
| B1 | Tool object with a schema key other than `inputSchema` (`parameters`, `shape`) | 2 | 60 | @doist/todoist-mcp, fluf-mcp |
| B2 | Project-specific factory or wrapper (`defineAction({id})`, `defineProcessTool({...})`, `{name, register(server)}`) | 3 | 80 | @dreamworkhq/mcp, pixinsight-connector, @heroui/react-mcp |
| C | Imported bare function `tool('name', {...})` (not a method call) | 2 | 16 | @cyanheads/inaturalist-mcp-server, who-gho |
| D | `registerTool` inside a loop over a table of names | 1 | 3 | verdix-mcp |
| E | Decorator name override `@tool(name="x")` (the extractor keeps the function name) | 1 | 3 | forkflux-mcp |
| F | Tools not in the package source: served from a bundled JSON catalog (proxy), or defined in a dependency | 3 | 120 | appcrane-mcp, inn-check-ru-mcp, mcp-ksef-pl (44 of 56) |
| | **Total** | **14** | **305** | |

Correction (same day): mcp-ksef-pl was first counted wholly under A (56). After fix A, its own 12 tools were found. The other
44 are registered by `register_peppol_*_tools` imported from the dependency `mcp_einvoicing_core`, so they belong to F.

## What fixing each category would recover (in-sample, upper bound)

Each row assumes every category above it is also fixed. These are counts on the same 82 servers used to find the patterns, so
they are **not** an estimate of new recall. A fixed extractor must be validated on servers it was not tuned on.

| Fix | Effort and risk | Recall on this set if fully recovered |
|---|---|---|
| none (paper) | — | 78.0% |
| A + C + E (**done, measured: 81.0%**) | small; patterns are unambiguous | 81.0% |
| + B1 (accept `parameters`/`shape` keys on objects that also have `name` and `description`) (**done, measured: 85.3%**) | small; some false-positive risk | 85.3% |
| + B2 + D (follow a value into a factory or a loop over a literal table) | moderate; interprocedural | 91.3% |
| F | not possible from the package's own source | ceiling for static extraction: 91.3% |

Category F is the case for capturing the real `tools/list` once at lock time, in a sandbox with no network.
The lock side then no longer depends on the extractor. The pre-launch check stays static.

## Precision side (static names the runtime did not list: 91)

| Server | Extra | Cause |
|---|---|---|
| outlook-graph-mcp | 66 | real tools hidden by configuration (`OUTLOOK_MCP_TOOLSETS`); only 2 are exposed with no config |
| forkflux-mcp | 3 | category E: function names instead of the `name=` override |
| freeplay-mcp | 2 | wrong names (`name`, `object`) from the dict-literal rule matching a vendored Swagger model (`vendor/swagger_client/models/anthropic_tool.py`); still present in v3 |
| seu-claude, stock-scanner-mcp, @vukvukovich/hammerspoon-mcp, kiwoom-mcp | 20 | not examined |

Most of the precision loss is therefore conditional exposure. These are real tool definitions in the code, which a lock may
reasonably pin.

## Limits of this analysis

- Recall was measured only on the 82 of 171 held-out servers that started (48%). Servers that fail to start may use other
  patterns.
- Fourteen servers is a small base for ranking categories.

## Extractor v3 (fixes A, B1, C, E; 2026-11-14)

| Fix | Change | File |
|---|---|---|
| A | `x.tool(...)(fn)`, and `for t in [f, g] / CONST_LIST: x.tool(...)(t)`; name and description from the inner call, else the function | `census/extract_py.py` |
| B1 | object literal `{name, description, parameters / shape}`; without `inputSchema` a description is required | `census/extract_js.py` |
| C | bare `tool("name", {description, input / inputSchema})`; the config must have a description | `census/extract_js.py` |
| E | `@tool(name="x")` / `@x.tool("x")` on a function later passed to `add_tool(fn)` or the call form uses `"x"` | `census/extract_py.py` |

Five unit tests cover these (`tests/test_extract.py`, `test_v3_*`), including negative cases. All 108 tests pass.

**Re-run on all 82 validated servers. This is in-sample, exploratory and not a recall estimate:**

| | Recall (micro) | Precision (micro) | Static names | Matched |
|---|---|---|---|---|
| v2 (paper) | 78.0% | 92.2% | 1,171 | 1,080 |
| v3 with A, C, E | 81.0% | 92.7% | 1,210 | 1,122 |
| v3 with A, B1, C, E | 85.3% | 93.1% | 1,270 | 1,182 |

- **Changed servers:** eight — who-gho 0→6, inaturalist 0→10, mcp-ksef-pl 0→12, mcp-monumenten 0→2, freeplay-mcp 0→9
  matched, forkflux-mcp 6→9 matched with its 3 wrong names gone, and (B1) @doist/todoist-mcp 0→47 and fluf-mcp 0→13.
- **Unchanged:** the other 74 servers are identical to v2. No server lost a tool or gained a wrong one.

**Reproducibility:** the gate (`gate/signals.py`), lockfile generation and the evaluation corpora import the extractor, so `main`
now behaves differently from the frozen gate. Check out `prereg-v1` (gate) or `extract-v2.1` (census) to reproduce the paper.

## Next steps

1. ~~Implement A, C and E as extractor v3, with unit tests from these servers.~~ Done.
2. ~~Add B1.~~ Done. Freeze v3 at a tag before the new validation run.
3. Draw a fresh held-out validation sample that excludes these 171 servers. Report v3 recall on it next to v2.
4. Keep every paper number on v2 as reported. Any v3 census re-run is reported as exploratory.
