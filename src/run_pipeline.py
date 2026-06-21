"""Run the complete Ohio MVP pipeline from raw/staged data to Power BI exports."""

from __future__ import annotations

from build_features import build_all_features
from clean_water_systems import build_master
from download_data import main as download_main
from export_powerbi import export_powerbi
from load_drought import load_drought
from load_sdwis import load_sdwis
from load_service_areas import load_service_areas
from load_svi import load_svi
from score_risk import score_risk
from validate_outputs import validate_outputs


def run_pipeline() -> None:
    print("Loading SDWA...")
    load_sdwis()
    print("Loading service areas...")
    load_service_areas()
    print("Loading SVI...")
    load_svi()
    print("Loading drought...")
    load_drought()
    print("Building master...")
    build_master()
    print("Building features...")
    build_all_features()
    print("Scoring risk...")
    score_risk()
    print("Validating outputs...")
    validate_outputs()
    print("Exporting Power BI files...")
    export_powerbi()
    print("Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
