"""Stratified random sample of eligible packages (plan §3).

Strata: ecosystem x within-ecosystem download tercile. Ecosystem allocation is proportional to
the eligible frame with a floor of 50; within an ecosystem the three terciles get equal shares.
Each stratum is permuted once with numpy default_rng(SEED); the first n_h are the sample and the
remaining order is kept so the sample can be extended (n=400) without re-drawing.

Usage: python -m census.sample <eligible_downloads.jsonl> [n] [out_dir]
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from census import provenance

SEED = 20261008
FLOOR = 50


def _largest_remainder(total: int, weights: dict) -> dict:
    s = sum(weights.values())
    raw = {k: total * w / s for k, w in weights.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: (-(raw[k] - out[k]), k))[: total - sum(out.values())]:
        out[k] += 1
    return out


def allocate(n: int, counts: dict[str, int]) -> dict[str, int]:
    alloc = _largest_remainder(n, counts)
    small = [e for e in alloc if alloc[e] < FLOOR and counts[e] >= FLOOR]
    if small:
        for e in small:
            alloc[e] = FLOOR
        rest = {e: counts[e] for e in alloc if e not in small}
        alloc.update(_largest_remainder(n - FLOOR * len(small), rest))
    return alloc


def strata(rows: list[dict]) -> dict[tuple[str, int], list[dict]]:
    out: dict[tuple[str, int], list[dict]] = {}
    for eco in sorted({r["ecosystem"] for r in rows}):
        eco_rows = sorted((r for r in rows if r["ecosystem"] == eco),
                          key=lambda r: (-r["downloads_last_month"], r["package"]))
        for t, chunk in enumerate(np.array_split(np.arange(len(eco_rows)), 3)):
            # tercile 0 = most downloaded
            out[(eco, t)] = sorted((eco_rows[i] for i in chunk), key=lambda r: r["package"])
    return out


def draw(path: str, n: int = 200, out_dir: str = "results/census/pilot") -> Path:
    rows = [json.loads(x) for x in open(path, encoding="utf-8")]
    st = strata(rows)
    eco_counts = {e: sum(len(v) for (ee, _), v in st.items() if ee == e)
                  for e in {e for e, _ in st}}
    eco_alloc = allocate(n, eco_counts)
    rng = np.random.default_rng(SEED)
    sample, order = [], []
    for (eco, t) in sorted(st):
        members = st[(eco, t)]
        n_h = _largest_remainder(eco_alloc[eco], {0: 1, 1: 1, 2: 1})[t]
        n_h = min(n_h, len(members))
        perm = rng.permutation(len(members))
        weight = len(members) / n_h if n_h else 0.0
        lo = min(m["downloads_last_month"] for m in members)
        hi = max(m["downloads_last_month"] for m in members)
        for rank, i in enumerate(perm):
            rec = {"ecosystem": eco, "tercile": t, "package": members[i]["package"],
                   "perm_rank": rank, "N_h": len(members), "n_h": n_h,
                   "downloads_last_month": members[i]["downloads_last_month"],
                   "stratum_downloads_range": [lo, hi], "weight": weight}
            order.append(rec)
            if rank < n_h:
                sample.append(rec)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_hash = hashlib.sha256("\n".join(sorted(json.dumps(r, sort_keys=True) for r in rows))
                                .encode()).hexdigest()
    out = out_dir / "sample.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in sample:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with open(out_dir / "stratum_order.jsonl", "w", encoding="utf-8") as f:
        for r in order:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    alloc = {f"{e}:{t}": (len(st[(e, t)]), sum(1 for s in sample if (s['ecosystem'], s['tercile'])
                                                == (e, t))) for (e, t) in sorted(st)}
    provenance.write(out, inputs=[Path(path)],
                     params={"seed": SEED, "n": n, "floor": FLOOR, "frame_sha256": frame_hash,
                             "strata_N_n": alloc})
    print("sample:", alloc, "->", out)
    return out


if __name__ == "__main__":
    draw(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 200,
         sys.argv[3] if len(sys.argv) > 3 else "results/census/pilot")
