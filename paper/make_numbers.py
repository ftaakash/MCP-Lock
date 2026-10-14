"""Generate paper/numbers.tex: every number in the paper as a LaTeX macro, read from the result files.

No number in the manuscript is typed by hand. Each macro carries a comment naming its source file, so a
reviewer can trace it (pipeline Stage 8: every number traced to a result file).

Usage: python paper/make_numbers.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "numbers.tex"
LINES: list[str] = []


def load(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def macro(name: str, value: str, src: str) -> None:
    assert re.fullmatch(r"[A-Za-z]+", name), name
    LINES.append(f"\\newcommand{{\\{name}}}{{{value}}}  % {src}")


def num(n: int) -> str:
    return f"{n:,}".replace(",", "{,}")


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}\\%"


def ci(lo: float, hi: float, d: int = 1) -> str:
    return f"[{100 * lo:.{d}f}, {100 * hi:.{d}f}]"


def kn(name: str, k: int, n: int, lo: float, hi: float, src: str, d: int = 1) -> None:
    """name = 'k/n', nameP = percentage, nameCI = Wilson 95% CI."""
    macro(name, f"{num(k)}/{num(n)}", src)
    macro(name + "P", pct(k / n, d), src)
    macro(name + "CI", ci(lo, hi, d), src)


def prop(name: str, p: dict, src: str, d: int = 1) -> None:
    """p = {k, n, pct, ci95:[lo%, hi%]} (Phase 5 format, already in percent)."""
    macro(name, f"{num(p['k'])}/{num(p['n'])}", src)
    macro(name + "P", f"{p['pct']:.{d}f}\\%", src)
    macro(name + "CI", f"[{p['ci95'][0]:.{d}f}, {p['ci95'][1]:.{d}f}]", src)


def phase2() -> None:
    src = "results/census/phase2/rq1.json"
    r = load(src)
    ks = r["kill_style"]
    g2 = ks["G2"]
    macro("CensusSample", num(ks["n_packages"]), src)
    kn("DriftPkgs", g2["k"], g2["n"], *g2["wilson"][1:], src)
    w = g2["secondary_among_with_window_release"]
    kn("DriftWinRel", w["k"], w["n"], *w["wilson"][1:], src)
    t = r["tool_change_per_transition"]
    kn("DriftTrans", t["k"], t["n"], *t["wilson"][1:], src)
    g1 = ks["G1"]
    kn("Extractable", g1["k"], g1["n"], *g1["wilson"][1:], src)
    k = r["tool_change_without_any_signal"]
    from census.stats import wilson
    p, lo, hi = wilson(k, t["k"])
    kn("NoSignal", k, t["k"], lo, hi, src)
    macro("CoSignalMinP", f"{min(v['fisher_p'] for v in r['co_signals'].values()):.2f}", src)
    kinds = r["change_kinds"]
    for key, name in (("added", "KindAdded"), ("removed", "KindRemoved"), ("desc", "KindDesc"),
                      ("schema", "KindSchema")):
        macro(name, num(kinds[key]), src)

    src = "results/census/phase2/validation_heldout_summary.json"
    v = load(src)["all"]
    macro("ValN", str(v["validated"]), src)
    macro("ValPrec", pct(v["name_precision_micro"]), src)
    macro("ValRec", pct(v["name_recall_micro"]), src)

    src = "results/census/metacensus/summary.json"
    m = load(src)
    macro("MetaPkgs", num(m["packages"]), src)
    macro("MetaTrans", num(m["transitions"]), src)
    npm, py = m["npm"], m["pypi"]
    macro("MetaNpmActive", num(npm["packages_with_window_transition"]), src)
    macro("MetaPyActive", num(py["packages_with_window_transition"]), src)
    for eco, tag in ((npm, "Npm"), (py, "Py")):
        k, n, (_, lo, hi) = eco["provenance_lost"]["packages"]
        kn(f"MetaProvLost{tag}", k, n, lo, hi, src, 2)
        k, n, (_, lo, hi) = eco["latest_with_provenance"]
        kn(f"MetaLatestProv{tag}", k, n, lo, hi, src)
    for key, name in (("new_install_script", "MetaInstallNpm"), ("maintainers_changed", "MetaMaintNpm")):
        k, n, (_, lo, hi) = npm[key]["packages"]
        kn(name, k, n, lo, hi, src, 2)
    src = "results/census/metacensus/publisher_breakdown.json"
    pb = load(src)
    k, n, (_, lo, hi) = pb["CI->human"]["packages"]
    kn("MetaCiHuman", k, n, lo, hi, src, 2)
    k, n, (_, lo, hi) = pb["human->CI"]["packages"]
    kn("MetaHumanCi", k, n, lo, hi, src)


def phase4() -> None:
    src = "results/candidate/phase4/phase4_results.json"
    r = load(src)
    macro("NR", num(r["n_R"]), src)
    macro("NB", num(r["n"]["B"]), src)
    rm = r["detection_RM_by_class"]
    macro("NRM", num(rm["C"]["G"]["n"] + rm["N"]["G"]["n"]), src)
    macro("NRMC", num(r["detection_RM_by_class"]["C"]["G"]["n"]), src)
    macro("NRMN", num(r["detection_RM_by_class"]["N"]["G"]["n"]), src)
    macro("NRB", num(r["n_R"] - rm["C"]["G"]["n"] - rm["N"]["G"]["n"]), src)
    for sys_, name in (("G", "DetG"), ("S1-C", "DetSC"), ("S1-L", "DetSL")):
        d = r["detection_R"][sys_]
        kn(name, d["k"], d["n"], *d["ci95"], src)
    h1 = r["H1"]
    macro("AddedDet", num(h1["table"]["G_only"]), src)
    macro("SCOnly", num(h1["table"]["S1C_only"]), src)
    macro("McNemarHOne", "3.2\\times10^{-30}", src)
    assert abs(h1["p_exact_mcnemar"] - 3.155e-30) < 1e-32
    macro("HolmHOne", "6.3\\times10^{-30}", src)
    assert abs(r["holm"]["H1"]["p_adj"] - 6.31e-30) < 1e-31
    for sys_, name in (("G", "FbG"), ("S1-C", "FbSC")):
        d = r["benign"][sys_]["false_block"]
        kn(name, d["k"], d["n"], *d["ci95"], src)
    d = r["benign"]["G"]["warn"]
    kn("WarnG", d["k"], d["n"], *d["ci95"], src)
    d = r["benign"]["G"]["interruption"]
    kn("InterG", d["k"], d["n"], *d["ci95"], src)
    macro("FbExtra", num(r["H2"]["table"]["G_only"]), src)
    macro("FbDiffPP", f"{100 * r['H2']['difference'][0]:.2f}", src)
    macro("FbDiffCI", f"[{100 * r['H2']['difference'][1]:.2f}, {100 * r['H2']['difference'][2]:.2f}]", src)
    macro("McNemarHTwo", "1.2\\times10^{-10}", src)
    assert abs(r["H2"]["p_exact_mcnemar"] - 1.164e-10) < 1e-12
    g = r["detection_R"]["G"]["k"]
    for s, word in (("S2", "Two"), ("S3", "Three"), ("S4", "Four"), ("S5", "Five")):
        macro(f"Abl{word}", num(g - r["detection_R"][f"G-{s}"]["k"]), src)
    c = r["detection_RM_by_class"]
    kn("RMCG", c["C"]["G"]["k"], c["C"]["G"]["n"], *c["C"]["G"]["ci95"], src)
    kn("RMCSC", c["C"]["S1-C"]["k"], c["C"]["S1-C"]["n"], *c["C"]["S1-C"]["ci95"], src)
    kn("RMNG", c["N"]["G"]["k"], c["N"]["G"]["n"], *c["N"]["G"]["ci95"], src)
    rs = r["detection_RS_by_class"]
    macro("RSG", f"{sum(rs[a]['G']['k'] for a in ('A1', 'A2', 'A3', 'A4'))}/"
                 f"{sum(rs[a]['G']['n'] for a in ('A1', 'A2', 'A3', 'A4'))}", src)
    macro("RSSC", f"{sum(rs[a]['S1-C']['k'] for a in ('A1', 'A2', 'A3', 'A4'))}/40", src)
    macro("RSCtrl", f"{rs['CTRL']['G']['k']}/{rs['CTRL']['G']['n']}", src)
    s2 = r["s2_coverage"]
    kn("STwoB", s2["B"]["k"], s2["B"]["n"], *s2["B"]["ci95"], src)
    kn("STwoRMC", s2["R-M_C"]["k"], s2["R-M_C"]["n"], *s2["R-M_C"]["ci95"], src)
    ev = r["evaluability_RM"]
    macro("EvalSTwo", num(ev["S2"]), src)
    macro("EvalSFour", num(ev["S4"]), src)
    macro("EvalSFive", num(ev["S5"]), src)
    c = r["cost_per_added_detection"]
    macro("FbPerDet", f"{c['false_blocks_per_detection']:.2f}", src)
    macro("WarnPerDet", f"{c['warns_per_detection']:.1f}", src)
    lat = r["latency"]
    macro("LatN", str(lat["G_cold"]["n"]), src)
    macro("LatColdMed", f"{lat['G_cold']['median_s']:.2f}", src)
    macro("LatColdPNF", f"{lat['G_cold']['p95_s']:.2f}", src)
    macro("LatColdMax", f"{lat['G_cold']['max_s']:.1f}", src)
    macro("LatWarmMed", f"{lat['G_warm']['median_s']:.2f}", src)
    bs = r["benign_by_stratum"]
    macro("NBMcp", num(bs["mcp"]["G"]["false_block"]["n"]), src)
    macro("NBNpmTop", num(bs["npm-top"]["G"]["false_block"]["n"]), src)
    macro("NBPyTop", num(bs["pypi-top"]["G"]["false_block"]["n"]), src)
    kn("FbSCMcp", bs["mcp"]["S1-C"]["false_block"]["k"], bs["mcp"]["S1-C"]["false_block"]["n"],
       *bs["mcp"]["S1-C"]["false_block"]["ci95"], src)
    w = bs["mcp"]["G"]["warn"]
    kn("WarnGMcp", w["k"], w["n"], *w["ci95"], src)
    sens = r["sensitivity_RM_all_evaluable"]
    macro("SensN", str(sens["n"]), src)
    macro("SensG", str(sens["detection"]["G"]["k"]), src)
    macro("SensSC", str(sens["detection"]["S1-C"]["k"]), src)


def phase5() -> None:
    src = "results/candidate/phase5/evasion_matrix.json"
    m = load(src)
    base = m["baseline"]
    main = {k: v for k, v in base.items() if v["labels"]["case"] != "E11"}
    macro("ENCases", str(len(main)), src)
    macro("EGBlock", str(sum(v["G"] == "block" for v in main.values())), src)
    macro("EGWarn", str(sum(v["G"] == "warn" for v in main.values())), src)
    macro("EGAllow", str(sum(v["G"] == "allow" for v in main.values())), src)
    macro("EGStop", str(sum(v["G"] != "allow" for v in main.values())), src)
    macro("ESCAllow", str(sum(v["S1-C"] == "allow" for v in main.values())), src)
    allh = {k: m["all_hardening"][k] for k in main}
    macro("EAllBlock", str(sum(v["G"] == "block" for v in allh.values())), src)
    e11 = [v for v in base.values() if v["labels"]["case"] == "E11"]
    macro("EElevenN", str(len(e11)), src)
    macro("EElevenG", str(sum(v["detected"] for v in e11)), src)
    e11h = [m["all_hardening"][k] for k, v in base.items() if v["labels"]["case"] == "E11"]
    macro("EElevenH", str(sum(v["detected"] for v in e11h)), src)

    src = "results/candidate/phase5/exposure.json"
    x = load(src)
    prop("ExpNoProv", x["E2_no_provenance_lock"], src)
    prop("ExpNonStatic", x["E6_E8_non_extractable_tools"], src)
    prop("ExpFloatSdk", x["E9_floating_sdk_dependency"], src)

    src = "results/candidate/phase5/hardening_cost.json"
    h = load(src)
    h2 = h["H2_runtime_tool_pin"]
    prop("HTwoLo", h2["block_lower"], src)
    prop("HTwoHi", h2["block_upper"], src)
    prop("HTwoMcp", h["by_stratum"]["mcp"]["H2_block_lower"], src)
    macro("HTwoUnmeas", num(h2["classes"]["unmeasurable"]), src)
    prop("HTwoAddLo", h2["added_block_over_G_lower"], src)
    prop("HTwoAddHi", h2["added_block_over_G_upper"], src)
    prop("HFourAdd", h["H4_require_provenance"]["added_block_over_G"], src)
    h3 = h["H3_pypi_all_files"]["exposure_pinned_relaunch"]
    prop("HThreeLate", h3["gained_file_after_1h"], src, 2)
    prop("HThreeLateDay", h3["gained_file_after_24h"], src, 2)
    prop("HFour", h["H4_require_provenance"]["block"], src)
    prop("HFive", h["H5_command_normalise"]["decisions_changed"], src)
    h1 = h["H1_dependency_lock"]
    macro("HOneN", num(h1["n_npm_cases"]), src)
    for b, tag in (("early", "Early"), ("late", "Late")):
        prop(f"HOneBlock{tag}", h1[b]["added_block_over_G"], src, 2)
        prop(f"HOneWarn{tag}", h1[b]["allow_to_warn_over_G"], src, 2)
        prop(f"HOneStrict{tag}", h1[b]["strict_tree_lock_block"], src)
    macro("HOneMedNodes", str(h1["early"]["median_nodes_now"]), src)
    macro("HOneNewPub", num(h1["early"]["cases_by_check"].get("dep_new_publisher", 0)), src)

    src = "results/candidate/phase5/age_rule_sensitivity.json"
    a = load(src)
    prop("AgeFb", a["B"]["G_waived_false_block"], src, 2)
    prop("AgeWarn", a["B"]["G_waived_warn"], src)
    prop("AgeInter", a["B"]["G_waived_interruption"], src)
    prop("AgeDet", a["R"]["G_waived_detected"], src)
    macro("AgeLost", str(a["R"]["detections_lost"]), src)
    r4 = load("results/candidate/phase4/phase4_results.json")
    macro("AgeAdded", str(a["R"]["G_waived_detected"]["k"] - r4["detection_R"]["S1-C"]["k"]), src)

    src = "results/candidate/phase5/suggestions.json"
    g = load(src)
    for tag, key in (("RS", "R-S"), ("RMC", "R-M_C"), ("ADV", "ADV")):
        prop(f"Sg{tag}Cov", g[key]["with_verified_suggestion"], src)
        prop(f"Sg{tag}Lock", g[key]["suggests_locked_version"], src)
        prop(f"Sg{tag}Bad", g[key]["suggests_the_malicious_version"], src)
    prop("SgRBName", g["R-B"]["typosquat_correct"], src)
    prop("SgRBVer", g["R-B"]["vulnerable_pins_fixed"], src)
    macro("SgRMNFlag", str(g["R-M_N"]["flagged"]), src)
    macro("SgRMNCand", str(g["R-M_N"]["with_candidate"]["k"]), src)
    prop("SgBCov", g["B"]["with_verified_suggestion"], src)


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    phase2()
    phase4()
    phase5()
    OUT.write_text("% Generated by paper/make_numbers.py from results/; do not edit by hand.\n"
                   + "\n".join(LINES) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(LINES)} macros -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
