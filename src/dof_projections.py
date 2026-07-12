"""Per-county baseline-growth multipliers from DOF projections.

Replaces the uniform statewide growth taper (trajectory.baseline_growth_mult)
with a county-resolved one derived from CA Department of Finance projections
(Baseline 2024 / Vintage 2025):
  * P-4 Total Households, 2010-2040 (real household projections)
  * P-2A Total Population, 2020-2070 (to extend households past 2040)

Household growth -- not population change -- drives housing need, and households
keep growing even as population plateaus because average household size falls.
We build a household series 2020-2070 per county (real P-4 through 2040; beyond
that, Pop / a declining household-size trajectory fit to the 2020-2040 data),
then form a TWO-PART multiplier on each county's 6th-cycle allocation B_j:

    growth_ratio_d = HH_growth_county,d / HH_growth_county,2020s
    mult_county,d  = need_growth_share * growth_ratio_d + (1 - need_growth_share)

Only the growth share of an RHNA allocation responds to demographics; the
existing-deficit share (overcrowding, cost burden, vacancy) persists, so need
never collapses to zero in slow/declining counties. Bounded by [floor, cap].
DOF ends at 2070, so decades 2030s..2060s are data-backed and 2070s-2090s hold
the 2060s value.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import paths
from .config import load_assumptions

_YEARS = [2020, 2030, 2040, 2050, 2060, 2070]
_DECADE_DELTAS = {"2020s": (2020, 2030), "2030s": (2030, 2040), "2040s": (2040, 2050),
                  "2050s": (2050, 2060), "2060s": (2060, 2070)}
_LAST_DOF_DECADE = "2060s"


def _year_col(df: pd.DataFrame, year: int) -> str:
    return [c for c in df.columns if str(c).split(".")[0] == str(year)][0]


def _read_dof(path, sheet: str, name_col: str, years: list[int]) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, header=1)
    df = df.rename(columns={c: str(c) for c in df.columns})
    fips = pd.to_numeric(df["FIPS"], errors="coerce")
    mask = fips.notna() & (df[name_col].astype(str).str.upper() != "CALIFORNIA")
    df = df[mask].copy()
    out = pd.DataFrame({"county_fips": fips[mask].astype(int).astype(str).str.zfill(5).values})
    for y in years:
        out[y] = pd.to_numeric(df[_year_col(df, y)].values, errors="coerce")
    return out.set_index("county_fips")


@lru_cache(maxsize=1)
def _county_households() -> pd.DataFrame:
    """County households at each decade year 2020-2070: real P-4 to 2040, then
    Pop (P-2A) / a household-size trajectory extrapolated from the 2020-2040 fit."""
    hh = _read_dof(paths.DOF_P4, "Household Projections", "County", [2020, 2030, 2040])
    pop = _read_dof(paths.DOF_P2A, "Data", "Geography", _YEARS)

    # Statewide household size 2020/2040 -> linear trajectory to 2070.
    s2020 = pop[2020].sum() / hh[2020].sum()
    s2040 = pop[2040].sum() / hh[2040].sum()
    slope = (s2040 - s2020) / 20.0
    hh_size = {y: s2020 + slope * (y - 2020) for y in _YEARS}

    out = pd.DataFrame(index=pop.index)
    for y in [2020, 2030, 2040]:
        out[y] = hh[y].reindex(pop.index)
    for y in [2050, 2060, 2070]:
        out[y] = pop[y] / hh_size[y]
    return out


def county_growth_multipliers() -> pd.DataFrame:
    """DataFrame indexed by county_fips, one column per trajectory decade."""
    tj = load_assumptions()["trajectory"]
    decades = tj["decades"]
    gshare = tj.get("need_growth_share", 0.65)
    floor, cap = tj.get("county_growth_floor", 0.25), tj.get("county_growth_cap", 2.0)

    hh = _county_households()
    delta = {d: hh[b] - hh[a] for d, (a, b) in _DECADE_DELTAS.items()}
    ref = delta["2020s"]
    state_ref = ref.sum()

    mult = pd.DataFrame(index=hh.index)
    for dec in ["2030s", "2040s", "2050s", "2060s"]:
        # Where a county's 2020s growth is non-positive the ratio is undefined;
        # fall back to the statewide growth ratio for that decade.
        state_ratio = delta[dec].sum() / state_ref if state_ref else 1.0
        ratio = np.where(ref > 0, delta[dec] / ref.where(ref > 0, np.nan), state_ratio)
        ratio = np.clip(ratio, 0.0, cap)
        mult[dec] = np.clip(gshare * ratio + (1.0 - gshare), floor, cap)
    for dec in decades:  # hold last data-backed decade through the tail
        if dec not in mult.columns:
            mult[dec] = mult[_LAST_DOF_DECADE]
    return mult[decades]


def multiplier_by_jurisdiction(master: pd.DataFrame) -> pd.DataFrame:
    """Per-jurisdiction multipliers (indexed by slug), mapped by county FIPS.
    Jurisdictions whose county is missing from DOF fall back to 1.0."""
    cmult = county_growth_multipliers()
    decades = list(cmult.columns)
    m = master[["slug", "county_fips"]].copy()
    m["county_fips"] = m["county_fips"].astype(str).str.zfill(5)
    joined = m.merge(cmult, left_on="county_fips", right_index=True, how="left")
    joined[decades] = joined[decades].fillna(1.0)
    return joined.set_index("slug")[decades]
