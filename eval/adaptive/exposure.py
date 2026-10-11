"""Ecosystem exposure for the Phase 5 attacks (docs/PHASE5_PLAN.md §3.2), from existing data only.

How much of the ecosystem each evasion could apply to, with Wilson CIs. No new crawling.

Usage: python eval/adaptive/exposure.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census.stats import wilson  # noqa: E402

PHASE2 = ROOT / "results/census/phase2/rq1.json"
PHASE4 = ROOT / "results/candidate/phase4/phase4_results.json"
OUT = ROOT / "results/candidate/phase5/exposure.json"


def prop(k, n):
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * p, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}


def main():
    r2 = json.loads(PHASE2.read_text(encoding="utf-8"))
    r4 = json.loads(PHASE4.read_text(encoding="utf-8"))
    g1 = r2["kill_style"]["G1"]
    non_static = prop(g1["n"] - g1["k"], g1["n"])  # E6/E8: runtime-only / non-extractable tools
    b = r4["s2_coverage"]["B"]
    no_prov = prop(b["n"] - b["k"], b["n"])         # E2: locks without provenance

    sdk_float = sdk_tot = 0
    for line in open(ROOT / "results/census/phase2/versions.jsonl", encoding="utf-8"):
        row = json.loads(line)
        if row["ecosystem"] != "npm":
            continue
        dep = (row["versions"][-1] or {}).get("dependencies_on_mcp_sdk")
        if dep:
            sdk_tot += 1
            if any(ch in dep for ch in "^~<>=*x| -"):
                sdk_float += 1
    e9 = prop(sdk_float, sdk_tot)  # E9 proxy: floating SDK dependency range

    res = {
        "E2_no_provenance_lock": {**no_prov, "attack": "stolen-token runtime payload; S2/S3 blind",
                                  "source": "Phase 4 benign locks"},
        "E6_E8_non_extractable_tools": {**non_static, "attack": "runtime/remote/time-bomb tools; S5 blind",
                                        "source": "Phase 2 G1 (10 recent versions per package)"},
        "E9_floating_sdk_dependency": {**e9, "attack": "dependency substitution; top-level lock blind",
                                       "source": "Phase 2 npm latest version @modelcontextprotocol/sdk range",
                                       "caveat": "proxy: measures the SDK dep only, not every dependency"},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    from census import provenance
    provenance.write(OUT, inputs=[PHASE2, PHASE4, ROOT / "results/census/phase2/versions.jsonl"])
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
