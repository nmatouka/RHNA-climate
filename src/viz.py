"""Charts for the climate-adjusted allocation. Saves PNGs to outputs/charts/."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import paths
from .config import load_assumptions as load_cfg

_BLUE, _RED, _GREY = "#2b6cb0", "#c53030", "#718096"


def make_all(adj, region, statewide) -> None:
    paths.CHARTS.mkdir(parents=True, exist_ok=True)
    _statewide_bar(statewide)
    _region_change(region)
    _exposure_vs_delta(adj)
    _biggest_movers(adj)
    print(f"[charts] wrote 4 charts to {paths.CHARTS}")


def _statewide_bar(statewide) -> None:
    s = statewide.iloc[0]
    fig, ax = plt.subplots(figsize=(6, 4.5))
    bars = ax.bar(["Baseline\n(HCD 6th cycle)", "Climate-adjusted\nminimum"],
                  [s["baseline_total"], s["adjusted_total"]],
                  color=[_GREY, _BLUE], width=0.6)
    ax.bar_label(bars, fmt="{:,.0f}", padding=3, fontsize=10)
    ax.set_ylabel("Statewide RHNA (housing units)")
    ax.set_title(f"Statewide RHNA: +{s['increase']:,.0f} units "
                 f"(+{s['increase_pct']:.1f}%) under {s['scenario'].upper()}")
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "statewide_baseline_vs_adjusted.png", dpi=130)
    plt.close(fig)


def _region_change(region) -> None:
    r = region.sort_values("delta")
    fig, ax = plt.subplots(figsize=(7, 9))
    colors = [_RED if d < 0 else _BLUE for d in r["delta"]]
    ax.barh(r["region"], r["delta"], color=colors)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("Change in allocation (units)")
    ax.set_title("Net RHNA change by region (climate-adjusted − baseline)")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "region_change.png", dpi=130)
    plt.close(fig)


def _exposure_vs_delta(adj) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    sizes = np.clip(adj["rhna_baseline"] / 60.0, 4, 400)
    sc = ax.scatter(adj["E"], adj["delta_pct"], s=sizes, alpha=0.45,
                    c=adj["delta_pct"], cmap="coolwarm_r", vmin=-100, vmax=100,
                    edgecolors="none")
    ax.axhline(0, color="k", lw=0.7)
    ax.axvline(load_cfg()["receiver"]["max_exposure_eligible"], color=_GREY,
               lw=0.8, ls="--")
    # Clip y to a readable band; a few tiny-baseline towns sit off-scale.
    lo, hi = -100, 200
    off = int(((adj["delta_pct"] > hi) | (adj["delta_pct"] < lo)).sum())
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Climate hazard exposure index  E_j")
    ax.set_ylabel("Change in allocation (%)")
    note = f" · {off} off-scale" if off else ""
    ax.set_title("Hazard exposure vs. allocation change\n"
                 f"bubble = baseline · dashed = receiver threshold{note}",
                 fontsize=10)
    fig.colorbar(sc, ax=ax, label="% change")
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "exposure_vs_change.png", dpi=130)
    plt.close(fig)


def _biggest_movers(adj) -> None:
    top = adj.nlargest(12, "delta")
    bot = adj.nsmallest(12, "delta")
    both = (top.iloc[::-1]._append(bot) if hasattr(top, "_append")
            else __import__("pandas").concat([top.iloc[::-1], bot]))
    fig, ax = plt.subplots(figsize=(7, 8))
    colors = [_BLUE if d > 0 else _RED for d in both["delta"]]
    ax.barh(both["name"], both["delta"], color=colors)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("Change in allocation (units)")
    ax.set_title("Largest gainers and losers")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "biggest_movers.png", dpi=130)
    plt.close(fig)
