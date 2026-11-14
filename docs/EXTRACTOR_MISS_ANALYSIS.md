# Why the static extractor misses tools (held-out validation, 2026-11-14)

Diagnostic only. No reported result changes. The extractor (`census/extract_js.py`, `census/extract_py.py`,
`census/tooldefs.py`) is byte-identical to tag `prereg-v1`, and re-running it today reproduces every miss exactly.

- Input: `results/census/phase2/validation_heldout_{npm,pypi}.jsonl` (82 servers that started; 1,385 runtime tools)
- Re-run: `census/miss_rerun.py` (archives fetched with digest checks into a scratch folder, never executed)
- Output: `results/census/phase2/miss_analysis.json`
- Categories were assigned by reading each package's source.

## Where recall is lost

The paper's recall (78.0%, micro) means 305 of 1,385 runtime tool names were not found statically.

- **Concentration:** all 305 come from 14 of the 82 servers. The other 68 have no misses.
- **Whole-server failures:** 284 of the 305 (93%) come from 10 servers where static extraction found no tools at all.
- **Size effect:** a few large servers dominate the micro figure, which is why macro recall is higher (85.5%).

| Cat. | Pattern the extractor does not handle | Servers | Missed | Example |
|---|---|---|---|---|
| A | Python call form `mcp.tool()(fn)`, including in a loop | 3 | 67 | mcp-ksef-pl, freeplay-mcp, mcp-monumenten |
| B1 | Tool object with a schema key other than `inputSchema` (`parameters`, `shape`) | 2 | 60 | @doist/todoist-mcp, fluf-mcp |
| B2 | Project-specific factory or wrapper (`defineAction({id})`, `defineProcessTool({...})`, `{name, register(server)}`) | 3 | 80 | @dreamworkhq/mcp, pixinsight-connector, @heroui/react-mcp |
| C | Imported bare function `tool('name', {...})` (not a method call) | 2 | 16 | @cyanheads/inaturalist-mcp-server, who-gho |
| D | `registerTool` inside a loop over a table of names | 1 | 3 | verdix-mcp |
| E | Decorator name override `@tool(name="x")` (the extractor keeps the function name) | 1 | 3 | forkflux-mcp |
| F | Tools not in the package source: served from a bundled JSON catalog (proxy), or defined in a dependency | 2 | 76 | appcrane-mcp, inn-check-ru-mcp |
| | **Total** | **14** | **305** | |

## What fixing each category would recover (in-sample, upper bound)

Each row assumes every category above it is also fixed. These are counts on the same 82 servers used to find the patterns, so
they are **not** an estimate of new recall. A fixed extractor must be validated on servers it was not tuned on.

| Fix | Effort and risk | Recall on this set if fully recovered |
|---|---|---|
| none (paper) | — | 78.0% |
| A + C + E | small; patterns are unambiguous | 84.2% |
| + B1 (accept `parameters`/`shape` keys on objects that also have `name` and `description`) | small; some false-positive risk | 88.5% |
| + B2 + D (follow a value into a factory or a loop over a literal table) | moderate; interprocedural | 94.5% |
| F | not possible from the package's own source | ceiling for static extraction: 94.5% |

Category F is the case for capturing the real `tools/list` once at lock time, in a sandbox with no network.
The lock side then no longer depends on the extractor. The pre-launch check stays static.

## Precision side (static names the runtime did not list: 91)

| Server | Extra | Cause |
|---|---|---|
| outlook-graph-mcp | 66 | real tools hidden by configuration (`OUTLOOK_MCP_TOOLSETS`); only 2 are exposed with no config |
| forkflux-mcp | 3 | category E: function names instead of the `name=` override |
| freeplay-mcp | 2 | wrong names (`name`, `object`) from the call-form loop (category A) |
| seu-claude, stock-scanner-mcp, @vukvukovich/hammerspoon-mcp, kiwoom-mcp | 20 | not examined |

Most of the precision loss is therefore conditional exposure. These are real tool definitions in the code, which a lock may
reasonably pin.

## Limits of this analysis

- Recall was measured only on the 82 of 171 held-out servers that started (48%). Servers that fail to start may use other
  patterns.
- Fourteen servers is a small base for ranking categories.

## Next steps (proposed, not done)

1. Implement A, C and E (then B1) as extractor v3, with unit tests from these servers.
2. Freeze v3 at a tag.
3. Draw a fresh held-out validation sample that excludes these 171 servers. Report v3 recall on it next to v2.
4. Keep every paper number on v2 as reported. Any v3 census re-run is reported as exploratory.
