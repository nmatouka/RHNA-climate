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
./.venv/bin/python -m src.sensitivity   # uncertainty bands
./.venv/bin/python -m pytest -q         # invariants (20 tests)
```

## Headline result

**6th cycle — two models (base, and base + compound):**

| | Units |
|---|---|
| Baseline (HCD 6th cycle) | 2,495,457 |
| **BASE** model (hazards independent) | **2,719,039  (+9.0%)** |
| **COMPOUND** model (option 2, stranding) | **2,701,968  (+8.3%)** |
| Base sensitivity band (8–30 yr horizon) | 2.72M – 3.33M |
| Compound stranded band (uncertain) | 5.7k – 40k units |

The **compound** model is shown *alongside* the base, not merged into it:
stacked-hazard places (Inland Empire/Coachella) shed capacity that can't all be
rehoused in safe areas, so some is **stranded** and the total falls below the base
— a transparent scenario for an effect we're genuinely uncertain about.

**Longer horizon (cumulative need to 2100, SSP2-4.5, county-resolved DOF baseline):**

| | Units |
|---|---|
| Baseline (climate-blind) | ~11.8M |
| Climate-adjusted minimum | **~14.3M  (+20%)** |
| Climate share of need | rises **14% (2030s) → 27% (2090s)** |

County-resolved DOF growth moves cumulative need **out of SCAG (−10 pp)** into
Sacramento (SACOG +3.8 pp), the Bay Area, and the Central Valley — a shift the
uniform taper misses. See `outputs/trajectory_region_compare.csv`.

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
