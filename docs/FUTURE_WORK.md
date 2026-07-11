# Future work / roadmap

Planned extensions beyond the current 6th-cycle, single-horizon model. Both
build on hooks that already exist in the codebase.

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

## 2. Longer horizon — housing need *beyond* the 6th cycle

**Status:** `horizon_years` scales replacement need, and `src/sensitivity.py`
already sweeps 8/16/30 yr. The CMIP6 data is decadal (`2030s…2090s`) and fully
vendored, but the model currently uses a **single decade snapshot** (`2050s`) and
holds the baseline `B_j` fixed at the 6th-cycle allocation.

**Goal:** move from "adjust the 6th cycle" to a **trajectory of statewide housing
need to 2050/2100**, showing what future cycles (7th, 8th, …) might require once
climate is included — not just a scaled replacement figure.

**What's missing today:**
- **Future baseline growth.** Beyond the 6th cycle, `B_j` itself should grow with
  projected household formation (DOF projections to 2050/2060), not stay fixed.
  Replacement + displacement then layer on top of a *growing* baseline.
- **Time-varying climate.** Step through CMIP6 decades (exposure and
  `climate_uplift` recomputed per decade) instead of one 2050s snapshot, so later
  decades carry higher hazard.
- **Cumulative accounting.** Replacement and displacement accumulate across
  decades; SLR exposure ratchets up (the SLR data already has 2020→2100 steps).

**Design sketch:**
- New `src/trajectory.py` that walks decades `2030s → 2090s`:
  - baseline_growth_d from DOF projections,
  - exposure_d / uplift_d from that decade's CMIP6 (+ SLR year),
  - replacement_d, displacement_d, redistribution_d,
  - accumulate into a per-decade `need_d` and a running total.
- Output: `outputs/trajectory_statewide.csv` (need by decade) + a line/area chart
  of baseline vs. climate-adjusted need over time, with the scenario band.
- Keep the current single-horizon model as the "6th-cycle" special case.

**Data / methods to source:**
- DOF population/household projections (P-1/P-3) by county to 2060.
- Optionally HCD's household-growth methodology to keep the growth term
  consistent with how RHND is actually derived.

**Effort:** larger. This is a genuine model extension (a time-stepped engine) plus
DOF projection sourcing, but it reuses the existing exposure, replacement, and
redistribution components per decade.

---

### Cross-cutting refinements (smaller, noted in methodology.md §7)
- Per-jurisdiction **receiver cap** (small towns can absorb large % gains today).
- **CA-relative vs national** NRI percentile option for the exposure index.
- **Income-category** split of the adjustment (baseline has VLI/LI/MOD/AboveMod).
- **Managed-retreat** variant: assign replacement need to safer areas rather than
  in-place.
