"""Latency sample L (PREREG §3.5): the real gate, live, cold then warm cache.

200 packages drawn with seed 20261011 from the B strata (100 mcp, 50 npm-top, 50 pypi-top). For each:
the lock pins the second-latest stable version (generated with its own cache, untimed), the launch
`npx -y <pkg>` / `uvx <pkg>` resolves the latest one, and `gate.core.evaluate` is timed with an empty
cache (cold) and immediately again (warm). Systems timed: G (all signals) and S1-C.

Usage: python eval/scoring/latency.py
"""

from __future__ import annotations

import gzip
import json
import os
import platform
import random
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from census import http, provenance, tarballs  # noqa: E402
from gate import core, s1  # noqa: E402
from lockfile import generate  # noqa: E402

SEED = 20261011
QUOTA = {"mcp": 100, "npm-top": 50, "pypi-top": 50}


def _use_cache(base: Path) -> None:
    http.CACHE_DIR = base / "http"
    tarballs.TARBALLS = base / "tarballs"
    tarballs.SRC = base / "src"


def machine() -> dict:
    info = {"os": platform.platform(), "python": platform.python_version(),
            "cpu": platform.processor(), "logical_cpus": os.cpu_count(),
            "date": datetime.now(UTC).isoformat()}
    try:
        import ctypes

        class MEM(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEM()
        m.dwLength = ctypes.sizeof(MEM)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        info["ram_gb"] = round(m.ullTotalPhys / 1024 ** 3, 1)
    except Exception:  # non-Windows
        pass
    return info


def sample() -> list[dict]:
    trs = [json.loads(x) for x in gzip.open(ROOT / "results/candidate/phase4/benign/transitions.jsonl.gz",
                                            "rt", encoding="utf-8")]
    rng = random.Random(SEED)
    out = []
    for stratum, k in QUOTA.items():
        pkgs = sorted({(t["ecosystem"], t["package"]) for t in trs if t["stratum"] == stratum})
        rng.shuffle(pkgs)
        out += [{"stratum": stratum, "ecosystem": e, "package": p} for e, p in pkgs[:k]]
    return out


def one(case: dict, work: Path) -> dict:
    eco, pkg = case["ecosystem"], case["package"]
    runner = "npx" if eco == "npm" else "uvx"
    cmd = f"npx -y {pkg}" if eco == "npm" else f"uvx {pkg}"
    row = {**case, "command": cmd}
    # untimed: lock the second-latest stable version, with its own cache
    _use_cache(work / "lockgen")
    try:
        vs = generate.V.npm_versions(pkg) if eco == "npm" else generate.V.pypi_versions(pkg)
        stable = [v for v in vs if not v["prerelease"]]
        if len(stable) < 2:
            return {**row, "error": "fewer than 2 stable versions now"}
        entry = generate.lock_entry(eco, pkg, stable[-2], runner, [pkg])
    except Exception as e:
        return {**row, "error": f"lock generation: {type(e).__name__}: {e}"}
    cwd = work / "proj"
    cwd.mkdir(parents=True, exist_ok=True)
    lock = cwd / "mcp-lock.json"
    lock.write_text(json.dumps({"lockfileVersion": 1, "servers": {pkg: entry}}), encoding="utf-8")
    row["locked"], row["latest"] = stable[-2]["version"], stable[-1]["version"]
    for system, enabled in (("G", core.ALL_SIGNALS), ("S1-C", frozenset({"S1"}))):
        cache = work / f"gate-{system}"
        shutil.rmtree(cache, ignore_errors=True)
        _use_cache(cache)
        for phase in ("cold", "warm"):
            t0 = time.perf_counter()
            try:
                dec = core.evaluate(cmd, cwd, lock, s1.S1Config.charitable(), enabled)
                row[f"{system}_{phase}_decision"] = dec.decision
            except Exception as e:
                row[f"{system}_{phase}_error"] = f"{type(e).__name__}: {e}"
            row[f"{system}_{phase}_s"] = time.perf_counter() - t0
    return row


def main():
    cases = sample()
    out = ROOT / "results/candidate/phase4/runs/L.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d, open(out, "w", encoding="utf-8") as g:
        for i, c in enumerate(cases, 1):
            work = Path(d) / f"{i:03d}"
            row = one(c, work)
            g.write(json.dumps(row) + "\n")
            g.flush()
            shutil.rmtree(work, ignore_errors=True)
            if i % 20 == 0:
                print(f"{i}/{len(cases)}", flush=True)
    (out.parent / "L_machine.json").write_text(json.dumps(machine(), indent=1), encoding="utf-8")
    provenance.write(out, inputs=[ROOT / "results/candidate/phase4/benign/transitions.jsonl.gz"],
                     params={"seed": SEED, "quota": QUOTA})
    print(f"latency rows -> {out}")


if __name__ == "__main__":
    main()
