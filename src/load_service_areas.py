"""Load EPA public water system service area data and create spatial confidence fields."""

from __future__ import annotations

import argparse

import geopandas as gpd
import pandas as pd

from utils import REPO_ROOT, standardize_columns, write_dataframe


def load_service_areas() -> pd.DataFrame:
    raw_path = REPO_ROOT / "data" / "raw" / "service_areas" / "epa_pws_service_areas_ohio.geojson"
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing EPA service area GeoJSON: {raw_path}")

    gdf = gpd.read_file(raw_path)
    gdf = standardize_columns(gdf)
    projected = gdf.to_crs(5070)
    centroids = projected.geometry.centroid
    centroids_wgs84 = gpd.GeoSeries(centroids, crs=5070).to_crs(4326)

    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df["latitude"] = centroids_wgs84.y
    df["longitude"] = centroids_wgs84.x
    df["geometry_type"] = gdf.geometry.geom_type
    df["service_area_available_flag"] = True
    df["geometry_source"] = "EPA Public Water System Service Area FeatureServer"
    df["spatial_confidence"] = df["data_provider_type"].fillna("").str.lower().map(
        lambda value: "high" if any(token in value for token in ["state", "utility", "system"]) else "medium"
    )
    df["spatial_limitation_note"] = df["spatial_confidence"].map(
        {
            "high": "EPA service area boundary is marked as sourced from a state, utility, or system-level provider; EPA still notes boundaries may contain errors.",
            "medium": "EPA service area boundary is modeled or source type is not clearly authoritative; use for screening, not engineering siting.",
        }
    )
    df["pwsid"] = df["pwsid"].astype(str).str.upper()

    keep = [
        "pwsid",
        "pws_name",
        "primacy_agency",
        "population_served_count",
        "service_connections_count",
        "service_area_type",
        "data_provider_type",
        "data_source",
        "model_method",
        "verification_status",
        "area_sq_km",
        "geometry_type",
        "latitude",
        "longitude",
        "service_area_available_flag",
        "geometry_source",
        "spatial_confidence",
        "spatial_limitation_note",
    ]
    df = df[[column for column in keep if column in df.columns]]
    write_dataframe(df, REPO_ROOT / "data" / "interim" / "service_areas_ohio")
    print(f"service_areas_ohio: rows={len(df):,}; pwsid_nulls={int(df['pwsid'].isna().sum())}")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Ohio EPA public water system service areas.")
    parser.parse_args()
    load_service_areas()
