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
    # Two models: BASE (hazards independent) and COMPOUND (option 2, stranding).
    adj = assign_regions(apply_model(master, cfg, compound=False))
    comp = assign_regions(apply_model(master, cfg, compound=True))
    stranded = float(comp.attrs.get("stranded", 0.0))

    _check_conservation(adj, cfg, verbose)

    # ---- jurisdiction output (base primary + compound columns) ----
    jcols = ["slug", "name", "juris_type", "county", "region", "population",
             "occ_housing", "E", "W", "H", "annual_loss_rate", "unsafe_share",
             "rhna_baseline", "repl_R", "displace_D", "siting_S", "water_S",
             "removed", "received", "is_receiver", "rhna_adjusted", "delta",
             "delta_pct"]
    juris = adj[jcols].copy()
    juris["compound_S"] = comp["compound_S"].values
    juris["rhna_adjusted_compound"] = comp["rhna_adjusted"].values
    juris["delta_compound"] = comp["rhna_adjusted"].values - adj["rhna_adjusted"].values
    juris = juris.sort_values("rhna_adjusted", ascending=False)
    juris.to_csv(paths.ALLOC_JURISDICTION, index=False)

    # ---- region rollup (base + compound side by side) ----
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
    region["adjusted_compound"] = (comp.groupby("region")["rhna_adjusted"].sum()
                                   .reindex(region["region"]).values)
    region["compound_moved"] = (comp.groupby("region")["compound_S"].sum()
                                .reindex(region["region"]).values)
    region["delta"] = region["adjusted"] - region["baseline"]
    region["delta_pct"] = region["delta"] / region["baseline"] * 100.0
    region["delta_compound"] = region["adjusted_compound"] - region["adjusted"]
    region = region.sort_values("adjusted", ascending=False)
    region.to_csv(paths.ALLOC_REGION, index=False)

    # ---- statewide (two rows: base, compound) ----
    tot_base = adj["rhna_baseline"].sum()
    common = {"scenario": cfg["scenario"]["ssp"],
              "horizon_years": cfg["horizon"]["years"], "baseline_total": tot_base}
    statewide = pd.DataFrame([
        {"model": "base", **common, "adjusted_total": adj["rhna_adjusted"].sum(),
         "replacement_total": adj["repl_R"].sum(), "water_moved": adj["water_S"].sum(),
         "compound_moved": 0.0, "stranded": 0.0,
         "increase": adj["rhna_adjusted"].sum() - tot_base,
         "increase_pct": (adj["rhna_adjusted"].sum() - tot_base) / tot_base * 100.0},
        {"model": "compound", **common, "adjusted_total": comp["rhna_adjusted"].sum(),
         "replacement_total": comp["repl_R"].sum(), "water_moved": comp["water_S"].sum(),
         "compound_moved": comp["compound_S"].sum(), "stranded": stranded,
         "increase": comp["rhna_adjusted"].sum() - tot_base,
         "increase_pct": (comp["rhna_adjusted"].sum() - tot_base) / tot_base * 100.0},
    ])
    statewide.to_csv(paths.ALLOC_STATEWIDE, index=False)

    if verbose:
        _print_summary(statewide, region, juris)
    if make_charts:
        from .viz import make_all, make_model_compare_chart
        make_all(adj, region, statewide)
        make_model_compare_chart(region, statewide)

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
    b = statewide[statewide["model"] == "base"].iloc[0]
    c = statewide[statewide["model"] == "compound"].iloc[0]
    print("\n" + "=" * 66)
    print("  CLIMATE-ADJUSTED 'PROBABLE MINIMUM' STATEWIDE RHNA — TWO MODELS")
    print("=" * 66)
    print(f"  Baseline (HCD 6th cycle):        {b['baseline_total']:>12,.0f}")
    print(f"  BASE model (hazards independent):{b['adjusted_total']:>12,.0f}  "
          f"(+{b['increase_pct']:.1f}%)")
    print(f"  COMPOUND model (option 2):       {c['adjusted_total']:>12,.0f}  "
          f"(+{c['increase_pct']:.1f}%)")
    print(f"    stranded (un-rehousable):      {c['stranded']:>12,.0f}  "
          f"= base − compound")
    print("-" * 66)
    print("  Biggest gainers (units, base model):")
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
