# Methodology — A Climate-Adjusted "Probable Minimum" Statewide RHNA

## 1. Purpose and claim

California's Regional Housing Needs Allocation (RHNA) sets, for each region and
then each city/county, the number of housing units to plan for over a cycle.
HCD's determination is built from Dept. of Finance projections plus adjustments
for overcrowding, cost burden, vacancy, and existing replacement need. **It does
not consider climate change.** Housing that will be lost to wildfire, flood, and
sea-level rise, and population displaced by those hazards, does not enter the
formula.

This analysis layers climate exposure onto the **6th-cycle (2021–2029)** RHNA
baseline to estimate a *more probable minimum* statewide allocation, cascaded to
region and jurisdiction. It does two things at once:

- **Raises** the statewide total by the housing that must be **replaced** after
  climate-driven destruction (a floor that current RHNA omits entirely).
- **Redistributes** allocation away from high-hazard jurisdictions toward
  climate-resilient "receiver" areas (displacement + unsafe-siting discount).

> This is an analytical estimate to inform debate, **not** an official HCD
> determination. Parameters are chosen conservatively so the result reads as a
> defensible *floor*, presented with an uncertainty band.

## 2. Data

| Input | Source | Use |
|---|---|---|
| 6th-cycle RHNA allocation `B_j` | HCD "6th Cycle RHNA Progress Report" (data.ca.gov) | Baseline, per jurisdiction, 4 income categories |
| FEMA National Risk Index v1.20 (Dec 2025) | climateshed-cmip6-service | Tract building EAL ($) + hazard percentiles → replacement + exposure |
| CMIP6 5-model ensemble, SSP2-4.5 | climateshed-cmip6-service | Mid-century climate intensification multiplier |
| NOAA/Sweet et al. 2022 sea-level rise (OPC 2024) | climateshed-cmip6-service | Coastal exposure |
| Occupied housing + population (2024) | CA GHG Inventory / v2_jurisdictions | Stock at risk + capacity |

Full provenance in `data/external/PROVENANCE.md` and `data/raw/PROVENANCE.md`.
Jurisdictions join on 7-digit `PLACE_FIPS` (cities) / 5-digit `COUNTY_FIPS`
(unincorporated). Coverage: **539 / 539** analysis units (the phantom
"Unincorporated San Francisco County" is dropped — SF is a consolidated
city-county). Statewide baseline reconciles to **2,495,457 units**.

## 3. Hazard exposure index `E_j`

A build-value-weighted rollup of each jurisdiction's census tracts into four
components in [0,1], blended with configurable weights (`config/assumptions.yaml`
→ `exposure.weights`):

```
E_j = ( w_fire·fire + w_flood·flood + w_heat·heat + w_slr·slr ) / Σw
  fire  = NRI wildfire risk percentile (WFIR_RISKS/100)
  flood = max(inland, coastal) NRI flood percentile /100
  heat  = NRI heat-wave percentile (HWAV_RISKS/100)
  slr   = min(projected SLR cm at nearest gauge / slr_norm_cm, 1)  [coastal only]
```

Defaults weight fire 0.40 / flood 0.30 / heat 0.15 / slr 0.15. The index ranks
sensibly: Sierra-foothill fire+flood towns (Sutter Creek, Ione, Weed) score
highest; dense low-hazard LA-basin cities (Vernon, Bell) score lowest; Malibu,
Foster City, and Napa land high as expected.

## 4. The adjustment model (components A–D)

For each jurisdiction *j*, from baseline `B_j`:

### A. Replacement need `R_j` — raises the total
```
R_j = occ_housing_j · annual_loss_rate_j · horizon_years
annual_loss_rate_j = min( (WFIR_EALB+CFLD_EALB+IFLD_EALB) / BUILDVALUE
                          · climate_uplift_j , cap )
climate_uplift_j = 1 + max_uplift · normalized(CMIP6 SSP2-4.5 signals)
```
`annual_loss_rate` is a **real fractional building-loss rate** from FEMA NRI
building expected-annual-loss dollars over building value, scaled up by projected
mid-century intensification (dry-spell/heat → fire; extreme-precip → flood).
Statewide this is ≈0.17–0.22%/yr; over the 8-year horizon it adds replacement
need where destruction occurs.

### B. Out-displacement `D_j` — redistributes
```
D_j = population_j · displacement_fraction(E_j) / avg_household_size
displacement_fraction(E) = max_fraction · clip((E−min_exposure)/(1−min_exposure),0,1) ^ exponent
```
A convex, threshold-relative curve: **zero below `min_exposure` (0.5)**, rising
to `max_fraction` (10%) at E=1. Only the most-exposed places shed population.

### D. Siting discount `S_j` — redistributes
```
S_j = B_j · unsafe_share_j · move_fraction
```
`unsafe_share_j` = build-value-weighted share of the jurisdiction's tracts that
are very-high (≥90th pct) wildfire or flood hazard. Only `move_fraction` (50%)
of that share is actually moved (infill/retrofit keeps the rest) — conservative.

### C. Receiver capture — redistributes
The pool of units leaving hazardous places is captured by climate-resilient
jurisdictions:
```
removed_j  = min(S_j + D_j, B_j)          # can't remove more than allocated
pool       = Σ removed_j
w_j        = (1−E_j)^a · population_j^b   for eligible receivers (E_j < 0.5), else 0
received_j = pool · w_j / Σ w
```

### Result and conservation
```
B'_j = B_j − removed_j + received_j + R_j
```
The redistributed pool nets to zero (`Σ received = Σ removed`), so the statewide
total rises **only** by replacement need: `Σ B'_j = Σ B_j + Σ R_j`. This identity
is asserted at runtime and in the test suite.

## 5. Cascade

Jurisdictions roll up to region via a county→COG map (`src/regions.py`): the five
large MPOs from their member counties, every other county as its own COG. This
reproduces the published regional determinations — **SCAG, ABAG/MTC, SANDAG, and
AMBAG match exactly; SACOG within 0.19%** (a Tahoe-basin boundary rounding) —
which validates both the baseline join and the region map.

## 6. Results (central estimate)

| | Units |
|---|---|
| Baseline (HCD 6th cycle) | **2,495,457** |
| Climate-adjusted probable minimum | **2,719,039** |
| Increase (replacement need) | **+223,582  (+9.0%)** |
| Redistributed pool | 606,483 |

**Sensitivity band** (sweeping horizon 8/16/30 yr and displacement parameters):
adjusted total ranges **2.72M (+9.0%) to 3.33M (+33.6%)**. The central estimate
uses the conservative 8-year (single-cycle) horizon. Redistribution moves
allocation out of high-hazard Inland Empire jurisdictions (Unincorporated
Riverside, Ontario, Fontana, Irvine) into resilient high-capacity cores (Los
Angeles, San Francisco, Sacramento, Fresno). See `outputs/` and
`outputs/charts/`.

## 7. Key assumptions and limitations

- **All tunable parameters live in `config/assumptions.yaml`** and are chosen at
  the conservative end. Sensitivity (`src/sensitivity.py`) sweeps the three most
  uncertain (horizon, displacement fraction, displacement exponent).
- **Exposure uses national NRI percentiles**, so California (high inland-flood
  and wildfire nationally) skews high in absolute terms. This is appropriate for
  the *relative within-CA ranking* that drives redistribution; the displacement
  threshold (`min_exposure`) controls how much of that ranking translates into
  movement.
- **Displacement and receiver weighting are bottom-up but stylized.** Displaced
  households are re-housed by resilience × existing capacity (population as a
  jobs proxy); a few very small-baseline towns can receive large *percentage*
  (small absolute) increases. A per-jurisdiction receiver cap is a natural future
  refinement; it is omitted here to keep pool conservation exact.
- **Replacement is assigned in place.** Housing lost in *j* is counted as need in
  *j*; the model does not decide whether to rebuild elsewhere (that would be a
  managed-retreat extension).
- **External (out-of-state) climate in-migration is OFF by default** — the
  statewide increase is driven entirely by in-state replacement need. Enabling it
  (`external_migration`) adds an additive term distributed to receivers.
- **Not an official determination.** No income-category split of the adjustment,
  no legal/RHNA-methodology constraints (e.g. jobs-housing fit, equity
  adjustments) are modeled.

## 8. Reproduce

```bash
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m src.source_rhna     # normalize HCD baseline -> FIPS
./.venv/bin/python -m src.allocate        # full pipeline -> outputs/ + charts
./.venv/bin/python -m src.sensitivity     # uncertainty band -> outputs/sensitivity.csv
./.venv/bin/python -m pytest -q           # invariants
```
