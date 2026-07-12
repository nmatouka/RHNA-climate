# Future work / roadmap

Planned extensions beyond the current 6th-cycle, single-horizon model. Both
build on hooks that already exist in the codebase.

---

## 0. Water — imported-supply layer (partially done)

**Done:** water as a supply-side siting constraint — component E (`src/water.py`,
methodology §4/§8). `W_j` blends SGMA basin priority/overdraft (via climateshed's
own `casgem_basins` lookup), NRI drought, and CMIP6 aridification; it moves
allocation out of the overdrafted San Joaquin Valley + Sacramento region, purely
redistributively. Config `water:` (enabled by default).

**Remaining — imported-supply risk.** `W_j` is groundwater-based and under-counts
reliance on imported water with declining reliability (**Colorado River, State
Water Project**), so it overstates how water-secure the coastal metros (LA/SF/SD)
are as *receivers*. Add a per-jurisdiction imported-supply-risk term from **Urban
Water Management Plan** supply-demand balances (or a coarse Colorado-River /
SWP-dependence overlay by county). Until then the receiver-side water effect is
softened (`headroom_exponent` 0.5) and the robust signal is the siting discount.

---

## 1. External (out-of-state) climate in/out-migration

**Status:** hook present, disabled. `config/assumptions.yaml → external_migration`
(`enabled: false`, `net_households: 0`); `src/adjustment_model.py` already adds an
`ext_units` term distributed to receivers by the same resilience×capacity weights.
Today the statewide increase is driven purely by in-state replacement need.

**Goal:** account for net domestic migration into (or out of) California driven by
climate, on top of in-state redistribution — a term the RHNA formula ignores.

**Important — sign is an open empirical question.** California is plausibly a net
climate *sender* (wildfire, extreme heat, water stress, cost) as much as a
receiver. The term may be **negative** for parts of the state. So this work must:
- Support a **signed** net figure (currently only positive `ext_units` is handled;
  extend `apply_model` to allow net-negative, reducing allocation, while keeping
  the conservation identity explicit).
- Decide the sign/magnitude from evidence rather than assuming CA gains population.

**Data / methods to source:**
- IRS county-to-county migration flows; Census ACS migration (in/out).
- DOF P-3 projections (net-migration component) as the demographic baseline.
- Peer-reviewed climate-migration projections (e.g. Hauer-style SLR displacement,
  Rhodium/ProPublica county climate-migration models) for the climate *delta* on
  top of the demographic baseline.

**Design:**
- Anchor to a DOF net-migration baseline, add a climate delta (signed).
- Optionally give the external term its own spatial pattern (not just the internal
  receiver weights) — e.g. coastal-flight vs. inland-heat-flight destinations.
- Report it as a **separate line** from replacement so the statewide total
  decomposes into: baseline + replacement + net-external.
- Extend the conservation test to cover the signed external term.

**Effort:** medium. Mostly data sourcing + a signed-term generalization of the
existing hook; sensitivity should sweep the sign/magnitude given the uncertainty.

---

## 2. Longer horizon — housing need *beyond* the 6th cycle ✅ IMPLEMENTED

**Done** (`src/trajectory.py`, methodology §7). Walks decades `2030s → 2090s`
with a growing DOF-informed baseline, per-decade time-varying climate (CMIP6
decade + rising SLR, pooled-normalized so intensification rises over time), the
same A–D adjustment per decade, and cumulative accounting to 2100. Outputs
`trajectory_statewide.csv` / `trajectory_region.csv` and two charts; a growth-path
sensitivity (`sensitivity.trajectory_sweep`) covers flat/central/decline. Central
result: cumulative need to 2100 ~14.0M → ~16.5M (+18%), climate share rising
11%→30%.

**County-level DOF projections — ✅ DONE** (`src/dof_projections.py`,
`growth_source: county`). DOF P-4 household projections (2010–2040) + P-2A
population (2020–2070) now give each county its own two-part growth multiplier;
`trajectory.compare_sources` quantifies the shift vs. the uniform taper. Result:
cumulative need share moves out of SCAG (−10 pp) into Sacramento/Bay/Central
Valley, and the climate share rises (20.4% vs 18.2%).

**Remaining refinements here.** (a) **Sub-county growth** — within a county,
city vs. unincorporated growth still rides 6th-cycle shares; DOF has no
sub-county projections, so this would need a local land-use/ACS proxy.
(b) **Inter-cycle carryover** — each decade is an independent cycle; unmet need
from one cycle does not roll into the next. (c) **Post-2070 households** are
inferred from population via a declining household-size trajectory; revisit when
DOF extends the household series.

---

## 3. Other climate factors identified (available, not yet used)

A review of the CMIP6 server + climateshed layers against the model surfaced
housing-relevant signals still on the table (all present in existing data):

- **Heat-habitability — partially done.** `src/heat.py` builds `H_j` (warm nights
  + cooling burden + peak heat + AC access) and it feeds the compound view
  (methodology §8). It is deliberately **not** a discount component (would
  double-count the NRI heat-wave term already in `E_j`). If ever wired as a
  discount, remove `hwav` from `E_j` first.
- **Post-fire debris flow / landslide** (NRI `lnds`) — climate-linked location
  constraint for hillside/WUI parcels; a natural 6th compound axis.
- **Urban heat island** (NLCD `PCT_TREE_CANOPY` / `PCT_IMPERVIOUS`) — a
  within-jurisdiction siting signal (dense infill in low-canopy tracts is hotter).
- **Wildfire smoke / air quality** (CalEnviroScreen PM2.5) — habitability.
- **Snowpack decline** (`ca_snow_historical`) — would sharpen the water layer's
  surface-supply dimension (currently only aridification).
- **Compound-hazard as a model effect** (not just a reporting view) — the deeper
  refinement: the Inland Empire stacks fire+flood+water+heat, and a jurisdiction
  moderate on each individually may be effectively unbuildable when they combine.
- **Land subsidence** from overdraft (San Joaquin Valley) — needs InSAR/DWR data
  (not in climateshed); ties water → physical buildability.

### Cross-cutting refinements (smaller, noted in methodology.md §9)
- Per-jurisdiction **receiver cap** (small towns can absorb large % gains today).
- **CA-relative vs national** NRI percentile option for the exposure index.
- **Income-category** split of the adjustment (baseline has VLI/LI/MOD/AboveMod).
- **Managed-retreat** variant: assign replacement need to safer areas rather than
  in-place.
