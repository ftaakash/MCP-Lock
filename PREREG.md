# Pre-registration: MCP-Lock gate evaluation (Phase 4, RQ2)

| | |
|---|---|
| Title | Does build-provenance and tool-definition pinning catch MCP-server supply-chain attacks that name/source checks miss, and at what false-block cost? |
| Author | Aakash (GitHub: ftaakash) |
| Repository | https://github.com/ftaakash/MCP-Lock |
| Version | PREREG v1, written 2026-10-10, **before any Phase 4 evaluation run** |
| Code frozen at | tag `prereg-v1`. The commit hash goes into the registration form. |
| Registry | OSF or Zenodo. The DOI or URL is added here after registration in a separate commit; the plan itself is not edited. |

## 0. What is already known (disclosed so readers can judge what is confirmatory)
Phases 1–3 have already been run and published in this repository. The following results were seen before this plan
was written:
- **Benign base rates per npm/PyPI transition (Phase 2, Part M):**
  - Provenance lost: 0.36% npm, 0.54% PyPI.
  - New install script: 0.13% npm.
  - CI → human publisher: 0.24% npm.
  - Human → human publisher: 0.58% npm.
  - MCP transitions with a tool-definition change: 33.7% (Part T).
  These figures predict that S2 and S4 will add false blocks and that S5 will warn on about a third of MCP upgrades.
  This plan therefore treats those costs as **outcomes to report, not to hide**.
- **S1 parity (Phase 3):**
  - Literal variant: 10/11 on the Bagmar & Saraf scenarios (command form).
  - Charitable variant: 10/11 on every form.
  - False positives on the top 1,000 packages: 0/1,000 for the charitable variant; 52 (PyPI) and 35 (npm) for the literal variant.
- **No gate output has been computed** on any corpus defined below. That covers the OSV malicious-package versions, the
  synthetic rug pulls and the benign upgrade pairs.

## 1. Research question and hypotheses
**RQ2.** Does the MCP-Lock gate catch more real attacks than the Bagmar & Saraf baseline (S1)? At what false-block rate
on benign upgrades, and at what latency?

- **H1 (detection).** On the real-attack corpus R (§3.1, §3.2), the gate G detects more cases than S1-charitable.
  G = S1-charitable plus S2–S5 and the same-version integrity check.
- **H2 (cost).** On the benign corpus B (§3.4), G's false-block rate differs from S1-charitable's. The test is
  two-sided, and the expected direction is higher.
- **KILL rule** (from the project brief, fixed here): **the method claim is withdrawn if S2–S5 add fewer than 2
  detections over S1-charitable on R while G's false-block rate on B is equal to or worse than S1-charitable's.**
  - If killed, the paper reports the census (RQ1) and the evaluation as a negative result.
  - The paper may not claim that provenance or tool pinning improves detection.

H1, H2 and the kill rule are the only confirmatory analyses. Everything else in §5 is descriptive.

## 2. Systems compared
| ID | System | Role |
|---|---|---|
| S1-L | Bagmar & Saraf hook, literal Appendix I reading (`S1Config.literal()`) | baseline, reported |
| **S1-C** | Same hook with ambiguities resolved in its favour (`S1Config.charitable()`) | **primary comparator** (the stronger baseline: equal detection on Table 8, 0% false positives) |
| **G** | S1-C + S2 + S3 + S4 + S5 + integrity check (`gate.core.evaluate`, all signals) | **candidate** |
| G−Sk | G without one signal Sk (k = 2…5) | ablation, descriptive |

Configuration is exactly as at tag `prereg-v1` (`docs/GATE.md`): S2 and npm S4 block; S3, S5 and PyPI S4 warn.
Baseline and candidate outputs are written to separate folders: `results/baseline/phase4/` and `results/candidate/phase4/`.

### 2.1 What counts as a detection
- A case is **detected** if the decision is `block` or `warn` and at least one *counted* finding caused it.
  - Counted findings: any S1–S5 finding, plus `gate integrity_mismatch`.
- Not counted:
  - `gate unlocked`: it fires for every unlocked server, malicious or not.
  - `gate lookup_failed` and `gate unresolvable`: these are availability failures.
  - `info` findings.
  These are reported separately.
- Primary: block ∪ warn. A `warn` becomes `ask` in the Claude Code hook, so the agent cannot proceed without a human.
- Secondary: block only.

## 3. Corpora
All corpora are fixed by the procedures below before any gate run. Seed for every random draw: **20261011**.

### 3.1 R-B: Bagmar & Saraf scenarios (real-attack corpus, part 1)
- Source: `eval/scenarios/bagmar.py`.
  - PyPI R1–R11 as reconstructed in Phase 3.
  - npm port R1–R11.
  - R6b is reported but excluded from R, as in Table 8.
- Forms: command form and agent form (Phase 3 definitions). The confirmatory count uses the agent form, because
  that is what an agent runs. Command form is reported alongside.
- The scenarios are first installs with no lock entry. S2–S5 therefore cannot fire by design, and G = S1-C is
  expected. This corpus checks that G loses no baseline detection.

### 3.2 R-M: real malicious versions from OSV / OpenSSF (real-attack corpus, part 2)
- **Source.** `ossf/malicious-packages` (GitHub), OSV records with `MAL-` IDs, ecosystems npm and PyPI.
  - The repository commit is pinned on the day of registration and recorded in `eval/corpora/mal_commit.txt`.
- **Window.** Malicious versions published 2024-01-01 to 2026-10-08. Publish time comes from the registry `time`
  field, or from the record's `published` date when the registry no longer lists the version.
- **Classes**, assigned by rule before any gate run:
  - **C (compromised existing package):** the package has at least one version, published at least 7 days before
    the malicious version, that no `MAL-` record lists as affected. These are the cases S2–S5 are designed for.
  - **N (new or typosquat package):** every other record.
- **Selection:**
  - All C cases.
  - Plus a seeded random sample of N cases, stratified by ecosystem in proportion to the frame, so that
    |R-M| ≥ 200.
  - When fewer than 100 N cases would be included this way, draw 100.
  - One malicious version per record: the lowest affected version.
  - For ranges or `*`, use the first version the registry or record lists.
- **Replay context, as of the malicious publish time t:**
  - **C:** the lock pins the most recent unaffected version published before t. Its provenance, publisher, install
    scripts and tool hash are taken from the registry, as `mcplock lock` would record them. Command: `npx -y <pkg>` or
    `uvx <pkg>`, which resolves to the malicious version.
  - **N:** no lock. Command: `npm install <pkg>` or `pip install <pkg>`; the launch form is reported as well.
  - Metadata is truncated to versions published at or before t. Registry popularity lists, OSV and the name tables
    are used as frozen in Phase 3; this lookahead is stated as a limitation.
- **Evaluability.** Most malicious versions have been removed from the registries, so for each case and signal the
  input is either *observed* or *not evaluable*:
  - **S2.** Observed only if the version's registry record survives (attestation present or absent) or an archived
    copy records it. A removed version is **never** treated as "provenance lost".
  - **S3.** Observed only if `_npmUser` for the version is available.
  - **S4.** Observed if the version's `package.json` or registry record is available.
  - **S5.** Observed if the archive is available.
  - **Primary analysis:** a non-evaluable signal produces no finding, so it counts as a miss. This is conservative
    against G.
  - **Sensitivity analysis:** restricted to cases where every signal is evaluable.
- **Allowed sources:**
  1. The live registry (read-only, cached, rate-limited).
  2. The OSV record.
  3. A published malware-sample dataset with archives, if Aakash approves the download. The candidate is
     `DataDog/malicious-software-packages-dataset`; its availability and licence are **UNVERIFIED**.
  - No other sources may be added after registration without a logged deviation.
- **Safety.** Malicious archives are opened only inside Docker with `--network none` and a read-only mount, and are
  parsed statically. No code from them runs.

### 3.3 R-S: synthetic rug pulls on a local Verdaccio (mechanism corpus; **not part of R**)
- **Base servers.** 10 npm MCP servers drawn by seeded random from the Phase 2 sample. Eligibility:
  - permissive licence (MIT, Apache-2.0, ISC or BSD);
  - latest version has npm provenance and a CI publisher;
  - static extraction finds at least 1 tool;
  - archive under 5 MB.
- **Setup.** Each server's latest version is republished as v1 under the local scope `@mcplock-eval` on Verdaccio at
  `localhost` only (no uplink for that scope). The lock is generated from v1.
  - Verdaccio does not serve npm attestations (to be checked; if it does, the real endpoint is used). A local stub
    serves the copied v1 attestation and none for attack versions unless stated.
- **Attacks.** Four attack classes × 10 servers = **40 rug pulls**. Each is a patch bump; payloads are inert (they write a
  marker file and never touch the network).

  | Class | Change in v2 | Signal expected by design |
  |---|---|---|
  | A1 description poisoning | one tool description gains an injected instruction; nothing else changes | S5 |
  | A2 tool addition | a new tool is added | S5 |
  | A3 install script | `postinstall` is added | S4 |
  | A4 account takeover | inert payload; published manually by a different user, without attestation | S2, S3 |

- **Controls.** 10 benign v2 versions (version and README change only) as false-block controls.
- **Interpretation.** These attacks were built by us to target our signals. R-S therefore measures **implementation
  coverage**, not real-world detection, and is excluded from H1 and the kill rule.
- Nothing is ever published to a public registry.

### 3.4 B: benign upgrades (false-block corpus)
| Stratum | Packages | Transition |
|---|---|---|
| B-npm | top 1,000 npm (`gate/data/top_npm.json`, npm-high-impact 1.13.0) | latest consecutive stable pair, newer version published on or before 2026-10-08 |
| B-pypi | top 500 PyPI (`gate/data/top_pypi.json`) | same |
| B-mcp | Phase 2 Part T sample | **all** 6,695 window transitions (2026-07-10 → 2026-10-08), lock = older version |

- **Replay.** Each transition is replayed as of the newer version's publish time. Command: `npx -y <pkg>` or
  `uvx <pkg>`, with the lock pinned to the older version.
- **Benign label.** Benign unless any `MAL-` or GHSA malware advisory lists the newer version as of the evaluation
  date.
  - Flagged transitions are reviewed **only** to catch unlabelled malware.
  - If any is found, work stops and the case goes privately to npm or PyPI security before anything else (project
    hard rule). It is then moved to R-M with a logged deviation.
  - No other relabelling is allowed.
- **Exclusions:** packages with fewer than 2 stable versions, or unresolvable on the registry. They are counted and
  reported.

### 3.5 L: latency sample
- 200 packages drawn by seeded random: 100 from B-mcp, 50 from B-npm, 50 from B-pypi.
- Each runs the real gate in **live** mode: the lock pins the second-latest version and the launch resolves the
  latest.
- **Cold run:** empty `MCPLOCK_CACHE`. **Warm run:** repeated immediately afterwards.
- Single process on the author's machine. CPU, RAM, OS, network and the date are recorded.

## 4. Outcomes
| Outcome | Definition | Corpus |
|---|---|---|
| **Detection rate** (primary) | detected cases / cases (§2.1, block ∪ warn) | R = R-B (agent form) ∪ R-M |
| Detection per attack class | same, by R-B scenario class, R-M class C / N, R-S class A1–A4 | R-B, R-M, R-S |
| Added detections Δ | cases detected by G and not by S1-C | R |
| **False-block rate** (primary) | benign transitions with decision `block` / transitions | B |
| Warn rate | benign transitions with decision `warn` / transitions | B |
| Interruption rate | block ∪ warn on benign | B |
| S2 coverage | share of transitions where the locked version has provenance (S2 can fire) | B, R-M |
| Per-signal contribution | detections and false blocks with each Sk removed | R, B |
| Latency | wall-clock per command: median, p95, max; share over 60 s and over 120 s (hook timeout) | L |

## 5. Statistical analysis
- **Intervals:** Wilson 95% for every proportion.
  - B-mcp has several transitions per package, so it also gets a stratified cluster bootstrap by package:
    10,000 resamples, seed 20261011.
- **H1:** exact McNemar test (binomial on discordant pairs) for G vs S1-C on R, two-sided, α = 0.05.
  - G contains S1-C, so only one discordant direction is possible, and the test reduces to "Δ > 0".
  - At least 5 discordant cases are needed to reach p < 0.05. This is stated so that "Δ = 2 passes the kill rule
    but not the test" is not a surprise.
- **H2:** exact McNemar test on B, paired by transition, for false blocks G vs S1-C, two-sided. The difference is
  reported with a Newcombe paired score interval.
- **Multiplicity:** Holm correction across H1 and H2. Everything else is descriptive, with no p-values beyond those
  listed.
- **Kill rule:** evaluated on the primary definitions (block ∪ warn, agent form, all R-M cases with
  non-evaluable signals counted as misses). Secondary and sensitivity versions are reported but **cannot overturn a kill**.
- **Ecosystems:** results are reported for npm and PyPI separately and pooled. Pooling is primary.

## 6. Software freeze and deviations
- The gate and S1 code are frozen at `prereg-v1`. Corpus builders, the replay adapter (metadata as of t, the
  Verdaccio and attestation stub) and scoring scripts are written **after** registration, before any scored run.
  They are tested only on toy fixtures and on R-S controls.
- **Bugs found during evaluation:**
  - A fix gets a new tag.
  - Both pre-fix and post-fix results are reported.
  - The confirmatory numbers are the pre-fix ones unless the bug is a crash or harness error unrelated to detection
    logic.
- Every deviation is logged in `docs/DEVIATIONS.md` with date, reason and effect. Each result file carries a
  provenance JSON (command, commit, timestamp, input hashes).

## 7. Stop rules
- A live malicious version found anywhere: stop and tell Aakash; it goes privately to npm or PyPI security first.
- Downloads over 5 GB, or runs longer than 12 h: ask first.
- Anything run against a registry other than the local Verdaccio is read-only.

## 8. Known threats to validity
- **Sample construction:**
  - R-M is dominated by removed versions, so S2–S5 evaluability will be partial. The primary analysis counts that
    against G.
  - R-M covers malware broadly, not MCP servers specifically. S5 is mostly not exercised on it.
- **Measurement limits:**
  - S5's recall is bounded by the static extractor's held-out recall of 78.0%.
  - Signatures are not verified (v0.1), so a forged attestation would pass S2. This is RQ3 (Phase 5).
  - Benign labels can be wrong (undiscovered malware), which would inflate false blocks.
- **Replay and data effects:**
  - Popularity lists and the OSV snapshot are newer than t, which introduces lookahead.
  - Latency depends on the network and the machine; it is measured live, not in replay.

## 9. Decisions for Aakash before registering
1. **Kill rule on real attacks only**, with the synthetic rug pulls excluded. *Recommended*: including attacks we built
   for our own signals would make the rule trivial to pass.
2. **Warn counts as a detection** (primary block ∪ warn, secondary block only). *Recommended*: the hook turns warn
   into a human prompt.
3. **Approve downloading a malware-sample dataset** for R-M archives. Size and licence are to be checked first. If
   not approved, S4 and S5 on removed versions are not evaluable.
4. **Registry:** OSF (supports embargo) or Zenodo (DOI).
