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

## 2. Longer horizon — housing need *beyond* the 6th cycle ✅ IMPLEMENTED

**Done** (`src/trajectory.py`, methodology §7). Walks decades `2030s → 2090s`
with a growing DOF-informed baseline, per-decade time-varying climate (CMIP6
decade + rising SLR, pooled-normalized so intensification rises over time), the
same A–D adjustment per decade, and cumulative accounting to 2100. Outputs
`trajectory_statewide.csv` / `trajectory_region.csv` and two charts; a growth-path
sensitivity (`sensitivity.trajectory_sweep`) covers flat/central/decline. Central
result: cumulative need to 2100 ~14.0M → ~16.5M (+18%), climate share rising
11%→30%.

**Remaining refinement — county-level DOF household projections.** The baseline
growth taper is currently a *statewide* multiplier applied uniformly
(`trajectory.baseline_growth_mult`). Swapping in DOF **P-2A/P-4 county household
projections** would differentiate growth geographically (some counties keep
growing, others shrink), making the per-region trajectory more realistic. The
hook is clean: replace the uniform `growth_mult_d` with a per-county series.
DOF file: `P2A_County_Total.xlsx` (population) / P-4 households, on dof.ca.gov.
Also consider explicit inter-cycle carryover of unmet need (each decade is
currently an independent cycle).

---

### Cross-cutting refinements (smaller, noted in methodology.md §8)
- Per-jurisdiction **receiver cap** (small towns can absorb large % gains today).
- **CA-relative vs national** NRI percentile option for the exposure index.
- **Income-category** split of the adjustment (baseline has VLI/LI/MOD/AboveMod).
- **Managed-retreat** variant: assign replacement need to safer areas rather than
  in-place.
