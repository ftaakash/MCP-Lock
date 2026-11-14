# Pre-registration addendum A1: the locked-server age exemption on post-freeze data

**Written 2026-11-14.** This addendum to the OSF registration (osf.io/2amj3, DOI 10.17605/OSF.IO/2AMJ3) must be filed on
OSF before any scored run. It does not change the original registration or its results: H1, H2 and the kill rule of
`PREREG.md` stay as reported.

## 0. What is already known (disclosed)

| Source | Finding |
|---|---|
| Phase 4 | G's false-block rate on B is 33.4%, and 2,695 of its 2,729 false blocks involve S1 `new_package` (the baseline's 30-day age rule). |
| Exploratory analysis (`eval/adaptive/age_rule_sensitivity.py`) | Waiving that rule for locked servers gives 0.73% false blocks on B and 38.2% detection on R (8 young hijacked packages are lost). Warnings rise to 27.7%. |
| Why a new corpus | The exemption was chosen after seeing those results, so it is re-tested here on cases published after the original freeze, which no design decision has seen. |

## 1. Hypotheses (confirmatory)

| | Hypothesis | Corpus | Test |
|---|---|---|---|
| **A-H2** (cost) | G-X's false-block rate differs from S1-C's (expected: lower) | B′ | exact McNemar, paired by transition, two-sided |
| **A-H1** (detection) | G-X detects a different number of cases than S1-C (expected: more) | R-M′ | exact McNemar, paired by case, two-sided |

- **Multiplicity:** Holm correction across A-H1 and A-H2, α = 0.05.
- **Claim rule:** the paper may call G-X "a deployable default" only if A-H2 is significant with G-X lower, **and** G-X's
  point detection on R-M′ is at least S1-C's. Otherwise it reports the exemption as not confirmed.
- **Everything else is descriptive.**

**Power note.** R-M′ covers a 30-day window, so the number of class-C cases may be small. A-H1 can then fail for lack
of discordant pairs. That is reported as "not shown", not as "no difference".

## 2. Systems

| ID | System |
|---|---|
| S1-L, S1-C | baseline, exactly as registered |
| G | as registered (frozen at `prereg-v1`) |
| **G-X** | G, except that S1 `new_package` findings are dropped for a launched package that has an entry in the lock. Nothing else changes: same signals, same severities, same decision rule. Unlocked packages (class N, first use) keep the age rule. |
| G-X−Sk | ablations, descriptive |

- **Code freeze:** the scored code is tag `age-x-v1`. It is the `prereg-v1` gate and extractor v2 plus only the
  exemption, the system entry and the window settings below.
- **Bug fixes:** handled as in `PREREG.md` §6.

## 3. Corpora (post-freeze window)

**Window:** versions published from **2026-10-09T00:00:00Z to 2026-11-07T23:59:59Z**. The window ends one week before
the data pins, to leave time for malware reports on the newest versions.

- **B′ (benign upgrades).** Same strata and rules as `PREREG.md` §3.4, with the window above:
  - B-mcp′: every transition of the 2,000 Phase 2 sample packages whose newer version is in the window and whose two
    versions both have statically extracted tools (extractor v2). Lock = older version.
  - B-npm′ / B-pypi′: top 1,000 npm / top 500 PyPI (same lists). The latest consecutive stable pair **whose newer
    version is in the window**; packages without one are counted as excluded.
  - Benign label, review, exclusions and the stop rule for live malware are unchanged.
- **R-M′ (real attacks).** Same rules as `PREREG.md` §3.2 (class rule C/N, C_MIN_DAYS = 7, all C cases with cap 400, N
  sample to reach |R-M′| ≥ 200 with at least 100 N, one version per record, evaluability, safety), with these changes:
  - malicious versions published in the window above;
  - `ossf/malicious-packages` at commit `016024d631828d2b6827bee160888f7205e42635` (fetched 2026-11-14);
  - the DataDog dataset at the latest commit on the day of the scan, recorded in `eval/corpora/sources_a1.json` before
    the scan;
  - seed 20261114.
- **R-B and R-S:** not re-run. R-B is a fixed scenario set already scored. R-S is synthetic.

## 4. Outcomes and analysis

Outcomes are as in `PREREG.md` §4 and §5 (detection on block ∪ warn, Wilson intervals, cluster bootstrap for B-mcp′
by package with seed 20261114), for S1-L, S1-C, G and G-X.

- **Reported for G-X:** warn and interruption rates, so the false-block reduction is not shown alone.
- **Reported, not tested:** the G versus G-X difference on both corpora.

## 5. Stop rules

As `PREREG.md` §7. Downloads above 5 GB or runs longer than 12 h are asked about first.

---

**Filing record.** Filed on OSF as an update to osf.io/2amj3 on 2026-11-15, before any scored run. Every section's text
was added to the original answers. The PDF could not be attached in the update form, so the context section links to
this file at commits `bb70a6a` (text) and `3c836ec` (PDF). The update may show as pending until OSF approves it.
