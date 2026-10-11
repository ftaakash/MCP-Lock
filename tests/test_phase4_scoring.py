import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval" / "scoring"))
import phase4  # noqa: E402


def test_mcnemar_thresholds_match_prereg():
    assert phase4.mcnemar_exact(5, 0) == pytest.approx(0.0625)
    assert phase4.mcnemar_exact(6, 0) == pytest.approx(0.03125)
    assert phase4.mcnemar_exact(7, 0) == pytest.approx(0.015625)
    assert phase4.mcnemar_exact(0, 0) == 1.0
    assert phase4.mcnemar_exact(3, 3) == 1.0


def test_newcombe_interval_contains_difference():
    d, lo, hi = phase4.newcombe_paired(8, 5, 4, 27)
    assert d == pytest.approx(1 / 44)
    assert lo < d < hi and -1 <= lo and hi <= 1
    d, lo, hi = phase4.newcombe_paired(0, 0, 0, 100)
    assert d == 0 and lo <= 0 <= hi


def test_holm():
    adj = phase4.holm({"H1": 0.03, "H2": 0.001})
    assert adj["H2"] == pytest.approx(0.002) and adj["H1"] == pytest.approx(0.03)
    adj = phase4.holm({"H1": 0.02, "H2": 0.04})
    assert adj["H1"] == pytest.approx(0.04) and adj["H2"] == pytest.approx(0.04)


def _sys(decision="allow", detected=False):
    return {"decision": decision, "detected": detected, "detected_block": detected and
            decision == "block", "findings": []}


def _row(corpus, cid, g, s1c, labels=None, eco="npm", pkg="p"):
    systems = {s: _sys(*s1c) for s in ("S1-L", "S1-C")}
    systems.update({s: _sys(*g) for s in ("G", "G-S2", "G-S3", "G-S4", "G-S5")})
    return {"case_id": cid, "corpus": corpus, "ecosystem": eco, "package": pkg,
            "labels": labels or {}, "evaluable": {}, "lock_provenance": True, "systems": systems}


def _data(n_added, extra_fb):
    rm = [_row("R-M", f"m{i}", ("block", True), ("allow", False), {"class": "C"})
          for i in range(n_added)]
    rm += [_row("R-M", f"n{i}", ("block", True), ("block", True), {"class": "N"}) for i in range(5)]
    rb = [_row("R-B", f"b{i}", ("block", True), ("block", True),
               {"form": "agent", "core": True, "class": "name"}) for i in range(3)]
    b = [_row("B", f"t{i}", ("block" if i < extra_fb else "allow", False), ("allow", False),
              {"stratum": "mcp"}, pkg=f"p{i % 7}") for i in range(50)]
    return {"R-B": rb, "R-M": rm, "R-S": [], "B": b}


def test_kill_rule_and_h1():
    res = phase4.score(_data(n_added=1, extra_fb=3))
    assert res["kill_rule"]["added_detections"] == 1 and res["kill_rule"]["kill"]
    res = phase4.score(_data(n_added=7, extra_fb=3))
    assert not res["kill_rule"]["kill"]
    assert res["H1"]["table"]["G_only"] == 7
    assert res["H1"]["p_exact_mcnemar"] == pytest.approx(0.015625)
    assert res["benign"]["G"]["false_block"]["k"] == 3
    assert res["H2"]["table"]["G_only"] == 3
    # equal false blocks still count as "equal or worse"
    res = phase4.score(_data(n_added=1, extra_fb=0))
    assert res["kill_rule"]["fb_equal_or_worse"] and res["kill_rule"]["kill"]
    assert "KILL" in phase4.markdown(res)


def test_latency_summary():
    rows = [{"G_cold_s": float(i), "G_warm_s": 0.1, "S1-C_cold_s": 1.0, "S1-C_warm_s": 0.1}
            for i in range(1, 131)]
    rows.append({"error": "lock generation: x"})
    lat = phase4.latency(rows)
    assert lat["n"] == 131 and lat["errors"] == 1
    assert lat["G_cold"]["max_s"] == 130 and lat["G_cold"]["over_120s"]["k"] == 10
    assert lat["G_cold"]["over_60s"]["k"] == 70 and lat["G_warm"]["median_s"] == 0.1
