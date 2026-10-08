"""RQ1 analysis for Phase 2 (docs/CENSUS_PLAN.md): tool-definition drift on the n=2,000 sample,
joined with Part M metadata signals per transition.

Usage: python -m census.rq1 <phase2_dir>
"""

from __future__ import annotations

import gzip
import json
import sys
from math import comb
from pathlib import Path

import numpy as np

from census import provenance
from census.analyze import analyze, pairs_for
from census.stats import stratified_bootstrap, weighted_ratio, wilson
from census.tooldefs import diff

SIGNALS = ["provenance_lost", "publisher_changed", "maintainers_changed", "new_install_script"]


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Fisher's exact test for [[a, b], [c, d]] (two-sided, sum of p <= p_observed)."""
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d
    denom = comb(n, c1)

    def p(x):
        return comb(r1, x) * comb(r2, c1 - x) / denom

    p_obs = p(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p_obs * (1 + 1e-9)))


def run(phase2: Path) -> dict:
    res = {"kill_style": analyze(phase2)}  # G1 / G2 estimates on the 2,000 sample
    versions = [json.loads(x) for x in open(phase2 / "versions.jsonl", encoding="utf-8")]
    ex = {(r["ecosystem"], r["package"], r["version"]): r
          for r in map(json.loads, open(phase2 / "extractions.jsonl", encoding="utf-8"))}
    meta = {}
    mpath = Path("results/census/metacensus/transitions.jsonl.gz")
    for line in gzip.open(mpath, "rt", encoding="utf-8"):
        t = json.loads(line)
        meta[(t["e"], t["p"], t["from"], t["to"])] = t

    # transition-level table over extractable window pairs
    rows = []
    for r in versions:
        for a, b in pairs_for(r, ex):
            ea = ex[(r["ecosystem"], r["package"], a["version"])]
            eb = ex[(r["ecosystem"], r["package"], b["version"])]
            if ea["n_tools"] == 0 or eb["n_tools"] == 0:
                continue
            d = diff(ea["tools"], eb["tools"])
            m = meta.get((r["ecosystem"], r["package"], a["version"], b["version"]), {})
            rows.append({"e": r["ecosystem"], "p": r["package"], "w": r["weight"],
                         "stratum": f"{r['ecosystem']}:{r['tercile']}",
                         "changed": d["changed"], "names_desc": d["changed_names_or_desc"],
                         "added": bool(d["added"]), "removed": bool(d["removed"]),
                         "desc": bool(d["description_changed"]),
                         "schema": bool(d["schema_changed"]), "pre": a["prerelease"] or b["prerelease"],
                         **{s: m.get(s) for s in SIGNALS}, "meta_found": bool(m)})
    n = len(rows)
    k = sum(x["changed"] for x in rows)
    w = np.array([x["w"] for x in rows])
    y = np.array([x["changed"] for x in rows], float)
    res["transitions_extractable"] = n
    res["transitions_meta_joined"] = sum(x["meta_found"] for x in rows)
    res["tool_change_per_transition"] = {
        "k": k, "n": n, "wilson": wilson(k, n), "weighted": weighted_ratio(y, np.ones(n), w),
        "cluster_bootstrap": stratified_bootstrap(y, np.ones(n), w, [x["stratum"] for x in rows])}
    res["change_kinds"] = {kind: sum(x[kind] for x in rows) for kind in
                           ("added", "removed", "desc", "schema")}
    co = {}
    for s in SIGNALS:
        sub = [x for x in rows if x[s] is not None]
        a = sum(1 for x in sub if x["changed"] and x[s])
        b = sum(1 for x in sub if x["changed"] and not x[s])
        c = sum(1 for x in sub if not x["changed"] and x[s])
        d = sum(1 for x in sub if not x["changed"] and not x[s])
        co[s] = {"table_changed_signal": [[a, b], [c, d]],
                 "rate_among_tool_changes": wilson(a, a + b) if a + b else None,
                 "rate_among_no_change": wilson(c, c + d) if c + d else None,
                 "fisher_p": fisher_two_sided(a, b, c, d) if sub else None}
    res["co_signals"] = co
    res["tool_change_without_any_signal"] = sum(
        1 for x in rows if x["changed"] and not any(x[s] for s in SIGNALS if x[s] is not None))
    dest = phase2 / "rq1.json"
    dest.write_text(json.dumps(res, indent=2, default=float))
    provenance.write(dest, inputs=[phase2 / "versions.jsonl", phase2 / "extractions.jsonl", mpath])
    print(json.dumps({k: v for k, v in res.items() if k != "kill_style"}, indent=2, default=float))
    return res


if __name__ == "__main__":
    run(Path(sys.argv[1]))
