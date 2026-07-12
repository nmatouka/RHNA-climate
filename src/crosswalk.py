"""Assemble the master jurisdiction table: spine + housing + exposure (+ RHNA
baseline when sourced). Reports join coverage.

Run standalone to (re)build data/processed/master_jurisdiction.csv:
    python -m src.crosswalk
"""
from __future__ import annotations

import pandas as pd

from . import paths
from .housing import attach_housing
from .hazard_exposure import build_exposure
from .jurisdictions import load_jurisdictions


def build_master(verbose: bool = True) -> pd.DataFrame:
    spine = load_jurisdictions()
    spine = attach_housing(spine)
    exposure = build_exposure(spine)

    keep = ["slug", "name", "juris_type", "county", "county_fips", "place_fips",
            "occ_housing", "population", "housing_year"]
    master = spine[keep].merge(
        exposure.drop(columns=["name", "juris_type", "county"]), on="slug", how="left"
    )

    # Water-stress index W_j (reuses exposure's drought/CMIP6 cols + SGMA basins).
    from .water import build_water_stress
    master = master.merge(build_water_stress(master), on="slug", how="left")

    # Optional: merge sourced RHNA baseline (Phase 2 output).
    if paths.RHNA_BASELINE.exists():
        master = _merge_rhna(master, verbose)
        # Drop phantom analysis units with no HCD baseline. The only such row is
        # "Unincorporated San Francisco County" — SF is a consolidated city-
        # county with no unincorporated area, so HCD lists only the city.
        phantom = master["rhna_baseline"].isna()
        if phantom.any():
            if verbose:
                print(f"[note] dropping {int(phantom.sum())} unit(s) with no RHNA "
                      f"baseline: {list(master.loc[phantom, 'name'])}")
            master = master[~phantom].reset_index(drop=True)
    elif verbose:
        print(f"[note] RHNA baseline not yet sourced ({paths.RHNA_BASELINE.name} absent); "
              "master built without B_j.")

    if verbose:
        _report_coverage(master)
    return master


def _merge_rhna(master: pd.DataFrame, verbose: bool) -> pd.DataFrame:
    """Merge sourced baseline on PLACE_FIPS (cities) / COUNTY_FIPS (unincorp)."""
    rhna = pd.read_csv(paths.RHNA_BASELINE, dtype={"PLACE_FIPS": str, "COUNTY_FIPS": str})
    rhna["PLACE_FIPS"] = rhna["PLACE_FIPS"].where(rhna["PLACE_FIPS"].isna(),
                                                  rhna["PLACE_FIPS"].str.zfill(7))
    cities = rhna[rhna["PLACE_FIPS"].notna()][["PLACE_FIPS", "rhna_baseline"]]
    master = master.merge(cities.rename(columns={"PLACE_FIPS": "place_fips"}),
                          on="place_fips", how="left")
    # Unincorporated: join remaining on county FIPS.
    uninc = rhna[rhna["PLACE_FIPS"].isna()][["COUNTY_FIPS", "rhna_baseline"]]
    uninc = uninc.rename(columns={"COUNTY_FIPS": "county_fips", "rhna_baseline": "_uninc_b"})
    uninc["county_fips"] = uninc["county_fips"].str.zfill(5)
    master = master.merge(uninc, on="county_fips", how="left")
    mask = master["juris_type"] == "unincorporated"
    master.loc[mask, "rhna_baseline"] = master.loc[mask, "_uninc_b"]
    return master.drop(columns=["_uninc_b"])


def _report_coverage(master: pd.DataFrame) -> None:
    n = len(master)
    print(f"[coverage] {n} analysis jurisdictions "
          f"({(master['juris_type'] == 'city').sum()} city, "
          f"{(master['juris_type'] == 'unincorporated').sum()} unincorporated)")
    miss_h = master["occ_housing"].isna().sum()
    miss_e = master["E"].isna().sum()
    print(f"[coverage] housing matched: {n - miss_h}/{n} (missing {miss_h})")
    print(f"[coverage] exposure computed: {n - miss_e}/{n} (missing {miss_e})")
    if "rhna_baseline" in master.columns:
        miss_r = master["rhna_baseline"].isna().sum()
        print(f"[coverage] RHNA baseline matched: {n - miss_r}/{n} (missing {miss_r})")
    if miss_h:
        print("  unmatched housing:", list(master.loc[master["occ_housing"].isna(), "name"])[:15])


def main() -> None:
    paths.ensure_dirs()
    master = build_master(verbose=True)
    master.to_csv(paths.MASTER_TABLE, index=False)
    print(f"[write] {paths.MASTER_TABLE} ({len(master)} rows)")


if __name__ == "__main__":
    main()
