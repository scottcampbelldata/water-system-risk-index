"""Load and Ohio-filter EPA ECHO SDWA raw files."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import pandas as pd

from utils import REPO_ROOT, standardize_columns, write_dataframe

SDWIS_TABLES = {
    "pub_water_systems": "SDWA_PUB_WATER_SYSTEMS.csv",
    "violations_enforcement": "SDWA_VIOLATIONS_ENFORCEMENT.csv",
    "facilities": "SDWA_FACILITIES.csv",
    "geographic_areas": "SDWA_GEOGRAPHIC_AREAS.csv",
    "service_areas": "SDWA_SERVICE_AREAS.csv",
    "site_visits": "SDWA_SITE_VISITS.csv",
    "ref_code_values": "SDWA_REF_CODE_VALUES.csv",
}


def read_sdwis_table(zip_path: Path, member_name: str, state_prefix: str, chunksize: int) -> pd.DataFrame:
    """Read a SDWIS table from the zip and filter to a state PWSID prefix when possible."""
    with zipfile.ZipFile(zip_path) as archive:
        member = next(name for name in archive.namelist() if name.endswith(member_name))
        with archive.open(member) as file:
            if member_name == "SDWA_REF_CODE_VALUES.csv":
                return standardize_columns(pd.read_csv(file, dtype=str, low_memory=False))

            chunks: list[pd.DataFrame] = []
            for chunk in pd.read_csv(file, dtype=str, chunksize=chunksize, low_memory=False):
                if "PWSID" in chunk.columns:
                    chunk = chunk[chunk["PWSID"].fillna("").str.startswith(state_prefix)]
                # Most chunks of the national file have no rows for the target
                # state; don't retain empty frames until the concat.
                if not chunk.empty:
                    chunks.append(chunk)
    if not chunks:
        return pd.DataFrame()
    return standardize_columns(pd.concat(chunks, ignore_index=True))


def load_sdwis(state_prefix: str = "OH", chunksize: int = 250_000) -> dict[str, pd.DataFrame]:
    zip_path = REPO_ROOT / "data" / "raw" / "echo_sdwis" / "SDWA_latest_downloads.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"Missing SDWA zip: {zip_path}")

    output_dir = REPO_ROOT / "data" / "interim" / "echo_sdwis_ohio"
    outputs: dict[str, pd.DataFrame] = {}
    for table_name, member_name in SDWIS_TABLES.items():
        df = read_sdwis_table(zip_path, member_name, state_prefix, chunksize)
        outputs[table_name] = df
        write_dataframe(df, output_dir / table_name)
        key_nulls = {}
        for key in ["pwsid", "submissionyearquarter", "violation_id", "enforcement_id"]:
            if key in df.columns:
                key_nulls[key] = int(df[key].isna().sum())
        print(f"{table_name}: rows={len(df):,}; key_nulls={key_nulls}")
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Ohio-filtered SDWA files from the ECHO national zip.")
    parser.add_argument("--state-prefix", default="OH")
    parser.add_argument("--chunksize", type=int, default=250_000)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    load_sdwis(state_prefix=args.state_prefix, chunksize=args.chunksize)
