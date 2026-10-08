# How faithfully can S1 (Bagmar & Saraf hook) be rebuilt from the paper?

Source: arXiv:2607.15143v1, Sec. 9.3, Table 8, Appendix I. The code is unavailable (repo 404, checked 2026-10-08).

## Per-check fidelity
| # | Check | Specified in paper | Left open | Fidelity |
|---|---|---|---|---|
| 2 | Existence | absent on PyPI → flag | name normalization (PEP 503?) | High |
| 3 | Age | first release < 30 days | yanked releases, timezone | High |
| 4 | Source trust | 3 trusted hosts, substring match; any `--trusted-host` | `-i` short flag, `--index-url=` form, env `PIP_INDEX_URL` | High (literal) |
| 6 | Config poisoning | `PIP_CONFIG_FILE` assignment in command | `export` vs inline, `PIP_*` variables in general | High |
| 7 | Vulnerable pin | OSV; only advisories with a fix > v; report lowest fix | OSV snapshot date (results drift) | High, with the date pinned |
| 5 | Hidden directives | scan `-r` files for index redirects, trusted-host, `==` pins | nested `-r`, `-c` constraints, `-i` inside files | Medium |
| 1 | Name proximity | Levenshtein 1, adjacent transposition, separator normalization vs P | **P (size/source)**, case folding, exemptions, popularity ratio | **Low on false positives** (see below) |
| – | Command parsing | `pip install`, `uv pip install` | `python -m pip`, `pip3`, extras/markers, `-e .` | Medium |
| – | Hook I/O | JSON stdin, allow/block stdout | exit-code vs JSON decision form | Behaviourally irrelevant |

## Calibration: check 1 read literally does not reproduce the reported 0.5%
`results/baseline/s1_calibration_2026-10-08/` (top-15k PyPI snapshot of 2026-10-01): top-1,000 packages flagged by
check 1 alone, by size of P:

| P | 100 | 250 | 500 | 1,000 | 2,000 | 5,000 | 10,000 |
|---|---|---|---|---|---|---|---|
| flagged / 1,000 | 3 | 17 | 31 | **52** | 71 | 115 | 171 |

The paper reports **5 / 1,000**, and gives `tomli`/`toml` as an example. Read literally, the description reaches about
5 only with a very small P (about the top 100 to 150), or with an unstated filter (for example a popularity-ratio or
allowlist rule). Our snapshot is four months newer than theirs (June 2026), which does not explain a tenfold gap.
**The false-block rate, the main RQ2 comparison axis, is therefore underdetermined by the paper.**

## Scenarios R1–R11: reconstructable
- Given verbatim: the 40 sweep names (Table 11), the 10 CVE pins (Table 12), R5 (`httpclient`, `pytest==99.0.0`,
  `--extra-index-url http://packages.internal/simple/`), R7 (code shown), R10 (Makefile sets `PIP_CONFIG_FILE`).
- **Two coverage claims the pseudocode cannot explain:**
  - R3 and R11 put the typo in `pyproject.toml`, but the pseudocode never reads `pyproject.toml`.
  - R10 is triggered by `make setup`, which is not a pip command, so it should pass through untouched.
  So either the real code does more than Appendix I shows, or Table 8 was scored by feeding the expanded pip command
  to the hook directly. Our harness must state which input form it uses.

## Plan for a fair, defensible baseline
1. **S1-literal:** implement Appendix I exactly (substring URL match, no pyproject/Makefile parsing).
2. **S1-charitable:** fix every ambiguity in the baseline's favour (parse pyproject and Makefile; host-equality URL
   match; P chosen so the top-1,000 PyPI false positives equal 5, documented as calibration).
3. Report RQ2 against **both**. The headline uses the stronger baseline on each metric, so no reviewer can call it a strawman.
4. Parity targets: Table 8 pattern (10/11, R7 missed) and 5/1,000 top-PyPI flags. Every mismatch is logged here.
5. Send this file to the authors with the request for code. If they reply, swap S1 for their code and re-run.
