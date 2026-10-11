# OSF registration check (2026-10-11)

Registration: https://osf.io/2amj3 · DOI 10.17605/OSF.IO/2AMJ3 · OSF Preregistration template · public, not withdrawn,
no embargo. Checked through the public OSF API (`api.osf.io/v2/registrations/2amj3/`) against this repository.

| Check | Result |
|---|---|
| Registered plan file `PREREG.md` (OSF sha256 `9acecd4f…5ddf27`) | identical to `git show 914d2b3:PREREG.md` |
| Only change to `PREREG.md` since registration | commit `a15e4cc`: the "Registry" row now names the OSF registration (allowed by the plan: "added in a separate commit; the plan itself is not edited") |
| Attached `sources.json` (sha256 `9f6a90b1…670fbe`) | identical to `eval/corpora/sources.json` (unchanged since `9a59fdf`) |
| Commits named in the registration | `914d2b3352193e4daf1e117048884fddc8bebecb` and `prereg-v1` = `9a59fdf7e1a0b41d4ac5506a91daaecaa2e5fe4f` both resolve |
| Dataset pins | ossf/malicious-packages `1861f95ffacc…`, DataDog dataset `805fcd72db52…`, same in `sources.json` |
| Order of events | `prereg-v1` tagged 2026-10-11 06:00 UTC → registered 07:25 UTC → first scored run 09:31 UTC (run provenance files) |
| R-B: 11 PyPI + 11 npm scenarios, R6b reported but not counted | as run (22 core, R6b non-core in `eval/scoring/rb.py`) |
| R-M: ≥ 200 cases, class C capped at 400, ≥ 100 class N | 400 C drawn, 32 not replayable (deviation #6) → 368 C + 100 N = 468 |
| B: about 8,195 transitions minus exclusions; MCP stratum from 984 packages | 8,180 (992 npm-top, 493 PyPI-top, 6,695 MCP); 984 MCP packages |
| Cluster bootstrap 10,000 resamples, seed 20261011 | `census.stats.stratified_bootstrap(B=10_000)`, `SEED = 20261011` |
| L: 200 packages (100 MCP, 50 npm, 50 PyPI) | `eval/scoring/latency.py` quota; 199 measured, 1 error reported |
| Hypotheses, kill rule, Holm, McNemar, primary definitions | match `PREREG.md` §1 and §5 and the reported Phase 4 analysis |
| Phase 5 (adaptive attacker, hardening) | outside this registration (stated in its "other" field); reported as exploratory |

Contributor name: the OSF profile has given name "Aakash", middle name "G", family name "S", so citation styles print
"S, A. G.". OSF builds citations from the profile, so changing the name fields there corrects the registration's
citations; the registration itself does not need to change.
