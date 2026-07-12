"""End-to-end pipeline: master table -> climate adjustment -> region/statewide
cascade -> output CSVs + charts.

Run:  python -m src.allocate
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import paths
from .adjustment_model import apply_model
from .config import load_assumptions
from .crosswalk import build_master
from .regions import assign_regions


def run(verbose: bool = True, make_charts: bool = True) -> dict:
    paths.ensure_dirs()
    cfg = load_assumptions()

    master = build_master(verbose=verbose)
    adj = apply_model(master, cfg)
    adj = assign_regions(adj)

    _check_conservation(adj, cfg, verbose)

    # ---- jurisdiction output ----
    jcols = ["slug", "name", "juris_type", "county", "region", "population",
             "occ_housing", "E", "W", "annual_loss_rate", "unsafe_share",
             "rhna_baseline", "repl_R", "displace_D", "siting_S", "water_S",
             "removed", "received", "is_receiver", "rhna_adjusted", "delta",
             "delta_pct"]
    juris = adj[jcols].sort_values("rhna_adjusted", ascending=False)
    juris.to_csv(paths.ALLOC_JURISDICTION, index=False)

    # ---- region rollup ----
    region = (adj.groupby("region")
              .agg(baseline=("rhna_baseline", "sum"),
                   adjusted=("rhna_adjusted", "sum"),
                   replacement=("repl_R", "sum"),
                   displaced_out=("displace_D", "sum"),
                   siting_moved=("siting_S", "sum"),
                   water_moved=("water_S", "sum"),
                   received=("received", "sum"),
                   n_juris=("slug", "count"))
              .reset_index())
    region["delta"] = region["adjusted"] - region["baseline"]
    region["delta_pct"] = region["delta"] / region["baseline"] * 100.0
    region = region.sort_values("adjusted", ascending=False)
    region.to_csv(paths.ALLOC_REGION, index=False)

    # ---- statewide ----
    tot_base = adj["rhna_baseline"].sum()
    tot_adj = adj["rhna_adjusted"].sum()
    statewide = pd.DataFrame([{
        "scenario": cfg["scenario"]["ssp"],
        "horizon_years": cfg["horizon"]["years"],
        "baseline_total": tot_base,
        "adjusted_total": tot_adj,
        "replacement_total": adj["repl_R"].sum(),
        "water_moved": adj["water_S"].sum(),
        "redistributed_pool": adj["removed"].sum(),
        "increase": tot_adj - tot_base,
        "increase_pct": (tot_adj - tot_base) / tot_base * 100.0,
    }])
    statewide.to_csv(paths.ALLOC_STATEWIDE, index=False)

    if verbose:
        _print_summary(statewide, region, juris)
    if make_charts:
        from .viz import make_all
        make_all(adj, region, statewide)

    return {"jurisdiction": juris, "region": region, "statewide": statewide}


def _check_conservation(adj: pd.DataFrame, cfg: dict, verbose: bool) -> None:
    removed = adj["removed"].sum()
    received = adj["received"].sum()
    ext = cfg.get("external_migration", {})
    ext_units = float(ext.get("net_households", 0)) if ext.get("enabled") else 0.0
    # received should equal the redistributed pool (+ external term).
    assert np.isclose(received, removed + ext_units, rtol=1e-6), \
        f"pool not conserved: received={received} vs removed+ext={removed + ext_units}"
    increase = adj["rhna_adjusted"].sum() - adj["rhna_baseline"].sum()
    expected = adj["repl_R"].sum() + ext_units
    assert np.isclose(increase, expected, rtol=1e-6), \
        f"statewide increase {increase} != replacement+ext {expected}"
    if verbose:
        print(f"[check] pool conserved (removed={removed:,.0f} = received={received:,.0f}) OK")
        print(f"[check] statewide increase = replacement need ({increase:,.0f}) OK")


def _print_summary(statewide, region, juris) -> None:
    s = statewide.iloc[0]
    print("\n" + "=" * 66)
    print("  CLIMATE-ADJUSTED 'PROBABLE MINIMUM' STATEWIDE RHNA")
    print("=" * 66)
    print(f"  Baseline (HCD 6th cycle):   {s['baseline_total']:>12,.0f}")
    print(f"  Climate-adjusted minimum:   {s['adjusted_total']:>12,.0f}")
    print(f"  Increase (replacement need):{s['increase']:>12,.0f}  "
          f"(+{s['increase_pct']:.1f}%)")
    print(f"  Redistributed pool:         {s['redistributed_pool']:>12,.0f}")
    print(f"    of which water-siting:    {s['water_moved']:>12,.0f}")
    print("-" * 66)
    print("  Biggest gainers (units):")
    for _, r in juris.nlargest(5, "delta").iterrows():
        print(f"    {r['name'][:32]:32s} {r['rhna_baseline']:>8,.0f} -> "
              f"{r['rhna_adjusted']:>8,.0f}  ({r['delta']:>+7,.0f})")
    print("  Biggest losers (units):")
    for _, r in juris.nsmallest(5, "delta").iterrows():
        print(f"    {r['name'][:32]:32s} {r['rhna_baseline']:>8,.0f} -> "
              f"{r['rhna_adjusted']:>8,.0f}  ({r['delta']:>+7,.0f})")
    print("=" * 66)


if __name__ == "__main__":
    run()
