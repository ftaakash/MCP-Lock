"""R-M detection by publication window (exploratory, post hoc; reviewer W7 in paper/REVIEW.md).

Most of G's added detections on real attacks are install scripts. This checks how much of that gain comes
from the two 2025 Shai-Hulud worm waves, by the publication date of the malicious version only (OSV
records carry no campaign label, so a case published in a window is not proven to belong to the worm).
Windows, from the public reports:
  wave 1: 2025-09-14 .. 2025-09-30   (CISA alert of 23 Sep 2025)
  wave 2: 2025-11-21 .. 2025-12-05   ("Shai-Hulud 2.0", from 24 Nov 2025)
For each window and for everything outside both, it reports G vs S1-C detection (block or warn, and block
only) and the exact McNemar test of G vs S1-C.

Usage: python eval/scoring/rm_windows.py
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from eval.scoring.phase4 import mcnemar_exact, prop  # noqa: E402

CAND = ROOT / "results/candidate/phase4/runs/R-M.jsonl"
BASE = ROOT / "results/baseline/phase4/runs/R-M.jsonl"
BUNDLES = ROOT / "results/candidate/phase4/malicious/bundles.jsonl.gz"
OUT = ROOT / "results/candidate/phase5/rm_windows.json"
WINDOWS = {"wave1": ("2025-09-14", "2025-09-30"), "wave2": ("2025-11-21", "2025-12-05")}


def window(day: str) -> str:
    return next((w for w, (lo, hi) in WINDOWS.items() if lo <= day <= hi), "outside")


def main():
    cand = {r["case_id"]: r for r in map(json.loads, open(CAND, encoding="utf-8"))}
    base = {r["case_id"]: r for r in map(json.loads, open(BASE, encoding="utf-8"))}
    published = {}
    for line in gzip.open(BUNDLES, "rt", encoding="utf-8"):
        b = json.loads(line)
        published[b["case_id"]] = (b["versions"][-1].get("published") or b["t"])[:10]
    rows = []
    for cid, r in cand.items():
        if not r["labels"].get("primary", True):
            continue
        g, s = r["systems"]["G"], base[cid]["systems"]["S1-C"]
        rows.append({"case_id": cid, "class": r["labels"]["class"], "window": window(published[cid]),
                     "G": g["detected"], "G_block": g["detected_block"],
                     "S1C": s["detected"], "S1C_block": s["detected_block"]})
    res = {"n": len(rows), "windows": WINDOWS, "by_window": {}}
    for w in ("wave1", "wave2", "outside", "all"):
        sub = [x for x in rows if w == "all" or x["window"] == w]
        g_only = sum(x["G"] and not x["S1C"] for x in sub)
        s_only = sum(x["S1C"] and not x["G"] for x in sub)
        res["by_window"][w] = {
            "n": len(sub), "class_C": sum(x["class"] == "C" for x in sub),
            "G": prop(sum(x["G"] for x in sub), len(sub)), "S1-C": prop(sum(x["S1C"] for x in sub), len(sub)),
            "G_block_only": prop(sum(x["G_block"] for x in sub), len(sub)),
            "S1-C_block_only": prop(sum(x["S1C_block"] for x in sub), len(sub)),
            "G_only": g_only, "S1C_only": s_only, "mcnemar_p": mcnemar_exact(g_only, s_only)}
    res["note"] = ("exploratory, post hoc; window = publication date of the malicious version, not a "
                   "campaign label; R-M primary cases only (R-B excluded)")
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    provenance.write(OUT, inputs=[CAND, BASE, BUNDLES], params={"windows": WINDOWS})
    print(json.dumps(res["by_window"], indent=1))


if __name__ == "__main__":
    main()
