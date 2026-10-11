# Citation verification log

| Claim in brief | Source | Status | Notes |
|---|---|---|---|
| Bagmar & Saraf hook: 7 checks, pip-only, 11 scenarios | arXiv:2607.15143v1 (16 Jul 2026), Sec. 9.3, App. I | VERIFIED (full text) | Covers `pip install` **and** `uv pip install`. Code repo `cardwizard/Sentinel` is 404, so "open source" is UNVERIFIED. |
| Kapner et al.: 9.8% of setups unpinned | arXiv:2609.07360**v3** (25 Sep 2026), Table 1, Sec. 4.2 | VERIFIED (full text, 2026-10-08) | 260 of 2,660 setups = 9.8%; 24.5% of the 1,063 setups with MCP config. Corpus proportions with **no CIs** (non-probability sample). v3 title: "Scanning the Harness: Configuration Exposures in AI Coding-Agent Supply Chains" (v1 title differs, so cite v3). Explicitly says "No ... installation-provenance analysis was conducted", which supports our gap. Artifact: github.com/Benkapner/harness-eval-experiments @ 217b8620e8a7 (961 unpinned-MCP findings). Possible extra frame source F3, pending a licence check. |

## Paper references (verified 2026-10-11, Phase 5 / Stage 8)
Each entry was checked against its primary source (arXiv abstract page, Crossref record for the DOI, or the publisher's
own page). Bibliographic data in `paper/refs.bib` is copied from these checks.

| Key | Source checked | Status | Notes |
|---|---|---|---|
| kraishan2026drift | arXiv:2609.14119v1 (12 Sep 2026), full text read | VERIFIED | Closest work to RQ1. Measures drift of registry fields (description, packages, remote endpoints) on 8,900 multi-version servers; states the registry "does not version tool definitions at all"; recommends client-side pinning. Does not diff tool definitions. Its own reference list misspells the authors of arXiv:2509.24272. |
| metere2026attested | arXiv:2605.24248 (abstract and intro read) | VERIFIED | Signed clearance assertion + per-server tool allowlist for MCP hosts. |
| hou2025mcp | arXiv:2503.23278 (v1 30 Mar 2025, v3 7 Oct 2025) | VERIFIED | Hou, Zhao, Wang, Wang. |
| zhao2025attack | arXiv:2509.24272 (29 Sep 2025) | VERIFIED | Authors: Weibo Zhao, Jiahao Liu, Bonan Ruan, Shaofei Li, Zhenkai Liang. |
| hasan2025glance | arXiv:2506.13538 (v1 16 Jun 2025, v5 13 Apr 2026) | VERIFIED | |
| shan2026check | arXiv:2609.07754 (7 Sep 2026) | VERIFIED | Pre-registered audit: assistants almost never check trust signals before installing. |
| invariant2025poisoning | invariantlabs.ai blog, 1 Apr 2025 | VERIFIED | Beurer-Kellner and Fischer; defines the rug pull. |
| mcpspec2025tools | modelcontextprotocol.io spec 2025-06-18, Tools | VERIFIED | tools/list, pagination, list_changed. |
| zimmermann2019small | usenix.org, USENIX Security 2019, pp. 995–1010 | VERIFIED | |
| ohm2020backstabber | Crossref 10.1007/978-3-030-52683-2_2, DIMVA 2020, pp. 23–43 | VERIFIED | |
| ladisa2023sok | Crossref 10.1109/SP46215.2023.10179304, IEEE S&P 2023, pp. 1509–1526 | VERIFIED | |
| zahan2022weak | Crossref 10.1145/3510457.3513044, ICSE-SEIP 2022, pp. 331–340 | VERIFIED | |
| newman2022sigstore | Crossref 10.1145/3548606.3560596, CCS 2022, pp. 2353–2367 | VERIFIED | |
| slsa2023provenance | slsa.dev/spec/v1.0/provenance | VERIFIED | v1.0 page now marked retired (v1.2 current); predicate type unchanged. |
| pep740 | peps.python.org/pep-0740 | VERIFIED | Woodruff, Tuesca, Ingram; Final; created 8 Jan 2024. |
| npmprovenance | docs.npmjs.com/generating-provenance-statements | VERIFIED | |
| cisa2025shaihulud | CISA alert, 23 Sep 2025 | VERIFIED | Shai-Hulud worm, 500+ npm packages. |
| ossfmalicious | github.com/ossf/malicious-packages | VERIFIED | OSV-format reports. |
| datadogmalicious | github.com/DataDog/malicious-software-packages-dataset | VERIFIED | |
| wilson1927 | Crossref 10.1080/01621459.1927.10502953 | VERIFIED | |
| mcnemar1947 | Crossref 10.1007/BF02295996 | VERIFIED | |
| holm1979 | Scand. J. Statist. 6(2):65–70 (JSTOR 4615733; bibliographic records) | VERIFIED (metadata) | JSTOR page did not render; details consistent across indexes. |
