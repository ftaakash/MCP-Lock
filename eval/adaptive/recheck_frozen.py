"""Re-replay the Phase 4 corpora on the default (frozen, no hardening) gate path and diff every system's
decision, reason and findings against the committed runs. Guards the prereg-v1 behaviour after gate edits.

Usage: python eval/adaptive/recheck_frozen.py  (from the repo root)
"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from eval import replay  # noqa: E402

CORPORA = {"R-S": "results/candidate/phase4/synthetic/bundles.jsonl.gz",
           "R-M": "results/candidate/phase4/malicious/bundles.jsonl.gz",
           "B": "results/candidate/phase4/benign/bundles.jsonl.gz"}


def committed(name):
    out = {}
    for group in ("baseline", "candidate"):
        p = ROOT / f"results/{group}/phase4/runs/{name}.jsonl"
        if not p.exists():
            p = p.with_suffix(".jsonl.gz")
        op = gzip.open if p.suffix == ".gz" else open
        for line in op(p, "rt", encoding="utf-8"):
            r = json.loads(line)
            out.setdefault(r["case_id"], {}).update(r["systems"])
    return out


def strip(d):
    return {k: d[k] for k in ("decision", "reason", "findings", "detected", "detected_block", "enabled")}


for name, path in CORPORA.items():
    ref = committed(name)
    n = same = 0
    bad = []
    for line in gzip.open(ROOT / path, "rt", encoding="utf-8"):
        b = json.loads(line)
        got = replay.run(b)
        n += 1
        want = ref[b["case_id"]]
        if set(got) == set(want) and all(strip(got[s]) == strip(want[s]) for s in got):
            same += 1
        else:
            bad.append(b["case_id"])
        if n % 1000 == 0:
            print(name, n, "replayed", flush=True)
    print(f"{name}: {same}/{n} identical (all systems, decisions, reasons, findings)", bad[:10], flush=True)
