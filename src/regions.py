"""Map each jurisdiction to its RHNA region (COG/MPO) by county.

The 5 large MPOs are mapped from their member counties (well established). Every
other county is treated as its own region (most non-MPO COGs are single-county:
Fresno COG, Kern COG, Butte CAG, Shasta, Stanislaus, etc.). This reproduces the
published regional determinations closely (validated in tests / allocate.py).
"""
from __future__ import annotations

# county name (as in the data) -> MPO region label
_MPO_COUNTIES = {
    # ABAG/MTC — Bay Area (9)
    **{c: "ABAG/MTC" for c in [
        "Alameda", "Contra Costa", "Marin", "Napa", "San Francisco",
        "San Mateo", "Santa Clara", "Solano", "Sonoma"]},
    # SACOG — Sacramento region (6)
    **{c: "SACOG" for c in [
        "Sacramento", "Sutter", "Yolo", "Yuba", "El Dorado", "Placer"]},
    # SANDAG — San Diego (1)
    "San Diego": "SANDAG",
    # AMBAG — Monterey Bay (2 for RHNA; San Benito is its own COG, SBtCOG)
    **{c: "AMBAG" for c in ["Monterey", "Santa Cruz"]},
    # SCAG — Southern California (6)
    **{c: "SCAG" for c in [
        "Los Angeles", "Orange", "Riverside", "San Bernardino",
        "Ventura", "Imperial"]},
}


def region_for_county(county: str) -> str:
    """Return the MPO label, or '<County> County' for non-MPO counties."""
    if county in _MPO_COUNTIES:
        return _MPO_COUNTIES[county]
    return f"{county} County"


def assign_regions(df):
    out = df.copy()
    out["region"] = out["county"].map(region_for_county)
    return out
