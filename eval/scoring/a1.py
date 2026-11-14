"""Scoring of pre-registration addendum A1 (docs/PREREG_ADDENDUM_AGE.md).

Reads results/{baseline,candidate}/a1/runs/{B,R-M}.jsonl and writes results/candidate/a1/a1_results.{json,md}.

Confirmatory (addendum §1): A-H2 = false blocks of G-X vs S1-C on B', A-H1 = detection of G-X vs S1-C on R-M'
(primary cases), both exact two-sided McNemar with Holm correction; claim rule. Everything else is descriptive.

Usage: python eval/scoring/a1.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import provenance  # noqa: E402
from eval.scoring import phase4 as P  # noqa: E402

SEED = 20261114
SYSTEMS = ("S1-L", "S1-C", "G", "G-X", "G-X-S2", "G-X-S3", "G-X-S4", "G-X-S5")
OUT = ROOT / "results/candidate/a1"


def load() -> dict[str, list[dict]]:
    out = {}
    for corpus in ("B", "R-M"):
        rows: dict[str, dict] = {}
        files = [ROOT / "results" / g / "a1" / "runs" / f"{corpus}.jsonl" for g in ("baseline", "candidate")]
        for f in files:
            for line in provenance.open_text(f):
                r = json.loads(line)
                rows.setdefault(r["case_id"], {**r, "systems": {}})["systems"].update(r["systems"])
        out[corpus] = list(rows.values())
    return out


def paired(rows, x, y, test):
    a = b = c = d = 0
    for r in rows:
        p, q = test(r["systems"][x]), test(r["systems"][y])
        a += p and q
        b += p and not q
        c += q and not p
        d += not p and not q
    return {"both": a, f"{x}_only": b, f"{y}_only": c, "neither": d}, (a, b, c, d)


def score(data: dict) -> dict:
    P.SYSTEMS = SYSTEMS
    P.SEED = SEED
    B = data["B"]
    R = [r for r in data["R-M"] if r["labels"].get("primary", True)]
    res: dict = {"addendum": "docs/PREREG_ADDENDUM_AGE.md", "n_B": len(B), "n_RM": len(R)}

    def fb(d):
        return d["decision"] == "block"

    def det(d):
        return bool(d["detected"])

    tab2, (a, b, c, d) = paired(B, "G-X", "S1-C", fb)
    p2 = P.mcnemar_exact(b, c)
    tab1, (a1, b1, c1, d1) = paired(R, "G-X", "S1-C", det)
    p1 = P.mcnemar_exact(b1, c1)
    adj = P.holm({"A-H1": p1, "A-H2": p2})
    res["A-H2"] = {"table": tab2, "p": p2, "p_holm": adj["A-H2"],
                   "diff_GX_minus_S1C": P.newcombe_paired(a, b, c, d)}
    res["A-H1"] = {"table": tab1, "p": p1, "p_holm": adj["A-H1"],
                   "diff_GX_minus_S1C": P.newcombe_paired(a1, b1, c1, d1)}
    gx_fb, s1_fb = a + b, a + c
    gx_det, s1_det = a1 + b1, a1 + c1
    res["claim_rule"] = {"A-H2_significant_lower": adj["A-H2"] < P.ALPHA and gx_fb < s1_fb,
                         "GX_detection_at_least_S1C": gx_det >= s1_det}
    res["claim_rule"]["deployable_default_supported"] = all(res["claim_rule"].values())
    # descriptive
    res["B"] = P.benign(B)
    res["B_by_stratum"] = {k: P.benign(v) for k, v in P.by(B, "stratum").items()}
    res["B_cluster_ci"] = {s: {dec: P.cluster_ci(B, s, dec) for dec in ("block", "warn")}
                           for s in ("S1-C", "G", "G-X")}
    res["R-M"] = P.detection(R)
    res["R-M_block_only"] = P.detection(R, "detected_block")
    res["R-M_by_class"] = {k: P.detection(v) for k, v in P.by(R, "class").items()}
    res["G_vs_GX"] = {"B_false_block": paired(B, "G", "G-X", fb)[0],
                      "R-M_detection": paired(R, "G", "G-X", det)[0]}
    res["lookup_failures"] = {"B": P.lookup_failures(B), "R-M": P.lookup_failures(R)}
    return res


def pct(x):
    return f"{100 * x['p']:.2f}% [{100 * x['ci95'][0]:.2f}, {100 * x['ci95'][1]:.2f}] ({x['k']}/{x['n']})"


def markdown(res: dict) -> str:
    L = ["# Addendum A1 results", "",
         f"B′: {res['n_B']} benign transitions. R-M′: {res['n_RM']} primary real-attack cases.", "",
         "| Test | Discordant (G-X only / S1-C only) | p | p (Holm) |", "|---|---|---|---|"]
    for h in ("A-H2", "A-H1"):
        t = list(res[h]["table"].values())
        L.append(f"| {h} | {t[1]} / {t[2]} | {res[h]['p']:.3g} | {res[h]['p_holm']:.3g} |")
    L += ["", f"Claim rule: {res['claim_rule']}", "", "| System | False block | Warn | Interruption |",
          "|---|---|---|---|"]
    for s, v in res["B"].items():
        L.append(f"| {s} | {pct(v['false_block'])} | {pct(v['warn'])} | {pct(v['interruption'])} |")
    L += ["", "| System | Detection on R-M′ |", "|---|---|"]
    for s, v in res["R-M"].items():
        L.append(f"| {s} | {pct(v)} |")
    return "\n".join(L) + "\n"


def main():
    res = score(load())
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "a1_results.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "a1_results.md").write_text(markdown(res), encoding="utf-8")
    provenance.write(out, inputs=[ROOT / "results" / g / "a1" / "runs" / f"{c}.jsonl"
                                  for g in ("baseline", "candidate") for c in ("B", "R-M")])
    sys.stdout.reconfigure(encoding="utf-8")
    print(markdown(res))


if __name__ == "__main__":
    main()
