"""Phase 1 kill-test analysis (plan §5, §7).

Usage: python -m census.analyze <pilot_dir> [--validation validation.jsonl]
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from census import provenance
from census.stats import stratified_bootstrap, weighted_ratio, wilson
from census.tooldefs import diff

G1_THRESHOLD = 0.60
G2_THRESHOLD = 0.05


def _decision(p, lo, hi, thr):
    if lo <= thr <= hi:
        return "INCONCLUSIVE (CI straddles threshold; extend to n=400 once)"
    return "PASS" if p >= thr else "KILL"


def _fmt(p, lo, hi):
    return f"{100 * p:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def load(pilot: Path):
    versions = [json.loads(x) for x in open(pilot / "versions.jsonl", encoding="utf-8")]
    ex = {(r["ecosystem"], r["package"], r["version"]): r
          for r in map(json.loads, provenance.open_text(pilot / "extractions.jsonl"))}
    return versions, ex


def pairs_for(pkg_row: dict, ex: dict, include_pre: bool = True):
    """Consecutive (by version precedence) pairs whose newer version is in the window."""
    vs = sorted(pkg_row["versions"], key=lambda v: v["order"])
    by_order = {v["order"]: v for v in vs}
    for v in vs:
        if not v["in_window"]:
            continue
        prev = by_order.get(v["order"] - 1)
        if prev is None:
            continue
        if not include_pre and (v["prerelease"] or prev["prerelease"]):
            continue
        yield prev, v


def analyze(pilot: Path) -> dict:
    versions, ex = load(pilot)
    eco_of = lambda r: r["ecosystem"]  # noqa: E731
    res: dict = {"n_packages": len(versions)}

    # ---------------- G1: version-level extractability over the K=10 set
    rows_g1 = []
    for r in versions:
        g1 = [v for v in r["versions"] if v["in_g1"]]
        succ = sum(1 for v in g1 if ex[(r["ecosystem"], r["package"], v["version"])]["n_tools"] > 0)
        rows_g1.append((r, succ, len(g1)))
    k = sum(s for _, s, _ in rows_g1)
    n = sum(m for _, _, m in rows_g1)
    p, lo, hi = wilson(k, n)
    num = np.array([s for _, s, _ in rows_g1], float)
    den = np.array([m for _, _, m in rows_g1], float)
    w = np.array([r["weight"] for r, _, _ in rows_g1], float)
    strata = [f"{r['ecosystem']}:{r['tercile']}" for r, _, _ in rows_g1]
    pw = weighted_ratio(num, den, w)
    blo, bhi = stratified_bootstrap(num, den, w, strata)
    pkg_any = sum(1 for _, s, _ in rows_g1 if s > 0)
    res["G1"] = {
        "k": k, "n": n, "wilson": [p, lo, hi], "weighted": pw, "cluster_bootstrap": [blo, bhi],
        "packages_with_any_extractable_version": pkg_any,
        "by_ecosystem": {e: {"k": sum(s for r, s, _ in rows_g1 if eco_of(r) == e),
                             "n": sum(m for r, _, m in rows_g1 if eco_of(r) == e)}
                         for e in ("npm", "pypi")},
        "decision": _decision(p, lo, hi, G1_THRESHOLD),
        "decision_weighted_bootstrap": _decision(pw, blo, bhi, G1_THRESHOLD),
    }
    for d in res["G1"]["by_ecosystem"].values():
        d["wilson"] = wilson(d["k"], d["n"])
    status = Counter(ex[(r["ecosystem"], r["package"], v["version"])]["status"]
                     for r in versions for v in r["versions"] if v["in_g1"])
    res["G1"]["status_counts"] = dict(status)

    # ---------------- G2: package-level tool change within the window
    def g2(include_pre=True, names_desc_only=False):
        y, has_release, has_pair, events = [], [], [], []
        for r in versions:
            changed = False
            rel = any(v["in_window"] for v in r["versions"]
                      if include_pre or not v["prerelease"])
            usable = False
            for a, b in pairs_for(r, ex, include_pre):
                ea = ex[(r["ecosystem"], r["package"], a["version"])]
                eb = ex[(r["ecosystem"], r["package"], b["version"])]
                if ea["n_tools"] == 0 or eb["n_tools"] == 0:
                    continue
                usable = True
                d = diff(ea["tools"], eb["tools"])
                hit = d["changed_names_or_desc"] if names_desc_only else d["changed"]
                if hit:
                    changed = True
                    events.append({"package": r["package"], "ecosystem": r["ecosystem"],
                                   "from": a["version"], "to": b["version"],
                                   "published": b["published"], **d,
                                   "co_signals": co_signals(r["ecosystem"], a, b)})
            y.append(changed)
            has_release.append(rel)
            has_pair.append(usable)
        y = np.array(y)
        k = int(y.sum())
        p, lo, hi = wilson(k, len(y))
        w = np.array([r["weight"] for r in versions], float)
        strata = [f"{r['ecosystem']}:{r['tercile']}" for r in versions]
        pw = weighted_ratio(y.astype(float), np.ones(len(y)), w)
        blo, bhi = stratified_bootstrap(y.astype(float), np.ones(len(y)), w, strata)
        rel = np.array(has_release)
        pair = np.array(has_pair)
        return {
            "k": k, "n": len(y), "wilson": [p, lo, hi], "weighted": pw,
            "cluster_bootstrap": [blo, bhi],
            "decision": _decision(p, lo, hi, G2_THRESHOLD),
            "secondary_among_with_window_release": {
                "k": int(y[rel].sum()), "n": int(rel.sum()), "wilson": wilson(int(y[rel].sum()),
                                                                             int(rel.sum()))},
            "secondary_among_with_extractable_window_pair": {
                "k": int(y[pair].sum()), "n": int(pair.sum()),
                "wilson": wilson(int(y[pair].sum()), int(pair.sum()))},
            "by_ecosystem": {e: {"k": int(sum(y[i] for i, r in enumerate(versions)
                                              if r["ecosystem"] == e)),
                                 "n": sum(1 for r in versions if r["ecosystem"] == e)}
                             for e in ("npm", "pypi")},
        }, events

    res["G2"], events = g2()
    res["G2_sensitivity_no_prerelease"], _ = g2(include_pre=False)
    res["G2_robust_names_or_descriptions_only"], _ = g2(names_desc_only=True)
    res["G2_change_events"] = len(events)
    kinds = Counter()
    for ev in events:
        kinds["added"] += bool(ev["added"])
        kinds["removed"] += bool(ev["removed"])
        kinds["description_changed"] += bool(ev["description_changed"])
        kinds["schema_changed"] += bool(ev["schema_changed"])
    res["G2_event_kinds"] = dict(kinds)
    co = Counter()
    for ev in events:
        for kk, vv in ev["co_signals"].items():
            co[kk] += bool(vv)
    res["G2_event_co_signals"] = dict(co)
    with open(pilot / "change_events.jsonl", "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, sort_keys=True) + "\n")

    # ---------------- context
    res["window_capped_packages"] = sum(1 for r in versions if r.get("window_capped"))
    res["packages_with_window_release"] = sum(1 for r in versions
                                              if any(v["in_window"] for v in r["versions"]))
    att = defaultdict(lambda: [0, 0])
    for r in versions:
        for v in r["versions"]:
            if v["in_g1"]:
                has = (v.get("has_attestation") if r["ecosystem"] == "npm"
                       else (v.get("provenance") or {}).get("pypi_provenance"))
                att[r["ecosystem"]][0] += bool(has)
                att[r["ecosystem"]][1] += 1
    res["provenance_share_g1_versions"] = {e: {"k": a, "n": b} for e, (a, b) in att.items()}
    return res


def _install_set(v: dict) -> set:
    # registry installs never run `prepare`; older version records may still list it
    return set(v.get("install_scripts") or {}) - {"prepare"}


def co_signals(eco: str, a: dict, b: dict) -> dict:
    if eco != "npm":
        pa = (a.get("provenance") or {}).get("pypi_provenance")
        pb = (b.get("provenance") or {}).get("pypi_provenance")
        return {"provenance_lost": bool(pa and not pb), "publisher_changed": None,
                "new_install_script": None}
    return {
        "provenance_lost": bool(a.get("has_attestation") and not b.get("has_attestation")),
        "publisher_changed": bool(a.get("publisher") and b.get("publisher")
                                  and a["publisher"] != b["publisher"]),
        "new_install_script": bool(_install_set(b) - _install_set(a)),
    }


def report(res: dict) -> str:
    g1, g2 = res["G1"], res["G2"]
    lines = [
        "# Phase 1 pilot: kill test",
        "",
        f"Packages: {res['n_packages']}",
        "",
        "| Gate | Estimate (Wilson 95% CI) | Weighted (stratified cluster bootstrap) | Threshold "
        "| Decision |",
        "|---|---|---|---|---|",
        f"| G1 extractable versions | {g1['k']}/{g1['n']} = {_fmt(*g1['wilson'])} | "
        f"{100 * g1['weighted']:.1f}% [{100 * g1['cluster_bootstrap'][0]:.1f}, "
        f"{100 * g1['cluster_bootstrap'][1]:.1f}] | 60% | {g1['decision']} |",
        f"| G2 packages changing tools in 90 d | {g2['k']}/{g2['n']} = {_fmt(*g2['wilson'])} | "
        f"{100 * g2['weighted']:.1f}% [{100 * g2['cluster_bootstrap'][0]:.1f}, "
        f"{100 * g2['cluster_bootstrap'][1]:.1f}] | 5% | {g2['decision']} |",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    pilot = Path(sys.argv[1])
    res = analyze(pilot)
    out = pilot / "kill_test.json"
    out.write_text(json.dumps(res, indent=2, default=float))
    (pilot / "kill_test.md").write_text(report(res))
    provenance.write(out, inputs=[pilot / "versions.jsonl", pilot / "extractions.jsonl"])
    print(report(res))
