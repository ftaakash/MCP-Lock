"""Wilson intervals and stratified cluster bootstrap."""

from __future__ import annotations

from math import sqrt

import numpy as np

Z = 1.959963984540054


def wilson(k: int, n: int, z: float = Z) -> tuple[float, float, float]:
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def weighted_ratio(num: np.ndarray, den: np.ndarray, w: np.ndarray) -> float:
    d = float(np.sum(w * den))
    return float(np.sum(w * num)) / d if d else float("nan")


def stratified_bootstrap(num, den, w, strata, B: int = 10_000, seed: int = 20261008):
    """Resample clusters (packages) with replacement within each stratum."""
    num, den, w = map(np.asarray, (num, den, w))
    strata = np.asarray(strata)
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    stats = np.empty(B)
    for b in range(B):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        stats[b] = weighted_ratio(num[idx], den[idx], w[idx])
    return float(np.nanpercentile(stats, 2.5)), float(np.nanpercentile(stats, 97.5))
