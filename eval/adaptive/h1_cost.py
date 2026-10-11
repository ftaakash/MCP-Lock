"""Cost of H1 (dependency-tree lock, gate/deptree.py) on the Phase 4 benign corpus B (npm cases).

For each benign upgrade (lock at v_old, launch at t resolving to v_new) the tree is resolved as of the lock
time and as of t from the npm packuments, and gate/deptree.check is applied. The time the user took the
lock is not known, so two bounds are reported:

  early  lock taken when v_old was published: the longest window for dependencies to move (upper bound)
  late   lock taken just before t: only the new version's own dependency changes count (lower bound)

Cost is reported as raw H1 findings and as the change to G's frozen decision on the same case (allow ->
warn/block, warn -> block). For comparison, `strict` is the plain `npm ci` reading of a tree lock: any
dependency that is not the locked name@version blocks. Build identities are fetched only for dependencies
whose version changed.
Needs registry.npmjs.org (HTTP-cached); --sample N runs a seeded random subset.

Usage: python eval/adaptive/h1_cost.py [--sample N] [--seed 20261011]
"""

from __future__ import annotations

import argparse
import functools
import gzip
import json
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from census.stats import wilson  # noqa: E402
from gate import core, deptree  # noqa: E402
from gate.findings import Finding  # noqa: E402

BENIGN = ROOT / "results/candidate/phase4/benign/bundles.jsonl.gz"
G_RUN = ROOT / "results/candidate/phase4/runs/B.jsonl"
OUT = ROOT / "results/candidate/phase5"
RANK = {"allow": 0, "warn": 1, "block": 2}


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def prop(k, n):
    p, lo, hi = wilson(k, n) if n else (0, 0, 0)
    return {"k": k, "n": n, "pct": round(100 * p, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}


@functools.lru_cache(maxsize=4000)
def _all_versions(name: str) -> dict:
    return _orig_versions(name, None)


def _versions(name: str, as_of: datetime | None = None) -> dict:
    allv = _all_versions(name)
    if as_of is None:
        return dict(allv)
    return {v: n for v, n in allv.items() if n["published"] and _ts(n["published"]) <= as_of}


_orig_versions = deptree.versions
deptree.versions = _versions  # parse each packument once; as-of filtering on the parsed nodes


def _locked(before: dict, after: dict) -> dict:
    """Lock records for `before`; identities only where a dependency's version changed (lazy)."""
    changed = {k.rpartition("@")[0] for k in after if k not in before}
    nodes = {}
    for key, n in before.items():
        name = key.rpartition("@")[0]
        if not n.get("attestation_url"):
            prov = None
        elif name in changed:
            prov = deptree._identity(n)
        else:
            prov = {"digest": None, "unfetched": True}  # present; never compared (version unchanged)
        nodes[key] = {"integrity": n["integrity"], "provenance": prov, "publisher": n["publisher"],
                      "maintainers": n["maintainers"], "installScripts": n["install_scripts"]}
    return {"nodes": nodes}


def one(b: dict, g: dict) -> dict:
    pkg, t = b["package"], _ts(b["t"])
    v_old, v_new = b["lock"]["version"], b["versions"][-1]["version"]
    pub_old = next((v["published"] for v in b["versions"] if v["version"] == v_old), None)
    out = {"case_id": b["case_id"], "stratum": b["labels"]["stratum"]}
    bounds = (("early", _ts(pub_old) if pub_old else None), ("late", t - timedelta(milliseconds=1)))
    for scen, lock_at in bounds:
        if lock_at is None:
            out[scen] = {"error": "no publish time for the locked version"}
            continue
        try:
            before, un_b = deptree.resolve(pkg, v_old, lock_at)
            after, un_a = deptree.resolve(pkg, v_new, t)
            f = deptree.check(pkg, v_new, _locked(before, after), as_of=t)
        except Exception as e:  # noqa: BLE001 - recorded per case, never silently dropped
            out[scen] = {"error": f"{type(e).__name__}: {e}"}
            continue
        g_findings = [Finding(**x) for x in g["findings"]]
        combined = core.decide(g_findings + f).decision
        out[scen] = {"nodes_lock": len(before), "nodes_now": len(after),
                     "unresolved": len(un_b) + len(un_a),
                     "h1": Counter(x.check for x in f if x.severity != "info"),
                     "h1_block": any(x.severity == "block" for x in f),
                     "h1_warn": any(x.severity == "warn" for x in f),
                     "strict_block": any(k not in before for k in after),
                     "g": g["decision"], "g_h1": combined}
    return out


def summarise(cases: list[dict]) -> dict:
    res = {}
    for scen in ("early", "late"):
        ok = [c[scen] for c in cases if "error" not in c[scen]]
        n = len(ok)
        checks = Counter()
        for c in ok:
            checks.update(set(c["h1"]))
        res[scen] = {
            "n_evaluated": n, "n_error": len(cases) - n,
            "h1_block": prop(sum(c["h1_block"] for c in ok), n),
            "h1_warn_only": prop(sum(c["h1_warn"] and not c["h1_block"] for c in ok), n),
            "strict_tree_lock_block": prop(sum(c["strict_block"] for c in ok), n),
            "added_block_over_G": prop(sum(c["g"] != "block" and c["g_h1"] == "block" for c in ok), n),
            "allow_to_warn_over_G": prop(sum(c["g"] == "allow" and c["g_h1"] == "warn" for c in ok), n),
            "G_allow": prop(sum(c["g"] == "allow" for c in ok), n),
            "G_plus_H1_allow": prop(sum(c["g_h1"] == "allow" for c in ok), n),
            "cases_by_check": dict(checks.most_common()),
            "trees_with_unresolved": prop(sum(c["unresolved"] > 0 for c in ok), n),
            "median_nodes_now": sorted(c["nodes_now"] for c in ok)[n // 2] if n else None,
        }
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="seeded random subset of npm cases (0 = all)")
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--workers", type=int, default=6, help="parallel cases (HTTP stays rate-limited)")
    a = ap.parse_args()
    rows = [json.loads(x) for x in gzip.open(BENIGN, "rt", encoding="utf-8")]
    npm = [b for b in rows if b["ecosystem"] == "npm"]
    if a.sample:
        npm = random.Random(a.seed).sample(npm, a.sample)
    g = {}
    for line in open(G_RUN, encoding="utf-8"):
        r = json.loads(line)
        g[r["case_id"]] = r["systems"]["G"]
    cases = []
    with ThreadPoolExecutor(a.workers) as ex:
        for i, c in enumerate(ex.map(lambda b: one(b, g[b["case_id"]]), npm), 1):
            cases.append(c)
            if i % 100 == 0:
                print(f"{i}/{len(npm)}", flush=True)
    res = {"n_npm_cases": len(npm), "sample": a.sample or None, "seed": a.seed if a.sample else None,
           **summarise(cases),
           "note": "exploratory (docs/PHASE5_PLAN.md §4); early = lock at v_old publish (upper bound), "
                   "late = lock just before t (lower bound)"}
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"h1_cost{'_sample' + str(a.sample) if a.sample else ''}"
    with gzip.open(OUT / f"{name}_cases.jsonl.gz", "wt", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")
    (OUT / f"{name}.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    provenance.write(OUT / f"{name}.json", inputs=[BENIGN, G_RUN],
                     params={"sample": a.sample, "seed": a.seed})
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
