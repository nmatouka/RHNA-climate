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

### E. Water-siting discount `Sw_j` — redistributes (supply-side)
Water constrains *where* housing can be built, not how much is needed, so it acts
like a supply-driven siting discount:
```
Sw_j = B_j · max_move · clip((W_j − 0.55)/(1−0.55), 0, 1) ^ 1.5
```
`W_j` (0 = secure → 1 = constrained) is a renormalized blend of **SGMA basin
priority/critical-overdraft** (40%), **NRI drought risk** (35%), and **CMIP6
aridification** (25%) — built entirely from existing data (`src/water.py`),
with the SGMA basin assignment produced by reusing climateshed's own
`casgem_basins` lookup (`scripts/extract_sgma_by_jurisdiction.py`). Only stress
above 0.55 is discounted; `max_move` (25%) caps it.

### C. Receiver capture — redistributes
The pool of units leaving hazardous / water-constrained places is captured by
climate-resilient, water-secure jurisdictions:
```
removed_j  = min(S_j + D_j + Sw_j, B_j)   # can't remove more than allocated
pool       = Σ removed_j
w_j        = (1−E_j)^a · population_j^b · (1−W_j)^c   for eligible receivers, else 0
received_j = pool · w_j / Σ w
```
The water-headroom exponent `c` is kept **modest (0.5)** — see the imported-supply
limitation in §9.

### Result and conservation
```
B'_j = B_j − removed_j + received_j + R_j
```
The redistributed pool nets to zero (`Σ received = Σ removed`), so the statewide
total rises **only** by replacement need: `Σ B'_j = Σ B_j + Σ R_j`. Water is purely
redistributive — it leaves the statewide total unchanged. This identity is
asserted at runtime and in the test suite.

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

## 7. Longer-horizon trajectory (beyond the 6th cycle)

Sections 1–6 adjust the single 6th-cycle allocation. `src/trajectory.py` extends
this to a **decade-by-decade projection of statewide housing need to 2100**,
answering "what might future cycles need once climate is included?"

For each decade *d* ∈ {2030s … 2090s} (each ≈ one 8–10 yr planning cycle):

1. **Growing baseline, resolved by county.** `baseline_need_j,d = B_j ×
   growth_mult_county(j),d`. The default multiplier is **county-resolved from real
   DOF projections** (`src/dof_projections.py`, `growth_source: county`): DOF P-4
   household projections (2010–2040) plus P-2A population (2020–2070, converted to
   households via a declining household-size trajectory) give each county its own
   household-growth path. The multiplier is two-part —
   `need_growth_share × (HH_growth_d / HH_growth_2020s) + (1 − need_growth_share)`
   — so only the ~65% growth share of an allocation responds to demographics while
   the existing-deficit share persists (need never collapses); bounded to
   [0.25, 2.0]. A **uniform statewide taper** (`baseline_growth_mult`, 2030s = 1.0
   → 0.60) is retained for comparison and sensitivity. Rationale: DOF projects
   California to **plateau in the mid-2040s then slowly decline**, with growth
   concentrating **inland** (Central Valley, Sacramento) while coastal metros
   (esp. Los Angeles) taper — a geography the uniform curve cannot see.
2. **Time-varying climate.** Exposure, the CMIP6 uplift, and sea-level rise are
   recomputed for decade *d* (`build_exposure_for_decade`). CMIP6 signals are
   normalized against **bounds pooled across all decades** so intensification
   rises monotonically over time instead of being re-centred each decade; SLR uses
   the end-of-decade year. NRI hazard *geography* is static (it sets where risk
   is); climate supplies the *intensification* over time.
3. **Adjustment.** The same components A–D (`apply_model`, 10-yr replacement
   horizon) produce `adjusted_need_j,d`, with exact per-decade pool conservation.
4. **Stock growth.** The housing stock — which drives future replacement — grows
   by only the net-new share (`stock_growth_fraction ≈ 0.65`) of each decade's
   baseline need; the remainder addresses the *existing* deficit and adds no
   physical units.

Results accumulate into a cumulative-need trajectory. **Central case (SSP2-4.5,
county-resolved baseline):**

| Cumulative need to 2100 | County (DOF) | Uniform taper |
|---|---|---|
| Baseline (climate-blind) | **~11.8M** | ~14.0M |
| Climate-adjusted minimum | **~14.3M** | ~16.5M |
| Climate-driven addition | **+2.4M (+20%)** | +2.5M (+18%) |

Two things change when the real county DOF baseline replaces the uniform taper.
(a) **Magnitude falls ~13%** — DOF's actual projected household growth is lower
than the earlier hand-set curve; the 2030s baseline lands at 0.77× the 6th cycle,
matching how real 7th-cycle determinations have come in below the 6th. (b) **The
regional mix shifts materially**: county resolution moves cumulative need share
**out of SCAG (−10 pp: 54% → 44%)** — slow-growing coastal Southern California —
and **into SACOG (+3.8 pp), the Bay Area, and the Central Valley** (San Joaquin,
Stanislaus, Merced). The uniform taper froze every region at its 6th-cycle share
and missed this entirely. See `outputs/trajectory_region_compare.csv` and
`charts/trajectory_region_shift.png`.

The signature finding is temporal: the climate-driven **share** of housing need
rises from ~14% (2030s) to ~27% (2090s) — as demographic growth tapers, climate
replacement and sea-level displacement become an ever-larger fraction of why
California must build. Routing growth into higher-exposure inland counties makes
this share **larger** than under the uniform baseline (20.4% vs 18.2% cumulative).
The cumulative climate addition is robust (~2.4M–2.6M) across county/flat/decline
growth paths (`trajectory_sweep`), because it is
driven by housing stock and hazard, not the demographic path. Outputs:
`outputs/trajectory_statewide.csv`, `outputs/trajectory_region.csv`, and
`outputs/charts/trajectory_*.png`.

**Added limitations for the trajectory:** the baseline is county-resolved but not
finer — within a county, city vs. unincorporated growth still rides the 6th-cycle
shares. DOF ends at 2070, so 2070s–2090s hold the 2060s multiplier, and post-2040
households are inferred from population via a declining household-size trajectory.
Each decade is an independent planning cycle (no explicit inter-cycle carryover of
unmet need), and compounding uncertainty makes late-century decades more
illustrative than predictive. It shows the *shape and direction* of climate-driven
need, not a point forecast for 2090.

## 8. Compound climate-constraint view

Components A–E adjust *how much / where* to build. `src/constraints.py` is a
separate **reporting layer** that asks a different question: *what share of RHNA
sits somewhere genuinely hard to build, and where do hazards stack?* It flags
five **distinct** hazard axes, each counted **once** — so nothing is
double-counted:

| Axis | Source | "Constrained" cutoff |
|---|---|---|
| fire | NRI wildfire (exposure sub-score) | ≥90th pct |
| flood | NRI inland/coastal flood | ≥90th pct |
| slr | sea-level-rise exposure | ≥0.40 |
| water | `W_j` (SGMA + drought + aridification) | ≥0.55 |
| heat | `H_j` heat-habitability | ≥0.55 |

**Avoiding double-counting.** The acute NRI heat-wave term (`hwav`) already lives
in the exposure index `E_j`, so heat enters the compound view **only once**, via
the *habitability* index `H_j` (`src/heat.py`: CMIP6 warm nights + cooling
degree-days + peak heat + Census-LACE AC-access — deliberately **not** `hwav`).
Fire/flood use the 90th-pct "very high" cutoff (matching the siting
`unsafe_percentile`) because California skews high on *national* NRI percentiles —
a looser cutoff would flag half the state on flood alone.

**Result (6th-cycle baseline):**

| | Jurisdictions | RHNA | % of state |
|---|---|---|---|
| water | 135 | 433,962 | 17.4% |
| flood | 157 | 356,020 | 14.3% |
| fire | 123 | 174,007 | 7.0% |
| slr | 53 | 155,906 | 6.2% |
| heat | 21 | 89,393 | 3.6% |
| **≥1 axis (union)** | **357** | **976,426** | **39.1%** |
| ≥2 axes (stacked) | 109 | 166,256 | 6.7% |
| ≥3 axes | 22 | 66,573 | 2.7% |

**~39% of statewide RHNA carries at least one genuinely-high climate constraint;
~7% stacks two or more.** The single largest axis is **water** (17%), then flood
(14%). Crucially, the compound view surfaces what no single axis did: the
**Inland Empire + Coachella Valley** as the epicenter of *stacked* constraints —
Unincorporated Riverside (fire+flood+heat), Coachella (flood+water+heat), Perris
and Menifee (fire+flood+water). These are a growth destination **and** the hardest
places to build, a tension invisible to any one hazard. Output:
`outputs/constraints_by_jurisdiction.csv`, `charts/compound_constraints.png`.

### 8a. The compound effect as a SECOND model (option 2)

The base model (§4) treats hazards independently. Whether they *compound* —
whether being moderately bad on several axes is worse than the sum — is genuinely
uncertain, so it is presented as a **separate second model** shown alongside the
base, never folded into a single headline. Every run emits both.

`apply_model(compound=True)` adds one term to the base: jurisdictions stacking
`n_constraints ≥ min_stack` (2) shed an **extra** siting discount
`Sw_comp = B_j · rate · (n−min+1)^exp`, of which only **`rehouse_fraction`** can be
absorbed by climate-safe receivers. The remainder is **stranded** — California may
simply lack enough safe, water-secure, heat-livable land to rehouse everyone — and
**drops out of the total**, so the compound model's probable minimum lands *below*
the base:

```
Σ B'_compound = Σ B'_base − stranded,   stranded = (1−rehouse_fraction)·Σ Sw_comp
```

This deliberately **breaks the base model's conservation identity** (that's the
point: stacked capacity that can't be rehoused is lost, not moved). The base path
(`compound=False`) is byte-identical to before and still conserves.

**Result (6th cycle):** base **2,719,039** → compound **2,701,968** (17,072
stranded). Swept over the uncertain parameters (`rate`, `rehouse_fraction`), the
stranded band is **~5.7k–40k units** (`sensitivity_compound.csv`). Cumulative to
2100 the compound trajectory strands ~105k. Compounding pulls allocation out of
the **Inland Empire** (SCAG −17k; Unincorporated Riverside, Ontario, Perris) — a
"there aren't enough safe places" signal. **Option 3** (explicit physical
couplings — post-fire debris flow, overdraft subsidence — which could *raise* the
total via cascade losses) is the planned more rigorous successor.

## 9. Key assumptions and limitations

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
- **Water (component E) is a contained, redistributive constraint.** It moves
  ~19,400 units (with `move_fraction`) out of water-constrained jurisdictions and
  leaves the statewide total unchanged. The signal is strong where it should be —
  allocation flows **out of the overdrafted San Joaquin Valley + Sacramento region**
  (Fresno, Kern, San Joaquin, Stanislaus, Merced; SACOG). Statewide, projected
  growth and water stress are ~uncorrelated (r≈0), so water refines the geography
  rather than the totals.
- **`W_j` under-counts imported-supply risk (key water caveat).** It is a
  *groundwater*-overdraft + drought + aridification index. It does **not** capture
  reliance on imported water with declining reliability (Colorado River, State
  Water Project), so it scores coastal metros (LA, SF, San Diego) as more
  water-secure *receivers* than they really are. The **siting discount** (moving
  out of overdrafted basins) is the robust part; the receiver-side reallocation to
  the coast is deliberately softened (`headroom_exponent` 0.5) and should be read
  cautiously. Per-jurisdiction imported-supply / UWMP supply-demand balance is the
  natural next data layer (see `FUTURE_WORK.md`).
- **External (out-of-state) climate in-migration is OFF by default** — the
  statewide increase is driven entirely by in-state replacement need. Enabling it
  (`external_migration`) adds an additive term distributed to receivers.
- **Not an official determination.** No income-category split of the adjustment,
  no legal/RHNA-methodology constraints (e.g. jobs-housing fit, equity
  adjustments) are modeled.

## 10. Reproduce

```bash
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m src.source_rhna     # normalize HCD baseline -> FIPS
./.venv/bin/python -m src.allocate        # 6th-cycle pipeline -> outputs/ + charts
./.venv/bin/python -m src.trajectory      # decadal need to 2100 -> outputs/trajectory_*
./.venv/bin/python -m src.constraints     # compound climate-constraint view
./.venv/bin/python -m src.sensitivity     # uncertainty bands -> outputs/sensitivity*.csv
./.venv/bin/python -m pytest -q           # invariants
```
