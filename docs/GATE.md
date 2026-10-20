# The MCP-Lock gate

The gate decides **allow / warn / block** with a one-line reason *before* an agent runs a package
install or launches an MCP server. It never executes package code: registry metadata, attestations
and archive contents are read statically.

## Signals
| Signal | Question | Data | Default |
|---|---|---|---|
| **S1** baseline (Bagmar & Saraf, reimplemented) | Is the name confusable with a popular package, absent, or under 30 days old? Is the source untrusted? Is there a hidden index, config poisoning, or a known-vulnerable pin? | command line, project files, PyPI / npm, OSV | block |
| **S2** provenance continuity | Did the build provenance disappear, or does a different repository/workflow/builder produce the new version? | npm SLSA attestations, PyPI PEP 740 | block |
| **S3** publisher change (npm) | Was the new version published manually after CI releases, or by an account that is not a locked maintainer? Human → CI migration is **not** flagged. | npm `_npmUser`, maintainers | warn |
| **S4** install script | Does the new version add `preinstall`/`install`/`postinstall` (or `node-gyp`)? PyPI: an sdist-only release after wheels. | npm packument, PyPI files | block (npm), warn (PyPI) |
| **S5** tool-definition drift | Do the tool names, descriptions or input schemas differ from the locked hash? | static extraction of the new archive | warn, with the diff |
| gate | Is the server unlocked? Does the same version's archive digest differ from the lock? | lockfile | warn / block |

S2–S5 compare against the server's entry in `mcp-lock.json` ([spec](../lockfile/SPEC.md)).
Phase 2 showed that tool drift is independent of every metadata signal: 97.0% of tool changes carry none.
S5 is therefore the only signal that sees it.

## S1 variants
| | literal (Appendix I as written) | charitable (ambiguities resolved in the baseline's favour) |
|---|---|---|
| Popular set P | top-1,000 | top-5,000, with names in the top-15,000 exempt |
| URL trust | substring of a trusted host | parsed host equals a trusted host, HTTPS only |
| Project files | only `-r` files named on the command line | also `pyproject.toml`, `package.json`, `Makefile`, `.npmrc`, nested `-r` / `-c` |
| Environment | `PIP_CONFIG_FILE` / `NPM_CONFIG_USERCONFIG` | also `PIP_INDEX_URL` & co., `npm_config_registry` |
| `npx` / `uvx` launches | not checked (the paper hooks `pip install` only) | checked as installs |

## Command line
```bash
mcplock lock .mcp.json -o mcp-lock.json
mcplock check --lock mcp-lock.json -- npx -y @modelcontextprotocol/server-filesystem /tmp
```
Exit codes: 0 allow, 1 warn, 2 block. `--s1 literal` and `--signals S1,S5` switch variants and signals.

## Claude Code hook
Add to `.claude/settings.json` in a project. This is a manual step; the repository does not change your settings.
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Write",
        "hooks": [{ "type": "command", "command": "python -m gate.cli hook", "timeout": 120 }]
      }
    ]
  }
}
```
- block → `deny`; warn → `ask` (you see the reason and decide); allow → no output.
- `Write` calls to `.mcp.json`, `claude_desktop_config.json`, `.vscode/mcp.json` or `.cursor/mcp.json` are checked for every
  npm/PyPI server the new config would launch.
- Internal errors fail closed to `ask`. A PreToolUse hook that **times out does not block**, so keep the timeout generous.
  The first check of a new version downloads and statically analyses its archive.
- Caches live in `~/.cache/mcplock` (override with `MCPLOCK_CACHE`). The lockfile defaults to `<cwd>/mcp-lock.json`
  (override with `MCPLOCK_LOCKFILE`).

## Safer alternatives (`gate/suggest.py`)
When a command is flagged, the gate proposes a replacement and offers it only if the gate itself passes the
rewritten command. Suggestions never change the decision.

| Finding | Suggested replacement |
|---|---|
| S1 `name_proximity` (typosquat) | the popular package the name imitates |
| S1 `vulnerable_pin` | the lowest release that fixes every listed advisory |
| S2–S5 (and H1/H3) on a locked server, or a digest mismatch | the newest version between the locked and the new one that passes every lock check, then the locked version |
| S1 `absent` / `new_package` | up to three popular names within edit distance 2 |
| gate `unlocked` | advice only: review the server, then `mcplock lock` |

Several flagged packages in one command are fixed together, and the combined command is checked as a whole.
`mcplock check` prints `TRY:` lines (`--no-suggest` turns them off); the hook appends "Try instead: …" to the
deny/ask reason, so the agent can retry with it. When checking a suggestion, the age rule is waived for a package
that is already in the lock (it guards first use), and `gate unlocked` does not count against it.

## Exploratory hardening (Phase 5, off by default)
These are not part of the pre-registered gate. With no switch on, the gate runs exactly as tagged `prereg-v1`.
The paper calls them D1–D5, so that they are not confused with the pre-registered hypotheses H1 and H2.
Lock fields: [spec §6](../lockfile/SPEC.md). Evasion matrix and benign cost: `results/candidate/phase5/`.

| Switch | What | How to turn it on |
|---|---|---|
| H1 | dependency-tree continuity: S2–S4 rules applied to every dependency of the locked server (closes E9) | `mcplock check --signals S1,S2,S3,S4,S5,H1` |
| H2 | runtime `tools/list` pin, enforced by a stdio proxy between client and server (closes E5–E9) | launch the server through `mcplock proxy` (below) |
| H3 | PyPI: every file of the locked release is pinned; an added file blocks (closes E10) | `mcplock check --signals S1,S2,S3,S4,S5,H3` |

H2 wraps the server command in the MCP config. The first run with `--record` writes the pin into the lock:
```json
{"mcpServers": {"notes": {"command": "mcplock",
  "args": ["proxy", "--server", "notes", "--lock", "mcp-lock.json", "--record", "--", "npx", "-y", "notes-mcp@1.0.0"]}}}
```
`--record` writes only when the lock has no pin, so it never overwrites one. With a pin, a changed or added tool is
answered with a JSON-RPC error and the reason is logged on stderr. A new server version that legitimately changes its
tools needs a new pin: delete `tools.runtime` and run once with `--record`.

## Known limitations (to be measured in Phase 4)
- S5 inherits the static extractor's recall (held-out 78.0%): drift in runtime-generated tools is missed.
- v0.1 records build identity without verifying the Sigstore signature.
- PyPI has no per-release uploader, so S3 is npm-only.
- Commands hidden behind scripts the parser cannot follow (`npm run setup`, shell scripts) are not expanded.
