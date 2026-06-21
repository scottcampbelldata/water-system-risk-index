"""Build compact JSON data for the static portfolio web app."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from utils import REPO_ROOT


def clean_number(value, digits: int | None = None):
    if pd.isna(value):
        return None
    number = float(value)
    if digits is not None:
        number = round(number, digits)
    if number.is_integer():
        return int(number)
    return number


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value)


def export_web_app_data() -> Path:
    processed = REPO_ROOT / "data" / "processed"
    risk = pd.read_csv(processed / "water_system_risk_scores.csv", dtype={"pwsid": str})
    master = pd.read_csv(processed / "water_system_master.csv", dtype={"pwsid": str, "county_fips": str})
    geo = pd.read_csv(processed / "water_system_geography.csv", dtype={"pwsid": str, "county_fips": str})
    compliance = pd.read_csv(processed / "water_system_compliance_summary.csv", dtype={"pwsid": str})
    enforcement = pd.read_csv(processed / "water_system_enforcement_summary.csv", dtype={"pwsid": str})
    funding = pd.read_csv(processed / "water_system_funding_summary.csv", dtype={"pwsid": str})
    quality = pd.read_csv(processed / "data_quality_report.csv")

    df = (
        risk.merge(master[["pwsid", "owner_type", "primary_source_water_type", "activity_status", "service_connections", "data_quality_flags"]], on="pwsid", how="left")
        .merge(
            geo[
                [
                    "pwsid",
                    "latitude",
                    "longitude",
                    "spatial_confidence",
                    "geo_join_confidence",
                    "overall_svi_percentile",
                    "recent_drought_exposure_score",
                    "severe_drought_weeks_52w",
                ]
            ],
            on="pwsid",
            how="left",
            suffixes=("", "_geo"),
        )
        .merge(
            compliance[
                [
                    "pwsid",
                    "total_violations_36m",
                    "health_based_violations_36m",
                    "open_violation_flag",
                    "violation_trend_direction",
                ]
            ],
            on="pwsid",
            how="left",
        )
        .merge(
            enforcement[["pwsid", "enforcement_actions_36m", "formal_actions_60m", "recent_enforcement_flag"]],
            on="pwsid",
            how="left",
        )
        .merge(
            funding[["pwsid", "funding_gap_flag", "funding_match_confidence", "funding_notes"]],
            on="pwsid",
            how="left",
        )
    )

    systems = []
    component_cols = [
        "compliance_risk_component",
        "enforcement_risk_component",
        "vulnerability_component",
        "drought_component",
        "funding_gap_component",
        "small_system_component",
        "data_quality_penalty",
    ]
    for row in df.itertuples(index=False):
        record = row._asdict()
        systems.append(
            {
                "pwsid": clean_text(record["pwsid"]),
                "name": clean_text(record["pws_name"]),
                "county": clean_text(record["county"]) or "Unknown",
                "population": clean_number(record["population_served"]),
                "sizeClass": clean_text(record["system_size_class"]),
                "ownerType": clean_text(record["owner_type"]),
                "waterSource": clean_text(record["primary_source_water_type"]),
                "activityStatus": clean_text(record["activity_status"]),
                "serviceConnections": clean_number(record["service_connections"]),
                "score": clean_number(record["overall_risk_score"], 2),
                "tier": clean_text(record["risk_tier"]),
                "rankStatewide": clean_number(record["rank_statewide"]),
                "rankCounty": clean_number(record["rank_county"]),
                "drivers": [
                    clean_text(record["top_risk_driver_1"]),
                    clean_text(record["top_risk_driver_2"]),
                    clean_text(record["top_risk_driver_3"]),
                ],
                "explanation": clean_text(record["explanation_text"]),
                "latitude": clean_number(record["latitude"], 6),
                "longitude": clean_number(record["longitude"], 6),
                "spatialConfidence": clean_text(record["spatial_confidence"]),
                "geoJoinConfidence": clean_text(record["geo_join_confidence"]),
                "svi": clean_number(record["overall_svi_percentile"], 4),
                "droughtExposure": clean_number(record["recent_drought_exposure_score"], 2),
                "severeDroughtWeeks": clean_number(record["severe_drought_weeks_52w"]),
                "violations36m": clean_number(record["total_violations_36m"]),
                "healthViolations36m": clean_number(record["health_based_violations_36m"]),
                "openViolation": bool(record["open_violation_flag"]),
                "violationTrend": clean_text(record["violation_trend_direction"]),
                "enforcement36m": clean_number(record["enforcement_actions_36m"]),
                "formalActions60m": clean_number(record["formal_actions_60m"]),
                "recentEnforcement": bool(record["recent_enforcement_flag"]),
                "fundingGapFlag": clean_text(record["funding_gap_flag"]),
                "fundingMatchConfidence": clean_text(record["funding_match_confidence"]),
                "fundingNotes": clean_text(record["funding_notes"]),
                "dataQualityFlags": clean_text(record["data_quality_flags"]),
                "components": {column: clean_number(record[column], 2) for column in component_cols},
            }
        )

    high_tiers = {"Critical Review", "High Review"}
    county_summary = (
        df.assign(high_review=df["risk_tier"].isin(high_tiers))
        .groupby("county", dropna=False)
        .agg(
            systems=("pwsid", "count"),
            highReviewSystems=("high_review", "sum"),
            avgScore=("overall_risk_score", "mean"),
            populationServed=("population_served", "sum"),
            lowSpatialSystems=("spatial_confidence", lambda values: int(values.isin(["low", "unknown"]).sum())),
        )
        .reset_index()
    )
    counties = [
        {
            "county": clean_text(row.county) or "Unknown",
            "systems": int(row.systems),
            "highReviewSystems": int(row.highReviewSystems),
            "avgScore": round(float(row.avgScore), 2),
            "populationServed": clean_number(row.populationServed),
            "lowSpatialSystems": int(row.lowSpatialSystems),
        }
        for row in county_summary.itertuples(index=False)
    ]

    tier_order = ["Critical Review", "High Review", "Moderate Review", "Monitor", "Lower Priority"]
    tiers = [
        {"tier": tier, "systems": int((df["risk_tier"] == tier).sum())}
        for tier in tier_order
    ]

    metadata = {
        "title": "Water System Risk & Funding Priority Index",
        "state": "Ohio",
        "modelVersion": clean_text(df["model_version"].mode().iloc[0]),
        "scoreDate": clean_text(df["score_date"].mode().iloc[0]),
        "systemCount": int(len(df)),
        "highReviewCount": int(df["risk_tier"].isin(high_tiers).sum()),
        "criticalReviewCount": int(df["risk_tier"].eq("Critical Review").sum()),
        "lowSpatialCount": int(df["spatial_confidence"].isin(["low", "unknown"]).sum()),
        "validationPassCount": int(quality["status"].eq("pass").sum()),
        "validationCheckCount": int(len(quality)),
        "sourceNote": "Public-data screening model using EPA ECHO SDWA, EPA service areas, CDC/ATSDR SVI, Census TIGER/Line, and U.S. Drought Monitor county data.",
        "useNote": "This is a review-priority screening model, not a regulatory finding, legal determination, engineering siting tool, or claim that any system is unsafe.",
    }

    output = {
        "metadata": metadata,
        "tiers": tiers,
        "counties": counties,
        "systems": systems,
        "validation": quality.to_dict(orient="records"),
    }

    # Seed source for the Postgres-backed API (no longer a deployed web asset).
    output_path = REPO_ROOT / "data" / "processed" / "app_data.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    print(f"Wrote {output_path} ({len(systems):,} systems)")
    return output_path


if __name__ == "__main__":
    export_web_app_data()
