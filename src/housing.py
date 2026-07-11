"""Attach current occupied-housing and population to the jurisdiction spine.

Source: v2_jurisdictions.csv (jurisdiction x year, 2019-2024). We use the
latest year as the current housing stock / population baseline.

Join strategy (confirmed FIPS-based):
  - Cities        -> 7-digit PLACE_FIPS.
  - Unincorporated -> county name (v2 has JURIS_TYPE='Unincorporated County',
    no real place FIPS; spine carries the county name).
"""
from __future__ import annotations

import pandas as pd

from . import paths


def _load_v2_latest() -> pd.DataFrame:
    df = pd.read_csv(paths.V2_JURISDICTIONS, dtype={"PLACE_FIPS": str})
    latest = df["YEAR"].max()
    df = df[df["YEAR"] == latest].copy()
    df["_year"] = latest
    return df


def attach_housing(spine: pd.DataFrame) -> pd.DataFrame:
    """Return `spine` with added columns: occ_housing, population, housing_year.

    Population prefers the v2 value; falls back to climateshed's population_cs
    when unmatched.
    """
    v2 = _load_v2_latest()

    cities = v2[v2["JURIS_TYPE"] == "City"].copy()
    cities["place_fips"] = cities["PLACE_FIPS"].str.zfill(7)
    city_map = cities.set_index("place_fips")[["OCC_HOUSING", "POPULATION", "_year"]]

    uninc = v2[v2["JURIS_TYPE"] == "Unincorporated County"].copy()
    uninc_map = uninc.set_index("COUNTY")[["OCC_HOUSING", "POPULATION", "_year"]]

    out = spine.copy()
    occ, pop, yr = [], [], []
    for _, row in out.iterrows():
        rec = None
        if row["juris_type"] == "city" and row["place_fips"] in city_map.index:
            rec = city_map.loc[row["place_fips"]]
        elif row["juris_type"] == "unincorporated" and row["county"] in uninc_map.index:
            rec = uninc_map.loc[row["county"]]
        if rec is not None:
            occ.append(float(rec["OCC_HOUSING"]))
            pop.append(float(rec["POPULATION"]))
            yr.append(int(rec["_year"]))
        else:
            occ.append(float("nan"))
            pop.append(row.get("population_cs") or float("nan"))
            yr.append(-1)
    out["occ_housing"] = occ
    out["population"] = pop
    out["housing_year"] = yr
    return out
