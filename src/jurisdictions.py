"""Canonical jurisdiction spine.

The analysis grain is the 540 RHNA-planning units: 482 incorporated cities +
58 unincorporated county remainders. We take these from climateshed's
ca_jurisdictions.json (which also carries tract lists, FIPS, and centroids we
need downstream) and DELIBERATELY EXCLUDE its 58 whole-`county` rows, which
have no counterpart in the RHNA/housing data (those carry only the
unincorporated remainder).
"""
from __future__ import annotations

import json

import pandas as pd

from . import paths

# juris_type values kept as analysis units (drop whole-county rollups)
ANALYSIS_TYPES = {"city", "unincorporated"}


def load_jurisdictions() -> pd.DataFrame:
    """Return one row per analysis jurisdiction with identity + geography.

    Columns: slug, name, juris_type, county, county_fips, place_fips,
    population_cs (climateshed's population, a fallback), centroid_lat,
    centroid_lon, tract_fips (list[str]).
    """
    raw = json.loads(paths.CA_JURISDICTIONS.read_text())
    rows = []
    for slug, r in raw["jurisdictions"].items():
        if r["juris_type"] not in ANALYSIS_TYPES:
            continue
        lat, lon = (r.get("centroid") or [None, None])
        rows.append(
            {
                "slug": slug,
                "name": r["name"],
                "juris_type": r["juris_type"],
                "county": r.get("county"),
                "county_fips": str(r.get("county_fips") or "").zfill(5),
                "place_fips": _norm_place_fips(r.get("place_fips"), r["juris_type"]),
                "population_cs": r.get("population"),
                "centroid_lat": lat,
                "centroid_lon": lon,
                "tract_fips": [str(t) for t in (r.get("tract_fips") or [])],
            }
        )
    df = pd.DataFrame(rows)
    return df


def _norm_place_fips(place_fips, juris_type: str) -> str | None:
    """7-digit place FIPS for cities; None for unincorporated (joined on county
    FIPS instead)."""
    if juris_type != "city" or place_fips in (None, ""):
        return None
    return str(place_fips).zfill(7)
