"""Create the water system master table from standardized SDWA inventory records."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from utils import REPO_ROOT, parse_date_series, parse_submission_quarter, to_numeric, write_dataframe


STATE_FIPS = {"OH": "39"}


def read_interim(name: str) -> pd.DataFrame:
    path = REPO_ROOT / "data" / "interim" / "echo_sdwis_ohio" / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing interim SDWA table: {path}")
    return pd.read_parquet(path)


def ref_lookup(ref: pd.DataFrame, value_type: str) -> dict[str, str]:
    if ref.empty:
        return {}
    subset = ref[ref["value_type"].eq(value_type)]
    return dict(zip(subset["value_code"].astype(str), subset["value_description"].astype(str)))


def size_class(population: float) -> str:
    if pd.isna(population):
        return "unknown"
    if population <= 500:
        return "very_small"
    if population <= 3300:
        return "small"
    if population <= 10000:
        return "medium"
    return "large"


def build_geo_lookup(geo: pd.DataFrame) -> pd.DataFrame:
    if geo.empty:
        return pd.DataFrame(columns=["pwsid", "county", "county_fips", "city"])
    geo = geo.copy()
    geo["submission_sort"] = geo["submissionyearquarter"].map(parse_submission_quarter)
    geo["county_fips_candidate"] = geo["ansi_entity_code"].fillna("").astype(str).str.extract(r"(\d+)")[0].str.zfill(3)
    geo["county_fips_candidate"] = geo["county_fips_candidate"].where(
        geo["county_fips_candidate"].str.len().eq(3), pd.NA
    )

    counties = geo[geo["area_type_code"].eq("CN")].copy()
    counties["county"] = counties["county_served"].fillna("").str.title()
    counties["county_fips"] = STATE_FIPS["OH"] + counties["county_fips_candidate"].fillna("")
    counties.loc[counties["county_fips"].str.len().ne(5), "county_fips"] = pd.NA
    county_summary = (
        counties.sort_values(["pwsid", "submission_sort"], ascending=[True, False])
        .groupby("pwsid", as_index=False)
        .agg(
            county=("county", lambda values: " | ".join(sorted({v for v in values if v}))),
            county_fips=("county_fips", "first"),
        )
    )

    cities = geo[geo["area_type_code"].eq("CT")].copy()
    city_summary = (
        cities.sort_values(["pwsid", "submission_sort"], ascending=[True, False])
        .groupby("pwsid", as_index=False)
        .agg(city=("city_served", lambda values: " | ".join(sorted({str(v).title() for v in values if pd.notna(v)}))))
    )
    return county_summary.merge(city_summary, on="pwsid", how="outer")


def build_master() -> pd.DataFrame:
    pws = read_interim("pub_water_systems")
    geo = read_interim("geographic_areas")
    ref = read_interim("ref_code_values")

    service_path = REPO_ROOT / "data" / "interim" / "service_areas_ohio.parquet"
    service = pd.read_parquet(service_path) if service_path.exists() else pd.DataFrame(columns=["pwsid", "spatial_confidence"])

    pws = pws.copy()
    pws["submission_sort"] = pws["submissionyearquarter"].map(parse_submission_quarter)
    for column in ["first_reported_date", "last_reported_date", "pws_deactivation_date"]:
        if column in pws.columns:
            pws[column] = parse_date_series(pws[column])
    pws["population_served"] = to_numeric(pws["population_served_count"])
    pws["service_connections"] = to_numeric(pws["service_connections_count"])

    first_last = (
        pws.groupby("pwsid", as_index=False)
        .agg(first_seen_date=("first_reported_date", "min"), last_seen_date=("last_reported_date", "max"))
        .copy()
    )
    latest = pws.sort_values(["pwsid", "submission_sort"], ascending=[True, False]).drop_duplicates("pwsid")
    geo_lookup = build_geo_lookup(geo)

    owner_map = ref_lookup(ref, "OWNER_TYPE_CODE")
    source_map = ref_lookup(ref, "PRIMARY_SOURCE_CODE")
    type_map = {
        "CWS": "Community water system",
        "TNCWS": "Transient non-community water system",
        "NTNCWS": "Non-transient non-community water system",
    }
    activity_map = {"A": "Active", "I": "Inactive", "N": "Changed from public to non-public", "M": "Merged", "P": "Potential future"}

    master = latest.merge(first_last, on="pwsid", how="left").merge(geo_lookup, on="pwsid", how="left")
    service_conf = service[["pwsid", "spatial_confidence"]].drop_duplicates("pwsid") if not service.empty else service
    master = master.merge(service_conf.rename(columns={"spatial_confidence": "service_area_spatial_confidence"}), on="pwsid", how="left")

    master["state"] = "OH"
    master["county"] = master["county"].fillna("")
    master["city"] = master["city"].fillna(master.get("city_name", "")).fillna("").str.title()
    master["system_type"] = master["pws_type_code"].map(type_map).fillna(master["pws_type_code"])
    master["owner_type"] = master["owner_type_code"].map(owner_map).fillna(master["owner_type_code"])
    master["primary_source_water_type"] = master["primary_source_code"].map(source_map).fillna(master["primary_source_code"])
    master["activity_status"] = master["pws_activity_code"].map(activity_map).fillna(master["pws_activity_code"])
    master["system_size_class"] = master["population_served"].map(size_class)
    master["is_small_system"] = master["population_served"].le(3300).fillna(False)
    master["is_very_small_system"] = master["population_served"].le(500).fillna(False)
    master["spatial_confidence"] = master["service_area_spatial_confidence"].fillna(
        master["county_fips"].notna().map(lambda value: "low" if value else "unknown")
    )

    def flags(row: pd.Series) -> str:
        values = []
        if pd.isna(row["population_served"]):
            values.append("missing_population_served")
        if not row["county"]:
            values.append("missing_county")
        if row["spatial_confidence"] in {"low", "unknown"}:
            values.append(f"{row['spatial_confidence']}_spatial_confidence")
        if row["activity_status"] != "Active":
            values.append("inactive_or_non_active_status")
        return " | ".join(values) if values else "none"

    master["data_quality_flags"] = master.apply(flags, axis=1)

    keep = [
        "pwsid",
        "pws_name",
        "state",
        "county",
        "county_fips",
        "city",
        "system_type",
        "owner_type",
        "primary_source_water_type",
        "population_served",
        "service_connections",
        "activity_status",
        "system_size_class",
        "is_small_system",
        "is_very_small_system",
        "first_seen_date",
        "last_seen_date",
        "spatial_confidence",
        "data_quality_flags",
    ]
    output = master[keep].sort_values("pwsid").reset_index(drop=True)
    write_dataframe(output, REPO_ROOT / "data" / "processed" / "water_system_master")
    print(f"water_system_master: rows={len(output):,}; duplicate_pwsid={int(output.duplicated('pwsid').sum())}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build water_system_master.")
    parser.parse_args()
    build_master()
