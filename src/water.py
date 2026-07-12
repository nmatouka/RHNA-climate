"""Per-jurisdiction water-stress index W_j (0 = secure .. 1 = constrained).

Built entirely from data already on hand (no new geospatial analysis):
  * NRI Drought risk       -> rollup_nri adds `drought` (DRGT_RISKS percentile)
  * CMIP6 aridification     -> max_dry_spell + precip_change_pct (SSP2-4.5, 2050s)
  * SGMA basin priority     -> data/external/sgma_by_jurisdiction.csv, produced by
    reusing climateshed's own casgem_basins.query_point (DWR B118 basins + SGMA
    2019 prioritization); critically-overdrafted basins score highest.

W_j feeds a supply-side WATER-SITING DISCOUNT in the adjustment model: a share of
a water-constrained jurisdiction's allocation is treated as not-probable-to-be-
watered and redistributed to water-secure receivers. It is purely redistributive
(water constrains WHERE need is met, not how much), so the statewide total is
unchanged.

Empirically water is a contained constraint: ~9% of statewide RHNA sits over
critically-overdrafted basins, but growth and water stress are ~uncorrelated
statewide (r~0); the sharp fast-growth-and-overdrafted overlap (~2.5%) is the
northern San Joaquin Valley (San Joaquin, Merced, Stanislaus).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import paths
from .config import load_assumptions

# SGMA 2019 basin priority -> a 0..1 stress score (critically-overdrafted = 1).
_SGMA_PRIORITY_SCORE = {
    "High": 0.8, "Medium": 0.5, "Low": 0.3, "Very Low": 0.15, "None": 0.1,
}


def _minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) if hi > lo else s * 0.0


def _sgma_scores() -> pd.DataFrame:
    sg = pd.read_csv(paths.SGMA_BY_JURISDICTION)

    def score(r):
        if bool(r["sgma_critically_overdrafted"]):
            return 1.0
        return _SGMA_PRIORITY_SCORE.get(r["sgma_priority"], 0.1)

    sg["sgma_score"] = sg.apply(score, axis=1)
    return sg[["slug", "sgma_score", "sgma_priority", "sgma_critically_overdrafted"]]


def build_water_stress(master: pd.DataFrame) -> pd.DataFrame:
    """Return per-slug water columns: W, water_drought, water_arid, sgma_score,
    sgma_priority, sgma_critically_overdrafted.

    `master` must carry `drought`, `dry_spell`, `precip_change` (produced by the
    exposure build). Aridification is min-max normalized across the given set.
    """
    cfg = load_assumptions().get("water", {})
    w = cfg.get("weights", {"sgma": 0.40, "drought": 0.35, "aridification": 0.25})

    df = master[["slug", "drought", "dry_spell", "precip_change"]].copy()
    df = df.merge(_sgma_scores(), on="slug", how="left")
    df["sgma_score"] = df["sgma_score"].fillna(0.1)
    df["sgma_priority"] = df["sgma_priority"].fillna("None")
    df["sgma_critically_overdrafted"] = df["sgma_critically_overdrafted"].fillna(False)

    df["water_drought"] = df["drought"].fillna(df["drought"].median())
    df["water_arid"] = (_minmax(df["dry_spell"]) + _minmax(-df["precip_change"])) / 2.0

    wsum = w["sgma"] + w["drought"] + w["aridification"]
    df["W"] = (
        w["sgma"] * df["sgma_score"]
        + w["drought"] * df["water_drought"]
        + w["aridification"] * df["water_arid"]
    ).clip(0, 1) / (wsum if wsum else 1.0)
    df["W"] = df["W"].clip(0, 1)
    return df[["slug", "W", "water_drought", "water_arid", "sgma_score",
               "sgma_priority", "sgma_critically_overdrafted"]]
