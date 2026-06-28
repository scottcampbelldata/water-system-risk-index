"""Score water systems using transparent, configurable component weights."""

from __future__ import annotations

import argparse
from datetime import date

import pandas as pd

from utils import REPO_ROOT, clamp, load_yaml, write_dataframe

COMPONENT_LABELS = {
    "compliance_risk_component": "recent compliance history",
    "enforcement_risk_component": "enforcement history",
    "vulnerability_component": "community vulnerability",
    "drought_component": "recent drought exposure",
    "funding_gap_component": "no recent matched SRF funding record",
    "small_system_component": "small system capacity context",
    "data_quality_penalty": "data quality limitations",
}


def risk_tier(score: float) -> str:
    if score >= 80:
        return "Critical Review"
    if score >= 65:
        return "High Review"
    if score >= 45:
        return "Moderate Review"
    if score >= 25:
        return "Monitor"
    return "Lower Priority"


def small_system_component(population: float) -> float:
    if pd.isna(population):
        return 50
    if population <= 500:
        return 100
    if population <= 3300:
        return 70
    if population <= 10000:
        return 30
    return 0


def funding_gap_component(flag: str, confidence: str) -> float:
    if flag == "recent_matched_project":
        return 0
    if confidence in {"exact_pwsid_match", "exact_name_county_match", "fuzzy_name_county_match"}:
        return 60
    if flag == "unknown_no_staged_srf_record":
        return 35
    return 50


def data_quality_penalty(row: pd.Series) -> float:
    penalty = 0.0
    flags = str(row.get("data_quality_flags", ""))
    if "missing_population_served" in flags:
        penalty += 15
    if "missing_county" in flags:
        penalty += 10
    if row.get("spatial_confidence") == "very_low":
        penalty += 10
    if row.get("spatial_confidence") == "unknown":
        penalty += 20
    if row.get("funding_match_confidence") == "unmatched":
        penalty += 5
    return min(penalty, 100)


def top_drivers(row: pd.Series) -> list[str]:
    # Drivers explain why a system was *prioritized*, so we rank only the
    # positive-weighted components. The data-quality penalty has a negative weight
    # (it lowers the score to avoid over-ranking poorly-documented systems), so it
    # is never a "driver" of higher priority and is excluded from this ranking.
    values = {
        "compliance_risk_component": row.get("compliance_risk_component", 0),
        "enforcement_risk_component": row.get("enforcement_risk_component", 0),
        "vulnerability_component": row.get("vulnerability_component", 0),
        "drought_component": row.get("drought_component", 0),
        "funding_gap_component": row.get("funding_gap_component", 0),
        "small_system_component": row.get("small_system_component", 0),
    }
    ordered = sorted(values.items(), key=lambda item: item[1], reverse=True)
    return [COMPONENT_LABELS[key] for key, value in ordered[:3]]


def explanation_text(row: pd.Series) -> str:
    drivers = [row["top_risk_driver_1"], row["top_risk_driver_2"], row["top_risk_driver_3"]]
    spatial_note = f"Spatial confidence is {str(row['spatial_confidence']).replace('_', ' ')} because {row.get('spatial_limitation_note', 'the best available geography was used')}"
    funding_note = (
        "Funding records were not overclaimed; unmatched SRF data means no recent project was matched in the staged source, not proof that funding never occurred."
        if row.get("funding_match_confidence") == "unmatched"
        else f"Funding match confidence is {row.get('funding_match_confidence')}."
    )
    return (
        f"Ranked {row['risk_tier']} primarily due to {drivers[0]}, {drivers[1]}, and {drivers[2]}. "
        f"{spatial_note}. {funding_note}"
    )


def score_risk() -> pd.DataFrame:
    config = load_yaml(REPO_ROOT / "config" / "scoring_weights.yaml")
    weights = config["overall_weights"]
    master = pd.read_csv(
        REPO_ROOT / "data" / "processed" / "water_system_master.csv", dtype={"pwsid": str, "county_fips": str}
    )
    compliance = pd.read_csv(
        REPO_ROOT / "data" / "processed" / "water_system_compliance_summary.csv", dtype={"pwsid": str}
    )
    enforcement = pd.read_csv(
        REPO_ROOT / "data" / "processed" / "water_system_enforcement_summary.csv", dtype={"pwsid": str}
    )
    funding = pd.read_csv(REPO_ROOT / "data" / "processed" / "water_system_funding_summary.csv", dtype={"pwsid": str})
    geography = pd.read_csv(
        REPO_ROOT / "data" / "processed" / "water_system_geography.csv", dtype={"pwsid": str, "county_fips": str}
    )

    df = (
        master.merge(compliance, on="pwsid", how="left")
        .merge(enforcement, on="pwsid", how="left")
        .merge(funding[["pwsid", "funding_gap_flag", "funding_match_confidence"]], on="pwsid", how="left")
        .merge(
            geography[
                [
                    "pwsid",
                    "spatial_confidence",
                    "spatial_limitation_note",
                    "geo_join_confidence",
                    "vulnerability_component",
                    "drought_component",
                    "overall_svi_percentile",
                    "recent_drought_exposure_score",
                    "severe_drought_weeks_52w",
                ]
            ],
            on="pwsid",
            how="left",
        )
    )

    for column in [
        "compliance_risk_component",
        "enforcement_risk_component",
        "vulnerability_component",
        "drought_component",
    ]:
        df[column] = clamp(pd.to_numeric(df[column], errors="coerce"))
    df["funding_gap_component"] = df.apply(
        lambda row: funding_gap_component(
            str(row.get("funding_gap_flag", "")), str(row.get("funding_match_confidence", ""))
        ),
        axis=1,
    )
    df["small_system_component"] = df["population_served"].map(small_system_component)
    df["data_quality_penalty"] = df.apply(data_quality_penalty, axis=1)

    df["overall_risk_score"] = (
        df["compliance_risk_component"] * weights["compliance_risk_component"]
        + df["enforcement_risk_component"] * weights["enforcement_risk_component"]
        + df["vulnerability_component"] * weights["vulnerability_component"]
        + df["drought_component"] * weights["drought_component"]
        + df["funding_gap_component"] * weights["funding_gap_component"]
        + df["small_system_component"] * weights["small_system_component"]
        + df["data_quality_penalty"] * weights["data_quality_penalty"]
    )
    df["overall_risk_score"] = clamp(df["overall_risk_score"]).round(2)
    df["county"] = df["county"].fillna("Unknown")
    df["risk_tier"] = df["overall_risk_score"].map(risk_tier)
    df["rank_statewide"] = df["overall_risk_score"].rank(method="dense", ascending=False).astype(int)
    df["rank_county"] = df.groupby("county")["overall_risk_score"].rank(method="dense", ascending=False).astype(int)

    drivers = df.apply(top_drivers, axis=1)
    df["top_risk_driver_1"] = drivers.map(lambda values: values[0])
    df["top_risk_driver_2"] = drivers.map(lambda values: values[1])
    df["top_risk_driver_3"] = drivers.map(lambda values: values[2])
    df["model_version"] = config["model"]["version"]
    df["score_date"] = date.today().isoformat()
    df["explanation_text"] = df.apply(explanation_text, axis=1)

    keep = [
        "pwsid",
        "pws_name",
        "state",
        "county",
        "population_served",
        "system_size_class",
        "compliance_risk_component",
        "enforcement_risk_component",
        "vulnerability_component",
        "drought_component",
        "funding_gap_component",
        "small_system_component",
        "data_quality_penalty",
        "overall_risk_score",
        "risk_tier",
        "rank_statewide",
        "rank_county",
        "top_risk_driver_1",
        "top_risk_driver_2",
        "top_risk_driver_3",
        "explanation_text",
        "model_version",
        "score_date",
    ]
    output = df[keep].sort_values(["rank_statewide", "pwsid"]).reset_index(drop=True)
    write_dataframe(output, REPO_ROOT / "data" / "processed" / "water_system_risk_scores")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score Ohio public water systems.")
    parser.parse_args()
    score_risk()
