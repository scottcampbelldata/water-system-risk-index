"""Export star-schema-friendly CSV files for Power BI."""

from __future__ import annotations

import argparse

import pandas as pd

from utils import REPO_ROOT


def export_powerbi() -> None:
    processed = REPO_ROOT / "data" / "processed"
    powerbi = REPO_ROOT / "data" / "powerbi"
    powerbi.mkdir(parents=True, exist_ok=True)

    master = pd.read_csv(processed / "water_system_master.csv", dtype={"pwsid": str})
    compliance = pd.read_csv(processed / "water_system_compliance_summary.csv", dtype={"pwsid": str})
    enforcement = pd.read_csv(processed / "water_system_enforcement_summary.csv", dtype={"pwsid": str})
    funding = pd.read_csv(processed / "water_system_funding_summary.csv", dtype={"pwsid": str})
    geography = pd.read_csv(processed / "water_system_geography.csv", dtype={"pwsid": str, "county_fips": str})
    risk = pd.read_csv(processed / "water_system_risk_scores.csv", dtype={"pwsid": str})
    dqr = pd.read_csv(processed / "data_quality_report.csv")

    exports = {
        "DimWaterSystem.csv": master,
        "FactViolationsSummary.csv": compliance,
        "FactEnforcementSummary.csv": enforcement,
        "FactFundingSummary.csv": funding,
        "DimGeography.csv": geography,
        "FactRiskScores.csv": risk,
        "DataQualityReport.csv": dqr,
        "DimRiskTier.csv": pd.DataFrame(
            [
                {"risk_tier": "Critical Review", "sort_order": 1, "minimum_score": 80},
                {"risk_tier": "High Review", "sort_order": 2, "minimum_score": 65},
                {"risk_tier": "Moderate Review", "sort_order": 3, "minimum_score": 45},
                {"risk_tier": "Monitor", "sort_order": 4, "minimum_score": 25},
                {"risk_tier": "Lower Priority", "sort_order": 5, "minimum_score": 0},
            ]
        ),
    }

    dates = pd.DataFrame({"date": pd.date_range(risk["score_date"].min(), risk["score_date"].max(), freq="D")})
    dates["year"] = dates["date"].dt.year
    dates["quarter"] = dates["date"].dt.quarter
    dates["month"] = dates["date"].dt.month
    exports["DimDate.csv"] = dates

    for filename, df in exports.items():
        path = powerbi / filename
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Power BI-ready CSV files.")
    parser.parse_args()
    export_powerbi()
