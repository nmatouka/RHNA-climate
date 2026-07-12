# DOF projections — provenance

California Department of Finance, Demographic Research Unit. Downloaded
2026-07-11 from the DOF Projections page
(https://dof.ca.gov/forecasting/demographics/projections/).

| File | Report | Coverage | Use |
|---|---|---|---|
| `P4_HHProjections_B2024.xlsx` | P-4 Total Households (Baseline 2024 / Vintage 2025) | CA counties, 2010–2040 | Real household counts drive per-county baseline-need growth (2020s/2030s). |
| `P2A_County_Total.xlsx` | P-2A Total Population Projections (2024 Baseline) | CA counties, 2020–2070 | Extends households past 2040 (Pop ÷ a declining household-size trajectory fit to 2020–2040). |

Consumed by `src/dof_projections.py` to build per-county, per-decade baseline-need
multipliers. Population/household growth beyond 2070 is held at the 2060s value
(documented extrapolation). See methodology §7.
