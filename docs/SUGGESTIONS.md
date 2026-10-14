# Safer-alternative suggestions (2026-10-14, exploratory)

When the gate flags a command it now proposes a replacement, and shows it only if the gate passes the replacement.
Decisions never change. Code: `gate/suggest.py`; usage: `docs/GATE.md`; evaluation: `eval/adaptive/suggest_eval.py`
→ `results/candidate/phase5/suggestions.json` (per case: `suggestions_cases.jsonl.gz`). Not pre-registered.

## What is suggested
| Finding | Suggestion |
|---|---|
| typosquat (S1 `name_proximity`) | the popular package the name imitates |
| vulnerable pin (S1 `vulnerable_pin`) | the lowest release with no advisory, stepping forward when a fix carries newer advisories (axios 0.21.0 → 0.33.0 → 0.34.0) |
| lock checks S2–S5 / H1 / H3 / digest mismatch, or any flag on a locked package | newest version between lock and target that passes every lock check, then the locked version |
| unknown or new name (S1 `absent` / `new_package`) | up to three popular names within edit distance 2 |
| not locked | advice: review, then `mcplock lock` |

Several packages in one command are fixed in one combined command, checked as a whole. Packages named only in a
project file (requirements.txt, package.json, pyproject.toml) get a verified edit ("change X to Y") instead.

## Results
| Corpus | Flagged by G | Verified suggestion | Correct | Suggests the attack |
|---|---|---|---|---|
| R-S synthetic rug pulls | 40 | 40 (100%) | 40/40 locked v1 | 0 |
| R-M hijacked packages (class C) | 116 | 114 (98.3%, CI 93.9–99.5) | 114/114 last clean version | 0 (CI 0–3.3) |
| Adaptive attacks E1–E11 | 18 | 17 | 17/17 locked v1 | 0 |
| R-B typosquats (agent + command form) | 20 | 20 | 20/20 intended package | — |
| R-B vulnerable pins | 4 | 4 | 4/4 fixed version | — |
| R-M new / typosquat names (class N) | 59 | 0 | — | — |
| B benign upgrades | 4,075 | 4,075 | rollback to the reviewed version | — |

- Class C "correct" is by construction of the corpus: the lock is the last version no advisory lists. A version
  that was malicious but never reported would not be caught by this check.
- Class N: none of the 59 flagged names is within edit distance 2 of a popular name; these are invented names, not
  typos, so there is nothing safe to point to. The gate says nothing rather than guess.
- The 2 class C misses (`sklern`, `morin`) are locked packages whose own name trips the typosquat rule, so rolling
  back still fails the gate; the popular-name alternative could not be checked offline.
- On benign upgrades every suggestion is a rollback to the reviewed version: safe, but it defers an honest update
  until the user re-locks. Re-locking remains the way to accept an update.

## Novelty sweep (2026-10-14)
alphaXiv searches (typosquatting / package hallucination / remediation; coding-agent guardrails that propose a safe
command) plus a web search for industry tools.

| Part | Prior art | Verdict |
|---|---|---|
| typosquat → intended package | Socket "Did you mean" alert (socket.dev/alerts/didYouMean); SpellBound (arXiv:2003.03471) flags typosquats before install | not new |
| vulnerable pin → fixed version | `npm audit fix`, `pip-audit --fix`; OWASP cve-lite-cli notes `npm audit` can land on a version that is still vulnerable | not new; the fixpoint step and gate re-check address that known weakness |
| rug pull / hijack → locked or last-good version, re-checked by the gate and returned to the agent as a runnable command in the pre-execution hook | not found. Closest: TRIAD (arXiv:2606.05805) feeds natural-language guardrail feedback to the agent, not a concrete command, and its abstract does not mention packages; CARE (arXiv:2607.21642) verifies shell commands before execution; its abstract describes verification only and does not mention proposing replacements (full text not read) | possibly new as a combination; modest (it applies lockfile semantics at the moment of the block) |

Claim to make, if any: an engineering contribution with measured coverage and safety, not a novelty claim.
