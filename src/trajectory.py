"""Longer-horizon trajectory: housing need DECADE-BY-DECADE beyond the 6th cycle.

Where `allocate.py` adjusts the single 6th-cycle allocation, this walks the
decades 2030s -> 2090s and, for each, layers TIME-VARYING climate (CMIP6 decade
+ rising sea level) onto a GROWING, demographically-tapered baseline, then
accumulates the result into a cumulative housing-need trajectory to 2100.

Per decade d (each ~ one 8-10 yr planning cycle):
  baseline_need_j,d = B_j * growth_mult_d          (climate-blind; DOF-informed)
  exposure/uplift/SLR recomputed for decade d      (hazard_exposure, pooled norm)
  adjusted_need_j,d = apply_model(...)             (components A-D, 10-yr horizon)
  stock_j grows by baseline_need_j,d               (replacement scales with stock)

The single-shot model (allocate.py) is the 6th-cycle base case; this module does
NOT replace it. Reuses apply_model so the per-decade adjustment is identical in
form to the headline model.

Run:  python -m src.trajectory
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from . import paths
from .adjustment_model import apply_model
from .config import load_assumptions
from .crosswalk import build_master
from .dof_projections import multiplier_by_jurisdiction
from .hazard_exposure import (build_exposure_for_decade, pooled_cmip6_bounds,
                              rollup_nri)
from .housing import attach_housing
from .jurisdictions import load_jurisdictions
from .regions import assign_regions


def _decade_end_year(decade: str) -> str:
    """'2030s' -> '2040' (end-of-decade year for the SLR lookup)."""
    return str(int(decade[:4]) + 10)


def run(verbose: bool = True, make_charts: bool = True,
        growth_variant: str | None = None, growth_curve: dict | None = None) -> dict:
    paths.ensure_dirs()
    cfg = load_assumptions()
    tj = cfg["trajectory"]
    decades = tj["decades"]
    ypd = tj["years_per_decade"]

    # Growth source: an explicit statewide curve/variant (for comparison and
    # sensitivity) forces the uniform path; otherwise follow config (county-
    # resolved DOF households by default).
    growth = None
    if growth_curve is not None:
        source, growth = "statewide", growth_curve
    elif growth_variant:
        source, growth = "statewide", tj["baseline_growth_variants"][growth_variant]
    else:
        source = tj.get("growth_source", "statewide")
        if source == "statewide":
            growth = tj["baseline_growth_mult"]

    # Per-decade adjustment uses a 10-yr replacement horizon.
    cfg_d = copy.deepcopy(cfg)
    cfg_d["horizon"]["years"] = ypd

    # Authoritative analysis set (539 units w/ 6th-cycle baseline) + geometry.
    master = build_master(verbose=False)
    jm = multiplier_by_jurisdiction(master) if source == "county" else None
    spine = attach_housing(load_jurisdictions())
    spine = spine[spine["slug"].isin(master["slug"])].reset_index(drop=True)
    nri = rollup_nri(spine)
    bounds = pooled_cmip6_bounds(spine, decades)

    base = master.set_index("slug")
    B0 = base["rhna_baseline"].astype(float)
    stock = base["occ_housing"].astype(float).copy()
    stock0 = stock.copy()
    pop0 = base["population"].astype(float)
    region_of = assign_regions(master[["slug", "county"]]).set_index("slug")["region"]

    state_rows, region_frames, juris_frames = [], [], []

    for d in decades:
        yr = _decade_end_year(d)
        ex = build_exposure_for_decade(spine, nri, d, yr, bounds).set_index("slug")

        # Per-jurisdiction baseline-growth multiplier for the decade.
        if source == "county":
            mult_d = jm[d].reindex(B0.index).fillna(1.0).values
        else:
            mult_d = growth[d]

        # Assemble the per-decade "master" apply_model expects.
        md = pd.DataFrame({
            "slug": B0.index,
            "name": base["name"].values,
            "county": base["county"].values,
            "rhna_baseline": (B0 * mult_d).values,          # grown baseline
            "occ_housing": stock.reindex(B0.index).values,  # start-of-decade stock
            "population": (pop0 * (stock / stock0)).reindex(B0.index).values,
            "unsafe_share": base["unsafe_share"].values,    # static
            "E": ex["E"].reindex(B0.index).values,
            "annual_loss_rate": ex["annual_loss_rate"].reindex(B0.index).values,
        })

        adj = apply_model(md, cfg_d)
        _check_decade(adj, cfg_d, d)

        adj["decade"] = d
        adj["region"] = region_of.reindex(adj["slug"]).values
        juris_frames.append(adj[["decade", "slug", "name", "region", "rhna_baseline",
                                 "rhna_adjusted", "repl_R", "removed", "received",
                                 "E"]].copy())

        # Statewide record.
        b, a = adj["rhna_baseline"].sum(), adj["rhna_adjusted"].sum()
        state_rows.append({
            "decade": d, "slr_year": yr, "growth_source": source,
            "eff_growth_mult": b / float(B0.sum()),
            "baseline_need": b, "adjusted_need": a,
            "replacement": adj["repl_R"].sum(),
            "redistributed_pool": adj["removed"].sum(),
            "climate_add": a - b, "climate_add_pct": (a - b) / b * 100.0,
            "mean_E": adj["E"].mean(),
        })

        # Region rollup for the decade.
        rg = (adj.groupby("region")
              .agg(baseline_need=("rhna_baseline", "sum"),
                   adjusted_need=("rhna_adjusted", "sum"),
                   replacement=("repl_R", "sum"))
              .reset_index())
        rg["decade"] = d
        region_frames.append(rg)

        # Grow stock by the net-new (growth-component) share of this decade's
        # baseline need; the existing-deficit share does not enlarge the stock.
        grow = pd.Series(adj["rhna_baseline"].values * tj["stock_growth_fraction"],
                         index=adj["slug"])
        stock = stock.add(grow.reindex(stock.index).fillna(0.0))

    statewide = pd.DataFrame(state_rows)
    statewide["cum_baseline"] = statewide["baseline_need"].cumsum()
    statewide["cum_adjusted"] = statewide["adjusted_need"].cumsum()
    statewide["cum_climate_add"] = statewide["cum_adjusted"] - statewide["cum_baseline"]
    statewide.to_csv(paths.TRAJ_STATEWIDE, index=False)

    region = pd.concat(region_frames, ignore_index=True)
    region = region.sort_values(["region", "decade"])
    region["cum_baseline"] = region.groupby("region")["baseline_need"].cumsum()
    region["cum_adjusted"] = region.groupby("region")["adjusted_need"].cumsum()
    region.to_csv(paths.TRAJ_REGION, index=False)

    juris = pd.concat(juris_frames, ignore_index=True)

    if verbose:
        _print_summary(statewide, region)
    if make_charts:
        from .viz import make_trajectory_charts
        make_trajectory_charts(statewide, region)

    return {"statewide": statewide, "region": region, "jurisdiction": juris}


def compare_sources(make_charts: bool = True, verbose: bool = True) -> pd.DataFrame:
    """Run the trajectory under the county-resolved DOF baseline vs the uniform
    statewide taper and quantify how much county resolution shifts the REGIONAL
    distribution of cumulative need. Writes outputs/trajectory_region_compare.csv."""
    cfg = load_assumptions()
    county = run(verbose=False, make_charts=False)
    uniform = run(verbose=False, make_charts=False,
                  growth_curve=cfg["trajectory"]["baseline_growth_mult"])

    def _cum(reg):
        last = reg.sort_values("decade").groupby("region").tail(1)
        return last.set_index("region")["cum_adjusted"]

    u, c = _cum(uniform["region"]), _cum(county["region"])
    cmp = pd.DataFrame({"uniform": u, "county": c}).fillna(0.0)
    cmp["uniform_share_pct"] = cmp["uniform"] / cmp["uniform"].sum() * 100
    cmp["county_share_pct"] = cmp["county"] / cmp["county"].sum() * 100
    cmp["share_shift_pp"] = cmp["county_share_pct"] - cmp["uniform_share_pct"]
    cmp = cmp.sort_values("share_shift_pp", ascending=False)
    cmp.to_csv(paths.OUTPUTS / "trajectory_region_compare.csv")

    if verbose:
        us, cs = uniform["statewide"].iloc[-1], county["statewide"].iloc[-1]
        print("\n" + "=" * 72)
        print("  COUNTY-RESOLVED vs UNIFORM baseline — cumulative need to 2100")
        print("=" * 72)
        print(f"  {'':22} {'uniform':>14} {'county (DOF)':>14}")
        print(f"  {'cum baseline':22} {us['cum_baseline']:>14,.0f} {cs['cum_baseline']:>14,.0f}")
        print(f"  {'cum climate-adjusted':22} {us['cum_adjusted']:>14,.0f} {cs['cum_adjusted']:>14,.0f}")
        print(f"  {'climate share':22} {us['cum_climate_add']/us['cum_baseline']*100:>13.1f}% "
              f"{cs['cum_climate_add']/cs['cum_baseline']*100:>13.1f}%")
        print("-" * 72)
        print("  Largest regional share shifts (county − uniform), pp of statewide:")
        for r, row in pd.concat([cmp.head(4), cmp.tail(3)]).iterrows():
            print(f"    {r[:26]:26} {row['share_shift_pp']:>+6.1f} pp   "
                  f"({row['uniform_share_pct']:.1f}% -> {row['county_share_pct']:.1f}%)")
        print("=" * 72)
    if make_charts:
        from .viz import make_trajectory_compare_chart
        make_trajectory_compare_chart(cmp)
    return cmp


def _check_decade(adj: pd.DataFrame, cfg: dict, decade: str) -> None:
    removed, received = adj["removed"].sum(), adj["received"].sum()
    assert np.isclose(received, removed, rtol=1e-6), \
        f"[{decade}] pool not conserved: {received} vs {removed}"
    increase = adj["rhna_adjusted"].sum() - adj["rhna_baseline"].sum()
    assert np.isclose(increase, adj["repl_R"].sum(), rtol=1e-6), \
        f"[{decade}] increase {increase} != replacement {adj['repl_R'].sum()}"


def _print_summary(statewide: pd.DataFrame, region: pd.DataFrame) -> None:
    last = statewide.iloc[-1]
    cum_b, cum_a = last["cum_baseline"], last["cum_adjusted"]
    src = statewide.iloc[0].get("growth_source", "statewide")
    src_lbl = "county-resolved (DOF households)" if src == "county" else "uniform statewide taper"
    print("\n" + "=" * 72)
    print("  LONGER-HORIZON HOUSING-NEED TRAJECTORY  (SSP2-4.5, 2030s->2090s)")
    print(f"  baseline growth source: {src_lbl}")
    print("=" * 72)
    print(f"  {'decade':7} {'baseline':>12} {'climate-adj':>12} {'+climate':>10} {'+%':>7}")
    for _, r in statewide.iterrows():
        print(f"  {r['decade']:7} {r['baseline_need']:>12,.0f} {r['adjusted_need']:>12,.0f}"
              f" {r['climate_add']:>10,.0f} {r['climate_add_pct']:>6.1f}%")
    print("-" * 72)
    print(f"  CUMULATIVE need to 2100:")
    print(f"    Baseline (climate-blind):   {cum_b:>14,.0f}")
    print(f"    Climate-adjusted minimum:   {cum_a:>14,.0f}")
    print(f"    Climate-driven addition:    {cum_a - cum_b:>14,.0f}  "
          f"(+{(cum_a - cum_b) / cum_b * 100:.1f}%)")
    print("=" * 72)


if __name__ == "__main__":
    run()
    compare_sources()
