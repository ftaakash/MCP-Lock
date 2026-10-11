"""Cost of the Phase 5 hardening switches on the Phase 4 benign corpus B (docs/PHASE5_PLAN.md §4).

Every security gain must be paid for in false blocks / warns on real upgrades. From the frozen benign
bundles and the HTTP cache (no new crawling):

  H1 dependency lock      : measured by eval/adaptive/h1_cost.py (needs dependency packuments); merged here.
  H2 runtime tool pin     : gate/proxy.check rule. Assumes the live tools/list equals the static extraction
                            (live lists of 8,180 historical upgrades cannot be observed without running them).
                            A tool added or changed blocks; a removal alone does not. Removal-only upgrades
                            may still have changed a remaining tool, so they bound the rate from above.
  H3 PyPI all-files lock  : fires only when a launch resolves to the *locked* version; every case in B is an
                            upgrade, so its cost on B is 0 by construction. Exposure instead: locked releases
                            that gained a file after their first upload (a pinned relaunch would block).
  H4 require-provenance   : blocks any upgrade whose resolved version has no build provenance.
  H5 command normalise    : must not change the decision on the benign commands (all plain npx/uvx).

Usage: python eval/adaptive/hardening_cost.py
"""

from __future__ import annotations

import gzip
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import http  # noqa: E402
from census.meta import pypi_url  # noqa: E402
from census.stats import wilson  # noqa: E402
from eval import replay  # noqa: E402
from eval.adaptive import hardening  # noqa: E402

BENIGN = ROOT / "results/candidate/phase4/benign/bundles.jsonl.gz"
OUT = ROOT / "results/candidate/phase5"
STRATA = ("mcp", "npm-top", "pypi-top")


def prop(k, n):
    p, lo, hi = wilson(k, n) if n else (0, 0, 0)
    return {"k": k, "n": n, "pct": round(100 * p, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def h2_class(b: dict) -> str:
    """unmeasurable | same | added | changed | removal_only, under live == static."""
    lt = b["lock"].get("tools") or {}
    nt = (b.get("tools") or {}).get(b["versions"][-1]["version"]) or {}
    if not lt.get("hash") or nt.get("too_large") or not nt.get("hash"):
        return "unmeasurable"
    if lt["hash"] == nt["hash"]:
        return "same"
    old, new = set(lt.get("names") or []), set(nt.get("names") or [])
    if new - old:
        return "added"
    return "removal_only" if new < old else "changed"


def h3_late_files(rows: list[dict]) -> dict:
    """Locked PyPI releases in B whose files were uploaded over 1 h / 24 h apart (HTTP cache only)."""
    rel = sorted({(b["package"], b["lock"]["version"]) for b in rows if b["ecosystem"] == "pypi"})
    n = late1 = late24 = 0
    examples = []
    for pkg, v in rel:
        files = (http.get_json(pypi_url(pkg)).get("releases") or {}).get(v) or []
        t = sorted(_ts(f["upload_time_iso_8601"]) for f in files if f.get("upload_time_iso_8601"))
        if not t:
            continue
        n += 1
        gap = (t[-1] - t[0]).total_seconds()
        late1 += gap > 3600
        late24 += gap > 86400
        if gap > 86400:
            examples.append(f"{pkg}=={v}")
    return {"releases": n, "gained_file_after_1h": prop(late1, n), "gained_file_after_24h": prop(late24, n),
            "examples_24h": examples}


def main():
    rows = [json.loads(x) for x in gzip.open(BENIGN, "rt", encoding="utf-8")]
    n = len(rows)
    cls = {}
    h4 = h5_changed = 0
    by = {s: {"n": 0, "H4": 0, "H2_lo": 0, "H2_hi": 0} for s in STRATA}
    for b in rows:
        strat = b["labels"]["stratum"]
        tv = b["versions"][-1]["version"]
        no_prov = (b.get("identities") or {}).get(tv) is None
        c = h2_class(b)
        cls[c] = cls.get(c, 0) + 1
        h4 += no_prov
        by[strat]["n"] += 1
        by[strat]["H4"] += no_prov
        by[strat]["H2_lo"] += c in ("added", "changed")
        by[strat]["H2_hi"] += c in ("added", "changed", "removal_only")
        # H5 must be decision-preserving on benign commands
        h5_changed += replay.run(b)["G"]["decision"] != hardening.run(b, {"H5"})["G"]["decision"]
    lo = cls.get("added", 0) + cls.get("changed", 0)
    hi = lo + cls.get("removal_only", 0)
    meas = n - cls.get("unmeasurable", 0)
    res = {
        "n": n,
        "H1_dependency_lock": None,
        "H2_runtime_tool_pin": {
            "block_lower": prop(lo, n), "block_upper": prop(hi, n),
            "block_lower_of_measurable": prop(lo, meas), "block_upper_of_measurable": prop(hi, meas),
            "classes": cls,
            "note": "live tools/list assumed equal to static extraction; unmeasurable = no static tools"},
        "H3_pypi_all_files": {
            "block_on_B": prop(0, sum(b["ecosystem"] == "pypi" for b in rows)),
            "note": "B holds upgrades only; H3 fires on a relaunch of the locked version",
            "exposure_pinned_relaunch": h3_late_files(rows)},
        "H4_require_provenance": {"block": prop(h4, n),
                                  "note": "blocks every upgrade without build provenance"},
        "H5_command_normalise": {"decisions_changed": prop(h5_changed, n),
                                 "note": "must be 0: H5 only rewrites evasive shapes"},
        "by_stratum": {s: {"n": v["n"], "H4_block": prop(v["H4"], v["n"]),
                           "H2_block_lower": prop(v["H2_lo"], v["n"]),
                           "H2_block_upper": prop(v["H2_hi"], v["n"])} for s, v in by.items()},
    }
    h1 = OUT / "h1_cost.json"
    inputs = [BENIGN]
    if h1.exists():
        res["H1_dependency_lock"] = json.loads(h1.read_text(encoding="utf-8"))
        inputs.append(h1)
    else:
        res["H1_dependency_lock"] = {"measured": False, "note": "run eval/adaptive/h1_cost.py"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hardening_cost.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    from census import provenance
    provenance.write(OUT / "hardening_cost.json", inputs=inputs)
    print(json.dumps({k: v for k, v in res.items() if k != "H1_dependency_lock"}, indent=1))


if __name__ == "__main__":
    main()
