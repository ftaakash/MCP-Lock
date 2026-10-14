"""Evaluate safer-alternative suggestions (gate/suggest.py) on every corpus with a known ground truth.

Exploratory (not pre-registered). The gate's decisions are unchanged; this measures, for each case the gate
flags, whether it offers a runnable alternative that the gate itself passes (coverage), and whether that
alternative is the right one (correctness) and not the attack (safety).

  R-S  synthetic rug pulls        correct = the locked v1 (benign by construction)
  R-M  class C, hijacked package  correct = the locked last-clean version (PREREG §3.2 rule); unsafe = the
                                  malicious version itself
  R-M  class N, new / typosquat   the suggested popular name; replay is offline, so those names are re-checked
                                  live (registry metadata only)
  R-B  Bagmar & Saraf scenarios   typosquats: the intended package from the scenario;
                                  CVE pins: a fixed version
  ADV  adaptive attacks E1-E11    correct = the locked v1
  B    benign upgrades            coverage, and how often the suggestion rolls back an honest update

Usage: python eval/adaptive/suggest_eval.py
"""

from __future__ import annotations

import gzip
import json
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval" / "scenarios"))

import bagmar  # noqa: E402

from census import provenance  # noqa: E402
from census.stats import wilson  # noqa: E402
from eval import replay  # noqa: E402
from gate import core, s1, suggest  # noqa: E402

P4 = ROOT / "results/candidate/phase4"
BUNDLES = {"R-S": P4 / "synthetic/bundles.jsonl.gz", "R-M": P4 / "malicious/bundles.jsonl.gz",
           "B": P4 / "benign/bundles.jsonl.gz",
           "ADV": ROOT / "results/candidate/phase5/adaptive/bundles.jsonl.gz"}
OUT = ROOT / "results/candidate/phase5"
RB_NOW = datetime(2026, 10, 9, tzinfo=UTC)  # as in eval/scoring/rb.py
# Intended package per typosquat scenario, from the scenario descriptions in eval/scenarios/bagmar.py.
# npm R1 ("requets") has no stated target; npm R11 names the legitimate `request`, used for both.
RB_INTENDED = {("pypi", "R1"): "transformers", ("pypi", "R2"): "azure-core", ("pypi", "R3"): "aiohttp",
               ("pypi", "R4"): "langchain", ("pypi", "R11"): "requests", ("npm", "R1"): "request",
               ("npm", "R2"): "date-fns", ("npm", "R3"): "express", ("npm", "R4"): "axios",
               ("npm", "R11"): "request"}


def prop(k, n):
    if not n:
        return {"k": 0, "n": 0}
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * p, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}


def run_g(b: dict) -> dict:
    """G with suggestions, offline as of t (same set-up as eval/replay.run, G only)."""
    t = replay._ts(b["t"])
    with tempfile.TemporaryDirectory() as d:
        cwd = Path(d)
        for rel, text in (b.get("cwd_files") or {}).items():
            (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
            (cwd / rel).write_text(text, encoding="utf-8")
        lock_path = None
        if b.get("lock"):
            lock_path = cwd / ".mcplock-replay.json"
            lock_path.write_text(json.dumps({"lockfileVersion": 1, "servers": {b["package"]: b["lock"]}}),
                                 encoding="utf-8")
        variant, enabled = replay.systems(b.get("evaluable") or {})["G"]
        with replay.offline(b):
            dec = core.evaluate(b["command"], cwd, lock_path, s1.S1Config.charitable(now=t), enabled,
                                suggest=True)
    out = dec.to_dict()
    out["detected"] = replay.detected(out)
    return out


def first_cmd(dec: dict) -> dict | None:
    return next((s for s in dec.get("suggestions") or [] if s["command"]), None)


def pinned_version(cmd: str, eco: str, pkg: str) -> str | None:
    for name, ver in (suggest._split(eco, tok.removeprefix("--package=").strip("\"'"))
                      for tok in cmd.split(" ")):
        if suggest._norm(eco, name) == suggest._norm(eco, pkg):
            return ver
    return None


def lock_corpus(name: str, keep=lambda b: True) -> tuple[dict, list[dict]]:
    """Corpora whose correct alternative is the locked version (R-S, R-M class C, ADV)."""
    flagged = with_sugg = correct = unsafe = 0
    kinds = Counter()
    rows = []
    for line in gzip.open(BUNDLES[name], "rt", encoding="utf-8"):
        b = json.loads(line)
        if not keep(b):
            continue
        d = run_g(b)
        if d["decision"] == "allow":
            continue
        flagged += 1
        s = first_cmd(d)
        rec = {"case_id": b["case_id"], "decision": d["decision"], "suggestion": s}
        if s:
            with_sugg += 1
            kinds[s["kind"]] += 1
            v = pinned_version(s["command"], b["ecosystem"], b["package"])
            lock_v = (b.get("lock") or {}).get("version")
            target = b["versions"][-1]["version"]
            correct += v is not None and v == lock_v
            unsafe += v is not None and v == target
            rec.update(suggested_version=v, lock_version=lock_v, target_version=target)
        rows.append(rec)
    return {"flagged": flagged, "with_verified_suggestion": prop(with_sugg, flagged),
            "suggests_locked_version": prop(correct, with_sugg),
            "suggests_the_malicious_version": prop(unsafe, with_sugg), "kinds": dict(kinds)}, rows


def rm_class_n() -> tuple[dict, list[dict]]:
    """Class N: the offline replay cannot check another package, so popular names are checked live."""
    flagged = with_cand = 0
    names: dict[tuple[str, str], str] = {}
    rows = []
    cfg = s1.S1Config.charitable()
    for line in gzip.open(BUNDLES["R-M"], "rt", encoding="utf-8"):
        b = json.loads(line)
        if b["labels"].get("class") != "N" or not b["labels"].get("primary", True):
            continue
        d = run_g(b)
        if d["decision"] == "allow":
            continue
        flagged += 1
        eco, pkg = b["ecosystem"], b["package"]
        q = s1.name_proximity(eco, pkg, cfg) or next(iter(suggest.similar_popular(eco, pkg, cfg)), None)
        rows.append({"case_id": b["case_id"], "ecosystem": eco, "candidate": q})
        if q:
            with_cand += 1
            names[(eco, q)] = q
    live_ok = {}
    with tempfile.TemporaryDirectory() as tmp:
        for (eco, q) in sorted(names):
            cmd = f"npm install {q}" if eco == "npm" else f"pip install {q}"
            fs = core.evaluate(cmd, Path(tmp), None, cfg, frozenset({"S1"})).findings
            live_ok[(eco, q)] = suggest.passes(fs, {})
    for r in rows:
        r["candidate_passes"] = live_ok.get((r["ecosystem"], r["candidate"])) if r["candidate"] else None
    passing = sum(bool(r["candidate_passes"]) for r in rows)
    return {"flagged": flagged, "with_candidate": prop(with_cand, flagged),
            "candidate_passes_gate_live": prop(passing, with_cand),
            "distinct_candidates": len(names),
            "note": "class N packages are attacker-owned; the candidate is the popular name it imitates. "
                    "Whether the victim meant that package is not observable."}, rows


def rb() -> tuple[dict, list[dict]]:
    rows = []
    name_n = name_ok = ver_n = ver_ok = 0
    for eco, scen in (("pypi", bagmar.PIP), ("npm", bagmar.NPM)):
        for sc in scen:
            if sc["id"] not in bagmar.TABLE8_EXPECTED or sc["class"] not in ("name", "version"):
                continue
            for form in ("agent", "command"):
                with tempfile.TemporaryDirectory() as d:
                    for fname, text in (sc.get("files") or {}).items():
                        (Path(d) / fname).write_text(text, encoding="utf-8")
                    dec = core.evaluate(sc[form], Path(d), None, s1.S1Config.charitable(now=RB_NOW),
                                        core.ALL_SIGNALS, suggest=True).to_dict()
                s = first_cmd(dec)
                edit = next((x for x in dec.get("suggestions") or [] if x["verified"] and not x["command"]),
                            None)
                rec = {"scenario": f"{eco}:{sc['id']}:{form}", "command": sc[form],
                       "decision": dec["decision"], "suggestion": s and s["command"],
                       "file_edit": edit and edit["because"]}
                if sc["class"] == "name":
                    name_n += 1
                    want = RB_INTENDED[(eco, sc["id"])]
                    rec["intended"] = want
                    rec["correct"] = (bool(s) and want in s["command"].split(" ")) or \
                        (bool(edit) and f"'{want}'" in edit["because"])
                    name_ok += rec["correct"]
                else:
                    ver_n += 1
                    edits = [x for x in dec.get("suggestions") or [] if x["verified"]
                             and x["kind"] == "fixed_version" and not x["command"]]
                    rec["file_edits"] = len(edits)
                    rec["correct"] = (bool(s) and s["kind"] in ("fixed_version", "combined")) or bool(edits)
                    ver_ok += rec["correct"]
                rows.append(rec)
    return {"typosquat_correct": prop(name_ok, name_n), "vulnerable_pins_fixed": prop(ver_ok, ver_n),
            "note": "agent forms that install from a project file (pip install -e ., npm install) have no "
                    "package name on the command line; there the suggestion is a verified file edit"}, rows


def benign() -> tuple[dict, list[dict]]:
    flagged = with_sugg = 0
    kinds = Counter()
    by_dec = Counter()
    rows = []
    for line in gzip.open(BUNDLES["B"], "rt", encoding="utf-8"):
        b = json.loads(line)
        d = run_g(b)
        if d["decision"] == "allow":
            continue
        flagged += 1
        s = first_cmd(d)
        by_dec[(d["decision"], bool(s))] += 1
        if s:
            with_sugg += 1
            kinds[s["kind"]] += 1
        rows.append({"case_id": b["case_id"], "decision": d["decision"], "kind": s and s["kind"]})
    return {"flagged": flagged, "with_verified_suggestion": prop(with_sugg, flagged), "kinds": dict(kinds),
            "block_with_suggestion": by_dec[("block", True)], "block_without": by_dec[("block", False)],
            "warn_with_suggestion": by_dec[("warn", True)], "warn_without": by_dec[("warn", False)],
            "note": "every B case is an honest upgrade, so a locked_version suggestion rolls it back to the "
                    "reviewed version: safe, but it defers the update until the user re-locks"}, rows


def main():
    res, cases = {}, {}
    res["R-S"], cases["R-S"] = lock_corpus("R-S", lambda b: b["labels"].get("class") != "CTRL")
    ctrl, _ = lock_corpus("R-S", lambda b: b["labels"].get("class") == "CTRL")
    res["R-S"]["controls_flagged"] = ctrl["flagged"]
    res["R-M_C"], cases["R-M_C"] = lock_corpus(
        "R-M", lambda b: b["labels"].get("class") == "C" and b["labels"].get("primary", True))
    res["R-M_N"], cases["R-M_N"] = rm_class_n()
    res["ADV"], cases["ADV"] = lock_corpus("ADV", lambda b: b.get("lock") is not None)
    res["R-B"], cases["R-B"] = rb()
    res["B"], cases["B"] = benign()
    res["note"] = "exploratory; decisions unchanged; a suggestion is shown only if the gate passes it"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "suggestions.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    with gzip.open(OUT / "suggestions_cases.jsonl.gz", "wt", encoding="utf-8") as f:
        for corpus, rows in cases.items():
            for r in rows:
                f.write(json.dumps({"corpus": corpus, **r}) + "\n")
    provenance.write(OUT / "suggestions.json",
                     inputs=list(BUNDLES.values()) + [ROOT / "eval/scenarios/bagmar.py"])
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
