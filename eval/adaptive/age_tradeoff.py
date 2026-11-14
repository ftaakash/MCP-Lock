"""Exploratory trade-off curve for narrower versions of the locked-server age exemption.

Not pre-registered. Uses data already seen (Phase 4 and addendum A1), so nothing here is confirmatory. A threshold picked
from this curve has to be tested on new data under a new addendum.

Each variant re-decides the frozen gate G's stored findings (findings are independent, as in age_rule_sensitivity.py):
S1 `new_package` is dropped for a locked case only when the variant's condition holds.
  pkg_age >= d : the package's first release is at least d days before t (d = 0 is G-X; d = 30 equals G, because the
                 age rule only fires below 30 days)
  lock_age >= d: the locked version was published at least d days before t ("the lock has been trusted for d days")

Usage: python eval/adaptive/age_tradeoff.py
"""

from __future__ import annotations

import gzip
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from census.stats import wilson  # noqa: E402
from eval import replay  # noqa: E402
from eval.scoring.phase4 import r_primary  # noqa: E402
from gate import core  # noqa: E402
from gate.findings import Finding  # noqa: E402

OUT = ROOT / "results/candidate/phase5/age_tradeoff.json"
DAYS = (0, 1, 3, 7, 14, 21, 30)
SETS = {
    "phase4": {"runs": ROOT / "results/candidate/phase4/runs",
               "bundles": {"B": ROOT / "results/candidate/phase4/benign/bundles.jsonl.gz",
                           "R-M": ROOT / "results/candidate/phase4/malicious/bundles.jsonl.gz"}},
    "a1": {"runs": ROOT / "results/candidate/a1/runs",
           "bundles": {"B": ROOT / "results/candidate/a1/benign/bundles.jsonl.gz",
                       "R-M": ROOT / "results/candidate/a1/malicious/bundles.jsonl.gz"}},
}


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def ages(path: Path) -> dict[str, dict]:
    """case_id -> {locked, pkg_age, lock_age} in days at t."""
    out = {}
    for line in gzip.open(path, "rt", encoding="utf-8"):
        b = json.loads(line)
        t = ts(b["t"])
        lock = b.get("lock")
        first = (b.get("registry_info") or {}).get(b["package"], {}).get("first_release")
        lock_pub = None
        if lock:
            lv = lock.get("version")
            lock_pub = next((v.get("published") for v in b["versions"] if v["version"] == lv), None)
        out[b["case_id"]] = {"locked": bool(lock),
                             "pkg_age": (t - ts(first)).total_seconds() / 86400 if first else None,
                             "lock_age": (t - ts(lock_pub)).total_seconds() / 86400 if lock_pub else None}
    return out


def redecide(g: dict, drop: bool) -> dict:
    if not drop:
        return g
    kept = [Finding(**f) for f in g["findings"] if not (f["signal"] == "S1" and f["check"] == "new_package")]
    d = core.decide(kept).to_dict()
    d["detected"] = replay.detected(d)
    return d


def waive(info: dict, kind: str, d: int) -> bool:
    if not info or not info["locked"]:
        return False  # first use keeps the age rule
    a = info[kind]
    return a is not None and a >= d  # unknown age: keep the rule (conservative)


def rows(runs: Path, name: str) -> list[dict]:
    p = runs / f"{name}.jsonl"
    return [json.loads(x) for x in provenance.open_text(p)]


def prop(k, n):
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * p, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}


def main():
    res = {"note": "EXPLORATORY; not pre-registered; uses data already seen (Phase 4 and A1)", "days": DAYS}
    for name, s in SETS.items():
        info = {}
        for corpus, path in s["bundles"].items():
            info.update(ages(path))
        B = rows(s["runs"], "B")
        if name == "phase4":
            R = r_primary({"R-B": rows(s["runs"], "R-B"), "R-M": rows(s["runs"], "R-M")})
        else:
            R = [r for r in rows(s["runs"], "R-M") if r["labels"].get("primary", True)]
        Rc = [r for r in R if r["labels"].get("class") == "C"]
        cur = {}
        for kind in ("pkg_age", "lock_age"):
            for d in DAYS:
                fb = wn = det = detc = 0
                for r in B:
                    x = redecide(r["systems"]["G"], waive(info.get(r["case_id"]), kind, d))
                    fb += x["decision"] == "block"
                    wn += x["decision"] == "warn"
                for r in R:
                    x = redecide(r["systems"]["G"], waive(info.get(r["case_id"]), kind, d))
                    det += bool(x["detected"])
                    detc += bool(x["detected"]) and r["labels"].get("class") == "C"
                cur[f"{kind}>={d}"] = {"B_false_block": prop(fb, len(B)), "B_warn": prop(wn, len(B)),
                                       "B_interruption": prop(fb + wn, len(B)),
                                       "R_detected": prop(det, len(R)), "R_class_C_detected": prop(detc, len(Rc))}
        res[name] = cur
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    provenance.write(OUT, inputs=[p for s in SETS.values() for p in s["bundles"].values()])
    for name in SETS:
        print(f"\n== {name}  (false block / warn on B; detection on R; hijacked detected)")
        for k, v in res[name].items():
            print(f"{k:13} FB {v['B_false_block']['pct']:6.2f}%  warn {v['B_warn']['pct']:6.2f}%  "
                  f"R {v['R_detected']['k']:4}/{v['R_detected']['n']}  C {v['R_class_C_detected']['k']:3}/"
                  f"{v['R_class_C_detected']['n']}")


if __name__ == "__main__":
    main()
