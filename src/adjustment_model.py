"""The climate adjustment model (components A-D).

For each jurisdiction j, starting from baseline RHNA B_j:

  A. Replacement need   R_j  = occ_housing * annual_loss_rate * horizon_years
                               (added to j; RAISES the statewide total)
  B. Out-displacement   D_j  = population * displacement_fraction(E_j) / hh_size
                               (households leaving j; REDISTRIBUTED)
  D. Siting discount    S_j  = B_j * unsafe_share * move_fraction
                               (unsafe-sited capacity moved out of j)
  C. Receiver capture        pool = Σ removed_j  distributed to climate-resilient
                               receivers by weight (1-E)^a * pop^b

  removed_j  = min(S_j + D_j, B_j)          # can't remove more than allocated
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


def apply_model(master: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """Return `master` with adjustment columns and the adjusted allocation B'_j."""
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

    # --- D. Siting discount ---
    S = B * df["unsafe_share"].to_numpy(dtype=float) * cfg["siting"]["move_fraction"]

    # Units removed from j and pushed into the redistribution pool (capped at B).
    removed = np.minimum(S + D, B)
    pool = float(removed.sum())

    # --- C. Receiver capture ---
    rec = cfg["receiver"]
    eligible = E < rec["max_exposure_eligible"]
    w = np.where(
        eligible,
        (1.0 - E) ** rec["resilience_exponent"] * pop ** rec["capacity_exponent"],
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
    df["removed"] = removed
    df["received"] = received
    df["is_receiver"] = eligible
    df["rhna_adjusted"] = Bp
    df["delta"] = Bp - B
    df["delta_pct"] = np.where(B > 0, df["delta"] / B * 100.0, np.nan)
    return df
