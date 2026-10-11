# MCP-Lock specification (draft v0.1)

MCP-Lock pins every MCP server that an agent harness launches from a package registry. Each pin
covers the exact version, the archive bytes, the build identity that produced it, and the tool
definitions it advertises. The file is checked into the repository next to the harness config
(`.mcp.json`, `claude_desktop_config.json`, `.vscode/mcp.json`, `.cursor/mcp.json`). A gate then
compares every launch against it **before** package code runs.

Schema: [`mcp-lock.schema.json`](mcp-lock.schema.json). Reference generator:
`python -m lockfile.generate .mcp.json -o mcp-lock.json`.

## 1. Scope
In scope: servers launched as `npx` / `pnpx` / `pnpm dlx` / `bunx` (npm), or `uvx` / `uv tool run` / `pipx run` (PyPI).
Recorded under `skipped` with a reason: remote servers (`url`), local scripts (`node dist/index.js`), and Docker images.
Docker images are pinned by digest, which is future work.

## 2. Entry fields
| Field | Meaning | Source |
|---|---|---|
| `ecosystem`, `name`, `version` | exact resolved version, never a range or dist-tag | npm packument / PyPI JSON |
| `launch.runner`, `launch.args` | the launch line as declared | harness config |
| `integrity` | `sha512-…` (npm SRI) or `sha256-…` (PyPI file digest) over the archive bytes | registry, re-verified on download |
| `archive` | tarball URL (npm) or file name (PyPI) | registry |
| `provenance` | build identity, or `null` if the version has no attestation | npm SLSA provenance; PyPI PEP 740 |
| `publisher` | npm `_npmUser` and the maintainers at lock time | npm packument |
| `installScripts` | `preinstall` / `install` / `postinstall` (and `install` implied by `gypfile`) | npm packument |
| `tools.hash` | `sha256:` over sorted canonical `(name, description, schema)` | static extraction (or `tools/list` in a sandbox) |
| `tools.names` | tool names, for readable diffs | same |

## 3. Canonical tool hash
1. Extract each tool's `name`, `description` (whitespace collapsed) and input schema.
2. Serialize each tool as JSON with sorted keys and no whitespace (`separators=(",", ":")`, UTF-8).
3. Sort the serialized strings, join them with `\n`, and take sha256.

In static mode, values that cannot be resolved without execution become the literal `"$opaque"`, and
identifiers renamed by bundlers are normalized. A rebuild of unchanged source therefore keeps the same hash.
Static and dynamic hashes are not comparable with each other; `tools.method` records which one was used.

## 4. Build identity and continuity
The *continuity identity* is `[sourceRepository, workflowPath, builder]`, and `provenance.digest` is its sha256.
`sourceRef` and `sourceCommit` are recorded but **not** compared, because they change with every honest release.
For PyPI trusted publishing, the workflow file name is expanded to `.github/workflows/<file>`, so that npm and PyPI
releases of one project built by the same workflow get the same identity.

v0.1 records identity without verifying signatures. A conforming gate must verify the attestation
(Sigstore bundle) before trusting `provenance` (Phase 3).

## 5. Gate semantics (Phase 3)
When a launch resolves to a version **different** from the lock entry:

| Signal | Condition | Default action |
|---|---|---|
| S1 | baseline checks (name, existence, age, source, hidden index, config, OSV) fail | block |
| S2 | the locked version had provenance and the new one has none, or a different continuity identity | block |
| S3 | npm publisher not among the locked maintainers | warn |
| S4 | new version adds an install script | block |
| S5 | `tools.hash` differs | warn, and show the tool diff (added / removed / changed descriptions) |

When the launch resolves to the **same** version but the archive digest differs, block (tampering or a registry
problem). A clean upgrade happens by re-running the generator, which rewrites the entry and produces a reviewable diff.

## 6. v0.2: exploratory hardening fields (Phase 5, not part of the pre-registered gate)
v0.2 adds three optional fields. A v0.1 lock stays valid; a gate that finds the field missing reports an `info`
finding and nothing else. Measured cost and coverage: `results/candidate/phase5/`.

| Field | Ecosystem | Content | Checked by |
|---|---|---|---|
| `dependencies.nodes` | npm | every node of the dependency tree resolved at lock time, keyed `name@version`: `integrity`, `provenance`, `publisher`, `maintainers`, `installScripts`; ranges that are not registry ranges go to `dependencies.unresolved` | H1, `gate/deptree.py` |
| `files` | PyPI | `{filename: "sha256-…"}` for **every** file of the locked release, yanked ones included | H3, `gate/signals.py` |
| `tools.runtime` | both | live `tools/list` pin: one `sha256:` per tool over its canonical `(name, description, inputSchema)` (§3), plus the hash of the whole list | H2, `gate/proxy.py` |

- **H1.** The gate re-resolves the tree npm would install now (`dependencies`, `optionalDependencies`, non-optional
  `peerDependencies`; highest satisfying stable version) and applies S2–S4 to every node whose version changed, with the
  highest locked version of that dependency as the baseline. A changed digest for the same `name@version` blocks, and a
  dependency not in the lock blocks only when it runs an install script.
- **H2.** `mcplock proxy --record` writes the pin on first use (trust on first use). Afterwards, a `tools/list` that
  adds a tool or changes one is answered with a JSON-RPC error, and `tools/call` for a tool that is not pinned is refused.
  A tool that disappears is only reported. The check runs on every listing, so a time-triggered or remote change is
  caught when it appears, not only at upgrade time.
- **H3.** On a launch that resolves to the locked version, a file the lock does not list blocks (E10). An installer can
  enforce the same thing with `--require-hashes` over the `files` digests.
