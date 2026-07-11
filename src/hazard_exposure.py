"""Per-jurisdiction climate hazard exposure.

Produces, for each jurisdiction:
  * hazard component scores (fire / flood / heat / slr), each in [0,1]
  * the composite exposure index E_j in [0,1]
  * `loss_rate_hist` — historical annual building-loss rate from NRI building
    expected-annual-loss (EAL) dollars / building value
  * `climate_uplift` — CMIP6 SSP2-4.5 mid-century multiplier on that rate
  * `annual_loss_rate` = loss_rate_hist * climate_uplift (capped)
  * `unsafe_share` — build-value-weighted share of tracts that are very-high
    wildfire/flood hazard (feeds the siting-discount component D)

All parameters come from config/assumptions.yaml.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from . import paths
from .config import load_assumptions

# ---------------------------------------------------------------------------
# NRI tract rollup
# ---------------------------------------------------------------------------
_HAZ_RISKS = ["WFIR_RISKS", "CFLD_RISKS", "IFLD_RISKS", "HWAV_RISKS"]
_HAZ_EALB = ["WFIR_EALB", "CFLD_EALB", "IFLD_EALB"]


def _load_nri() -> pd.DataFrame:
    df = pd.read_csv(paths.NRI_CA_TRACTS, dtype={"TRACTFIPS": str})
    df["TRACTFIPS"] = df["TRACTFIPS"].str.zfill(11)
    # Coastal flood is null for inland tracts -> 0 exposure there.
    for c in ["CFLD_RISKS", "CFLD_EALB", "WFIR_EALB", "IFLD_EALB"]:
        df[c] = df[c].fillna(0.0)
    df["BUILDVALUE"] = df["BUILDVALUE"].fillna(0.0)
    return df.set_index("TRACTFIPS")


def rollup_nri(spine: pd.DataFrame) -> pd.DataFrame:
    """Build-value-weighted NRI rollup per jurisdiction from its tract list."""
    nri = _load_nri()
    cfg = load_assumptions()
    thr = cfg["siting"]["unsafe_percentile"] * 100.0

    out = []
    for _, row in spine.iterrows():
        tracts = [t.zfill(11) for t in row["tract_fips"]]
        sub = nri.reindex(tracts).dropna(how="all")
        if len(sub) == 0 or sub["BUILDVALUE"].sum() <= 0:
            out.append(
                {"slug": row["slug"], "fire": np.nan, "flood": np.nan,
                 "heat": np.nan, "loss_rate_hist": np.nan, "unsafe_share": np.nan,
                 "buildvalue": float(sub["BUILDVALUE"].sum()) if len(sub) else 0.0}
            )
            continue
        bv = sub["BUILDVALUE"].to_numpy()
        w = bv / bv.sum()
        fire = float((sub["WFIR_RISKS"].to_numpy() * w).sum()) / 100.0
        flood_raw = np.maximum(sub["IFLD_RISKS"].to_numpy(), sub["CFLD_RISKS"].to_numpy())
        flood = float((flood_raw * w).sum()) / 100.0
        heat = float((sub["HWAV_RISKS"].to_numpy() * w).sum()) / 100.0
        eal = sub[_HAZ_EALB].sum(axis=1).to_numpy()
        loss_rate_hist = float(eal.sum() / bv.sum())
        unsafe = (sub["WFIR_RISKS"].to_numpy() >= thr) | (flood_raw >= thr)
        unsafe_share = float((unsafe * w).sum())
        out.append(
            {"slug": row["slug"], "fire": fire, "flood": flood, "heat": heat,
             "loss_rate_hist": loss_rate_hist, "unsafe_share": unsafe_share,
             "buildvalue": float(bv.sum())}
        )
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# CMIP6 SSP2-4.5 mid-century signals
# ---------------------------------------------------------------------------
def cmip6_signals(spine: pd.DataFrame) -> pd.DataFrame:
    """Raw ensemble-median CMIP6 values per jurisdiction for the configured
    scenario/decade. Missing jurisdictions get NaN (filled later)."""
    cfg = load_assumptions()["scenario"]
    ssp, decade = cfg["ssp"], cfg["decade"]
    clim = json.loads(paths.CA_CLIMATE.read_text())["jurisdictions"]
    rows = []
    for slug in spine["slug"]:
        rec = clim.get(slug)
        vals = {"slug": slug, "tasmax": np.nan, "dry_spell": np.nan, "precip": np.nan}
        if rec:
            block = rec.get("scenarios", {}).get(ssp, {}).get(decade, {})
            if block:
                vals["tasmax"] = block.get("tasmax_peak_f", {}).get("median", np.nan)
                vals["dry_spell"] = block.get("max_dry_spell", {}).get("median", np.nan)
                vals["precip"] = block.get("extreme_precip_days", {}).get("median", np.nan)
        rows.append(vals)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Sea-level rise signal (coastal jurisdictions)
# ---------------------------------------------------------------------------
def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def slr_signal(spine: pd.DataFrame) -> pd.DataFrame:
    cfg = load_assumptions()["exposure"]
    scenario, year, coastal_km = cfg["slr_scenario"], cfg["slr_year"], cfg["coastal_km"]
    pts = json.loads(paths.CA_SLR.read_text())["points"]
    rows = []
    for _, row in spine.iterrows():
        lat, lon = row["centroid_lat"], row["centroid_lon"]
        best_d, best_cm = float("inf"), 0.0
        if lat is not None and lon is not None and not pd.isna(lat):
            for p in pts:
                d = _haversine_km(lat, lon, p["lat"], p["lon"])
                if d < best_d:
                    best_d = d
                    best_cm = p["scenarios"][scenario][year]
        coastal = best_d <= coastal_km
        rows.append({"slug": row["slug"], "slr_cm": best_cm if coastal else 0.0,
                     "coastal": coastal, "slr_dist_km": None if math.isinf(best_d) else best_d})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Compose exposure index + annual loss rate
# ---------------------------------------------------------------------------
def _minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    lo, hi = s.min(), s.max()
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return pd.Series(0.0, index=s.index)
    return (s - lo) / (hi - lo)


def build_exposure(spine: pd.DataFrame) -> pd.DataFrame:
    """Merge NRI + CMIP6 + SLR and compute E_j, climate_uplift, annual_loss_rate."""
    cfg = load_assumptions()
    ex = cfg["exposure"]
    rep = cfg["replacement"]

    df = (
        spine[["slug", "name", "juris_type", "county"]]
        .merge(rollup_nri(spine), on="slug", how="left")
        .merge(cmip6_signals(spine), on="slug", how="left")
        .merge(slr_signal(spine), on="slug", how="left")
    )

    # Fill missing hazard components with statewide medians (rare fallbacks).
    for c in ["fire", "flood", "heat", "loss_rate_hist", "unsafe_share"]:
        df[c] = df[c].fillna(df[c].median())

    # Normalize the SLR magnitude onto [0,1].
    df["slr"] = (df["slr_cm"] / ex["slr_norm_cm"]).clip(0, 1)

    # Composite exposure index E_j.
    w = ex["weights"]
    wsum = sum(w.values())
    df["E"] = (
        w["fire"] * df["fire"] + w["flood"] * df["flood"]
        + w["heat"] * df["heat"] + w["slr"] * df["slr"]
    ) / wsum
    df["E"] = df["E"].clip(0, 1)

    # CMIP6 climate-intensification signals, min-max normalized statewide.
    fire_sig = (_minmax(df["tasmax"]) + _minmax(df["dry_spell"])) / 2.0
    flood_sig = _minmax(df["precip"])
    up = rep["climate_uplift"]
    signal = (up["fire_signal_weight"] * fire_sig + up["flood_signal_weight"] * flood_sig)
    signal = signal / (up["fire_signal_weight"] + up["flood_signal_weight"])
    df["climate_uplift"] = 1.0 + up["max_uplift"] * signal
    # Jurisdictions missing CMIP6 data get no amplification (conservative).
    df["climate_uplift"] = df["climate_uplift"].fillna(1.0)

    # Annual loss rate = historical NRI rate * CMIP6 uplift, capped.
    df["annual_loss_rate"] = (
        df["loss_rate_hist"] * rep["eal_to_unit_loss_factor"] * df["climate_uplift"]
    ).clip(upper=rep["max_annual_loss_rate"])
    df["annual_loss_rate"] = df["annual_loss_rate"].fillna(0.0)

    return df
