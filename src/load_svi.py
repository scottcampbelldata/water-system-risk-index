"""Load CDC/ATSDR SVI files and filter Ohio county records."""

from __future__ import annotations

import argparse

import pandas as pd

from state_config import target_state_abbrs
from utils import REPO_ROOT, standardize_columns, write_dataframe


def load_svi() -> pd.DataFrame:
    raw_path = REPO_ROOT / "data" / "raw" / "svi" / "SVI2022_US_county.parquet"
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing SVI county parquet: {raw_path}")

    df = standardize_columns(pd.read_parquet(raw_path))
    df = df[df["st_abbr"].isin(target_state_abbrs())].copy()
    df["county_fips"] = df["fips"].astype(str).str.zfill(5)

    keep = [
        "county_fips",
        "county",
        "st_abbr",
        "rpl_themes",
        "rpl_theme1",
        "rpl_theme2",
        "rpl_theme3",
        "rpl_theme4",
        "e_totpop",
    ]
    df = df[keep].rename(
        columns={
            "st_abbr": "state",
            "rpl_themes": "overall_svi_percentile",
            "rpl_theme1": "socioeconomic_svi_percentile",
            "rpl_theme2": "household_characteristics_svi_percentile",
            "rpl_theme3": "racial_ethnic_minority_svi_percentile",
            "rpl_theme4": "housing_transportation_svi_percentile",
            "e_totpop": "svi_county_population",
        }
    )
    for column in [
        "overall_svi_percentile",
        "socioeconomic_svi_percentile",
        "household_characteristics_svi_percentile",
        "racial_ethnic_minority_svi_percentile",
        "housing_transportation_svi_percentile",
    ]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    write_dataframe(df, REPO_ROOT / "data" / "interim" / "svi_2022_ohio_county")
    print(f"svi_2022_ohio_county: rows={len(df):,}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Ohio county SVI records.")
    parser.parse_args()
    load_svi()
