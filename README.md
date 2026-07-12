# RHNA-Climate

A climate-adjusted **"probable minimum"** for California's statewide Regional
Housing Needs Allocation (RHNA).

## Why

California's RHNA determines how many housing units each region — then each
city/county — must plan for. HCD's determination is built from Dept. of Finance
projections plus adjustments for overcrowding, cost burden, vacancy, and
replacement need. **None of these inputs account for climate change** — housing
lost to wildfire/flood/sea-level rise, or population displaced by future climate
hazards, is invisible to the formula.

This project layers climate exposure onto the **6th-cycle (2021–2029)** RHNA
baseline to produce a more probable *minimum* statewide allocation, cascaded to
region (COG/MPO) and jurisdiction. The adjustment both **raises** the total
(disaster replacement need) and **redistributes** it away from high-hazard
jurisdictions toward climate-resilient receiver areas. Displacement is modeled
**bottom-up from California hazard exposure** under **SSP2-4.5** using CMIP6
decadal projections.

> This is an analytical estimate, **not** an official HCD determination.

## Model (see `docs/methodology.md` for full formulas)

For each jurisdiction *j*, starting from baseline RHNA `B_j`:

| Component | Effect | Source |
|---|---|---|
| **A. Replacement** `R_j` | raises total | FEMA NRI building EAL (fire/flood) × CMIP6 uplift × horizon |
| **B. Out-displacement** `D_j` | redistributes | exposure index `E_j` → displaced households |
| **C. Receiver capture** | redistributes | pool `ΣD_j` → resilient jurisdictions |
| **D. Siting discount** `S_j` | redistributes | unsafe-tract share of `B_j` moved out |

`B'_j = B_j − S_j − D_j + received + R_j`

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
./.venv/bin/python -m src.trajectory    # decadal need to 2100 -> outputs/trajectory_*
./.venv/bin/python -m src.sensitivity   # uncertainty bands
./.venv/bin/python -m pytest -q         # invariants (12 tests)
```

## Headline result

**6th cycle (single adjustment):**

| | Units |
|---|---|
| Baseline (HCD 6th cycle) | 2,495,457 |
| Climate-adjusted **probable minimum** | **2,719,039  (+9.0%)** |
| Sensitivity band (8–30 yr horizon) | 2.72M – 3.33M |

**Longer horizon (cumulative need to 2100, SSP2-4.5):**

| | Units |
|---|---|
| Baseline (climate-blind) | ~14.0M |
| Climate-adjusted minimum | **~16.5M  (+18%)** |
| Climate share of need | rises **11% (2030s) → 30% (2090s)** |

Full write-up and caveats in [`docs/methodology.md`](docs/methodology.md);
planned extensions in [`docs/FUTURE_WORK.md`](docs/FUTURE_WORK.md).

## Status

Complete and reproducible end-to-end. Baseline reconciles to the known ~2.5M
statewide total; regional rollup matches published MPO determinations (SCAG,
ABAG/MTC, SANDAG, AMBAG exact). Both the single 6th-cycle adjustment and the
longer-horizon decadal trajectory to 2100 are implemented. External out-of-state
in-migration term is available but off by default (see `docs/FUTURE_WORK.md`).
