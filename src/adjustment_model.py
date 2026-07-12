"""The climate adjustment model (components A-D).

For each jurisdiction j, starting from baseline RHNA B_j:

  A. Replacement need   R_j  = occ_housing * annual_loss_rate * horizon_years
                               (added to j; RAISES the statewide total)
  B. Out-displacement   D_j  = population * displacement_fraction(E_j) / hh_size
                               (households leaving j; REDISTRIBUTED)
  D. Siting discount    S_j  = B_j * unsafe_share * move_fraction
                               (hazard-unsafe capacity moved out of j)
  E. Water-siting       Sw_j = B_j * f(W_j)  (supply-side; not-probable-to-water
                               capacity moved out of water-constrained j)
  C. Receiver capture        pool = Σ removed_j  distributed to climate-resilient,
                               water-secure receivers by (1-E)^a * pop^b * (1-W)^c

  removed_j  = min(S_j + D_j + Sw_j, B_j)   # can't remove more than allocated
  received_j = pool * w_j / Σ w             # receivers only (E < eligibility)
  B'_j       = B_j - removed_j + received_j + R_j

Conservation: Σ B'_j = Σ B_j + Σ R_j (the redistributed pool nets to zero); the
statewide total rises ONLY by replacement need (+ optional external migration).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import load_assumptions


def displacement_fraction(E: np.ndarray, cfg: dict) -> np.ndarray:
    d = cfg["displacement"]
    e = np.clip((E - d["min_exposure"]) / (1.0 - d["min_exposure"]), 0.0, 1.0)
    return d["max_fraction"] * e ** d["exponent"]


def apply_model(master: pd.DataFrame, cfg: dict | None = None,
                compound: bool = False) -> pd.DataFrame:
    """Return `master` with adjustment columns and the adjusted allocation B'_j.

    compound=False -> the BASE model (components A-E, pool conserved, total rises
    only by replacement). compound=True -> adds the option-2 compound effect: an
    extra siting discount on multiply-stacked jurisdictions of which only
    `rehouse_fraction` can be absorbed by safe receivers; the rest is STRANDED,
    lowering the statewide total below the base (the "not enough safe places"
    scenario). The base path is byte-identical to compound=False.
    """
    cfg = cfg or load_assumptions()
    df = master.copy()

    B = df["rhna_baseline"].to_numpy(dtype=float)
    E = df["E"].to_numpy(dtype=float)
    occ = df["occ_housing"].to_numpy(dtype=float)
    pop = df["population"].to_numpy(dtype=float)

    horizon = cfg["horizon"]["years"]
    hh_size = cfg["household"]["avg_size"]

    # --- A. Replacement need (raises total) ---
    R = occ * df["annual_loss_rate"].to_numpy(dtype=float) * horizon

    # --- B. Out-displacement ---
    D = pop * displacement_fraction(E, cfg) / hh_size

    # --- D. Siting discount (hazard-driven) ---
    S = B * df["unsafe_share"].to_numpy(dtype=float) * cfg["siting"]["move_fraction"]

    # --- E. Water-siting discount (supply-driven) ---
    W = (df["W"].to_numpy(dtype=float) if "W" in df.columns
         else np.zeros_like(B))
    water = cfg.get("water", {})
    if water.get("enabled") and "W" in df.columns:
        ws = water["siting"]
        e_w = np.clip((W - ws["min_stress"]) / (1.0 - ws["min_stress"]), 0.0, 1.0)
        S_water = B * ws["max_move_fraction"] * e_w ** ws["exponent"]
    else:
        S_water = np.zeros_like(B)

    # Units removed from j and pushed into the redistribution pool (capped at B).
    base_removed = np.minimum(S + D + S_water, B)

    # --- Compound (option 2): extra siting discount on multiply-stacked places;
    #     only rehouse_fraction is rehousable, the rest is STRANDED. ---
    comp = cfg.get("compound", {})
    if compound and comp.get("enabled") and "H" in df.columns:
        from .constraints import constraint_flags
        nc = constraint_flags(df, cfg)["n_constraints"].to_numpy(dtype=float)
        g = np.clip(nc - comp["min_stack"] + 1.0, 0.0, None) ** comp["exponent"]
        S_comp = np.minimum(B * comp["rate"] * g, np.maximum(B - base_removed, 0.0))
        rehouse = float(comp["rehouse_fraction"])
    else:
        S_comp = np.zeros_like(B)
        rehouse = 1.0

    removed = base_removed + S_comp
    base_pool = float(base_removed.sum())
    compound_pool = float(S_comp.sum())
    stranded = (1.0 - rehouse) * compound_pool
    pool = base_pool + rehouse * compound_pool   # what actually gets rehoused

    # --- C. Receiver capture ---
    rec = cfg["receiver"]
    eligible = E < rec["max_exposure_eligible"]
    # Water-secure jurisdictions preferred as receivers (headroom = 1 - W).
    if water.get("enabled") and "W" in df.columns:
        headroom = np.clip(1.0 - W, 0.0, 1.0) ** water["receiver"]["headroom_exponent"]
    else:
        headroom = np.ones_like(B)
    w = np.where(
        eligible,
        (1.0 - E) ** rec["resilience_exponent"] * pop ** rec["capacity_exponent"] * headroom,
        0.0,
    )
    wsum = w.sum()
    if wsum <= 0:  # degenerate fallback: distribute by population
        w = np.where(eligible, pop, 0.0)
        wsum = w.sum()
    received = pool * (w / wsum) if wsum > 0 else np.zeros_like(w)

    # Optional external in-migration (default off): add proportionally to receivers.
    ext = cfg.get("external_migration", {})
    ext_units = float(ext.get("net_households", 0)) if ext.get("enabled") else 0.0
    if ext_units > 0 and wsum > 0:
        received = received + ext_units * (w / wsum)

    Bp = B - removed + received + R

    df["repl_R"] = R
    df["displace_D"] = D
    df["siting_S"] = S
    df["water_S"] = S_water
    df["compound_S"] = S_comp
    df["removed"] = removed
    df["received"] = received
    df["is_receiver"] = eligible
    df["rhna_adjusted"] = Bp
    df["delta"] = Bp - B
    df["delta_pct"] = np.where(B > 0, df["delta"] / B * 100.0, np.nan)
    df.attrs["stranded"] = stranded
    df.attrs["compound"] = bool(compound and comp.get("enabled"))
    return df
