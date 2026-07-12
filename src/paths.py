"""Canonical filesystem paths for the project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"
EXTERNAL = DATA / "external"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
OUTPUTS = ROOT / "outputs"
CHARTS = OUTPUTS / "charts"

# Vendored external inputs (see data/external/PROVENANCE.md)
CA_JURISDICTIONS = EXTERNAL / "ca_jurisdictions.json"
CA_CLIMATE = EXTERNAL / "ca_jurisdictions_climate.json"
NRI_CA_TRACTS = EXTERNAL / "nri_ca_tracts.csv.gz"
CA_SLR = EXTERNAL / "ca_coastal_slr.json"
GHG_JURISDICTION_TABLE = EXTERNAL / "ghg_jurisdiction_table.csv"
V2_JURISDICTIONS = EXTERNAL / "v2_jurisdictions.csv"

ASSUMPTIONS = CONFIG / "assumptions.yaml"

# Sourced RHNA baseline (populated in Phase 2)
RHNA_BASELINE = RAW / "rhna_6th_cycle_jurisdiction.csv"

# Generated artifacts
MASTER_TABLE = PROCESSED / "master_jurisdiction.csv"
ALLOC_JURISDICTION = OUTPUTS / "allocation_jurisdiction.csv"
ALLOC_REGION = OUTPUTS / "allocation_region.csv"
ALLOC_STATEWIDE = OUTPUTS / "allocation_statewide.csv"

# Longer-horizon trajectory (src/trajectory.py)
TRAJ_STATEWIDE = OUTPUTS / "trajectory_statewide.csv"
TRAJ_REGION = OUTPUTS / "trajectory_region.csv"


def ensure_dirs() -> None:
    for d in (PROCESSED, OUTPUTS, CHARTS):
        d.mkdir(parents=True, exist_ok=True)
