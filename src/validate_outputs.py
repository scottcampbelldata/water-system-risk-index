"""Validate processed outputs and write data_quality_report.csv."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from utils import REPO_ROOT, write_dataframe


VALID_TIERS = {"Critical Review", "High Review", "Moderate Review", "Monitor", "Lower Priority"}
SPATIAL_CONFIDENCE = {"high", "medium", "low", "unknown"}
FUNDING_CONFIDENCE = {
    "exact_pwsid_match",
    "exact_name_county_match",
    "fuzzy_name_county_match",
    "county_only_match",
    "unmatched",
}


def add_check(rows: list[dict], name: str, passed: bool, severity: str, affected: int, notes: str) -> None:
    rows.append(
        {
            "check_name": name,
            "status": "pass" if passed else "fail",
            "severity": severity,
            "rows_affected": int(affected),
            "notes": notes,
        }
    )


def require_columns(df: pd.DataFrame, required: list[str]) -> list[str]:
    return [column for column in required if column not in df.columns]


def validate_outputs() -> pd.DataFrame:
    rows: list[dict] = []
    processed = REPO_ROOT / "data" / "processed"
    master = pd.read_csv(processed / "water_system_master.csv", dtype={"pwsid": str})
    risk = pd.read_csv(processed / "water_system_risk_scores.csv", dtype={"pwsid": str})
    geography = pd.read_csv(processed / "water_system_geography.csv", dtype={"pwsid": str})
    funding = pd.read_csv(processed / "water_system_funding_summary.csv", dtype={"pwsid": str})

    duplicate_count = int(master.duplicated("pwsid").sum())
    add_check(rows, "no_duplicate_pwsid_in_master", duplicate_count == 0, "critical", duplicate_count, "One row per PWSID is required.")

    required_master = ["pwsid", "pws_name", "state", "county", "population_served", "spatial_confidence", "data_quality_flags"]
    missing = require_columns(master, required_master)
    add_check(rows, "master_required_columns_present", not missing, "critical", len(missing), f"Missing columns: {', '.join(missing)}")

    out_of_range = risk[~risk["overall_risk_score"].between(0, 100)]
    add_check(rows, "risk_score_between_0_and_100", out_of_range.empty, "critical", len(out_of_range), "Scores must be bounded.")

    bad_tiers = risk[~risk["risk_tier"].isin(VALID_TIERS)]
    add_check(rows, "valid_risk_tiers_only", bad_tiers.empty, "critical", len(bad_tiers), "Risk tier names must match dashboard dictionary.")

    negative_pop = master[pd.to_numeric(master["population_served"], errors="coerce").lt(0)]
    add_check(rows, "population_served_not_negative", negative_pop.empty, "critical", len(negative_pop), "Population served cannot be negative.")

    component_columns = [
        "compliance_risk_component",
        "enforcement_risk_component",
        "vulnerability_component",
        "drought_component",
        "funding_gap_component",
        "small_system_component",
        "data_quality_penalty",
    ]
    bad_components = pd.Series(False, index=risk.index)
    for column in component_columns:
        bad_components = bad_components | ~pd.to_numeric(risk[column], errors="coerce").between(0, 100)
    add_check(
        rows,
        "component_scores_between_0_and_100",
        not bad_components.any(),
        "critical",
        int(bad_components.sum()),
        "Every normalized component must be within 0-100.",
    )

    missing_spatial = master[master["spatial_confidence"].isna() | ~master["spatial_confidence"].isin(SPATIAL_CONFIDENCE)]
    add_check(rows, "spatial_confidence_valid_not_null", missing_spatial.empty, "high", len(missing_spatial), "Spatial confidence is required.")

    missing_funding = funding[funding["funding_match_confidence"].isna() | ~funding["funding_match_confidence"].isin(FUNDING_CONFIDENCE)]
    add_check(rows, "funding_match_confidence_valid_not_null", missing_funding.empty, "high", len(missing_funding), "Funding match confidence is required.")

    row_count_notes = (
        f"master={len(master)}, geography={len(geography)}, funding={len(funding)}, risk={len(risk)}"
    )
    add_check(rows, "row_counts_by_stage", len(master) == len(risk) == len(geography) == len(funding), "high", 0, row_count_notes)

    for column in ["pws_name", "county", "population_served"]:
        missing_pct = master[column].isna().mean() * 100
        add_check(
            rows,
            f"percent_missing_{column}",
            missing_pct < 25,
            "medium",
            int(master[column].isna().sum()),
            f"{missing_pct:.1f}% missing.",
        )

    top20 = risk.nsmallest(20, "rank_statewide")
    obvious_errors = top20[top20["explanation_text"].isna() | top20["pwsid"].isna()]
    add_check(rows, "top_20_systems_reviewed_for_obvious_errors", obvious_errors.empty, "medium", len(obvious_errors), "Top ranked rows have PWSID and explanation text.")

    output = pd.DataFrame(rows)
    write_dataframe(output, REPO_ROOT / "data" / "processed" / "data_quality_report")
    output.to_csv(REPO_ROOT / "data" / "powerbi" / "data_quality_report.csv", index=False)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate processed outputs.")
    parser.parse_args()
    validate_outputs()
