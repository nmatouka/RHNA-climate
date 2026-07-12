"""Roll up Census LACE air-conditioning access to the jurisdiction level, reusing
climateshed's tract-level LACE data (housing-unit-weighted). Run with the venv:

    ./.venv/bin/python scripts/extract_ac_access_by_jurisdiction.py

Writes data/external/ac_access_by_jurisdiction.csv (pct_without_ac per slug).
No geospatial join — uses each jurisdiction's tract list.
"""
import csv
import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LACE = Path("/Users/neilmatouka/Developer/climateshed-cmip6-service/ca_census_lace.csv.gz")

with gzip.open(LACE, "rt") as f:
    lace = pd.read_csv(f, dtype={"TRACTFIPS": str})
lace["TRACTFIPS"] = lace["TRACTFIPS"].str.zfill(11)
lace = lace.set_index("TRACTFIPS")

juris = json.loads((ROOT / "data/external/ca_jurisdictions.json").read_text())["jurisdictions"]
ANALYSIS = {"city", "unincorporated"}

rows = []
for slug, r in juris.items():
    if r["juris_type"] not in ANALYSIS:
        continue
    tracts = [str(t).zfill(11) for t in (r.get("tract_fips") or [])]
    sub = lace.reindex(tracts).dropna(subset=["PCT_WITHOUT_AC"])
    sub = sub[sub["PCT_WITHOUT_AC"] >= 0]  # guard census sentinels
    if len(sub) and sub["HOUSING_UNITS"].sum() > 0:
        w = sub["HOUSING_UNITS"].to_numpy()
        pct = float((sub["PCT_WITHOUT_AC"].to_numpy() * (w / w.sum())).sum())
    else:
        pct = float("nan")
    rows.append({"slug": slug, "pct_without_ac": round(pct, 3) if pct == pct else ""})

out = ROOT / "data/external/ac_access_by_jurisdiction.csv"
with open(out, "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=["slug", "pct_without_ac"])
    wr.writeheader()
    wr.writerows(rows)
n = sum(1 for r in rows if r["pct_without_ac"] != "")
print(f"wrote {out} — {len(rows)} jurisdictions ({n} with AC data)")
