# Citation verification log

| Claim in brief | Source | Status | Notes |
|---|---|---|---|
| Bagmar & Saraf hook: 7 checks, pip-only, 11 scenarios | arXiv:2607.15143v1 (16 Jul 2026), Sec. 9.3, App. I | VERIFIED (full text) | Covers `pip install` **and** `uv pip install`. Code repo `cardwizard/Sentinel` is 404, so "open source" is UNVERIFIED. |
| Kapner et al.: 9.8% of setups unpinned | arXiv:2609.07360**v3** (25 Sep 2026), Table 1, Sec. 4.2 | VERIFIED (full text, 2026-10-08) | 260 of 2,660 setups = 9.8%; 24.5% of the 1,063 setups with MCP config. Corpus proportions with **no CIs** (non-probability sample). v3 title: "Scanning the Harness: Configuration Exposures in AI Coding-Agent Supply Chains" (v1 title differs, so cite v3). Explicitly says "No ... installation-provenance analysis was conducted", which supports our gap. Artifact: github.com/Benkapner/harness-eval-experiments @ 217b8620e8a7 (961 unpinned-MCP findings). Possible extra frame source F3, pending a licence check. |
