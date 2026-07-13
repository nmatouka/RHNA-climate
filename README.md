# RHNA-Climate

A climate-adjusted **"probable minimum"** for California's statewide Regional
Housing Needs Allocation (RHNA).

## Why

California's RHNA sets how many housing units each region, and then each city and
county, has to plan for. HCD builds that number from Department of Finance
projections plus adjustments for overcrowding, cost burden, vacancy, and
replacement need. **None of those inputs account for climate change.** The homes
wildfire, flood, and sea-level rise will destroy, and the households those hazards
displace, never enter the formula.

This project layers climate exposure onto the **6th-cycle (2021–2029)** RHNA
baseline to produce a more probable *minimum* statewide allocation, cascaded to
region (COG/MPO) and jurisdiction. The adjustment does two things. It **raises**
the total by disaster replacement need, and it **redistributes** allocation away
from high-hazard jurisdictions toward climate-resilient receiver areas.
Displacement is modeled bottom-up from California hazard exposure under
**SSP2-4.5**, using **LOCA2**-downscaled CMIP6 decadal projections (Scripps/UCSD,
5-GCM ensemble, from the Cal-Adapt Analytics Engine `cadcat` catalog on the 3-km
`d03` grid). See [`data/external/PROVENANCE.md`](data/external/PROVENANCE.md) for
the full climate-data lineage.

> This is an analytical estimate, not an official HCD determination.

## Model (see `docs/methodology.md` for full formulas)

For each jurisdiction *j*, starting from baseline RHNA `B_j`:

| Component | Effect | Source |
|---|---|---|
| **A. Replacement** `R_j` | raises total | FEMA NRI building EAL (fire/flood) × LOCA2 CMIP6 uplift × horizon |
| **B. Out-displacement** `D_j` | redistributes | exposure index `E_j` → displaced households |
| **C. Receiver capture** | redistributes | pool → resilient, water-secure jurisdictions |
| **D. Siting discount** `S_j` | redistributes | unsafe (fire/flood) tract share of `B_j` moved out |
| **E. Water-siting** `Sw_j` | redistributes | water-constrained (SGMA overdraft/drought) share moved out |

`B'_j = B_j − S_j − D_j − Sw_j + received + R_j`  (water is purely redistributive)

All tunable parameters live in [`config/assumptions.yaml`](config/assumptions.yaml).

## Layout

```
config/assumptions.yaml   all tunable parameters + scenario/horizon
data/external/            vendored snapshots of climate + housing data (see PROVENANCE.md)
data/raw/                 sourced RHNA baseline (6th cycle) + DOF projections
data/processed/           joined master jurisdiction table (generated)
src/                      pipeline modules (allocate = 6th cycle; trajectory = to 2100)
outputs/                  allocation + trajectory CSVs (statewide/region/jurisdiction) + charts
docs/methodology.md       full write-up (§7 = longer-horizon trajectory)
```

## Run

```bash
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m src.source_rhna   # normalize HCD baseline -> FIPS
./.venv/bin/python -m src.allocate      # 6th-cycle pipeline -> outputs/ + charts
./.venv/bin/python -m src.trajectory    # decadal need to 2100 (county DOF baseline)
./.venv/bin/python -m src.constraints   # compound climate-constraint view
./.venv/bin/python -m src.sensitivity   # uncertainty bands + tornado
./.venv/bin/python -m pytest -q         # invariants (23 tests)
```

**Results write-up with figures and citations:** [`docs/index.html`](docs/index.html)
(published via GitHub Pages). Full methodology: [`docs/methodology.md`](docs/methodology.md).

## Headline result

**6th cycle, two models (base, and base + compound):**

| | Units |
|---|---|
| Baseline (HCD 6th cycle) | 2,495,457 |
| **BASE** model (hazards independent) | **2,719,039  (+9.0%)** |
| **COMPOUND** model (option 2, stranding) | **2,711,041  (+8.6%)** |
| Base sensitivity band (8–30 yr horizon) | 2.72M – 3.33M |
| Compound stranded band (uncertain) | 2.7k – 20k units |

The **compound** model runs alongside the base, not merged into it. Stacked-hazard
places (Inland Empire/Coachella) shed capacity that can't all be rehoused in safe
areas, so some of it is **stranded** and the total lands below the base. Whether
hazards compound this way is uncertain, so it stays a separate scenario.

> **Two confidence levels.** The **statewide total** (+9%, replacement) is the
> solid number. It rests on FEMA NRI building-loss rates, the HCD baseline, and
> CMIP6, and the tornado in `docs/methodology.md §9` shows no redistribution
> parameter moves it. The **geography**, meaning who loses and who receives the
> ~626k redistributed units, rides on author-judgment parameters (blend weights and
> exponents, tagged in §2a). Read it as directional, not a forecast of exact
> per-jurisdiction counts.

**Longer horizon (cumulative need to 2100, SSP2-4.5, county-resolved DOF baseline):**

| | Units |
|---|---|
| Baseline (climate-blind) | ~11.8M |
| Climate-adjusted minimum | **~14.3M  (+20%)** |
| Climate share of need | rises **14% (2030s) → 27% (2090s)** |

County-resolved DOF growth moves cumulative need **out of SCAG (−10 pp)** into
Sacramento (SACOG +3.8 pp), the Bay Area, and the Central Valley. The uniform taper
misses this shift. See `outputs/trajectory_region_compare.csv`.

**Compound climate constraints (each hazard counted once):**

| | Share of 6th-cycle RHNA |
|---|---|
| ≥1 high climate constraint (fire/flood/SLR/water/heat) | **39%** |
| ≥2 stacked | 7% |
| Epicenter of stacking | **Inland Empire + Coachella Valley** |

Full write-up and caveats in [`docs/methodology.md`](docs/methodology.md);
planned extensions in [`docs/FUTURE_WORK.md`](docs/FUTURE_WORK.md).

## Status

Complete and reproducible end-to-end. Baseline reconciles to the known ~2.5M
statewide total; regional rollup matches published MPO determinations (SCAG,
ABAG/MTC, SANDAG, AMBAG exact). Both the single 6th-cycle adjustment and the
longer-horizon decadal trajectory to 2100 are implemented, the latter with a
**county-resolved baseline from real DOF household/population projections**.
External out-of-state in-migration term is available but off by default (see
`docs/FUTURE_WORK.md`).
