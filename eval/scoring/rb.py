"""R-B: Bagmar & Saraf scenarios through every Phase 4 system (PREREG §3.1).

Scenarios are first installs with project files and no lock entry. Registry and OSV lookups are live
(read-only, cached) with the clock fixed at 2026-10-09, as in the Phase 3 parity run.
Output rows have the same shape as eval/replay.py and are split into baseline / candidate folders.

Usage: python eval/scoring/rb.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval" / "scenarios"))

import bagmar  # noqa: E402

from eval import replay  # noqa: E402
from gate import core, s1  # noqa: E402

NOW = datetime(2026, 10, 9, tzinfo=UTC)


def run_case(sc: dict, eco: str, form: str) -> dict:
    systems = replay.systems({})
    res = {}
    with tempfile.TemporaryDirectory() as d:
        for name, text in (sc.get("files") or {}).items():
            (Path(d) / name).write_text(text, encoding="utf-8")
        for sid, (variant, enabled) in systems.items():
            cfg = (s1.S1Config.charitable if variant == "charitable" else s1.S1Config.literal)(now=NOW)
            dec = core.evaluate(sc[form], Path(d), None, cfg, enabled).to_dict()
            dec["detected"] = replay.detected(dec)
            dec["detected_block"] = replay.detected(dec, block_only=True)
            dec["enabled"] = sorted(enabled)
            res[sid] = dec
    return {"case_id": f"RB:{eco}:{sc['id']}:{form}", "corpus": "R-B", "ecosystem": eco,
            "package": None, "evaluable": {}, "lock_provenance": False,
            "labels": {"scenario": sc["id"], "class": sc["class"], "form": form,
                       "core": sc["id"] in bagmar.TABLE8_EXPECTED},
            "systems": res}


def main():
    rows = [run_case(sc, eco, form) for eco, scen in (("pypi", bagmar.PIP), ("npm", bagmar.NPM))
            for sc in scen for form in ("agent", "command")]
    base, cand = replay.write_split(rows, "R-B", [ROOT / "eval/scenarios/bagmar.py"])
    print(f"{len(rows)} R-B rows -> {base} | {cand}")


if __name__ == "__main__":
    main()
