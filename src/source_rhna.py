"""Normalize HCD's 6th-cycle RHNA Progress Report into the baseline the
crosswalk expects: one row per jurisdiction keyed to PLACE_FIPS (cities) /
COUNTY_FIPS (unincorporated), with `rhna_baseline` = sum of the four income
categories.

HCD names are UPPERCASE and use "X COUNTY" for the unincorporated remainder.
We resolve names to FIPS via the GHG jurisdiction table (mixed-case name +
FIPS), with an alias map for the handful of punctuation/accent variants.

Run:  python -m src.source_rhna
"""
from __future__ import annotations

import pandas as pd

from . import paths

RHNA_COLS = ["RHNA VLI", "RHNA LI", "RHNA MOD", "RHNA ABOVE MOD"]

# HCD uppercase name -> GHG canonical JURISDICTION string (for the 8 variants
# that don't match on a simple uppercase compare).
CITY_ALIASES = {
    "AMADOR": "Amador City",
    "ANGELS CAMP": "Angels",
    "CATHEDRAL": "Cathedral City",
    "LA CANADA FLINTRIDGE": "La Cañada Flintridge",
    "PASO ROBLES": "El Paso de Robles (Paso Robles)",
    "SAINT HELENA": "St. Helena",
    "VENTURA": "San Buenaventura (Ventura)",
    "CARMEL": "Carmel-by-the-Sea",
}


def build_baseline(verbose: bool = True) -> pd.DataFrame:
    hcd = pd.read_csv(paths.RAW / "rhna_progress_6.csv")
    hcd["rhna_baseline"] = hcd[RHNA_COLS].sum(axis=1)
    hcd["U"] = hcd["Jurisdiction"].str.upper().str.strip()

    ghg = pd.read_csv(
        paths.GHG_JURISDICTION_TABLE, dtype={"PLACE_FIPS": str, "COUNTY_FIPS": str}
    )
    ghg["U"] = ghg["JURISDICTION"].str.upper().str.strip()
    by_name = ghg.set_index("U")

    rows = []
    unmatched = []
    for _, r in hcd.iterrows():
        u = r["U"]
        is_county = u.endswith("COUNTY")
        key = None
        if is_county:
            key = "UNINCORPORATED " + u          # HCD "YOLO COUNTY" -> GHG uninc
        elif u in CITY_ALIASES:
            key = CITY_ALIASES[u].upper()
        else:
            key = u
        if key in by_name.index:
            g = by_name.loc[key]
            rows.append({
                "PLACE_FIPS": None if is_county else g["PLACE_FIPS"],
                "COUNTY_FIPS": g["COUNTY_FIPS"],
                "rhna_baseline": r["rhna_baseline"],
                "hcd_name": r["Jurisdiction"],
                "juris_type": "unincorporated" if is_county else "city",
            })
        else:
            unmatched.append(r["Jurisdiction"])

    out = pd.DataFrame(rows)
    if verbose:
        print(f"[source_rhna] {len(out)}/{len(hcd)} HCD rows matched to FIPS")
        print(f"[source_rhna] statewide baseline: {out['rhna_baseline'].sum():,.0f}")
        if unmatched:
            print(f"[source_rhna] UNMATCHED ({len(unmatched)}):", unmatched)
    return out


def main() -> None:
    out = build_baseline(verbose=True)
    dest = paths.RHNA_BASELINE
    out.to_csv(dest, index=False)
    print(f"[write] {dest} ({len(out)} rows)")


if __name__ == "__main__":
    main()
