# Census pilot: sampling plan (APPROVED by Aakash, 2026-10-08)

Goal: decide the Phase 1 KILL test on 200 MCP packages.
- **G1 extractability:** share of sampled versions whose tool definitions are statically extractable. KILL if < 60%.
- **G2 drift:** share of sampled packages with ≥1 tool-definition change in the last 90 days. KILL if < 5%.

## 1. Sampling frame (frozen before sampling)
A package enters the frame if it is launched as an MCP server through an **unpinned** runner:
`npx [-y] <pkg>` / `pnpm dlx` / `bunx` (npm) or `uvx <pkg>` / `pipx run` (PyPI), where `<pkg>`
carries no `@<exact-version>` or `==<version>`.

Sources:
- **F1, official MCP registry** (`registry.modelcontextprotocol.io`, read-only API, paginated). Use
  `packages[]` entries with `registryType` in {npm, pypi}, keeping the latest server.json per server.
- **F2, GitHub configs** via `gh search code` over `filename:.mcp.json`,
  `filename:claude_desktop_config.json`, `filename:mcp.json path:.vscode` and `path:.cursor`, plus
  `"npx"` / `"uvx"`. Code search returns at most 1,000 hits per query and is rate-limited to about
  10 requests/min, so queries are partitioned by `size:` ranges. Parse the `command`/`args` JSON;
  regex is a fallback only. Record how many configs mention each package (its config prevalence).

- **F3 (optional, pending licence check)**: unpinned-MCP findings in the Kapner et al. artifact
  (github.com/Benkapner/harness-eval-experiments @ 217b8620e8a7).

Frame = F1 ∪ F2 (∪ F3), de-duplicated by (ecosystem, normalized name). The frame snapshot is written to
`results/census/frame_2026-10-XX.jsonl` with SHA-256 and provenance JSON **before** the sample is drawn.

## 2. Eligibility (applied to the frame; counts reported at each step)
Include a package when all of these hold:
1. It resolves on npm or PyPI today.
2. It has ≥ 2 published (non-yanked, non-unpublished) versions, because a diff needs two versions.
3. It is not a pure proxy or launcher: `mcp-remote`, `@smithery/cli`, `supergateway` and similar
   ship no tool definitions of their own. They are listed but excluded, and their count is reported.

Single-version packages are counted in the frame statistics but are not sampled.

## 3. Stratification and allocation (n = 200)
- **Ecosystem:** npm vs PyPI, proportional to the eligible frame, with a **floor of 50 per
  ecosystem** so each has its own estimate.
- **Popularity tercile within ecosystem:** npm last-month downloads (`api.npmjs.org`); PyPI
  last-month downloads (`pypistats.org`, cached). Config prevalence from F2 is recorded as a covariate.
- Draw a simple random sample within each of the 6 cells with `numpy.random.default_rng(20261008)`
  over the frame sorted by (ecosystem, name). Store the seed and the sorted-frame hash.
- Estimates are **weighted back to the frame** (stratum weights), with unweighted results alongside.

## 4. Versions per package (for G1)
- Use the **most recent K = 10 versions** per package (all of them if fewer). The cap keeps
  high-churn packages from dominating. Expected total is about 1,000 to 2,000 tarballs.
- Pre-releases (`-alpha`, `rc`, `.devN`) are kept but tagged, and a sensitivity analysis excludes them.

## 5. Definitions
- **Tool definition:** the set of (name, description, inputSchema) for every tool, normalized: keys
  sorted, whitespace collapsed, and JSON Schema serialized canonically. The hash is SHA-256 of the
  sorted canonical list.
- **Statically extractable (G1 success):** the extractor returns ≥ 1 tool with a literal name **and**
  either a literal description or a resolvable schema, without executing any package code.
  - JS/TS: `server.tool(...)`, `registerTool(...)`, `setRequestHandler(ListToolsRequestSchema, ...)`
    returning literal arrays, and zod or raw-JSON schemas. Bundled or minified `dist/` is handled on
    a best-effort basis and logged separately.
  - Python: `@mcp.tool` / `@server.tool` (FastMCP; the schema comes from signature type hints and
    the docstring) and `Tool(name=...)` in `list_tools` handlers.
  - A result of zero tools counts as a **failure** unless the dynamic check confirms the server
    really exposes zero tools.
- **Tool change (G2 event):** for consecutive versions (v_{i-1}, v_i), both extractable, with v_i
  published in **[2026-07-10, 2026-10-08]** (90 days up to the scan date), and the hash differs.
  Each event is classified as added / removed / renamed tool, description-only, or schema-only.
- **Primary G2 denominator: all 200 sampled packages.** This is conservative: a package with no
  release in the window counts as "no change". As a secondary figure, report the rate among packages
  with ≥ 1 release in the window.

## 6. Validation of the static extractor (needed so G1 is honest)
A stratified random subsample of **40 versions** (20 npm, 20 PyPI) gets ground truth from a dynamic
`tools/list` run:
- Stage A (networked, **no package code run**): `npm install --ignore-scripts` / `uv pip download`
  into a volume.
- Stage B: `docker run --network none --read-only --cap-drop ALL`, then an MCP initialize and
  `tools/list` over stdio. No tool calls, a 30 s timeout, and the container is discarded afterwards.

Report extractor precision and recall on tool names, and the agreement rate of tool-definition
hashes. **This two-stage design needs your sign-off:** Stage A downloads dependencies with network
access but with scripts disabled. Only Stage B executes code, and it has no network.

## 7. Statistics and decision rule
- Wilson 95% CIs for G1 (per version) and G2 (per package).
- G1 versions are clustered within packages, so a package-level cluster bootstrap CI
  (B = 10,000, same seed) is reported next to the Wilson CI.
- Precision at n = 200 (Wilson): 10/200 = 5.0% gives [2.7%, 9.0%]; 120/200 = 60% gives
  [53.1%, 66.5%]. For G1 at around 1,500 versions the half-width is about ±2.5 pp, before clustering.
- **Proposed rule:**
  - Decide on the point estimate (the literal "under X%" in the brief).
  - If the 95% CI **straddles** the threshold, label the result *inconclusive* and extend the sample
    once, to 400 packages with the same frame and seed continuation, before deciding.
  - In practice G2 is a clean pass at ≥ 16/200 (lower bound ≥ 5%) and a clean kill only at ≤ 3/200.

## 8. Also collected in the pilot (not part of the gate; feeds RQ1 later)
For each version: npm provenance attestations (`/-/npm/v1/attestations/<pkg>@<ver>`) and PyPI
integrity/provenance, the maintainers/publisher list, and install scripts (`preinstall`/`install`/
`postinstall`, presence of `setup.py`). All are read-only and cached under `results/census/cache/`.

## 9. Safety and etiquette
- Tarballs are untrusted data. Extract them with `tarfile` `filter="data"` into fresh per-version
  directories, and run analyzers with `python -I` from outside those directories.
- Polite rate limits: npm ≤ 5 req/s, PyPI ≤ 5 req/s, pypistats ≤ 1 req/s, GitHub code search ≤ 9
  req/min. Every response is cached on disk with an ETag.
- If any version shows a suspicious drift (for example a new tool or description containing
  exfiltration or injection text), **stop and report to Aakash** before anything else.

## 10. Known threats to validity
- Frame bias: registry entries and public GitHub configs over-represent popular, public servers.
  Private configs are invisible.
- Static extraction is biased toward simple servers. The dynamic subsample measures this but cannot
  remove it.
- The 90-day window is anchored at the scan date, so results are a seasonal snapshot.
