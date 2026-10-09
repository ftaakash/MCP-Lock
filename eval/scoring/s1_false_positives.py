"""S1 false-positive estimate on popular packages (paper: 5 of the top-1,000 PyPI packages).

Usage: python eval/scoring/s1_false_positives.py [--n 1000]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval" / "scoring"))

from parity import NOW  # noqa: E402  (same fixed clock)

from census import provenance  # noqa: E402
from census.stats import wilson  # noqa: E402
from gate.s1 import S1Config, check, name_proximity, popular  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "results" / "baseline" / f"s1_fp_{time.strftime('%Y-%m-%d')}")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    res = {"n": a.n, "clock": NOW.isoformat()}
    for eco, tool in (("pypi", "pip install"), ("npm", "npm install")):
        names = popular(eco)[:a.n]
        for vname, cfg in (("literal", S1Config.literal(now=NOW)),
                           ("charitable", S1Config.charitable(now=NOW))):
            flagged = {}
            with tempfile.TemporaryDirectory() as d:
                for n in names:
                    f = check(f"{tool} {n}", Path(d), cfg)
                    if f:
                        flagged[n] = sorted({x.reason for x in f})
            k = len(flagged)
            res[f"{eco}/{vname}"] = {"flagged": k, "wilson": wilson(k, len(names)),
                                     "examples": dict(list(flagged.items())[:15])}
            print(f"{eco}/{vname}: {k}/{len(names)}", list(flagged)[:8], flush=True)
        # literal name check alone, by popular-set size: which P reproduces the paper's 5/1,000?
        sweep = {}
        for p_size in (100, 150, 200, 250, 500, 1000, 2000, 5000):
            cfg = S1Config.literal(p_size=p_size)
            sweep[p_size] = sum(1 for n in names if name_proximity(eco, n, cfg))
        res[f"{eco}/literal_name_check_by_P"] = sweep
        print(eco, "literal name-check flags by P:", sweep, flush=True)
    dest = a.out / "s1_fp.json"
    dest.write_text(json.dumps(res, indent=2, default=str))
    provenance.write(dest, inputs=[ROOT / "gate/data/top_pypi.json", ROOT / "gate/data/top_npm.json"])


if __name__ == "__main__":
    main()
