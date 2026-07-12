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
    _water_siting_by_region(region)
    print(f"[charts] wrote 5 charts to {paths.CHARTS}")


def _water_siting_by_region(region) -> None:
    """Units pulled out of each region by the water-siting discount (component E)."""
    if "water_moved" not in region.columns or region["water_moved"].sum() <= 0:
        return
    r = region[region["water_moved"] > 1].sort_values("water_moved")
    fig, ax = plt.subplots(figsize=(7, max(3.5, 0.4 * len(r) + 1)))
    ax.barh(r["region"], r["water_moved"], color="#2c7fb8")
    ax.set_xlabel("Allocation moved out by water constraint (units)")
    ax.set_title("Water-siting discount by region\n(SGMA overdraft + drought + aridification)",
                 fontsize=10)
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "water_siting_by_region.png", dpi=130)
    plt.close(fig)


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


def make_trajectory_charts(statewide, region) -> None:
    """Charts for the longer-horizon decadal trajectory."""
    paths.CHARTS.mkdir(parents=True, exist_ok=True)
    _trajectory_cumulative(statewide)
    _trajectory_per_decade(statewide)
    print(f"[charts] wrote 2 trajectory charts to {paths.CHARTS}")


def _trajectory_cumulative(statewide) -> None:
    s = statewide
    x = s["decade"].tolist()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.fill_between(x, s["cum_baseline"], s["cum_adjusted"], color=_RED, alpha=0.18,
                    label="Climate-driven addition")
    ax.plot(x, s["cum_adjusted"], "-o", color=_RED, lw=2, label="Climate-adjusted minimum")
    ax.plot(x, s["cum_baseline"], "-o", color=_GREY, lw=2, label="Baseline (climate-blind)")
    last = s.iloc[-1]
    ax.annotate(f"+{last['cum_climate_add']:,.0f}\n(+{last['cum_climate_add']/last['cum_baseline']*100:.0f}%)",
                xy=(len(x) - 1, last["cum_adjusted"]), xytext=(-10, 8),
                textcoords="offset points", ha="right", color=_RED, fontsize=9, fontweight="bold")
    ax.set_ylabel("Cumulative housing need (units)")
    ax.set_title("Cumulative statewide housing need to 2100 (SSP2-4.5)\n"
                 "baseline vs. climate-adjusted 'probable minimum'", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "trajectory_cumulative.png", dpi=130)
    plt.close(fig)


def make_constraints_chart(df) -> None:
    """Two panels: RHNA constrained per axis, and RHNA by number of stacked axes."""
    paths.CHARTS.mkdir(parents=True, exist_ok=True)
    axes = ["fire", "flood", "slr", "water", "heat"]
    tot = df["rhna_baseline"].sum()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))

    per = [(df[df[f"c_{a}"] == 1]["rhna_baseline"].sum()) for a in axes]
    colors = {"fire": "#c0392b", "flood": "#2980b9", "slr": "#16a085",
              "water": "#2c7fb8", "heat": "#e67e22"}
    ax1.bar(axes, per, color=[colors[a] for a in axes])
    for i, v in enumerate(per):
        ax1.text(i, v, f"{v/1e3:.0f}k\n{v/tot*100:.0f}%", ha="center", va="bottom", fontsize=8)
    ax1.set_ylabel("6th-cycle RHNA constrained (units)")
    ax1.set_title("RHNA constrained by each hazard axis\n(counted once, no double-count)", fontsize=10)
    ax1.margins(y=0.18)

    # RHNA by number of overlapping constraints.
    buckets = {"0": 0, "1": 1, "2": 2, "3+": 3}
    vals = []
    labels = list(buckets.keys())
    for lbl, k in buckets.items():
        if lbl == "3+":
            vals.append(df[df["n_constraints"] >= 3]["rhna_baseline"].sum())
        else:
            vals.append(df[df["n_constraints"] == k]["rhna_baseline"].sum())
    bar_colors = ["#bdc3c7", "#f1c40f", "#e67e22", "#c0392b"]
    ax2.bar(labels, vals, color=bar_colors)
    for i, v in enumerate(vals):
        ax2.text(i, v, f"{v/1e3:.0f}k\n{v/tot*100:.0f}%", ha="center", va="bottom", fontsize=8)
    ax2.set_xlabel("Number of climate constraints stacked")
    ax2.set_ylabel("6th-cycle RHNA (units)")
    ax2.set_title("Most RHNA faces one constraint;\nfew places stack many", fontsize=10)
    ax2.margins(y=0.18)
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "compound_constraints.png", dpi=130)
    plt.close(fig)


def make_trajectory_compare_chart(cmp) -> None:
    """Regional share shift from uniform -> county-resolved baseline."""
    paths.CHARTS.mkdir(parents=True, exist_ok=True)
    d = cmp[cmp["share_shift_pp"].abs() >= 0.2].sort_values("share_shift_pp")
    if d.empty:
        return
    fig, ax = plt.subplots(figsize=(7, max(4, 0.4 * len(d) + 1)))
    colors = [_BLUE if v > 0 else _RED for v in d["share_shift_pp"]]
    ax.barh(d.index, d["share_shift_pp"], color=colors)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("Shift in share of cumulative statewide need (percentage points)")
    ax.set_title("County-resolved DOF growth vs. uniform taper\n"
                 "how the region mix of 2100 need changes", fontsize=10)
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "trajectory_region_shift.png", dpi=130)
    plt.close(fig)


def _trajectory_per_decade(statewide) -> None:
    s = statewide
    x = np.arange(len(s))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    # Left: per-decade baseline vs adjusted bars.
    w = 0.4
    ax1.bar(x - w / 2, s["baseline_need"], w, color=_GREY, label="Baseline")
    ax1.bar(x + w / 2, s["adjusted_need"], w, color=_BLUE, label="Climate-adjusted")
    ax1.set_xticks(x); ax1.set_xticklabels(s["decade"], fontsize=8)
    ax1.set_ylabel("Housing need per decade (units)")
    ax1.set_title("Per-decade need: baseline vs. climate-adjusted", fontsize=10)
    ax1.legend(fontsize=8)
    # Right: climate share of need over time.
    ax2.plot(x, s["climate_add_pct"], "-o", color=_RED, lw=2)
    ax2.set_xticks(x); ax2.set_xticklabels(s["decade"], fontsize=8)
    ax2.set_ylabel("Climate-driven share of need (%)")
    ax2.set_title("Climate becomes a larger share of need over time", fontsize=10)
    ax2.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(paths.CHARTS / "trajectory_per_decade.png", dpi=130)
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
