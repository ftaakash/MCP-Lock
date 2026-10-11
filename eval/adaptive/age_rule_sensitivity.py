"""Exploratory sensitivity: G with S1's 30-day age rule waived for servers that are already locked.

In Phase 4, 2,695 of G's 2,729 false blocks on B involve S1 `new_package`: the baseline's age rule,
replayed at upgrade time, fires on young MCP servers that the user has already reviewed and locked. The
age rule exists to guard *first use* of a name. This analysis drops S1 `new_package` findings for cases
whose replay had a lock entry and re-decides with the unchanged policy (gate/core.decide). Findings are
independent of each other, so this equals running the gate with the exemption. Unlocked cases (R-B
scenarios, R-M class N) keep the rule.

Not pre-registered; the confirmatory Phase 4 results are unchanged.

Usage: python eval/adaptive/age_rule_sensitivity.py
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from census.stats import wilson  # noqa: E402
from eval import replay  # noqa: E402
from eval.scoring.phase4 import r_primary  # noqa: E402
from gate import core  # noqa: E402
from gate.findings import Finding  # noqa: E402

RUNS = ROOT / "results/candidate/phase4/runs"
BUNDLES = {"B": ROOT / "results/candidate/phase4/benign/bundles.jsonl.gz",
           "R-M": ROOT / "results/candidate/phase4/malicious/bundles.jsonl.gz"}
OUT = ROOT / "results/candidate/phase5/age_rule_sensitivity.json"


def prop(k, n):
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * p, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}


def locked_cases(path: Path) -> set[str]:
    return {b["case_id"] for b in map(json.loads, gzip.open(path, "rt", encoding="utf-8")) if b.get("lock")}


def waive(dec: dict) -> dict:
    kept = [Finding(**f) for f in dec["findings"]
            if not (f["signal"] == "S1" and f["check"] == "new_package")]
    d = core.decide(kept).to_dict()
    d["detected"] = replay.detected(d)
    return d


def rows(name: str) -> list[dict]:
    return [json.loads(x) for x in open(RUNS / f"{name}.jsonl", encoding="utf-8")]


def main():
    res = {"note": "exploratory; S1 new_package waived only where the case had a lock entry"}
    # B: false blocks and warnings
    locked = locked_cases(BUNDLES["B"])
    b = rows("B")
    n = len(b)
    fb_g = fb_w = warn_w = 0
    for r in b:
        g = r["systems"]["G"]
        w = waive(g) if r["case_id"] in locked else g
        fb_g += g["decision"] == "block"
        fb_w += w["decision"] == "block"
        warn_w += w["decision"] == "warn"
    res["B"] = {"locked_cases": len(locked & {r["case_id"] for r in b}),
                "G_false_block": prop(fb_g, n), "G_waived_false_block": prop(fb_w, n),
                "G_waived_warn": prop(warn_w, n), "G_waived_interruption": prop(fb_w + warn_w, n)}
    # R = R-B + R-M: detections lost by the waiver
    locked_rm = locked_cases(BUNDLES["R-M"])
    det_g = det_w = 0
    lost = []
    R = r_primary({"R-B": rows("R-B"), "R-M": rows("R-M")})  # the pre-registered R (PREREG §4)
    n_r = len(R)
    for r in R:
        g = r["systems"]["G"]
        w = waive(g) if r["case_id"] in locked_rm else g
        det_g += g["detected"]
        det_w += w["detected"]
        if g["detected"] and not w["detected"]:
            lost.append(r["case_id"])
    res["R"] = {"n": n_r, "G_detected": prop(det_g, n_r), "G_waived_detected": prop(det_w, n_r),
                "detections_lost": len(lost), "lost_cases": lost}
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    provenance.write(OUT, inputs=[BUNDLES["B"], BUNDLES["R-M"], RUNS / "B.jsonl", RUNS / "R-M.jsonl",
                                  RUNS / "R-B.jsonl"])
    print(json.dumps({k: v for k, v in res.items() if k != "R"} | {"R": {k: v for k, v in res["R"].items()
                                                                          if k != "lost_cases"}}, indent=1))


if __name__ == "__main__":
    main()
