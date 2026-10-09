"""S1 parity with Bagmar & Saraf Table 8, plus the npm port.

Usage: python eval/scoring/parity.py [--out results/baseline/parity_<date>]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval" / "scenarios"))

import bagmar  # noqa: E402

from census import provenance  # noqa: E402
from gate.s1 import S1Config, check  # noqa: E402

NOW = datetime(2026, 10, 9, tzinfo=UTC)  # fixed clock for the age check (reproducibility)


def run_scenarios(scenarios: list[dict], cfg: S1Config, form: str) -> dict:
    out = {}
    for sc in scenarios:
        with tempfile.TemporaryDirectory() as d:
            for name, text in sc["files"].items():
                (Path(d) / name).write_text(text, encoding="utf-8")
            findings = check(sc[form], Path(d), cfg)
        out[sc["id"]] = {"detected": bool(findings),
                         "checks": sorted({f.check for f in findings}),
                         "reasons": [f.reason for f in findings][:4]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=ROOT / "results" / "baseline" / f"parity_{time.strftime('%Y-%m-%d')}")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    configs = {"literal": S1Config.literal(now=NOW), "charitable": S1Config.charitable(now=NOW)}
    res = {"clock": NOW.isoformat(), "configs": {k: {f: str(getattr(v, f)) for f in
                                                      v.__dataclass_fields__} for k, v in configs.items()}}
    for eco, scen in (("pypi", bagmar.PIP), ("npm", bagmar.NPM)):
        for vname, cfg in configs.items():
            for form in ("command", "agent"):
                r = run_scenarios(scen, cfg, form)
                key = f"{eco}/{vname}/{form}"
                core = {k: v for k, v in r.items() if k in bagmar.TABLE8_EXPECTED}
                res[key] = {"scenarios": r,
                            "detected_core": sum(v["detected"] for v in core.values()),
                            "n_core": len(core),
                            "matches_table8": all(core[k]["detected"] == bagmar.TABLE8_EXPECTED[k]
                                                  for k in core)}
                print(f"{key:28s} {res[key]['detected_core']}/{res[key]['n_core']} "
                      f"table8-match={res[key]['matches_table8']} "
                      + " ".join(f"{k}:{'Y' if v['detected'] else '-'}" for k, v in r.items()))
    dest = a.out / "parity.json"
    dest.write_text(json.dumps(res, indent=2))
    provenance.write(dest, params={"clock": NOW.isoformat()},
                     note="Scenarios reconstructed from arXiv:2607.15143; no package installed.")


if __name__ == "__main__":
    main()
