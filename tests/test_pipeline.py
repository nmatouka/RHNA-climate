"""Invariant tests for the RHNA-climate pipeline. Run: ./.venv/bin/python -m pytest"""
import numpy as np
import pandas as pd

from src.adjustment_model import apply_model, displacement_fraction
from src.config import load_assumptions, slugify
from src.crosswalk import build_master
from src.regions import region_for_county

CFG = load_assumptions()


def test_baseline_reconciles_to_known_total():
    master = build_master(verbose=False)
    # HCD 6th-cycle statewide control total.
    assert abs(master["rhna_baseline"].sum() - 2_495_457) < 1


def test_full_coverage():
    master = build_master(verbose=False)
    assert len(master) == 539
    for col in ["occ_housing", "population", "E", "annual_loss_rate", "rhna_baseline"]:
        assert master[col].notna().all(), f"{col} has gaps"


def test_pool_conservation_and_increase_equals_replacement():
    master = build_master(verbose=False)
    adj = apply_model(master, CFG)
    # Redistributed pool nets to zero: received == removed.
    assert np.isclose(adj["received"].sum(), adj["removed"].sum(), rtol=1e-6)
    # Statewide increase equals replacement need only (external term off).
    increase = adj["rhna_adjusted"].sum() - adj["rhna_baseline"].sum()
    assert np.isclose(increase, adj["repl_R"].sum(), rtol=1e-6)


def test_adjusted_allocation_nonnegative():
    adj = apply_model(build_master(verbose=False), CFG)
    assert (adj["rhna_adjusted"] >= 0).all()


def test_high_exposure_loses_low_exposure_gains_on_average():
    adj = apply_model(build_master(verbose=False), CFG)
    thr = CFG["receiver"]["max_exposure_eligible"]
    hi = adj[adj["E"] >= thr]["delta"].mean()
    lo = adj[adj["E"] < thr]["delta"].mean()
    assert hi < 0 < lo, f"expected losers above / gainers below threshold, got {hi=}, {lo=}"


def test_regional_rollup_matches_published_mpo_determinations():
    master = build_master(verbose=False)
    master["region"] = master["county"].map(region_for_county)
    reg = master.groupby("region")["rhna_baseline"].sum()
    published = {"SCAG": 1_341_827, "ABAG/MTC": 441_176, "SANDAG": 171_685,
                 "AMBAG": 33_274}
    for r, p in published.items():
        assert abs(reg[r] - p) < 1, f"{r}: {reg[r]} != {p}"


def test_displacement_curve_zero_below_threshold():
    E = np.array([0.0, 0.4, 0.5, 0.75, 1.0])
    frac = displacement_fraction(E, CFG)
    assert frac[0] == 0 and frac[1] == 0 and frac[2] == 0
    assert frac[4] == CFG["displacement"]["max_fraction"]
    assert frac[3] < frac[4]


def test_slugify_matches_climateshed_convention():
    assert slugify("La Cañada Flintridge") == "la-ca-ada-flintridge"
    assert slugify("St. Helena") == "st-helena"
    assert slugify("Adelanto") == "adelanto"
