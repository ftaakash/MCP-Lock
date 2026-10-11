# Phase 5 evasion matrix (adaptive attacker, RQ3)

Frozen gate (`prereg-v1`) on local-registry attacks. G = all signals. Hardening is exploratory:
H1/H3 are gate checks (`gate/deptree.py`, `gate/signals.py`), H2 the runtime proxy
(`gate/proxy.py`), H4/H5 rules in `eval/adaptive/hardening.py`; costs on the Phase 4 benign
corpus are reported separately.

| Case | Tier | Attack | S1-C | G | signal | +all hardening |
|---|---|---|---|---|---|---|
| E1 | T1 | new name, edit distance >= 2, older than 30 days | allow | **warn** | gate:unlocked | warn |
| E2 | T2 | stolen token of the same maintainer; locked version had no provenance; runtime payload | allow | **allow** | — | block |
| E3 | T2 | stolen token; locked version had provenance | allow | **block** | S2:provenance_lost, S3:ci_to_human | block |
| E4 | T3 | payload shipped through the genuine release workflow | allow | **allow** | — | allow |
| E5 | T4 | poisoned description built at runtime (base64 + join) | allow | **warn** | S5:tool_drift | block |
| E6a | T4 | tools fetched from a remote URL; new version with identical code | allow | **allow** | — | block |
| E6b | T4 | tools fetched from a remote URL; rug pull changes the remote file only (no new version) | allow | **allow** | — | block |
| E7 | T4 | poisoning moved into an input-schema field description | allow | **warn** | S5:tool_drift | block |
| E8a | T4 | time bomb: extra tool registered only after a date | allow | **warn** | S5:tool_drift | block |
| E8b | T4 | extra tool registered from a base64 blob decoded at runtime | allow | **allow** | — | block |
| E9 | T5 | tools and payload live in a caret-range dependency; the locked server never changes | allow | **allow** | — | block |
| E10 | T2/T4 | extra file added to an already-locked PyPI release | allow | **allow** | — | block |

**E11 command shapes (T-any):** 13/22 blocked by G; 9 missed. With H5: 21/22 blocked.
Missed by G:

- `npm exec -y @mcplock-eval/adv-e11`
- `npm exec --package=@mcplock-eval/adv-e11 -- adv-notes`
- `npm x -y @mcplock-eval/adv-e11`
- `sh -c "npx -y @mcplock-eval/adv-e11"`
- `bash -lc 'npx -y @mcplock-eval/adv-e11'`
- `PKG=@mcplock-eval/adv-e11; npx -y $PKG`
- `npm install -g @mcplock-eval/adv-e11 && adv-notes`
- `npm i @mcplock-eval/adv-e11 && npx adv-notes`
- `echo bnB4IC15IEBtY3Bsb2NrLWV2YWwvYWR2LWUxMQ== | base64 -d | sh`

## Hardening (exploratory): which cases each switch closes

| Switch | Target cases | Closed (allow/warn → block, or blind spot removed) |
|---|---|---|
| H1 | E9 | E9 |
| H2 | E5, E6a, E6b, E7, E8a, E8b, E9 | E5, E6a, E6b, E7, E8a, E8b, E9 |
| H3 | E10 | E10 |
| H4 | E2 | E10, E2 |
| H5 | E11 | E11 |
