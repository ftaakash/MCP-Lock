# Phase 5 plan: adaptive attacker (RQ3) and paper

**RQ3.** Does the gate hold against an attacker who knows every check? For each realistic attacker, what is the
cheapest way past MCP-Lock, what does it require, and how much of the ecosystem is exposed to it?

Phase 4 established what the gate catches. Phase 5 asks what it *cannot* catch, and why, so that the paper's
security claim is bounded honestly. Every attack runs only against local registries (Verdaccio, plus a local PyPI
index), with inert payloads. Nothing is published publicly.

## 1. Threat model
The victim runs a coding agent with the MCP-Lock hook and a lock created when the server was benign. The attacker
knows S1–S5, the lock format, and the parser.

| Tier | Attacker controls | Real-world analogue | Can it publish with provenance? |
|---|---|---|---|
| **T1** squatter | a new package name | typosquats, slopsquats | no |
| **T2** stolen token | one maintainer's npm/PyPI token | token leaks, phishing, the 2025 npm worms | no (needs the CI identity) |
| **T3** CI / repo | the release workflow or a merged commit | build-pipeline compromise, malicious PR | **yes**: same repo, workflow and builder |
| **T4** owner | the package itself (malicious or sold maintainer) | MCP rug pulls, abandoned-package transfers | yes, if it already uses trusted publishing |
| **T5** dependency | a package that the locked server depends on | dependency takeover | depends on that package |

Out of scope: registry compromise, Sigstore forgery against the public-good instance, attacks on the model itself.

## 2. Evasion catalogue (to be built and measured)
Each row becomes one or more concrete packages on the local registry and is run through G. "Expected" is our
prediction from the code; the experiment decides.

| ID | Tier | Technique | Signals it targets | Expected |
|---|---|---|---|---|
| E1 | T1 | name at edit distance ≥ 2 from every popular name, aged > 30 days, default registry | S1 | evades S1; G warns `unlocked` on first use only |
| E2 | T2 | runtime payload in server code (no install script, tools unchanged); the locked version had **no** provenance; same maintainer account publishes | S2–S5 | **evades** (S2 inactive without provenance; S3 sees the same account) |
| E3 | T2 | same as E2, but the locked version **had** provenance | S2 | blocked by S2 |
| E4 | T3 | runtime payload shipped through the legitimate trusted-publishing workflow | S2–S5 | **evades**: provenance is genuine |
| E5 | T4 | description poisoning hidden behind dynamic construction (string concatenation, base64, env) | S5 | detected as drift if v1 was static (hash changes), but the diff hides the text |
| E6 | T4 | tools fetched from a remote URL at runtime; v1 is already dynamic, so the rug pull needs **no new version** | S5 | **evades**: nothing in the package changes |
| E7 | T4 | poisoning moved into an input-schema field description | S5 | detected (the schema is in the hash) |
| E8 | T4 | time bomb: new tools are registered only after a date or on a remote flag | S5 | depends on what the extractor sees; measured |
| E9 | T5 | tool definitions or payload moved into a dependency with a caret range; the locked server never changes | all | **evades**: the lock pins the top-level archive only, and `npx` resolves dependencies fresh |
| E10 | T2/T4 | PyPI: add a new wheel (for example a new platform tag) to an **already locked** release | integrity | **evades** if the installer picks the new file while the gate checks the locked one |
| E11 | any | command-shape evasion: `npm exec`, `pnpm dlx`, `yarn dlx`, `bunx`, `sh -c "npx …"`, `$PKG` expansion, `npx --package=`, `npm i x@npm:y`, script indirection | parser | measured per variant |

## 3. Measurements
1. **Evasion matrix:** for E1–E11, the G decision (block / warn / allow) and the signal responsible, run on the local
   registries with the frozen gate (`prereg-v1`).
2. **Exposure** from data we already have (no new crawling), with Wilson CIs. For example:
   - E2 needs a lock without provenance: 60.1% of the Phase 4 benign locks.
   - E6 needs a server whose tools static extraction cannot see: 21.7% of versions (Phase 2).
   - E9 needs a server with floating dependencies: to be counted from the Phase 2 manifests.
   - E10 needs a PyPI release that gained files after its first upload: to be counted from PyPI upload times.
3. **Attacker cost:** for each tier, what it needs (token vs CI vs ownership) and whether the attack leaves a public
   trace. This is qualitative and given in a table.

## 4. Hardening (exploratory; not part of the pre-registered claim)
Candidate fixes, each implemented as a switch, re-run on the evasion matrix **and** on the Phase 4 benign corpus, so
that every security gain is reported with its false-block or warn cost:

| ID | Fix | Closes |
|---|---|---|
| H1 | lock the full resolved dependency tree (integrity of every transitive package) | E9 |
| H2 | runtime `tools/list` pinning: hash the live tool list when the server starts (MCP proxy) | E5, E6, E8 |
| H3 | PyPI: lock the digests of **all** files of a release and pass `--require-hashes` | E10 |
| H4 | policy option "require provenance" (block servers without it) | E2 |
| H5 | parser normalisation for the E11 variants | E11 |

Phase 4 results remain the confirmatory ones; hardening results are labelled exploratory.

## 5. Paper (IEEEtran)
Working title: *MCP-Lock: Pinning Provenance and Tool Definitions for Coding-Agent MCP Servers*.

1. **Introduction:** the unpinned `npx -y` problem; three contributions (census, gate, pre-registered evaluation with an
   adaptive attacker).
2. **Background and threat model:** MCP, npm/PyPI provenance, Bagmar & Saraf, Kapner et al.
3. **RQ1 census:** Phase 1–2 (36.5% drift; 97% of it carries no metadata signal).
4. **MCP-Lock design:** lockfile spec, signals S1–S5, hook.
5. **RQ2 evaluation:** Phase 4 (pre-registered, kill rule, ablation, cost).
6. **RQ3 adaptive attacker:** evasion matrix, exposure, hardening.
7. **Discussion and limitations:** S2 on removed versions, static extraction, PyPI.
8. **Related work.**
9. **Conclusion.** Artifact and OSF links.

Citations are only those verified in `docs/CITATIONS_VERIFIED.md` plus new ones verified the same way; anything
unverified is marked UNVERIFIED.

## 6. Order of work
1. Build E1–E11 on local registries; run the evasion matrix. Add a local PyPI index (pypiserver, 127.0.0.1) for E10.
2. Compute the exposure numbers from existing data.
3. Implement H1–H5 as switches; re-run the evasion matrix and the Phase 4 benign corpus.
4. Write the paper section by section, figures from the result files.
5. STATUS, README, final cleanup (stop and remove the local registries).

**Review points for Aakash:** the threat-model tiers, whether E10/E11 belong in scope, and which hardening fixes are
worth building.
