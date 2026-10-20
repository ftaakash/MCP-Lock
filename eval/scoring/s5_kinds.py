"""S5 tool-drift warnings by kind of change (exploratory, post hoc; reviewer W2 in paper/REVIEW.md).

B: every S5 finding is one of the census tool-changing transitions (results/census/phase2/change_events.jsonl,
the same 2,259 transitions), which records the added, removed, description-changed and schema-changed tools.
Each finding is put in one exclusive class, in this order: adds a tool; changes a description; changes only
input schemas; only removes tools. For each class it counts how many cases end as a warning (S5 interrupts the
user) and how many are blocked anyway by another signal.

Attacks: for every case that G detects through S5 alone (no other warn/block finding), it records what S5
reported. The lock keeps one tool hash and the tool names, so S5's report names added and removed tools and
says "changes tool descriptions or input schemas" otherwise; it is S5's report, not a full diff.

Usage: python eval/scoring/s5_kinds.py
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from eval import replay  # noqa: E402
from eval.scoring.phase4 import prop  # noqa: E402

P4 = ROOT / "results/candidate/phase4/runs"
EVENTS = ROOT / "results/census/phase2/change_events.jsonl"
ADV = ROOT / "results/candidate/phase5/adaptive/bundles.jsonl.gz"
OUT = ROOT / "results/candidate/phase5/s5_kinds.json"
KINDS = ("adds", "description", "schema_only", "removal_only")


def kind(ev: dict) -> str:
    if ev["added"]:
        return "adds"
    if ev["description_changed"]:
        return "description"
    if ev["schema_changed"]:
        return "schema_only"
    return "removal_only"


def reported(reason: str) -> str:
    """What S5's reason text says (gate/signals.py)."""
    if " adds " in reason:
        return "adds"
    if " removes " in reason:
        return "removes"
    return "changes descriptions or schemas"


def run_file(corpus: str) -> Path:
    path = P4 / f"{corpus}.jsonl"
    return path if path.exists() else P4 / f"{corpus}.jsonl.gz"


def runs(corpus: str):
    path = run_file(corpus)
    with (gzip.open if path.suffix == ".gz" else open)(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def s5_alone(decision: dict) -> str | None:
    """S5's report if S5 is the only warn/block finding of a detected case, else None."""
    hits = [f for f in decision["findings"] if f["severity"] in ("warn", "block")]
    if decision["detected"] and hits and all(f["signal"] == "S5" for f in hits):
        return reported(hits[0]["reason"])
    return None


def main():
    events = {(e["ecosystem"], e["package"], e["from"], e["to"]): e
              for e in map(json.loads, open(EVENTS, encoding="utf-8"))}
    by_kind, warn, block = Counter(), Counter(), Counter()
    total = mcp = 0
    for r in runs("B"):
        mcp += r["labels"]["stratum"] == "mcp"
        g = r["systems"]["G"]
        if not any(f["signal"] == "S5" for f in g["findings"]):
            continue
        total += 1
        lab = r["labels"]
        k = kind(events[(r["ecosystem"], r["package"], lab["from"], lab["to"])])
        by_kind[k] += 1
        warn[k] += g["decision"] == "warn"
        block[k] += g["decision"] == "block"
    n_warn = sum(warn.values())
    res = {"B": {"s5_findings": total, "mcp_upgrades": mcp, "s5_findings_of_mcp": prop(total, mcp),
                 "by_kind": {k: prop(by_kind[k], total) for k in KINDS},
                 "ends_as_warning": {k: warn[k] for k in KINDS},
                 "ends_as_warning_share": {k: prop(warn[k], n_warn) for k in KINDS},
                 "blocked_anyway": {k: block[k] for k in KINDS}}}
    att = {}
    for corpus in ("R-B", "R-M", "R-S"):
        rows = [r for r in runs(corpus) if r["labels"].get("primary", True)]
        alone = {r["case_id"]: s5_alone(r["systems"]["G"]) for r in rows}
        alone = {k: v for k, v in alone.items() if v}
        att[corpus] = {"detected_by_S5_alone": len(alone), "reported": dict(Counter(alone.values())),
                       "cases": sorted(alone) if corpus == "R-M" else None}
    alone = {}
    for line in gzip.open(ADV, "rt", encoding="utf-8"):
        b = json.loads(line)
        rep = s5_alone(replay.run(b)["G"])
        if rep:
            alone[b["case_id"]] = rep
    att["ADV"] = {"detected_by_S5_alone": len(alone), "reported": dict(Counter(alone.values())),
                  "cases": sorted(alone)}
    res["attacks"] = att
    res["note"] = ("exploratory, post hoc; B classes are exclusive (adds > description > schema_only > "
                   "removal_only) from the census diff; attack classes are what S5 reported")
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    provenance.write(OUT, inputs=[*(run_file(c) for c in ("B", "R-B", "R-M", "R-S")), EVENTS, ADV])
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
