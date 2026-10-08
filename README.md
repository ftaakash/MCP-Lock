# MCP-Lock

Provenance-aware pre-install verification for coding agents.

| Dir | Contents |
|---|---|
| `census/` | RQ1: MCP launch-line collection, version histories, attestations, static tool-definition extraction, version diffs |
| `lockfile/` | MCP-Lock format (JSON schema + docs) |
| `gate/` | Signals S1 (Bagmar & Saraf baseline, reimplemented) to S5; PreToolUse hook + `mcplock check` CLI |
| `eval/` | Attack corpora and scoring (RQ2, RQ3) |
| `paper/` | IEEEtran LaTeX |
| `results/baseline/` | Baseline (S1-only) results, kept separate |
| `results/candidate/` | Candidate (S1-S5) results |
| `results/census/` | Census outputs |

Every raw result under `results/` ships with a provenance JSON (command, git commit, UTC timestamp).

Safety rules: nothing is ever published to a public registry (attacks target a local Verdaccio only);
unknown package code runs only in Docker with `--network none`; public APIs are read-only, rate-limited and cached.
