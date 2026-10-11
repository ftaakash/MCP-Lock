# Offline replay (Phase 4)

The registered plan ([PREREG.md](../PREREG.md) §3.2, §3.4) replays every case *as of* a past time `t`. This file fixes how,
before any scored run. Code: [`eval/replay.py`](../eval/replay.py) (runner), [`eval/corpora/`](../eval/corpora/) (bundle builders).

## Two stages
1. **Bundle** (network, read-only, cached). For each case, everything the gate would have fetched at `t` is written to one
   JSON bundle: version records, the lock entry, registry age/existence, OSV advisories, build identities, tool hashes and
   per-signal evaluability.
2. **Replay** (no network). The frozen gate (`gate/`, tag `prereg-v1`) runs unchanged. Its registry lookups are answered from
   the bundle, and every `census.http` call raises `OfflineViolation`, so a missing input fails loudly instead of fetching
   today's data. Malicious archives are only touched in stage 1.5 (static tool extraction inside Docker, `--network none`).

Systems per case: `S1-L`, `S1-C`, `G`, and `G-S2` … `G-S5`. Signals marked not evaluable are switched off for that case.
A case counts as detected only for block or warn caused by an S1–S5 finding or `integrity_mismatch` (PREREG §2.1).

## Benign transitions (B)
| Item | Rule |
|---|---|
| case | transition `a → b`, replayed at `t` = publish time of `b` |
| versions in bundle | the records of `a` and `b` only. The gate resolves the highest stable version it is given, so it resolves `b` |
| command | `npx -y <pkg>` / `uvx <pkg>`. If `b` is a pre-release, it is pinned (`<pkg>@b` / `<pkg>==b`), because an unpinned launch never selects a pre-release |
| lock | entry for `a`: integrity, archive, build identity, publisher and maintainers of `a`, install scripts of `a`, tool hash of `a` |
| S1 age | first release = earliest publish time at or before `t` |
| S1 OSV | only for pinned specs; advisories published after `t` are dropped |
| tools (mcp stratum) | Phase 2 tool hashes. `census/extract_*.py` and `census/tooldefs.py` are unchanged between tags `extract-v2.1` and `prereg-v1`, and the census and the gate hash the same way (valid tools → dedupe → sha256) |
| tools (top strata) | computed with the gate's own `signals.static_tools` |
| lock archive too large / digest error | lock `tools.method = "unavailable"`, so S5 cannot fire, as for a real lock without a static hash |
| identity lookup error after retries | S2 not evaluable for that case; reported as a lookup failure |
