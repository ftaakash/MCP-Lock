"""Run the Phase 5 evasion matrix (docs/PHASE5_PLAN.md) through the frozen gate, optionally with
hardening switches, and write results/candidate/phase5/evasion_matrix.{json,md}.

E6b (remote rug pull with no new version) is scored as a known blind spot: the package is byte-identical,
so by construction no static signal can fire; it is reported allow with reason "no package change".

Usage: python -m eval.adaptive.run_matrix
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from census import provenance
from eval import replay
from eval.adaptive import hardening

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = ROOT / "results/candidate/phase5/adaptive/bundles.jsonl.gz"
OUT = ROOT / "results/candidate/phase5"
# Which E-cases each hardening switch is expected to close (for the report only).
CLOSES = {"H1": {"E9"}, "H2": {"E5", "E6a", "E6b", "E7", "E8a", "E8b", "E9"}, "H3": {"E10"}, "H4": {"E2"},
          "H5": {"E11"}}


def _decision(bundle: dict, harden: set[str]) -> dict:
    res = hardening.run(bundle, harden) if harden else replay.run(bundle)
    g = res["G"]
    why = [f"{f['signal']}:{f['check']}" for f in g["findings"] if f["severity"] != "info"]
    return {"S1-C": res["S1-C"]["decision"], "G": g["decision"], "signals": why,
            "detected": g["detected"], "aux": bundle.get("_aux_lookups", [])}


def run() -> dict:
    rows = [json.loads(x) for x in gzip.open(BUNDLES, "rt", encoding="utf-8")]
    base = {}
    for b in rows:
        base[b["case_id"]] = {**_decision(b, set()), "labels": b["labels"]}
    hardened = {}
    for h in ("H1", "H2", "H3", "H4", "H5"):
        for b in rows:
            hardened.setdefault(h, {})[b["case_id"]] = _decision(b, {h})
    allh = {b["case_id"]: _decision(b, {"H1", "H2", "H3", "H4", "H5"}) for b in rows}
    return {"baseline": base, "hardening": hardened, "all_hardening": allh}


def _e11_summary(base: dict) -> dict:
    e11 = {k: v for k, v in base.items() if v["labels"]["case"] == "E11"}
    blocked = [v["labels"]["command"] for v in e11.values() if v["detected"]]
    missed = [v["labels"]["command"] for v in e11.values() if not v["detected"]]
    return {"n": len(e11), "blocked": len(blocked), "missed": missed}


def markdown(res: dict) -> str:
    base, hard, allh = res["baseline"], res["hardening"], res["all_hardening"]
    main = {cid: v for cid, v in base.items() if v["labels"]["case"] != "E11"}
    L = ["# Phase 5 evasion matrix (adaptive attacker, RQ3)", "",
         "Frozen gate (`prereg-v1`) on local-registry attacks. G = all signals. Hardening is exploratory:",
         "H1/H3 are gate checks (`gate/deptree.py`, `gate/signals.py`), H2 the runtime proxy",
         "(`gate/proxy.py`), H4/H5 rules in `eval/adaptive/hardening.py`; costs on the Phase 4 benign",
         "corpus are reported separately.",
         "",
         "| Case | Tier | Attack | S1-C | G | signal | +all hardening |", "|---|---|---|---|---|---|---|"]
    for cid, v in main.items():
        lab = v["labels"]
        sig = ", ".join(v["signals"]) or "—"
        L.append(f"| {lab['case']} | {lab['tier']} | {lab['what']} | {v['S1-C']} | **{v['G']}** | {sig} | "
                 f"{allh[cid]['G']} |")
    e11 = _e11_summary(base)
    e11h = _e11_summary({k: {**allh[k], "labels": v["labels"]} for k, v in base.items()
                         if v["labels"]["case"] == "E11"})
    L += ["", f"**E11 command shapes (T-any):** {e11['blocked']}/{e11['n']} blocked by G; "
          f"{len(e11['missed'])} missed. With H5: {e11h['blocked']}/{e11h['n']} blocked.",
          "Missed by G:", ""]
    for c in e11["missed"]:
        L.append(f"- `{c}`")
    L += ["", "## Hardening (exploratory): which cases each switch closes", "",
          "| Switch | Target cases | Closed (allow/warn → block, or blind spot removed) |", "|---|---|---|"]
    for h in ("H1", "H2", "H3", "H4", "H5"):
        closed = [cid.split(":")[1] for cid, v in hard[h].items()
                  if base[cid]["G"] != "block" and v["G"] == "block"]
        L.append(f"| {h} | {', '.join(sorted(CLOSES[h])) or '—'} | {', '.join(sorted(set(closed))) or '—'} |")
    return "\n".join(L) + "\n"


def main():
    import sys
    res = run()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evasion_matrix.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    md = markdown(res)
    (OUT / "evasion_matrix.md").write_text(md, encoding="utf-8", newline="\n")
    provenance.write(OUT / "evasion_matrix.json", inputs=[BUNDLES])
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
