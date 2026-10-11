"""Figures for the paper, drawn from the result files (vector PDF, single-column IEEE width).

Fig. hardening_cost: for each hardening switch, the share of the 8,180 benign upgrades it newly blocks on
top of the frozen gate G (bar = upper estimate with Wilson 95% whisker, tick = lower estimate where the
cost is a range), labelled with the attacks it closes. One series, one hue, values labelled directly, so
the figure reads the same in grayscale.

Usage: python paper/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
SERIES = "#2a78d6"  # dataviz reference palette, categorical slot 1
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def hardening_cost():
    h = load("results/candidate/phase5/hardening_cost.json")
    h1, h2 = h["H1_dependency_lock"], h["H2_runtime_tool_pin"]
    pb = h["H3_pypi_all_files"]["block_on_B"]
    # (label, closes, lower estimate or None, upper estimate {pct, ci95}, note)
    rows = [
        ("H5 command normalisation", "E11", None, h["H5_command_normalise"]["decisions_changed"], ""),
        ("H3 lock every PyPI file", "E10", None, pb, "acts only on relaunch"),
        ("H1 dependency-tree lock", "E9", h1["late"]["added_block_over_G"], h1["early"]["added_block_over_G"],
         "npm cases only"),
        ("H2 runtime tools/list pin", "E5–E9", h2["added_block_over_G_lower"],
         h2["added_block_over_G_upper"], ""),
        ("H4 require provenance", "E2", None, h["H4_require_provenance"]["added_block_over_G"], ""),
    ]
    plt.rcParams.update({"font.family": "serif", "font.size": 7.5, "axes.edgecolor": INK2,
                         "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK, "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(3.45, 1.85))
    ys = range(len(rows))
    for y, (_label, _closes, lo, hi, note) in zip(ys, rows, strict=True):
        v = hi["pct"]
        ax.barh(y, v, height=0.55, color=SERIES, edgecolor="white", linewidth=0.8, zorder=2)
        ax.plot(hi["ci95"], [y, y], color=INK, linewidth=0.8, zorder=3)
        if lo is not None and abs(lo["pct"] - v) > 0.05:
            ax.plot([lo["pct"], lo["pct"]], [y - 0.32, y + 0.32], color=INK, linewidth=1.0, zorder=3)
            txt = f"{lo['pct']:.1f}–{v:.1f}%"
        else:
            txt = f"{v:.1f}%"
        ax.text(max(hi["ci95"][1], v) + 1.2, y, txt + (f"  ({note})" if note else ""), va="center",
                color=INK, fontsize=7)
    ax.set_yticks(list(ys), [f"{r[0]}\ncloses {r[1]}" for r in rows], fontsize=7)
    ax.set_xlim(0, 70)
    ax.set_xlabel("newly blocked benign upgrades (%)")
    ax.xaxis.grid(True, color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout(pad=0.3)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "hardening_cost.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT / "hardening_cost.png", dpi=200, bbox_inches="tight", pad_inches=0.02)
    print("wrote", OUT / "hardening_cost.pdf")


if __name__ == "__main__":
    hardening_cost()
