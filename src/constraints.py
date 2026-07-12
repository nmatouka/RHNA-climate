"""Compound climate-constraint view.

Answers: what share of statewide RHNA is climate-constrained on >=1 axis, and
WHERE do constraints stack? Flags five DISTINCT hazard axes, each counted once
so nothing is double-counted:

    fire   <- exposure sub-score (NRI wildfire)
    flood  <- exposure sub-score (NRI inland/coastal flood)
    slr    <- exposure sub-score (sea-level rise)
    water  <- W_j (SGMA overdraft + drought + aridification)   [src/water.py]
    heat   <- H_j (heat-habitability)                           [src/heat.py]

The acute NRI heat-wave term already inside the exposure index E_j is NOT
re-counted here — heat enters once, via the habitability index. This is a
REPORTING layer (a per-jurisdiction constraint map), not a new discount
component: adding a heat discount while heat is also in E_j would double-count.

Run:  python -m src.constraints
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import paths
from .config import load_assumptions
from .crosswalk import build_master
from .heat import build_heat_habitability
from .regions import assign_regions

AXES = ["fire", "flood", "slr", "water", "heat"]


def build_constraints(master: pd.DataFrame | None = None,
                      verbose: bool = True, make_chart: bool = True) -> pd.DataFrame:
    if master is None:
        master = build_master(verbose=False)
    master = assign_regions(master)
    heat = build_heat_habitability(master)
    df = master.merge(heat[["slug", "H"]], on="slug", how="left")

    thr = load_assumptions()["constraints"]["thresholds"]
    score = {"fire": df["fire"], "flood": df["flood"], "slr": df["slr"],
             "water": df["W"], "heat": df["H"]}
    for ax in AXES:
        df[f"c_{ax}"] = (score[ax].fillna(0) >= thr[ax]).astype(int)
    df["n_constraints"] = df[[f"c_{ax}" for ax in AXES]].sum(axis=1)
    df["constraint_axes"] = df.apply(
        lambda r: ",".join(ax for ax in AXES if r[f"c_{ax}"]), axis=1)

    out = df[["slug", "name", "county", "region", "rhna_baseline",
              "fire", "flood", "slr", "W", "H",
              *[f"c_{ax}" for ax in AXES], "n_constraints", "constraint_axes"]]
    paths.ensure_dirs()
    out.to_csv(paths.OUTPUTS / "constraints_by_jurisdiction.csv", index=False)

    if verbose:
        _report(df)
    if make_chart:
        from .viz import make_constraints_chart
        make_constraints_chart(df)
    return df


def _report(df: pd.DataFrame) -> None:
    tot = df["rhna_baseline"].sum()
    print("\n" + "=" * 66)
    print("  COMPOUND CLIMATE-CONSTRAINT VIEW  (each axis counted once)")
    print("=" * 66)
    print(f"  {'axis':8} {'jurisdictions':>13} {'RHNA':>12} {'% of state':>11}")
    for ax in AXES:
        m = df[f"c_{ax}"] == 1
        print(f"  {ax:8} {int(m.sum()):>13} {df.loc[m, 'rhna_baseline'].sum():>12,.0f}"
              f" {df.loc[m, 'rhna_baseline'].sum()/tot*100:>10.1f}%")
    print("-" * 66)
    for k, lbl in [(1, ">=1 axis (union)"), (2, ">=2 axes (stacked)"),
                   (3, ">=3 axes")]:
        m = df["n_constraints"] >= k
        print(f"  {lbl:20} {int(m.sum()):>6} juris  {df.loc[m,'rhna_baseline'].sum():>12,.0f}"
              f"  ({df.loc[m,'rhna_baseline'].sum()/tot*100:.1f}%)")
    print("-" * 66)
    print("  Most compounded jurisdictions (n_constraints, by RHNA):")
    top = df[df["n_constraints"] >= 2].nlargest(8, "rhna_baseline")
    for _, r in top.iterrows():
        print(f"    {r['name'][:26]:26} {int(r['n_constraints'])}x  "
              f"[{r['constraint_axes']}]  {r['rhna_baseline']:>7,.0f}")
    print("=" * 66)


if __name__ == "__main__":
    build_constraints()
