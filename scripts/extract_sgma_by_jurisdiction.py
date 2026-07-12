"""Assign each jurisdiction its SGMA groundwater basin by REUSING climateshed's
own basin lookup (casgem_basins.query_point) rather than re-deriving a spatial
join here. Run with a Python that has shapely (system python3):

    python3 scripts/extract_sgma_by_jurisdiction.py

Writes data/external/sgma_by_jurisdiction.csv. Point-in-basin uses each
jurisdiction's centroid (single-point proxy, consistent with the SLR lookup).
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIMATESHED = Path("/Users/neilmatouka/Developer/climateshed-cmip6-service")
sys.path.insert(0, str(CLIMATESHED))

import casgem_basins  # noqa: E402  (climateshed module; uses its own ca_gw_basins.json.gz)

casgem_basins._load()
assert casgem_basins.is_loaded(), "climateshed basin data failed to load"

juris = json.loads((ROOT / "data/external/ca_jurisdictions.json").read_text())["jurisdictions"]
ANALYSIS = {"city", "unincorporated"}

rows = []
for slug, r in juris.items():
    if r["juris_type"] not in ANALYSIS:
        continue
    lat, lon = (r.get("centroid") or [None, None])
    b = casgem_basins.query_point(lat, lon) if lat is not None else None
    rows.append({
        "slug": slug,
        "sgma_basin": (b or {}).get("basin_name", ""),
        "sgma_priority": (b or {}).get("priority", "None"),  # High/Medium/Low/Very Low/None
        "sgma_critically_overdrafted": bool((b or {}).get("critically_overdrafted", False)),
        "hydrologic_region": (b or {}).get("hydrologic_region", ""),
    })

out = ROOT / "data/external/sgma_by_jurisdiction.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

n_basin = sum(1 for r in rows if r["sgma_priority"] != "None")
n_co = sum(1 for r in rows if r["sgma_critically_overdrafted"])
print(f"wrote {out} — {len(rows)} jurisdictions; {n_basin} over a mapped basin; "
      f"{n_co} over a critically-overdrafted basin")
