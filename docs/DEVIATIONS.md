# Deviations from the pre-registered plan

Registered plan: [PREREG.md](../PREREG.md), OSF https://osf.io/2amj3 (plan text commit `914d2b3`, code tag `prereg-v1`).
Every departure is logged here with date, reason and effect on results, before the affected results are reported.

| # | Date | Section | Deviation | Reason | Effect |
|---|---|---|---|---|---|
| 1 | 2026-10-11 | §3.4 | *Clarification, not a change.* Replay details fixed in `docs/REPLAY.md` before any scored run: each bundle holds the records of `a` and `b` only (so the gate resolves `b`); a pre-release `b` is launched pinned, with OSV advisories limited to those published by `t`; the lock has no static tool hash when its archive is over the size cap. | The plan says "replayed as of the newer version's publish time" without fixing these mechanics. | None on what is counted; pre-releases, lock-archive failures and lookup failures are reported as counts. |
| 2 | 2026-10-11 | §3.4 | B-mcp reuses the Phase 2 tool hashes and version records instead of downloading the archives again. | The extractor code is unchanged between `extract-v2.1` and `prereg-v1` (`git diff` is empty for `census/extract_*.py` and `census/tooldefs.py`). A recomputation check on a random sample of versions is reported with the results. | None expected; the check quantifies it. |
