# Bagmar & Saraf 2026 pre-install hook: read-only analysis

**Source:** A. Bagmar, P. Saraf, "Setup Complete, Now You Are Compromised: Weaponizing Setup
Instructions Against AI Coding Agents", arXiv:2607.15143v1, 16 Jul 2026. Hook described in Sec. 9.3
("Pre-install verification hook"), Table 8, and Appendix I. The full extracted text was read (100%).

**Code availability (checked 2026-10-08):** the paper links `github.com/cardwizard/Sentinel`
(footnotes 3 and 6). That repository returns **HTTP 404** (`gh api repos/cardwizard/Sentinel`) and is
not among the author's 25 public repositories. Sec. 9.3 says the hook "is released as open
source", but Appendix B promises artifacts only "upon publication". **The "open-source" claim is
UNVERIFIED.** Everything below comes from the paper's prose and pseudocode, not from code.

## What it is
- A Claude Code `PreToolUse` hook on the shell tool, about 400 lines of Python (paper's figure).
- Input: the pending command as JSON on stdin. Output: allow or block on stdout. A block aborts the
  command before any install-time code runs.
- **Scope:** `pip install` and `uv pip install` only. Every other command passes through untouched.
  Out of scope by the authors' own statement: `uv sync`, `uv run`, `[tool.uv.sources]`, and PEP 517
  in-tree backends. There is no npm, npx, uvx or Cargo support.
- **Policy:** binary. Any warning blocks (`ALLOW if W == {} else BLOCK(W)`). There is no warn tier.
  The warning set goes back to the agent, and the hook never rewrites the command.

## The seven checks (Appendix I)
| # | Check | Mechanism | Property | Data source |
|---|---|---|---|---|
| 1 | Name proximity | Levenshtein distance = 1, adjacent transposition, or separator normalization against a popular-package set P | INTENDED | local list P (size and origin unspecified) |
| 2 | Existence | name absent on PyPI is flagged | INTENDED | PyPI |
| 3 | Age | first release < 30 days old | INTENDED | PyPI |
| 4 | Source trust | any `--index-url` / `--extra-index-url` not matching {pypi.org, files.pythonhosted.org, test.pypi.org} by **substring**; any `--trusted-host` | AUTHENTIC | command line |
| 5 | Hidden directives | opens `-r` files and scans for index redirects, trusted-host and `name==ver` pins | AUTHENTIC | local files |
| 6 | Config poisoning | `PIP_CONFIG_FILE` assignment in the command | AUTHENTIC | command line |
| 7 | Vulnerable pins | OSV query per `p==v`; warns only if a fixed version > v exists and names the lowest fix | SAFE | OSV |

## Reported results (baseline numbers to cite, not re-derive)
- Caught 10/11 scenarios R1–R11 (Table 8). It misses R7 (an error message suggests a real but
  unrelated package, `data-utils`).
- Benign false-positive estimate: 5 of the top-1,000 PyPI packages flagged (0.5%; our Wilson 95% CI
  [0.21%, 1.17%]). All 5 were edit-distance-1 collisions (for example `tomli`/`toml`).
- The authors call it a "feasibility demonstration" evaluated on "the scenarios it was built to
  catch, measuring construction rather than generalization" (Sec. 10).

## What it does not check (our gap)
- No signature, attestation or provenance verification. Provenance appears only as future work
  ("provenance verification, anomaly scoring on age, download volume, and maintainer history").
- No maintainer or publisher change detection.
- No install-script diffing (npm `preinstall`/`postinstall`, new `setup.py` behaviour).
- No content inspection at all, and no tool-definition awareness. MCP is never mentioned.
- No version-to-version comparison: every check is stateless and has no lockfile or prior state.
- Unpinned launches (`npx -y pkg`, `uvx pkg`) are invisible to it: they are not `pip install`, and
  without a `==` pin there is nothing for check 7 to query.

## Extension points for MCP-Lock
1. **Command recognizer** (`if c is not a (uv) pip install`). Our gate needs a recognizer for `npm i`,
   `npx [-y]`, `pnpm dlx`, `yarn dlx`, `bunx`, `uvx`, `pipx run`, `uv tool run`, plus MCP config
   writes (`.mcp.json`, `claude_desktop_config.json`, `claude mcp add`). These install without
   saying "install".
2. **Parser output** (packages, index URLs, trusted hosts, `-r` files). Extend it to resolve
   unpinned specs to a concrete `name@version` via the registry before checking. This also closes
   their stated "act on the resolved install set" limitation.
3. **Accumulator `W` and the binary policy.** Replace with typed signals S1..S5, a severity for each,
   and an allow/warn/block policy with a one-line reason.
4. **Per-package loop.** This is the natural slot for S2 (provenance continuity vs. lockfile), S3
   (maintainer change), S4 (new install script) and S5 (tool-definition hash drift). All four need
   prior state (the MCP-Lock entry), which the baseline lacks entirely.
5. **Trusted-source set T.** Swap the substring match for parsed-host equality (see RISKS.md) and
   add npm (`registry.npmjs.org`).
6. **Hook I/O contract** (JSON stdin to decision stdout). Reuse unchanged so the S1 baseline and the
   S1–S5 candidate run under the identical harness. This matters for a fair McNemar comparison.

## Implication for RQ2 parity
Without the code, "Bagmar parity" means reimplementing S1 **to the published spec** (Appendix I)
and checking that our S1 reproduces Table 8 (10/11, R7 missed) and roughly 0.5% top-1,000 PyPI
false positives. Every place where the spec is ambiguous (the P list, separator normalization rules,
URL matching) must be logged as a deviation. Recommended: Aakash emails the corresponding author
(address in the paper) to request the code or scenario repos before Phase 3.
