"""Heat-habitability index H_j (0 = livable .. 1 = extreme-heat constrained).

The *chronic livability/cost* dimension of extreme heat — deliberately DISTINCT
from the acute NRI heat-wave risk (`hwav`) that already sits in the exposure
index E_j. To avoid double-counting, H_j uses only signals NOT already in the
model's heat term:
  * CMIP6 warm_nights  (nights >=70F/yr, SSP2-4.5 2050s)   — no nighttime relief
  * CMIP6 cdd_65f      (cooling degree-days)               — cooling-energy burden
  * CMIP6 tasmax_peak_f (annual peak heat)                 — daytime extremes
  * Census-LACE AC gap (pct_without_ac, vendored rollup)   — adaptive capacity

Used by the compound-constraint view (src/constraints.py) as the single "heat"
axis. It is NOT wired into apply_model as a discount (that would double-count
heat against E_j); it is a reporting axis only.

Validation: peaks in the SoCal deserts (Imperial / Coachella / Mojave), which the
groundwater-based water index W_j misses — heat broadens the constrained map
rather than reinforcing water (corr(H,W) ~ +0.25).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import paths
from .config import load_assumptions

_VARS = ["warm_nights", "cdd_65f", "tasmax_peak_f"]


def _minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) if hi > lo else s * 0.0


def _cmip6_heat(slugs) -> pd.DataFrame:
    cfg = load_assumptions()["scenario"]
    ssp, decade = cfg["ssp"], cfg["decade"]
    clim = json.loads(paths.CA_CLIMATE.read_text())["jurisdictions"]
    rows = []
    for slug in slugs:
        block = (clim.get(slug, {}).get("scenarios", {})
                 .get(ssp, {}).get(decade, {}))
        rows.append({"slug": slug,
                     **{v: block.get(v, {}).get("median", np.nan) for v in _VARS}})
    return pd.DataFrame(rows)


def build_heat_habitability(master: pd.DataFrame) -> pd.DataFrame:
    """Return per-slug: H (heat-habitability), plus the raw components."""
    cfg = load_assumptions().get("heat", {})
    w = cfg.get("weights", {"warm_nights": 0.35, "cdd_65f": 0.30,
                            "tasmax_peak_f": 0.20, "ac_gap": 0.15})

    df = _cmip6_heat(master["slug"])
    ac = pd.read_csv(paths.AC_ACCESS_BY_JURISDICTION)
    ac["ac_gap"] = pd.to_numeric(ac["pct_without_ac"], errors="coerce") / 100.0
    df = df.merge(ac[["slug", "ac_gap"]], on="slug", how="left")

    for c in _VARS + ["ac_gap"]:
        df[c] = df[c].fillna(df[c].median())

    wsum = sum(w.values())
    df["H"] = (
        w["warm_nights"] * _minmax(df["warm_nights"])
        + w["cdd_65f"] * _minmax(df["cdd_65f"])
        + w["tasmax_peak_f"] * _minmax(df["tasmax_peak_f"])
        + w["ac_gap"] * df["ac_gap"]
    ).clip(0, 1) / (wsum if wsum else 1.0)
    df["H"] = df["H"].clip(0, 1)
    return df[["slug", "H", "warm_nights", "cdd_65f", "ac_gap"]]
