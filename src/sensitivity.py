"""Sensitivity analysis: sweep the most uncertain, assumption-laden parameters
(horizon, displacement max fraction, displacement exponent) and report how the
statewide 'probable minimum' and the redistributed pool respond.

Because the statewide increase equals replacement need only (the pool is
conserved), the horizon and loss parameters move the TOTAL, while the
displacement parameters move the REDISTRIBUTED POOL. We report both.

Run:  python -m src.sensitivity
"""
from __future__ import annotations

import copy
import itertools

import numpy as np
import pandas as pd

from . import paths
from .adjustment_model import apply_model
from .config import load_assumptions
from .crosswalk import build_master


def _run(master, cfg) -> dict:
    adj = apply_model(master, cfg)
    base = adj["rhna_baseline"].sum()
    tot = adj["rhna_adjusted"].sum()
    return {
        "adjusted_total": tot,
        "increase": tot - base,
        "increase_pct": (tot - base) / base * 100.0,
        "redistributed_pool": adj["removed"].sum(),
    }


def sweep(verbose: bool = True) -> pd.DataFrame:
    master = build_master(verbose=False)
    cfg0 = load_assumptions()
    base = master["rhna_baseline"].sum()

    horizons = cfg0["horizon"]["years_sensitivity"]
    max_fracs = cfg0["displacement"]["max_fraction_sensitivity"]
    exps = cfg0["displacement"]["exponent_sensitivity"]

    rows = []
    for h, mf, ex in itertools.product(horizons, max_fracs, exps):
        cfg = copy.deepcopy(cfg0)
        cfg["horizon"]["years"] = h
        cfg["displacement"]["max_fraction"] = mf
        cfg["displacement"]["exponent"] = ex
        r = _run(master, cfg)
        rows.append({"horizon_years": h, "disp_max_fraction": mf,
                     "disp_exponent": ex, **r})
    df = pd.DataFrame(rows)
    df["baseline_total"] = base

    out = paths.OUTPUTS / "sensitivity.csv"
    df.to_csv(out, index=False)

    if verbose:
        _report(df, base, cfg0)
    return df


def trajectory_sweep(verbose: bool = True) -> pd.DataFrame:
    """Cumulative-to-2100 trajectory under the baseline household-growth variants
    (central / flat / decline). Shows how the long-horizon 'probable minimum'
    depends on the most uncertain input — the future demographic path."""
    from . import trajectory
    cfg0 = load_assumptions()
    variants = [None] + list(cfg0["trajectory"]["baseline_growth_variants"].keys())
    rows = []
    for v in variants:
        s = trajectory.run(verbose=False, make_charts=False, growth_variant=v,
                           write_outputs=False)["statewide"]
        last = s.iloc[-1]
        rows.append({
            "growth_variant": v or "central",
            "cum_baseline_2100": last["cum_baseline"],
            "cum_adjusted_2100": last["cum_adjusted"],
            "cum_climate_add": last["cum_climate_add"],
            "climate_add_pct_2100": last["climate_add_pct"],
        })
    df = pd.DataFrame(rows)
    df.to_csv(paths.OUTPUTS / "sensitivity_trajectory.csv", index=False)
    if verbose:
        print("\n" + "=" * 64)
        print("  TRAJECTORY SENSITIVITY — cumulative need to 2100")
        print("=" * 64)
        for _, r in df.iterrows():
            print(f"  {r['growth_variant']:8}  baseline {r['cum_baseline_2100']:>12,.0f}"
                  f"  climate-adj {r['cum_adjusted_2100']:>12,.0f}"
                  f"  (+{r['cum_climate_add']:,.0f})")
        print("=" * 64)
    return df


def trajectory_share_sweep(verbose: bool = True) -> pd.DataFrame:
    """Sweep the (author-judgment) growth-vs-deficit split `need_growth_share`
    (mirrored by `stock_growth_fraction`) over its sensitivity list, rebuilding the
    decadal trajectory under each via a config override. This is the one high-
    leverage trajectory knob that was declared but previously un-swept; it moves
    how much of need scales with demographics vs. persists as existing deficit."""
    import src.config as _config
    from . import trajectory
    cfg0 = load_assumptions()
    shares = cfg0["trajectory"].get("need_growth_share_sensitivity", [0.65])
    rows = []
    for s in shares:
        cfg = copy.deepcopy(cfg0)
        cfg["trajectory"]["need_growth_share"] = s
        cfg["trajectory"]["stock_growth_fraction"] = s
        _config.set_override(cfg)
        try:
            st = trajectory.run(verbose=False, make_charts=False,
                                write_outputs=False)["statewide"]
        finally:
            _config.set_override(None)
        last = st.iloc[-1]
        rows.append({"need_growth_share": s,
                     "cum_baseline_2100": last["cum_baseline"],
                     "cum_adjusted_2100": last["cum_adjusted"],
                     "cum_climate_add": last["cum_climate_add"],
                     "climate_add_pct_2100": last["climate_add_pct"]})
    df = pd.DataFrame(rows)
    df.to_csv(paths.OUTPUTS / "sensitivity_trajectory_share.csv", index=False)
    if verbose:
        print("\n" + "=" * 64)
        print("  TRAJECTORY SENSITIVITY — growth-vs-deficit share")
        print("=" * 64)
        for _, r in df.iterrows():
            print(f"  share {r['need_growth_share']:.2f}  baseline "
                  f"{r['cum_baseline_2100']:>12,.0f}  climate-adj "
                  f"{r['cum_adjusted_2100']:>12,.0f}  (+{r['cum_climate_add']:,.0f})")
        print("=" * 64)
    return df


def _report(df, base, cfg0) -> None:
    lo, hi = df["adjusted_total"].min(), df["adjusted_total"].max()
    print("\n" + "=" * 64)
    print("  SENSITIVITY OF THE 'PROBABLE MINIMUM'")
    print("=" * 64)
    print(f"  Baseline:                 {base:>12,.0f}")
    print(f"  Adjusted total range:     {lo:>12,.0f}  ..  {hi:,.0f}")
    print(f"                            (+{(lo-base)/base*100:.1f}%  ..  "
          f"+{(hi-base)/base*100:.1f}%)")
    # Central config row
    c = cfg0
    central = df[(df.horizon_years == c["horizon"]["years"])
                 & (df.disp_max_fraction == c["displacement"]["max_fraction"])
                 & (df.disp_exponent == c["displacement"]["exponent"])]
    if len(central):
        v = central.iloc[0]
        print(f"  Central estimate:         {v['adjusted_total']:>12,.0f}  "
              f"(+{v['increase_pct']:.1f}%)")
    print("-" * 64)
    print("  Total is driven by horizon (replacement); pool by displacement.")
    piv = df.pivot_table(index="horizon_years", values="adjusted_total", aggfunc="mean")
    for h, row in piv.iterrows():
        print(f"    horizon {h:>2} yr  ->  mean adjusted {row['adjusted_total']:,.0f}")
    print("=" * 64)


def _set_path(cfg: dict, path: str, value) -> None:
    keys = path.split(".")
    d = cfg
    for k in keys[:-1]:
        d = d[k]
    d[keys[-1]] = value


# One-at-a-time tornado. `rebuild=True` params are baked into `master` at build
# time, so they require rebuilding master under a config override; `rebuild=False`
# params are read by apply_model at runtime (fast path, master fixed).
_TORNADO = [
    ("horizon.years", [8, 16, 30], False),
    ("replacement.climate_uplift.max_uplift", [0.3, 0.5, 0.7], True),
    # Cap bracketed around the modeled distribution (max ~0.0087/yr): 0.005 bites
    # the top jurisdictions, >=0.01 is slack. The 0.02 default is a non-binding rail.
    ("replacement.max_annual_loss_rate", [0.005, 0.01, 0.02], True),
    ("exposure.weights.fire", [0.30, 0.40, 0.50], True),
    ("exposure.weights.flood", [0.20, 0.30, 0.40], True),
    ("displacement.max_fraction", [0.05, 0.10, 0.20], False),
    ("displacement.exponent", [1.5, 2.0, 3.0], False),
    ("siting.move_fraction", [0.30, 0.50, 0.70], False),
    ("receiver.resilience_exponent", [1.0, 1.5, 2.0], False),
    ("receiver.capacity_exponent", [0.5, 1.0, 1.5], False),
    ("water.siting.max_move_fraction", [0.15, 0.25, 0.35], False),
    ("water.weights.sgma", [0.30, 0.40, 0.50], True),
]


def tornado(verbose: bool = True) -> pd.DataFrame:
    """Vary each previously-FIXED parameter one at a time and report its effect on
    (a) the statewide TOTAL and (b) the MAP (L1 distance of the per-jurisdiction
    allocation from the central case). Substantiates: the total is robust to the
    redistribution parameters; only replacement parameters move it. Params baked
    into master are swept by rebuilding master under a config override."""
    import src.config as _config
    cfg0 = load_assumptions()
    master0 = build_master(verbose=False)
    c_alloc = apply_model(master0, cfg0)["rhna_adjusted"].to_numpy()
    c_total = c_alloc.sum()

    def _run(path, v, rebuild):
        cfg = copy.deepcopy(cfg0)
        _set_path(cfg, path, v)
        if rebuild:
            _config.set_override(cfg)
            try:
                adj = apply_model(build_master(verbose=False), cfg)
            finally:
                _config.set_override(None)
        else:
            adj = apply_model(master0, cfg)
        a = adj["rhna_adjusted"].to_numpy()
        return a.sum(), float(np.abs(a - c_alloc).sum())

    rows = []
    for path, vals, rebuild in _TORNADO:
        res = [_run(path, v, rebuild) for v in vals]
        totals = [r[0] for r in res]
        l1s = [r[1] for r in res]
        rows.append({"parameter": path, "values": str(vals),
                     "total_swing": max(totals) - min(totals),
                     "total_swing_pct": (max(totals) - min(totals)) / c_total * 100,
                     "map_L1_max": max(l1s)})
    df = pd.DataFrame(rows).sort_values("total_swing", ascending=False)
    df.to_csv(paths.OUTPUTS / "sensitivity_tornado.csv", index=False)
    try:
        from .viz import make_tornado_chart
        make_tornado_chart(df)
    except ImportError:
        pass  # matplotlib not installed; skip chart
    if verbose:
        print("\n" + "=" * 72)
        print("  TORNADO — effect of each fixed parameter (base 6th-cycle)")
        print("=" * 72)
        print(f"  {'parameter':38} {'total swing':>12} {'map L1':>12}")
        for _, r in df.iterrows():
            print(f"  {r['parameter']:38} {r['total_swing']:>10,.0f} "
                  f"({r['total_swing_pct']:>3.0f}%) {r['map_L1_max']:>11,.0f}")
        print("-" * 72)
        print("  Params with ~0 total swing move only the MAP (redistribution),")
        print("  confirming the statewide total is robust to them.")
        print("=" * 72)
    return df


def compound_sweep(verbose: bool = True) -> pd.DataFrame:
    """Sweep the (uncertain) compound-model parameters — how much extra capacity
    stacked places shed (`rate`) and how much can be rehoused (`rehouse_fraction`)
    — to present the stranded / compound-total as a band, not a point."""
    master = build_master(verbose=False)
    cfg0 = load_assumptions()
    base_total = apply_model(master, cfg0, compound=False)["rhna_adjusted"].sum()
    rows = []
    for rate in cfg0["compound"]["rate_sensitivity"]:
        for rehouse in cfg0["compound"]["rehouse_sensitivity"]:
            cfg = copy.deepcopy(cfg0)
            cfg["compound"]["rate"] = rate
            cfg["compound"]["rehouse_fraction"] = rehouse
            comp = apply_model(master, cfg, compound=True)
            rows.append({"rate": rate, "rehouse_fraction": rehouse,
                         "compound_total": comp["rhna_adjusted"].sum(),
                         "stranded": comp.attrs["stranded"]})
    df = pd.DataFrame(rows)
    df["base_total"] = base_total
    df.to_csv(paths.OUTPUTS / "sensitivity_compound.csv", index=False)
    if verbose:
        lo, hi = df["stranded"].min(), df["stranded"].max()
        print("\n" + "=" * 64)
        print("  COMPOUND-MODEL SENSITIVITY (stranded units band)")
        print("=" * 64)
        print(f"  Base model total:      {base_total:>12,.0f}")
        print(f"  Stranded range:        {lo:>12,.0f}  ..  {hi:,.0f}")
        print(f"  Compound total range:  {base_total-hi:>12,.0f}  ..  {base_total-lo:,.0f}")
        print("=" * 64)
    return df


if __name__ == "__main__":
    sweep()
    tornado()
    trajectory_sweep()
    trajectory_share_sweep()
    compound_sweep()
