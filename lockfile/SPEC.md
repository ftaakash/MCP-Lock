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
