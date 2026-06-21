"""Validate processed outputs and write data_quality_report.csv."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from geography_tiers import VALID_CONFIDENCE
from geography_tiers import VALID_TIERS as VALID_GEOMETRY_TIERS
from utils import REPO_ROOT, write_dataframe


VALID_TIERS = {"Critical Review", "High Review", "Moderate Review", "Monitor", "Lower Priority"}
MATCHED_TIERS = {"verified_service_area_boundary", "modeled_service_area_boundary"}
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

    required_master = ["pwsid", "pws_name", "state", "county", "population_served", "data_quality_flags"]
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

    bad_confidence = geography[geography["spatial_confidence"].isna() | ~geography["spatial_confidence"].isin(VALID_CONFIDENCE)]
    add_check(rows, "spatial_confidence_valid_not_null", bad_confidence.empty, "high", len(bad_confidence), "Spatial confidence is required and must use the geography hierarchy.")

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

    # --- Geometry source + service-area boundary checks (Phase 1) ---
    bad_tier = geography[geography["geometry_source_tier"].isna() | ~geography["geometry_source_tier"].isin(VALID_GEOMETRY_TIERS)]
    add_check(rows, "geometry_source_tier_valid", bad_tier.empty, "high", len(bad_tier), "Every record needs a valid geometry source tier.")

    boundaries_path = REPO_ROOT / "data" / "interim" / "service_area_boundaries_web.parquet"
    report_path = REPO_ROOT / "data" / "interim" / "service_area_simplification_report.json"
    boundaries = pd.read_parquet(boundaries_path) if boundaries_path.exists() else pd.DataFrame(columns=["pwsid", "geometry_geojson"])
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}

    def _parseable(value: str) -> bool:
        try:
            geom = json.loads(value)
            return geom.get("type") in {"Polygon", "MultiPolygon"} and bool(geom.get("coordinates"))
        except Exception:
            return False

    matched_pwsids = set(geography.loc[geography["geometry_source_tier"].isin(MATCHED_TIERS), "pwsid"])
    boundary_pwsids = set(boundaries["pwsid"])
    unparseable = int((~boundaries["geometry_geojson"].map(_parseable)).sum()) if len(boundaries) else 0
    missing_boundaries = matched_pwsids - boundary_pwsids
    add_check(
        rows,
        "boundary_geojson_parseable_for_matched",
        unparseable == 0 and not missing_boundaries,
        "high",
        unparseable + len(missing_boundaries),
        f"{unparseable} unparseable geometries; {len(missing_boundaries)} matched systems missing a boundary.",
    )

    duplicate_boundaries = int(boundaries["pwsid"].duplicated().sum()) if len(boundaries) else 0
    add_check(rows, "no_duplicate_boundary_pwsid_after_dissolve", duplicate_boundaries == 0, "critical", duplicate_boundaries, "One boundary geometry per PWSID after dissolve.")

    raw_n = report.get("raw_feature_count")
    unique_n = report.get("unique_pwsid_count")
    dissolved_n = report.get("dissolved_output_count")
    reconciles = (
        unique_n == dissolved_n == len(boundaries) == len(matched_pwsids)
        and raw_n is not None
        and raw_n >= unique_n
    )
    add_check(
        rows,
        "boundary_count_reconciles_to_source",
        bool(reconciles),
        "high",
        0,
        f"raw={raw_n} unique_pwsid={unique_n} dissolved={dissolved_n} web_rows={len(boundaries)} matched_in_geography={len(matched_pwsids)}",
    )

    simplification = report.get("simplification", {})
    fraction_over = simplification.get("fraction_over_threshold", 1.0)
    add_check(
        rows,
        "simplified_geometry_area_delta_within_threshold",
        fraction_over <= 0.02,
        "medium",
        simplification.get("count_over_threshold", 0),
        f"tolerance={simplification.get('tolerance_m')}m avg_area_delta={simplification.get('avg_area_delta')} "
        f"max_area_delta={simplification.get('max_area_delta')} over_threshold={simplification.get('count_over_threshold')} "
        f"fraction_over={fraction_over}",
    )

    try:
        features = [
            {"type": "Feature", "properties": {"pwsid": row.pwsid}, "geometry": json.loads(row.geometry_geojson)}
            for row in boundaries.itertuples()
        ]
        feature_collection = {"type": "FeatureCollection", "features": features}
        fc_valid = (
            feature_collection["type"] == "FeatureCollection"
            and len(feature_collection["features"]) == len(boundaries)
            and all(feature["geometry"].get("type") in {"Polygon", "MultiPolygon"} for feature in features)
        )
    except Exception:
        fc_valid = False
    add_check(rows, "map_boundaries_featurecollection_valid", bool(fc_valid), "high", 0, f"Assembled a valid FeatureCollection with {len(boundaries)} boundary features.")

    output = pd.DataFrame(rows)
    write_dataframe(output, REPO_ROOT / "data" / "processed" / "data_quality_report")
    output.to_csv(REPO_ROOT / "data" / "powerbi" / "data_quality_report.csv", index=False)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate processed outputs.")
    parser.parse_args()
    validate_outputs()
