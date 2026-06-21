"""Load SRF funding records and prepare PWSID/name/county matching candidates."""

from __future__ import annotations

import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from utils import REPO_ROOT, standardize_columns, write_dataframe


def normalize_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value).upper()
    text = re.sub(r"\b(CITY|VILLAGE|TOWN|TOWNSHIP|COUNTY|WATER|DEPT|DEPARTMENT|AUTHORITY|BOARD|OF|THE)\b", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    columns = {column.lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


def load_staged_srf(raw_path: Path) -> pd.DataFrame:
    if raw_path.suffix.lower() in {".xlsx", ".xls"}:
        return standardize_columns(pd.read_excel(raw_path))
    return standardize_columns(pd.read_csv(raw_path, dtype=str))


def summarize_srf(master: pd.DataFrame | None = None) -> pd.DataFrame:
    raw_csv = REPO_ROOT / "data" / "raw" / "srf" / "epa_srf_public_portal_ohio_projects.csv"
    raw_xlsx = REPO_ROOT / "data" / "raw" / "srf" / "epa_srf_public_portal_ohio_projects.xlsx"
    raw_path = raw_csv if raw_csv.exists() else raw_xlsx if raw_xlsx.exists() else None

    if master is None:
        master_path = REPO_ROOT / "data" / "processed" / "water_system_master.csv"
        if master_path.exists():
            master = pd.read_csv(master_path, dtype={"pwsid": str, "county_fips": str})

    if master is None or master.empty:
        raise FileNotFoundError("water_system_master is required before SRF summarization.")

    base = master[["pwsid", "pws_name", "county", "state"]].copy()

    if raw_path is None:
        output = base.assign(
            recipient_name="",
            total_srf_funding_10y=0.0,
            project_count_10y=0,
            most_recent_project_year=pd.NA,
            years_since_last_funding=pd.NA,
            funding_gap_flag="unknown_no_staged_srf_record",
            funding_match_confidence="unmatched",
            funding_notes="No Ohio SRF portal export was staged; do not interpret this as proof that the system has no SRF funding.",
        )
        write_dataframe(output, REPO_ROOT / "data" / "processed" / "water_system_funding_summary")
        return output

    srf = load_staged_srf(raw_path)
    pwsid_col = find_column(srf, ["pwsid", "pws_id", "public_water_system_id"])
    name_col = find_column(srf, ["recipient_name", "recipient", "borrower_name", "assistance_recipient", "project_sponsor"])
    county_col = find_column(srf, ["county", "county_name"])
    amount_col = find_column(srf, ["assistance_amount", "loan_amount", "funding_amount", "total_assistance", "amount"])
    year_col = find_column(srf, ["project_year", "fiscal_year", "year", "assistance_year"])

    if name_col is None:
        raise ValueError("Staged SRF file must include a recipient/name column.")

    srf["recipient_name"] = srf[name_col].fillna("")
    srf["recipient_norm"] = srf["recipient_name"].map(normalize_name)
    srf["county_norm"] = srf[county_col].fillna("").str.upper().str.replace(" COUNTY", "", regex=False) if county_col else ""
    srf["project_year"] = pd.to_numeric(srf[year_col], errors="coerce") if year_col else pd.NA
    srf["assistance_amount"] = pd.to_numeric(srf[amount_col].replace(r"[\$,]", "", regex=True), errors="coerce").fillna(0) if amount_col else 0
    srf["pwsid"] = srf[pwsid_col].fillna("").str.upper() if pwsid_col else ""

    rows = []
    current_year = pd.Timestamp.today().year
    for _, system in base.iterrows():
        candidates = srf[srf["pwsid"].eq(system["pwsid"])] if pwsid_col else pd.DataFrame()
        confidence = "exact_pwsid_match" if not candidates.empty else "unmatched"
        if candidates.empty:
            county_norm = str(system.get("county", "")).upper().replace(" COUNTY", "")
            system_norm = normalize_name(system["pws_name"])
            county_matches = srf[srf["county_norm"].eq(county_norm)] if county_col else srf
            exact = county_matches[county_matches["recipient_norm"].eq(system_norm)]
            if not exact.empty:
                candidates = exact
                confidence = "exact_name_county_match"
            else:
                scored = county_matches.copy()
                scored["name_score"] = scored["recipient_norm"].map(lambda value: SequenceMatcher(None, system_norm, value).ratio())
                fuzzy = scored[scored["name_score"].ge(0.84)]
                if not fuzzy.empty:
                    candidates = fuzzy
                    confidence = "fuzzy_name_county_match"
                elif not county_matches.empty:
                    candidates = county_matches.iloc[0:0]
                    confidence = "unmatched"

        recent = candidates[candidates["project_year"].ge(current_year - 10)] if not candidates.empty and "project_year" in candidates else candidates
        total = float(recent["assistance_amount"].sum()) if not recent.empty else 0.0
        project_count = int(len(recent))
        most_recent_year = int(recent["project_year"].max()) if not recent.empty and pd.notna(recent["project_year"].max()) else pd.NA
        years_since = current_year - most_recent_year if pd.notna(most_recent_year) else pd.NA
        rows.append(
            {
                "pwsid": system["pwsid"],
                "pws_name": system["pws_name"],
                "recipient_name": " | ".join(sorted(set(recent["recipient_name"]))) if not recent.empty else "",
                "county": system["county"],
                "state": system["state"],
                "total_srf_funding_10y": total,
                "project_count_10y": project_count,
                "most_recent_project_year": most_recent_year,
                "years_since_last_funding": years_since,
                "funding_gap_flag": "possible_gap_no_recent_matched_project" if project_count == 0 else "recent_matched_project",
                "funding_match_confidence": confidence,
                "funding_notes": "SRF match is based on staged portal export and matching confidence; unmatched records are not proof of no funding.",
            }
        )

    output = pd.DataFrame(rows)
    write_dataframe(output, REPO_ROOT / "data" / "processed" / "water_system_funding_summary")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize staged Ohio SRF records.")
    parser.parse_args()
    summarize_srf()
