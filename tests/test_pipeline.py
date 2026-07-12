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


# --- longer-horizon trajectory -------------------------------------------------
from src import trajectory  # noqa: E402
from src.dof_projections import county_growth_multipliers, multiplier_by_jurisdiction  # noqa: E402

_TRAJ = trajectory.run(verbose=False, make_charts=False)["statewide"]  # county (default)
_TRAJ_UNI = trajectory.run(verbose=False, make_charts=False,
                           growth_curve=CFG["trajectory"]["baseline_growth_mult"])["statewide"]


def test_uniform_trajectory_anchors_to_sixth_cycle():
    # In uniform mode the 2030s multiplier is 1.0, so baseline == 6th-cycle total.
    row = _TRAJ_UNI[_TRAJ_UNI["decade"] == "2030s"].iloc[0]
    assert abs(row["baseline_need"] - 2_495_457) < 1


def test_trajectory_cumulative_monotonic():
    for col in ["cum_baseline", "cum_adjusted"]:
        assert _TRAJ[col].is_monotonic_increasing
        assert (_TRAJ[col].diff().dropna() > 0).all()


def test_trajectory_decade_conservation_and_climate_positive():
    # Each decade: adjusted - baseline == replacement (pool nets to zero) and > 0.
    add = _TRAJ["adjusted_need"] - _TRAJ["baseline_need"]
    assert np.allclose(add, _TRAJ["replacement"], rtol=1e-6)
    assert (add > 0).all()


def test_trajectory_climate_share_grows_end_to_end():
    # Climate becomes a larger share of need over the horizon (not necessarily
    # monotone: DOF household growth is uneven across decades).
    assert _TRAJ.iloc[-1]["climate_add_pct"] > _TRAJ.iloc[0]["climate_add_pct"]


def test_county_multipliers_bounded_and_complete():
    cm = county_growth_multipliers()
    assert len(cm) == 58  # all CA counties
    floor = CFG["trajectory"]["county_growth_floor"]
    cap = CFG["trajectory"]["county_growth_cap"]
    assert (cm.values >= floor - 1e-9).all() and (cm.values <= cap + 1e-9).all()
    master = build_master(verbose=False)
    jm = multiplier_by_jurisdiction(master)
    assert len(jm) == len(master) and jm.notna().all().all()


def test_county_resolution_shifts_share_inland():
    # The signature refinement: DOF growth moves need share OUT of SCAG (slow-
    # growing coastal SoCal) toward Sacramento/Central Valley.
    cmp = trajectory.compare_sources(make_charts=False, verbose=False)
    assert cmp.loc["SCAG", "share_shift_pp"] < -2.0
    assert cmp.loc["SACOG", "share_shift_pp"] > 1.0
