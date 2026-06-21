"""Shared utilities for the water system risk pipeline."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data or {}


def ensure_directories(paths: list[str], base_dir: Path = REPO_ROOT) -> None:
    """Create configured project directories if they do not already exist."""
    for relative_path in paths:
        (base_dir / relative_path).mkdir(parents=True, exist_ok=True)


def snake_case(value: str) -> str:
    """Convert source field names to snake_case."""
    value = value.strip().replace("%", "pct")
    value = re.sub(r"[^0-9A-Za-z]+", "_", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_").lower()


def write_csv(rows: list[dict[str, Any]], path: Path, fieldnames: list[str]) -> None:
    """Write dictionaries to CSV with stable column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    """Read a CSV file if present, otherwise return an empty list."""
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def list_to_pipe(value: Any) -> str:
    """Convert list-like config values into Power BI-friendly pipe-delimited text."""
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)


def parse_submission_quarter(value: Any) -> int:
    """Convert values like 2026Q1 to sortable integers."""
    if pd.isna(value):
        return 0
    text = str(value).strip().upper()
    match = re.match(r"(\d{4})Q([1-4])", text)
    if not match:
        return 0
    return int(match.group(1)) * 10 + int(match.group(2))


def parse_date_series(series: pd.Series) -> pd.Series:
    """Parse common source dates, coercing invalid values to NaT."""
    return pd.to_datetime(series, errors="coerce", format="mixed")


def to_numeric(series: pd.Series) -> pd.Series:
    """Parse numeric source columns with consistent coercion."""
    return pd.to_numeric(series, errors="coerce")


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with snake_case column names."""
    output = df.copy()
    output.columns = [snake_case(str(column)) for column in output.columns]
    return output


def write_dataframe(df: pd.DataFrame, stem: Path, index: bool = False) -> None:
    """Write a DataFrame to CSV and Parquet using the provided path stem."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    csv_path = stem.with_suffix(".csv")
    parquet_path = stem.with_suffix(".parquet")
    df.to_csv(csv_path, index=index)
    df.to_parquet(parquet_path, index=index)
    print(f"Wrote {csv_path} ({len(df)} rows)")
    print(f"Wrote {parquet_path} ({len(df)} rows)")


def clamp(series: pd.Series, lower: float = 0, upper: float = 100) -> pd.Series:
    """Clamp numeric values to a bounded score range."""
    return series.fillna(0).clip(lower=lower, upper=upper)
