"""Score the current static extractor on the development set (validation harness v2 records).

Development-set accuracy guides extractor revisions only; reported accuracy comes from the
held-out validation (docs/CENSUS_PLAN.md).

Usage: python -m census.devset <pilot_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from census import provenance
from census import versions as V
from census.dynamic import compare
from census.run_extract import extract_one, fetch_one


def score(pilot: Path) -> dict:
    recs = []
    for p in ("validation_npm.jsonl", "validation_pypi.jsonl"):
        recs += [json.loads(x) for x in open(pilot / p, encoding="utf-8")]
    recs = [r for r in recs if r.get("stage_b_ok")]
    rows = []
    for r in recs:
        eco, pkg, ver = r["ecosystem"], r["package"], r["version"]
        vs = V.npm_versions(pkg) if eco == "npm" else V.pypi_versions(pkg)
        v = next(x for x in vs if x["version"] == ver)
        st = extract_one((eco, pkg, ver, fetch_one((eco, pkg, v))))
        c = compare(st.get("tools", []), r["dynamic_tools"])
        rows.append({"ecosystem": eco, "package": pkg, "version": ver, "old": r["compare"],
                     "new": c})
    out = {}
    for eco in ("all", "npm", "pypi"):
        sub = [x for x in rows if eco == "all" or x["ecosystem"] == eco]
        d = {}
        for k in ("old", "new"):
            c = [x[k] for x in sub]
            both, ns, nd = (sum(y[f] for y in c) for f in ("n_both", "n_static", "n_dynamic"))
            d[k] = {"precision": both / ns if ns else None, "recall": both / nd if nd else None,
                    "exact_sets": sum(y["name_set_equal"] for y in c),
                    "detected": sum(1 for y in c if y["n_dynamic"] and y["n_static"]),
                    "n": len(c)}
        out[eco] = d
    out["regressions"] = [x["package"] for x in rows
                          if x["new"]["n_both"] < x["old"]["n_both"]
                          or (x["new"]["name_precision"] or 1) < (x["old"]["name_precision"] or 1)]
    out["still_missing"] = [(x["package"], x["new"]["n_static"], x["new"]["n_dynamic"])
                            for x in rows if x["new"]["n_both"] < x["new"]["n_dynamic"]]
    dest = pilot / "devset_scores.json"
    dest.write_text(json.dumps(out, indent=2))
    provenance.write(dest, inputs=[pilot / "validation_npm.jsonl", pilot / "validation_pypi.jsonl"],
                     note="development set; not a reported accuracy figure")
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    score(Path(sys.argv[1]))
