"""Build compliance, enforcement, funding, geography, vulnerability, and drought features."""

from __future__ import annotations

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd

from geography_tiers import LIMITATION_NOTES, TIER_TO_CONFIDENCE
from load_srf import summarize_srf
from state_config import target_state_fips
from utils import REPO_ROOT, clamp, parse_date_series, write_dataframe

VALID_OPEN_STATUSES = {"Addressed", "Unaddressed"}


def read_processed(name: str) -> pd.DataFrame:
    return pd.read_csv(REPO_ROOT / "data" / "processed" / f"{name}.csv", dtype={"pwsid": str, "county_fips": str})


def read_interim(name: str) -> pd.DataFrame:
    return pd.read_parquet(REPO_ROOT / "data" / "interim" / "echo_sdwis_ohio" / f"{name}.parquet")


def months_ago(months: int) -> pd.Timestamp:
    return pd.Timestamp.today().normalize() - pd.DateOffset(months=months)


def violation_base() -> pd.DataFrame:
    viol = read_interim("violations_enforcement")
    if viol.empty:
        return viol
    viol = viol.copy()
    for column in [
        "non_compl_per_begin_date",
        "non_compl_per_end_date",
        "calculated_rtc_date",
        "viol_first_reported_date",
        "viol_last_reported_date",
    ]:
        viol[column] = parse_date_series(viol[column])
    viol["violation_event_date"] = viol["non_compl_per_begin_date"].fillna(viol["viol_first_reported_date"])
    viol["is_open_violation"] = viol["violation_status"].isin(VALID_OPEN_STATUSES)
    viol["is_resolved"] = viol["violation_status"].eq("Resolved")
    viol["is_health_based"] = viol["is_health_based_ind"].eq("Y")
    viol["is_monitoring_reporting"] = viol["violation_category_code"].isin(["MR", "MON", "RPT"])
    viol["is_major_mr"] = viol["is_major_viol_ind"].eq("Y")

    severity = np.select(
        [
            viol["is_health_based"] & viol["is_open_violation"],
            viol["violation_category_code"].isin(["MCL", "MRDL"]),
            viol["violation_category_code"].eq("TT"),
            viol["is_monitoring_reporting"] & viol["is_major_mr"],
            viol["is_monitoring_reporting"],
            viol["violation_status"].eq("Archived"),
        ],
        [100, 90, 85, 55, 35, 10],
        default=25,
    )
    viol["violation_severity_score"] = severity
    return viol.drop_duplicates(["pwsid", "violation_id"])


def build_compliance_summary(master: pd.DataFrame) -> pd.DataFrame:
    viol = violation_base()
    rows = []
    today = pd.Timestamp.today().normalize()
    # Compute the window cutoffs once (not per-row) for determinism and speed.
    cutoff_12, cutoff_36, cutoff_60, cutoff_72 = (months_ago(m) for m in (12, 36, 60, 72))
    # Group violations by PWSID once; an O(n) lookup per system instead of an
    # O(n*m) full-frame scan (matters once the pipeline scales past Ohio).
    by_pwsid = dict(tuple(viol.groupby("pwsid"))) if not viol.empty else {}
    empty = viol.iloc[0:0] if not viol.empty else pd.DataFrame()
    for _, system in master.iterrows():
        records = by_pwsid.get(system["pwsid"], empty)
        recent12 = records[records["violation_event_date"].ge(cutoff_12)]
        recent36 = records[records["violation_event_date"].ge(cutoff_36)]
        recent60 = records[records["violation_event_date"].ge(cutoff_60)]
        # Compare the most-recent 36 months against the prior 36 months
        # (cutoff_72..cutoff_36) so the trend is an apples-to-apples, equal-length
        # window comparison rather than 36m vs a shorter 24m window.
        previous36 = records[
            records["violation_event_date"].lt(cutoff_36) & records["violation_event_date"].ge(cutoff_72)
        ]
        last_date = records["violation_event_date"].max() if not records.empty else pd.NaT
        repeat_count = (
            int(recent60.duplicated(["violation_code", "contaminant_code"], keep=False).sum())
            if not recent60.empty
            else 0
        )
        open_flag = bool(recent60["is_open_violation"].any()) if not recent60.empty else False
        component = min(
            100,
            len(recent36) * 5
            + int(recent36["is_health_based"].sum()) * 12
            + int(recent36["is_monitoring_reporting"].sum()) * 3
            + repeat_count * 4
            + (20 if open_flag else 0)
            + (float(recent60["violation_severity_score"].max()) * 0.25 if not recent60.empty else 0),
        )
        rows.append(
            {
                "pwsid": system["pwsid"],
                "total_violations_12m": int(len(recent12)),
                "total_violations_36m": int(len(recent36)),
                "total_violations_60m": int(len(recent60)),
                "health_based_violations_36m": int(recent36["is_health_based"].sum()) if not recent36.empty else 0,
                "monitoring_reporting_violations_36m": int(recent36["is_monitoring_reporting"].sum())
                if not recent36.empty
                else 0,
                "repeat_violation_count_60m": repeat_count,
                "max_violation_severity": float(recent60["violation_severity_score"].max())
                if not recent60.empty
                else 0,
                "days_since_last_violation": int((today - last_date).days) if pd.notna(last_date) else pd.NA,
                "returned_to_compliance_flag": bool(recent60["is_resolved"].any()) if not recent60.empty else False,
                "open_violation_flag": open_flag,
                "violation_trend_direction": "increasing"
                if len(recent36) > len(previous36)
                else "decreasing"
                if len(recent36) < len(previous36)
                else "stable_or_none",
                "compliance_risk_component": round(component, 2),
            }
        )
    output = pd.DataFrame(rows)
    write_dataframe(output, REPO_ROOT / "data" / "processed" / "water_system_compliance_summary")
    return output


def build_enforcement_summary(master: pd.DataFrame) -> pd.DataFrame:
    raw = read_interim("violations_enforcement")
    if raw.empty:
        raw = pd.DataFrame(columns=["pwsid", "enforcement_id", "enforcement_date", "enf_action_category"])
    enf = raw[raw["enforcement_id"].notna()].copy()
    if not enf.empty:
        enf["enforcement_date"] = parse_date_series(enf["enforcement_date"])
        enf = enf.drop_duplicates(["pwsid", "enforcement_id"])
    today = pd.Timestamp.today().normalize()
    cutoff_36, cutoff_60 = months_ago(36), months_ago(60)
    by_pwsid = dict(tuple(enf.groupby("pwsid"))) if not enf.empty else {}
    empty = enf.iloc[0:0] if not enf.empty else pd.DataFrame()

    rows = []
    for _, system in master.iterrows():
        records = by_pwsid.get(system["pwsid"], empty)
        recent36 = records[records["enforcement_date"].ge(cutoff_36)]
        recent60 = records[records["enforcement_date"].ge(cutoff_60)]
        formal = int(recent60["enf_action_category"].eq("Formal").sum()) if not recent60.empty else 0
        informal = int(recent60["enf_action_category"].eq("Informal").sum()) if not recent60.empty else 0
        penalty = (
            int(recent60["enforcement_action_type_code"].fillna("").str.contains("PEN|PN", case=False).sum())
            if not recent60.empty
            else 0
        )
        last_date = records["enforcement_date"].max() if not records.empty else pd.NaT
        component = min(
            100, len(recent36) * 8 + formal * 16 + informal * 5 + penalty * 20 + (10 if len(recent36) else 0)
        )
        rows.append(
            {
                "pwsid": system["pwsid"],
                "enforcement_actions_36m": int(len(recent36)),
                "formal_actions_60m": formal,
                "informal_actions_60m": informal,
                "penalty_count_60m": penalty,
                "recent_enforcement_flag": bool(len(recent36)),
                "days_since_last_enforcement": int((today - last_date).days) if pd.notna(last_date) else pd.NA,
                "enforcement_risk_component": round(component, 2),
            }
        )
    output = pd.DataFrame(rows)
    write_dataframe(output, REPO_ROOT / "data" / "processed" / "water_system_enforcement_summary")
    return output


def county_centroids() -> pd.DataFrame:
    counties = gpd.read_file(f"zip://{REPO_ROOT / 'data' / 'raw' / 'tiger' / 'tl_2025_us_county.zip'}")
    counties = counties[counties["STATEFP"].isin(target_state_fips())].copy()
    projected = counties.to_crs(5070)
    centroids = gpd.GeoSeries(projected.geometry.centroid, crs=5070).to_crs(4326)
    return pd.DataFrame(
        {
            "county_fips": counties["GEOID"].astype(str),
            "county_centroid_latitude": centroids.y.values,
            "county_centroid_longitude": centroids.x.values,
            "county_name_tiger": counties["NAME"].astype(str) + " County",
        }
    )


def build_geography(master: pd.DataFrame) -> pd.DataFrame:
    service_path = REPO_ROOT / "data" / "interim" / "service_areas_ohio.parquet"
    service = pd.read_parquet(service_path) if service_path.exists() else pd.DataFrame()
    centroids = county_centroids()
    svi = pd.read_parquet(REPO_ROOT / "data" / "interim" / "svi_2022_ohio_county.parquet")
    drought = pd.read_parquet(REPO_ROOT / "data" / "interim" / "usdm_ohio_county_52w.parquet")

    geo = master[["pwsid", "county", "county_fips"]].merge(centroids, on="county_fips", how="left")

    # build_geography is the single authority for the FINAL geometry source tier and
    # spatial confidence: service-area boundary matches take priority, then county
    # centroid fallback, then unmatched. (clean_water_systems only carried a preliminary signal.)
    service_cols = [
        "pwsid",
        "geometry_source_tier",
        "boundary_type",
        "boundary_provider",
        "match_method",
        "area_sqkm",
        "latitude",
        "longitude",
        "geometry_source",
    ]
    if not service.empty:
        service_keep = service[[c for c in service_cols if c in service.columns]].drop_duplicates("pwsid")
        geo = geo.merge(service_keep, on="pwsid", how="left")
    for column in service_cols:
        if column not in geo.columns:
            geo[column] = pd.NA

    matched = geo["geometry_source_tier"].notna()
    has_county = geo["county_fips"].notna() & (geo["county_fips"].astype(str).str.len() > 0)

    # Resolve tier for unmatched systems: county centroid where a county is known, else unmatched.
    geo.loc[~matched & has_county, "geometry_source_tier"] = "county_centroid"
    geo.loc[~matched & ~has_county, "geometry_source_tier"] = "unmatched"

    # Coordinates: service-area centroid for matched; county centroid for county fallback; none otherwise.
    geo["latitude"] = geo["latitude"].fillna(geo["county_centroid_latitude"].where(has_county))
    geo["longitude"] = geo["longitude"].fillna(geo["county_centroid_longitude"].where(has_county))

    geo["service_area_available_flag"] = matched
    geo["geometry_type"] = np.select(
        [matched, geo["geometry_source_tier"].eq("county_centroid")],
        ["service_area_polygon", "county_centroid"],
        default="none",
    )
    geo["geometry_source"] = geo["geometry_source"].fillna(
        pd.Series(np.where(has_county, "Census TIGER county centroid fallback", "none"), index=geo.index)
    )
    geo["match_method"] = geo["match_method"].fillna(
        pd.Series(np.where(has_county, "county_fips", "none"), index=geo.index)
    )
    geo["tract_geoid"] = pd.NA
    geo["spatial_confidence"] = geo["geometry_source_tier"].map(TIER_TO_CONFIDENCE)
    geo["spatial_limitation_note"] = (
        geo["geometry_source_tier"].map(LIMITATION_NOTES).fillna("Geometry source is screening-level context only.")
    )
    geo["geo_join_confidence"] = np.select(
        [matched, geo["geometry_source_tier"].eq("county_centroid")],
        ["exact_pwsid", "county_fallback"],
        default="none",
    )

    geo = geo.merge(svi, on="county_fips", how="left").merge(
        drought[
            [
                "county_fips",
                "recent_drought_exposure_score",
                "severe_drought_weeks_52w",
                "drought_component",
            ]
        ],
        on="county_fips",
        how="left",
    )
    geo["vulnerability_component"] = clamp(geo["overall_svi_percentile"] * 100)
    geo["drought_component"] = clamp(geo["drought_component"])

    keep = [
        "pwsid",
        "geometry_type",
        "geometry_source_tier",
        "boundary_type",
        "boundary_provider",
        "match_method",
        "area_sqkm",
        "latitude",
        "longitude",
        "county_fips",
        "tract_geoid",
        "service_area_available_flag",
        "geometry_source",
        "spatial_confidence",
        "spatial_limitation_note",
        "geo_join_confidence",
        "overall_svi_percentile",
        "socioeconomic_svi_percentile",
        "household_characteristics_svi_percentile",
        "racial_ethnic_minority_svi_percentile",
        "housing_transportation_svi_percentile",
        "recent_drought_exposure_score",
        "severe_drought_weeks_52w",
        "drought_component",
        "vulnerability_component",
    ]
    output = geo[keep]
    write_dataframe(output, REPO_ROOT / "data" / "processed" / "water_system_geography")
    return output


def build_all_features() -> dict[str, pd.DataFrame]:
    master = read_processed("water_system_master")
    outputs = {
        "compliance": build_compliance_summary(master),
        "enforcement": build_enforcement_summary(master),
        "geography": build_geography(master),
    }
    outputs["funding"] = summarize_srf(master)
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build processed feature tables.")
    parser.parse_args()
    build_all_features()
