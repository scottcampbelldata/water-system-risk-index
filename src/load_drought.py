"""Load U.S. Drought Monitor county statistics and calculate drought exposure features."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from utils import REPO_ROOT, standardize_columns, write_dataframe


def load_drought() -> pd.DataFrame:
    raw_path = REPO_ROOT / "data" / "raw" / "drought" / "usdm_ohio_county_52w.csv"
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing U.S. Drought Monitor CSV: {raw_path}")

    df = standardize_columns(pd.read_csv(raw_path, dtype={"FIPS": str}))
    df["county_fips"] = df["fips"].astype(str).str.zfill(5)
    for column in ["none", "d0", "d1", "d2", "d3", "d4"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    df["valid_start"] = pd.to_datetime(df["valid_start"], errors="coerce")
    df["severe_drought_flag"] = (df[["d2", "d3", "d4"]].sum(axis=1) > 0).astype(int)
    df["weighted_drought_score"] = (
        df["d0"] * 20 + df["d1"] * 40 + df["d2"] * 65 + df["d3"] * 85 + df["d4"] * 100
    ) / 100

    summary = (
        df.groupby(["county_fips", "county", "state"], as_index=False)
        .agg(
            recent_drought_exposure_score=("weighted_drought_score", "mean"),
            severe_drought_weeks_52w=("severe_drought_flag", "sum"),
            drought_weeks_observed=("valid_start", "nunique"),
            max_d2_plus_area_pct=("d2", "max"),
            max_d3_plus_area_pct=("d3", "max"),
            max_d4_area_pct=("d4", "max"),
        )
        .copy()
    )
    summary["drought_component"] = np.clip(
        summary["recent_drought_exposure_score"] + summary["severe_drought_weeks_52w"] * 1.5,
        0,
        100,
    )
    write_dataframe(df, REPO_ROOT / "data" / "interim" / "usdm_ohio_county_weekly")
    write_dataframe(summary, REPO_ROOT / "data" / "interim" / "usdm_ohio_county_52w")
    print(f"usdm_ohio_county_52w: rows={len(summary):,}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Ohio county U.S. Drought Monitor data.")
    parser.parse_args()
    load_drought()
