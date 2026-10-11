"""Phase 4 scoring exactly as pre-registered (PREREG §4, §5; OSF https://osf.io/2amj3).

Reads results/{baseline,candidate}/phase4/runs/<corpus>.jsonl (written by eval/replay.py and
eval/scoring/rb.py), joins them by case_id and writes
  results/baseline/phase4/baseline_summary.json   S1-L / S1-C metrics only
  results/candidate/phase4/phase4_results.json    G, ablations, H1, H2, kill rule
  results/candidate/phase4/phase4_results.md      tables

Usage: python eval/scoring/phase4.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from math import comb, sqrt
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from census.stats import stratified_bootstrap, wilson  # noqa: E402

SEED = 20261011
ALPHA = 0.05
SYSTEMS = ("S1-L", "S1-C", "G", "G-S2", "G-S3", "G-S4", "G-S5")
BASE, CAND = "S1-C", "G"
CORPORA = ("R-B", "R-M", "R-S", "B")


# ------------------------------------------------------------------ statistics
def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar: binomial test of b vs c discordant pairs, p = 0.5."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def newcombe_paired(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    """Difference p1 - p2 of paired proportions with Newcombe's (1998) method 10 interval.
    a = both, b = first only, c = second only, d = neither."""
    n = a + b + c + d
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p1, l1, u1 = wilson(a + b, n)
    p2, l2, u2 = wilson(a + c, n)
    den = (a + b) * (c + d) * (a + c) * (b + d)
    phi = (a * d - b * c) / sqrt(den) if den else 0.0
    diff = p1 - p2
    dl = sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    du = sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return diff, diff - dl, diff + du


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, adj, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def prop(k: int, n: int) -> dict:
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": p, "ci95": [lo, hi]}


# ------------------------------------------------------------------ loading
def load(root: Path = ROOT) -> dict[str, list[dict]]:
    out = {}
    for corpus in CORPORA:
        rows: dict[str, dict] = {}
        for group in ("baseline", "candidate"):
            p = root / "results" / group / "phase4" / "runs" / f"{corpus}.jsonl"
            if not p.exists() and not Path(str(p) + ".gz").exists():
                continue
            for line in provenance.open_text(p):
                r = json.loads(line)
                cur = rows.setdefault(r["case_id"], {**r, "systems": {}})
                cur["systems"].update(r["systems"])
        out[corpus] = list(rows.values())
    lat = root / "results" / "candidate" / "phase4" / "runs" / "L.jsonl"
    if lat.exists():
        out["L"] = [json.loads(x) for x in open(lat, encoding="utf-8")]
    return out


def r_primary(data: dict) -> list[dict]:
    """R = R-B (agent form, Table 8 core scenarios) ∪ R-M primary cases (PREREG §4)."""
    rb = [r for r in data.get("R-B", []) if r["labels"].get("form") == "agent"
          and r["labels"].get("core")]
    rm = [r for r in data.get("R-M", []) if r["labels"].get("primary", True)]
    return rb + rm


# ------------------------------------------------------------------ metrics
def detection(rows: list[dict], key: str = "detected") -> dict:
    return {s: prop(sum(bool(r["systems"][s][key]) for r in rows), len(rows))
            for s in SYSTEMS if rows and s in rows[0]["systems"]}


def by(rows: list[dict], label: str) -> dict[str, list[dict]]:
    g = defaultdict(list)
    for r in rows:
        g[str(r["labels"].get(label))].append(r)
    return dict(g)


def paired(rows: list[dict], test) -> dict:
    a = b = c = d = 0
    for r in rows:
        x, y = test(r["systems"][CAND]), test(r["systems"][BASE])
        a += x and y
        b += x and not y
        c += y and not x
        d += not x and not y
    return {"both": a, "G_only": b, "S1C_only": c, "neither": d}


def benign(rows: list[dict]) -> dict:
    res = {}
    for s in SYSTEMS:
        if not rows or s not in rows[0]["systems"]:
            continue
        dec = [r["systems"][s]["decision"] for r in rows]
        res[s] = {"false_block": prop(sum(x == "block" for x in dec), len(dec)),
                  "warn": prop(sum(x == "warn" for x in dec), len(dec)),
                  "interruption": prop(sum(x != "allow" for x in dec), len(dec))}
    return res


def cluster_ci(rows: list[dict], system: str, decision: str) -> list[float]:
    """Stratified cluster bootstrap by package (PREREG §5), strata = B strata."""
    agg = defaultdict(lambda: [0, 0])
    strata = {}
    for r in rows:
        k = (r["labels"]["stratum"], r["ecosystem"], r["package"])
        agg[k][0] += r["systems"][system]["decision"] == decision
        agg[k][1] += 1
        strata[k] = r["labels"]["stratum"]
    keys = sorted(agg)
    num = np.array([agg[k][0] for k in keys], float)
    den = np.array([agg[k][1] for k in keys], float)
    lo, hi = stratified_bootstrap(num, den, np.ones(len(keys)), [strata[k] for k in keys],
                                  seed=SEED)
    return [lo, hi]


def lookup_failures(rows: list[dict]) -> dict:
    out = {}
    for s in SYSTEMS:
        n = sum(any(f["check"] in ("lookup_failed", "unresolvable")
                    for f in r["systems"].get(s, {}).get("findings", [])) for r in rows)
        out[s] = n
    return out


def kill_rule(R: list[dict], B: list[dict], key: str = "detected") -> dict:
    added = sum(bool(r["systems"][CAND][key]) and not r["systems"][BASE][key] for r in R)
    fb_g = sum(r["systems"][CAND]["decision"] == "block" for r in B)
    fb_b = sum(r["systems"][BASE]["decision"] == "block" for r in B)
    worse_or_equal = fb_g >= fb_b
    return {"added_detections": added, "fb_G": fb_g, "fb_S1C": fb_b, "n_B": len(B),
            "fb_equal_or_worse": worse_or_equal, "kill": added < 2 and worse_or_equal}


def score(data: dict) -> dict:
    R = r_primary(data)
    B = data.get("B", [])
    res: dict = {"n": {c: len(data.get(c, [])) for c in CORPORA}, "n_R": len(R)}
    # detection on R and per class
    res["detection_R"] = detection(R)
    res["detection_R_block_only"] = detection(R, "detected_block")
    res["detection_RB_by_class"] = {k: detection(v) for k, v in by(
        [r for r in R if r["corpus"] == "R-B"], "class").items()}
    res["detection_RM_by_class"] = {k: detection(v) for k, v in by(
        [r for r in R if r["corpus"] == "R-M"], "class").items()}
    res["detection_RM_by_ecosystem"] = {k: detection([r for r in R if r["corpus"] == "R-M"
                                                      and r["ecosystem"] == k])
                                        for k in ("npm", "pypi")}
    rs = data.get("R-S", [])
    res["detection_RS_by_class"] = {k: detection(v) for k, v in by(rs, "class").items()}
    # H1
    t1 = paired(R, lambda s: bool(s["detected"]))
    p1 = mcnemar_exact(t1["G_only"], t1["S1C_only"])
    res["H1"] = {"table": t1, "p_exact_mcnemar": p1,
                 "difference": newcombe_paired(t1["both"], t1["G_only"], t1["S1C_only"],
                                               t1["neither"])}
    # benign
    res["benign"] = benign(B)
    res["benign_by_stratum"] = {k: benign(v) for k, v in by(B, "stratum").items()}
    res["benign_cluster_ci"] = {s: {d: cluster_ci(B, s, d) for d in ("block", "warn")}
                                for s in (BASE, CAND)} if B else {}
    t2 = paired(B, lambda s: s["decision"] == "block")
    p2 = mcnemar_exact(t2["G_only"], t2["S1C_only"])
    res["H2"] = {"table": t2, "p_exact_mcnemar": p2,
                 "difference": newcombe_paired(t2["both"], t2["G_only"], t2["S1C_only"],
                                               t2["neither"])}
    adj = holm({"H1": p1, "H2": p2})
    res["holm"] = {k: {"p_adj": v, "reject": v <= ALPHA} for k, v in adj.items()}
    # kill rule (decisive: primary definitions only)
    res["kill_rule"] = kill_rule(R, B)
    res["kill_rule_block_only_secondary"] = kill_rule(R, B, "detected_block")
    # descriptive
    rb_cmd = [r for r in data.get("R-B", []) if r["labels"].get("form") == "command"
              and r["labels"].get("core")]
    res["detection_RB_command_form"] = detection(rb_cmd)
    rm_eval = [r for r in R if r["corpus"] == "R-M" and all(r["evaluable"].get(s, True)
                                                             for s in ("S2", "S3", "S4", "S5"))]
    res["sensitivity_RM_all_evaluable"] = {"n": len(rm_eval), "detection": detection(rm_eval)}
    res["evaluability_RM"] = {s: sum(bool(r["evaluable"].get(s, True)) for r in R
                                     if r["corpus"] == "R-M") for s in ("S2", "S3", "S4", "S5")}
    res["s2_coverage"] = {
        "B": prop(sum(r["lock_provenance"] for r in B), len(B)),
        "R-M_C": prop(sum(r["lock_provenance"] for r in R if r["corpus"] == "R-M"
                          and r["labels"].get("class") == "C"),
                      sum(1 for r in R if r["corpus"] == "R-M" and r["labels"].get("class") == "C"))}
    added = res["kill_rule"]["added_detections"]
    extra_fb = res["kill_rule"]["fb_G"] - res["kill_rule"]["fb_S1C"]
    extra_warn = (sum(r["systems"][CAND]["decision"] == "warn" for r in B)
                  - sum(r["systems"][BASE]["decision"] == "warn" for r in B))
    res["cost_per_added_detection"] = {"extra_false_blocks": extra_fb, "extra_warns": extra_warn,
                                       "added_detections": added,
                                       "false_blocks_per_detection": extra_fb / added if added else None,
                                       "warns_per_detection": extra_warn / added if added else None}
    res["lookup_failures"] = {c: lookup_failures(data.get(c, [])) for c in CORPORA}
    if data.get("L"):
        res["latency"] = latency(data["L"])
    return res


def latency(rows: list[dict]) -> dict:
    """PREREG §4: median, p95, max; share over 60 s and 120 s (hook timeout), cold and warm."""
    out = {"n": len(rows), "errors": sum(any(k.endswith("_error") or k == "error" for k in r)
                                         for r in rows)}
    for system in ("G", "S1-C"):
        for phase in ("cold", "warm"):
            xs = np.array([r[f"{system}_{phase}_s"] for r in rows if f"{system}_{phase}_s" in r])
            if not len(xs):
                continue
            out[f"{system}_{phase}"] = {
                "n": int(len(xs)), "median_s": float(np.median(xs)),
                "p95_s": float(np.percentile(xs, 95)), "max_s": float(xs.max()),
                "over_60s": prop(int((xs > 60).sum()), len(xs)),
                "over_120s": prop(int((xs > 120).sum()), len(xs))}
    return out


# ------------------------------------------------------------------ report
def pct(x: dict) -> str:
    return f"{x['k']}/{x['n']} = {100 * x['p']:.1f}% [{100 * x['ci95'][0]:.1f}, {100 * x['ci95'][1]:.1f}]" \
        if x["n"] else "n/a"


def markdown(res: dict) -> str:
    L = ["# Phase 4 results (pre-registered, OSF https://osf.io/2amj3)", ""]
    kr = res["kill_rule"]
    L += [f"**Kill rule:** added detections = {kr['added_detections']}, false blocks G {kr['fb_G']} vs "
          f"S1-C {kr['fb_S1C']} of {kr['n_B']} → **{'KILL' if kr['kill'] else 'NOT KILLED'}**", ""]
    L += ["## Detection on real attacks R (block ∪ warn)", "| System | R | block only |", "|---|---|---|"]
    for s, v in res["detection_R"].items():
        L.append(f"| {s} | {pct(v)} | {pct(res['detection_R_block_only'][s])} |")
    h1, h2 = res["H1"], res["H2"]
    L += ["", f"H1: G-only {h1['table']['G_only']}, S1-C-only {h1['table']['S1C_only']}, exact McNemar "
          f"p = {h1['p_exact_mcnemar']:.4g}, Holm p = {res['holm']['H1']['p_adj']:.4g}", ""]
    L += ["## Benign upgrades B", "| System | false block | warn | interruption |", "|---|---|---|---|"]
    for s, v in res["benign"].items():
        L.append(f"| {s} | {pct(v['false_block'])} | {pct(v['warn'])} | {pct(v['interruption'])} |")
    d = [100 * x for x in h2["difference"]]
    L += ["", f"H2: G-only blocks {h2['table']['G_only']}, S1-C-only {h2['table']['S1C_only']}, "
          f"exact McNemar p = {h2['p_exact_mcnemar']:.4g}, Holm p = {res['holm']['H2']['p_adj']:.4g}; "
          f"difference {d[0]:.2f} pp [{d[1]:.2f}, {d[2]:.2f}]", ""]
    L += ["## Synthetic rug pulls R-S (implementation coverage, not confirmatory)",
          "| Class | " + " | ".join(SYSTEMS) + " |", "|---" * (len(SYSTEMS) + 1) + "|"]
    for k, v in sorted(res["detection_RS_by_class"].items()):
        L.append(f"| {k} | " + " | ".join(f"{v[s]['k']}/{v[s]['n']}" for s in SYSTEMS if s in v) + " |")
    if "latency" in res:
        lat = res["latency"]
        L += ["", f"## Latency (live, n = {lat['n']}, {lat['errors']} with errors)",
              "| System | median s | p95 s | max s | > 60 s | > 120 s |", "|---|---|---|---|---|---|"]
        for k, v in lat.items():
            if isinstance(v, dict):
                L.append(f"| {k} | {v['median_s']:.2f} | {v['p95_s']:.2f} | {v['max_s']:.2f} | "
                         f"{pct(v['over_60s'])} | {pct(v['over_120s'])} |")
    return "\n".join(L) + "\n"


def main():
    data = load()
    res = score(data)
    cand = ROOT / "results/candidate/phase4"
    base = ROOT / "results/baseline/phase4"
    cand.mkdir(parents=True, exist_ok=True)
    base.mkdir(parents=True, exist_ok=True)
    (cand / "phase4_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (cand / "phase4_results.md").write_text(markdown(res), encoding="utf-8")
    bsum = {"detection_R": {s: res["detection_R"][s] for s in ("S1-L", "S1-C") if s in res["detection_R"]},
            "benign": {s: res["benign"][s] for s in ("S1-L", "S1-C") if s in res["benign"]}}
    (base / "baseline_summary.json").write_text(json.dumps(bsum, indent=1), encoding="utf-8")
    runs = [p for g in ("baseline", "candidate")
            for p in (ROOT / "results" / g / "phase4" / "runs").glob("*.jsonl")]
    provenance.write(cand / "phase4_results.json", inputs=runs, params={"seed": SEED})
    provenance.write(base / "baseline_summary.json", inputs=runs)
    sys.stdout.reconfigure(encoding="utf-8")
    print(markdown(res))


if __name__ == "__main__":
    main()
