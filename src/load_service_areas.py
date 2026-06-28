"""Load EPA public water system service area boundaries.

Preserves the real polygon geometry (previous versions discarded it and kept only
centroids). Produces three artifacts:

  1. data/interim/service_area_boundaries_audit.parquet   (GeoParquet, ORIGINAL geometry)
  2. data/interim/service_area_boundaries_web.parquet      (simplified GeoJSON per PWSID)
  3. data/interim/service_areas_ohio.parquet               (tabular attributes + centroid)

plus data/interim/service_area_simplification_report.json (simplification QA stats).

Classification uses the EPA ``Symbology_Field``:
  "System Sourced" -> verified_service_area_boundary (system/state/local sourced)
  "Modeled"        -> modeled_service_area_boundary  (EPA-modeled, NOT verified)
"""

from __future__ import annotations

import argparse
import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from geography_tiers import TIER_TO_CONFIDENCE
from utils import REPO_ROOT, standardize_columns

RAW_PATH = REPO_ROOT / "data" / "raw" / "service_areas" / "epa_pws_service_areas_ohio.geojson"
EQUAL_AREA_CRS = 5070  # CONUS Albers, metres
WGS84 = 4326

# Candidate simplification tolerances in metres (largest first).
TOLERANCE_CANDIDATES = [150.0, 100.0, 50.0, 25.0, 10.0, 5.0]
AREA_DELTA_THRESHOLD = 0.05  # 5% per-polygon area change is "too much"
MAX_FRACTION_OVER = 0.02  # at most 2% of polygons may exceed the threshold


def _classify_tier(symbology: str) -> str:
    value = (symbology or "").strip().lower()
    if value == "system sourced":
        return "verified_service_area_boundary"
    return "modeled_service_area_boundary"


def _pick_tolerance(projected: gpd.GeoSeries) -> tuple[float, dict]:
    """Choose the largest tolerance whose area-delta stays within bounds."""
    original_area = projected.area
    chosen = TOLERANCE_CANDIDATES[-1]
    chosen_stats: dict | None = None
    for tolerance in TOLERANCE_CANDIDATES:
        simplified = projected.simplify(tolerance, preserve_topology=True)
        simplified_area = simplified.area
        delta = (original_area - simplified_area).abs() / original_area.replace(0, pd.NA)
        delta = delta.fillna(0.0)
        over = int((delta > AREA_DELTA_THRESHOLD).sum())
        fraction_over = over / len(delta) if len(delta) else 0.0
        stats = {
            "tolerance_m": tolerance,
            "avg_area_delta": float(delta.mean()),
            "max_area_delta": float(delta.max()),
            "count_over_threshold": over,
            "fraction_over_threshold": round(fraction_over, 5),
        }
        if fraction_over <= MAX_FRACTION_OVER:
            return tolerance, stats
        chosen, chosen_stats = tolerance, stats
    # None met the bound; use the smallest (most faithful) tolerance.
    return chosen, chosen_stats or stats


def load_service_areas() -> pd.DataFrame:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Missing EPA service area GeoJSON: {RAW_PATH}")

    gdf = gpd.read_file(RAW_PATH)
    raw_feature_count = len(gdf)
    gdf = standardize_columns(gdf)  # title-case -> snake_case (PWSID->pwsid, Symbology_Field->symbology_field)

    required = ["pwsid", "symbology_field"]
    missing = [column for column in required if column not in gdf.columns]
    if missing:
        raise KeyError(f"Service area GeoJSON missing expected columns after normalization: {missing}")

    gdf["pwsid"] = gdf["pwsid"].astype(str).str.upper().str.strip()
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    unique_pwsid_count = gdf["pwsid"].nunique()

    # --- Correction #2: defensive dissolve so there is exactly one geometry per PWSID ---
    duplicate_pwsids = gdf["pwsid"].value_counts()
    duplicate_pwsids = duplicate_pwsids[duplicate_pwsids > 1]
    duplicates_handled = int(duplicate_pwsids.sum() - len(duplicate_pwsids)) if len(duplicate_pwsids) else 0
    # Capture lineage with a stable rule before the geometry union.
    attribute_cols = [c for c in gdf.columns if c != "geometry"]
    attributes = gdf.sort_values("pwsid")[attribute_cols].groupby("pwsid", as_index=False).first()
    dissolved = gdf.dissolve(by="pwsid", as_index=False, aggfunc="first")[["pwsid", "geometry"]]
    dissolved = dissolved.merge(
        attributes.drop(columns=[c for c in attributes.columns if c == "geometry"], errors="ignore"),
        on="pwsid",
        how="left",
    )
    dissolved_count = len(dissolved)

    dissolved["geometry_source_tier"] = dissolved["symbology_field"].map(_classify_tier)
    dissolved["boundary_type"] = dissolved["geometry_source_tier"].map(
        {"verified_service_area_boundary": "system_sourced", "modeled_service_area_boundary": "modeled"}
    )
    dissolved["spatial_confidence"] = dissolved["geometry_source_tier"].map(TIER_TO_CONFIDENCE)
    dissolved = gpd.GeoDataFrame(dissolved, geometry="geometry", crs=gdf.crs)

    # --- Correction #4: adaptive simplification with area-delta QA ---
    projected = dissolved.to_crs(EQUAL_AREA_CRS)
    original_area = projected.geometry.area
    tolerance, qa_stats = _pick_tolerance(projected.geometry)
    simplified_proj = projected.geometry.simplify(tolerance, preserve_topology=True)
    simplified_area = simplified_proj.area
    simplified_wgs = gpd.GeoSeries(simplified_proj, crs=EQUAL_AREA_CRS).to_crs(WGS84)
    centroids_wgs = gpd.GeoSeries(projected.geometry.centroid, crs=EQUAL_AREA_CRS).to_crs(WGS84)

    dissolved["area_sqkm"] = (original_area / 1_000_000).round(4).values
    dissolved["area_sqkm_simplified"] = (simplified_area.values / 1_000_000).round(4)
    dissolved["latitude"] = centroids_wgs.y.round(6).values
    dissolved["longitude"] = centroids_wgs.x.round(6).values
    dissolved["match_method"] = "exact_pwsid"
    dissolved["geometry_source"] = "EPA Public Water System Service Area FeatureServer"

    lineage_cols = {
        "data_provider_type": "boundary_provider",
        "model_method": "model_method",
        "service_area_type": "service_area_type",
        "original_data_created_date": "boundary_created_date",
    }
    for source_col, target_col in lineage_cols.items():
        dissolved[target_col] = dissolved[source_col] if source_col in dissolved.columns else None

    # --- Correction #3: audit artifact with ORIGINAL geometry (GeoParquet) ---
    interim = REPO_ROOT / "data" / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    audit = dissolved.copy()
    audit_path = interim / "service_area_boundaries_audit.parquet"
    audit.to_parquet(audit_path)

    # --- Web artifact: simplified GeoJSON geometry per PWSID ---
    web = pd.DataFrame(
        {
            "pwsid": dissolved["pwsid"].values,
            "geometry_source_tier": dissolved["geometry_source_tier"].values,
            "boundary_type": dissolved["boundary_type"].values,
            "boundary_provider": dissolved["boundary_provider"].values,
            "model_method": dissolved["model_method"].values,
            "match_method": dissolved["match_method"].values,
            "area_sqkm": dissolved["area_sqkm"].values,
            "area_sqkm_simplified": dissolved["area_sqkm_simplified"].values,
            "geometry_geojson": [json.dumps(mapping(geom), separators=(",", ":")) for geom in simplified_wgs.values],
        }
    )
    web_path = interim / "service_area_boundaries_web.parquet"
    web.to_parquet(web_path, index=False)

    # --- Tabular artifact: attributes + centroid (no geometry), for master/geography joins ---
    tabular_cols = [
        "pwsid",
        "pws_name",
        "primacy_agency",
        "population_served_count",
        "service_connections_count",
        "service_area_type",
        "boundary_provider",
        "model_method",
        "geometry_source_tier",
        "boundary_type",
        "spatial_confidence",
        "area_sqkm",
        "match_method",
        "latitude",
        "longitude",
        "geometry_source",
        "boundary_created_date",
    ]
    tabular = pd.DataFrame(dissolved.drop(columns="geometry"))
    tabular = tabular[[c for c in tabular_cols if c in tabular.columns]]
    tabular["service_area_available_flag"] = True
    tabular_path = interim / "service_areas_ohio.parquet"
    tabular.to_parquet(tabular_path, index=False)
    tabular.to_csv(interim / "service_areas_ohio.csv", index=False)

    # --- Simplification + dissolve report for validate_outputs ---
    report = {
        "raw_feature_count": int(raw_feature_count),
        "unique_pwsid_count": int(unique_pwsid_count),
        "dissolved_output_count": int(dissolved_count),
        "duplicate_pwsids_handled": duplicates_handled,
        "tier_counts": dissolved["geometry_source_tier"].value_counts().to_dict(),
        "simplification": qa_stats,
        "area_delta_threshold": AREA_DELTA_THRESHOLD,
    }
    report_path = interim / "service_area_simplification_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"service_areas: raw={raw_feature_count} unique_pwsid={unique_pwsid_count} "
        f"dissolved={dissolved_count} dups_handled={duplicates_handled}"
    )
    print(
        f"simplification: tol={qa_stats['tolerance_m']}m avg_delta={qa_stats['avg_area_delta']:.4f} "
        f"max_delta={qa_stats['max_area_delta']:.4f} over_threshold={qa_stats['count_over_threshold']}"
    )
    print(f"tiers: {report['tier_counts']}")
    return tabular


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Ohio EPA public water system service area boundaries.")
    parser.parse_args()
    load_service_areas()
