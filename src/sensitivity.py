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
        s = trajectory.run(verbose=False, make_charts=False, growth_variant=v)["statewide"]
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


if __name__ == "__main__":
    sweep()
    trajectory_sweep()
