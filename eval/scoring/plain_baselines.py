"""Plain alternatives to a gate (exploratory, post hoc; reviewer W1 in paper/REVIEW.md).

Two things a careful user can do without any gate, scored on the same R-M and B cases as Phase 4:

  PIN  exact version in the MCP config (npx -y pkg@x.y.z). Nothing new is ever fetched, so every R-M
       class C case (a new malicious version of a locked package) is prevented; a class N case (a malicious
       name the user pins) is not. Every benign upgrade is held back until the user edits the config.
  IGN  npm --ignore-scripts. Install-time scripts never run. An R-M npm case whose malicious version has an
       install script loses that code path; whether its payload also runs at launch is not known from
       metadata, so this is an upper bound on what IGN prevents. On B it counts honest npm upgrades whose new
       version has an install script that would be skipped (top-level package only, a lower bound on what it
       could break).

G and S1-C detections come from the frozen Phase 4 runs, for comparison on the same cases.

Usage: python eval/scoring/plain_baselines.py
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from eval.scoring.phase4 import prop  # noqa: E402

P4 = ROOT / "results/candidate/phase4"
RUNS = {"cand": P4 / "runs/R-M.jsonl", "base": ROOT / "results/baseline/phase4/runs/R-M.jsonl"}
BUNDLES = {"R-M": P4 / "malicious/bundles.jsonl.gz", "B": P4 / "benign/bundles.jsonl.gz"}
OUT = ROOT / "results/candidate/phase5/plain_baselines.json"


def bundles(corpus: str):
    for line in gzip.open(BUNDLES[corpus], "rt", encoding="utf-8"):
        yield json.loads(line)


def main():
    cand = {r["case_id"]: r for r in map(json.loads, open(RUNS["cand"], encoding="utf-8"))}
    base = {r["case_id"]: r for r in map(json.loads, open(RUNS["base"], encoding="utf-8"))}
    rm = [b for b in bundles("R-M") if b["labels"].get("primary", True)]
    n = len(rm)
    pin = sum(b["labels"]["class"] == "C" for b in rm)
    npm = [b for b in rm if b["ecosystem"] == "npm"]
    ign = sum(bool(b["versions"][-1].get("install_scripts")) for b in npm)
    g = sum(cand[b["case_id"]]["systems"]["G"]["detected"] for b in rm)
    s1c = sum(base[b["case_id"]]["systems"]["S1-C"]["detected"] for b in rm)
    g_npm = sum(cand[b["case_id"]]["systems"]["G"]["detected"] for b in npm)
    g_or_ign = sum(cand[b["case_id"]]["systems"]["G"]["detected"]
                   or bool(b["versions"][-1].get("install_scripts")) for b in npm)
    s1c_or_ign = sum(base[b["case_id"]]["systems"]["S1-C"]["detected"]
                     or bool(b["versions"][-1].get("install_scripts")) for b in npm)
    s1c_npm = sum(base[b["case_id"]]["systems"]["S1-C"]["detected"] for b in npm)

    ben = list(bundles("B"))
    ben_npm = [b for b in ben if b["ecosystem"] == "npm"]
    ign_b = sum(bool(b["versions"][-1].get("install_scripts")) for b in ben_npm)
    res = {
        "R-M": {"n": n, "npm": len(npm),
                "PIN_prevents": prop(pin, n), "G_detects": prop(g, n), "S1-C_detects": prop(s1c, n),
                "IGN_prevents_upper_bound_npm": prop(ign, len(npm)), "G_detects_npm": prop(g_npm, len(npm)),
                "S1-C_detects_npm": prop(s1c_npm, len(npm)), "S1-C_or_IGN_npm": prop(s1c_or_ign, len(npm)),
                "G_or_IGN_npm": prop(g_or_ign, len(npm))},
        "B": {"n": len(ben), "PIN_holds_back": prop(len(ben), len(ben)),
              "npm": len(ben_npm), "IGN_skips_honest_script_npm": prop(ign_b, len(ben_npm))},
        "note": ("exploratory, post hoc. PIN prevents by construction (R-M class C is a new version of "
                 "a locked package) and holds back every upgrade; IGN is an upper bound on R-M (payload "
                 "may also run at launch) and a lower bound on B breakage (top-level scripts only)"),
    }
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    provenance.write(OUT, inputs=[*RUNS.values(), *BUNDLES.values()])
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
