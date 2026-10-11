"""DEVIATIONS #2 check: recompute Phase 2 tool hashes with the gate's own static_tools.

Seeded sample (20261011) of 40 distinct versions from the B-mcp bundles (both sides of transitions).
Usage: python eval/scoring/recompute_tool_hashes.py
"""

from __future__ import annotations

import gzip
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from gate import signals  # noqa: E402


def main():
    trs = [json.loads(x) for x in gzip.open(ROOT / "results/candidate/phase4/benign/transitions.jsonl.gz",
                                            "rt", encoding="utf-8") if '"stratum": "mcp"' in x]
    pool = {}
    for t in trs:
        for side, tk in (("a", "tools_a"), ("b", "tools_b")):
            pool[(t["ecosystem"], t["package"], t[side]["version"])] = (t[side], t[tk])
    keys = sorted(pool)
    random.Random(20261011).shuffle(keys)
    rows = []
    for eco, pkg, ver in keys[:40]:
        rec, stored = pool[(eco, pkg, ver)]
        h, names = signals.static_tools(eco, pkg, rec)
        rows.append({"ecosystem": eco, "package": pkg, "version": ver, "stored": stored["hash"],
                     "recomputed": h, "match": h == stored["hash"]})
    out = ROOT / "results/candidate/phase4/checks/tool_hash_recompute.json"
    summary = {"n": len(rows), "match": sum(r["match"] for r in rows), "rows": rows}
    out.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    provenance.write(out, inputs=[ROOT / "results/candidate/phase4/benign/transitions.jsonl.gz"])
    print(f"{summary['match']}/{summary['n']} identical")


if __name__ == "__main__":
    main()
