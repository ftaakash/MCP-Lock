"""Cost of the Phase 5 hardening switches on the Phase 4 benign corpus B (docs/PHASE5_PLAN.md §4).

Every security gain must be paid for in false blocks / warns on real upgrades. This measures, from the
frozen benign bundles, what each switch would do to the 8,180 benign cases:

  H4 require-provenance : blocks any upgrade whose resolved version has no build provenance.
  H2 runtime tool pin   : on benign upgrades the live tool list equals the static one, so H2 blocks
                          exactly the upgrades whose tool hash changed (S5 drift) — reported as block.
  H5 command normalise  : must not change the decision on the benign commands (all plain npx/uvx).
  H1 dependency lock / H3 PyPI all-files : need data outside B (resolved dep trees / per-file digests);
                          reported as not-measured-here with the ecosystem exposure from Phase 2 data.

Usage: python eval/adaptive/hardening_cost.py
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census.stats import wilson  # noqa: E402
from eval import replay  # noqa: E402
from eval.adaptive import hardening  # noqa: E402

BENIGN = ROOT / "results/candidate/phase4/benign/bundles.jsonl.gz"
OUT = ROOT / "results/candidate/phase5"


def prop(k, n):
    p, lo, hi = wilson(k, n)
    return {"k": k, "n": n, "pct": round(100 * p, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}


def main():
    rows = [json.loads(x) for x in gzip.open(BENIGN, "rt", encoding="utf-8")]
    n = len(rows)
    h4_block = 0          # target lacks provenance
    h2_block = 0          # tool hash changed (= benign S5 drift, promoted to block)
    h5_changed = 0        # H5 would change the decision on a benign command
    by = {"mcp": [0, 0, 0], "npm-top": [0, 0, 0], "pypi-top": [0, 0, 0]}  # n, h4, h2
    for b in rows:
        strat = b["labels"]["stratum"]
        tv = b["versions"][-1]["version"]
        no_prov = (b.get("identities") or {}).get(tv) is None
        lock_tools = ((b.get("lock") or {}).get("tools") or {}).get("hash")
        new_tools = (b.get("tools") or {}).get(tv, {}).get("hash")
        drift = lock_tools is not None and new_tools != lock_tools
        h4_block += no_prov
        h2_block += drift
        by[strat][0] += 1
        by[strat][1] += no_prov
        by[strat][2] += drift
        # H5 must be decision-preserving on benign commands
        base = replay.run(b)["G"]["decision"]
        hard = hardening.run(b, {"H5"})["G"]["decision"]
        h5_changed += base != hard
    res = {
        "n": n,
        "H4_require_provenance": {"block": prop(h4_block, n),
                                  "note": "blocks every upgrade without build provenance"},
        "H2_runtime_tool_pin": {"block": prop(h2_block, n),
                                "note": "= benign tool-definition drift, promoted from warn to block"},
        "H5_command_normalise": {"decisions_changed": prop(h5_changed, n),
                                 "note": "must be 0: H5 only rewrites evasive shapes"},
        "by_stratum": {s: {"n": v[0], "H4_block": prop(v[1], v[0]), "H2_block": prop(v[2], v[0])}
                       for s, v in by.items()},
        "H1_dependency_lock": {"measured": False,
                               "note": "needs resolved dependency trees; exposure from Phase 2 manifests"},
        "H3_pypi_all_files": {"measured": False,
                              "note": "needs per-file upload history; exposure from PyPI JSON API"},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hardening_cost.json").write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    from census import provenance
    provenance.write(OUT / "hardening_cost.json", inputs=[BENIGN])
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
