"""Fairness / bias audit for the review-priority score.

Social vulnerability (CDC/ATSDR SVI) is both a model *input* (20% weight, by design)
and a *fairness axis*. The concern: is the model simply re-flagging vulnerable
communities, or do high-vulnerability systems also carry genuine compliance signal?

This examines (1) how strongly the score tracks SVI, (2) whether the objective
compliance signal is itself correlated with SVI (independent of the vulnerability
input), and (3) high-review rates across SVI quartiles. The intended use is
directing *support and funding* (where prioritizing under-resourced communities is
appropriate), not enforcement targeting.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from utils import REPO_ROOT, load_yaml


def _corr(a: pd.Series, b: pd.Series) -> float:
    mask = a.notna() & b.notna()
    if mask.sum() < 2:
        return float("nan")
    return round(float(np.corrcoef(a[mask], b[mask])[0, 1]), 4)


def run_fairness_audit() -> dict:
    risk = pd.read_csv(REPO_ROOT / "data" / "processed" / "water_system_risk_scores.csv", dtype={"pwsid": str})
    geo = pd.read_csv(REPO_ROOT / "data" / "processed" / "water_system_geography.csv", dtype={"pwsid": str})
    df = risk.merge(geo[["pwsid", "overall_svi_percentile"]], on="pwsid", how="left")
    df = df[df["overall_svi_percentile"].notna()].copy()

    # Read the weight from the single source of truth so this audit stays correct
    # if the vulnerability weight is retuned.
    weights = load_yaml(REPO_ROOT / "config" / "scoring_weights.yaml")["overall_weights"]
    df["score_excl_vulnerability"] = (
        df["overall_risk_score"] - df["vulnerability_component"] * weights["vulnerability_component"]
    )

    high = df["risk_tier"].isin(["Critical Review", "High Review"])
    df["svi_quartile"] = pd.qcut(df["overall_svi_percentile"], 4, labels=["Q1 (least)", "Q2", "Q3", "Q4 (most)"])
    by_quartile = (
        df.assign(high_review=high)
        .groupby("svi_quartile", observed=True)
        .agg(
            systems=("pwsid", "count"),
            high_review_rate=("high_review", "mean"),
            mean_score=("overall_risk_score", "mean"),
        )
        .reset_index()
    )

    report = {
        "note": "SVI is an intended input (equity weighting) and a fairness axis. This tool is for directing support/funding, not enforcement targeting.",
        "correlations_with_svi": {
            "overall_score": _corr(df["overall_risk_score"], df["overall_svi_percentile"]),
            "compliance_component_only": _corr(df["compliance_risk_component"], df["overall_svi_percentile"]),
            "score_excluding_vulnerability_input": _corr(df["score_excl_vulnerability"], df["overall_svi_percentile"]),
        },
        "high_review_mean_svi": round(float(df.loc[high, "overall_svi_percentile"].mean()), 4),
        "overall_mean_svi": round(float(df["overall_svi_percentile"].mean()), 4),
        "by_svi_quartile": [
            {
                "quartile": str(row.svi_quartile),
                "systems": int(row.systems),
                "high_review_rate": round(float(row.high_review_rate), 4),
                "mean_score": round(float(row.mean_score), 2),
            }
            for row in by_quartile.itertuples(index=False)
        ],
    }
    (REPO_ROOT / "data" / "processed" / "fairness_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run_fairness_audit()
