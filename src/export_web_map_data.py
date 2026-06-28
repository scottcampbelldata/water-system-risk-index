"""Build compact SVG-ready Ohio map data for the static web app."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon

from state_config import target_state_fips
from utils import REPO_ROOT

WIDTH = 980
HEIGHT = 820
PADDING = 24


def fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def ring_to_path(coords, minx: float, maxy: float, scale: float) -> str:
    parts = []
    for index, (x, y) in enumerate(coords):
        sx = PADDING + (x - minx) * scale
        sy = PADDING + (maxy - y) * scale
        parts.append(("M" if index == 0 else "L") + fmt(sx) + "," + fmt(sy))
    return " ".join(parts) + " Z"


def geometry_to_path(geometry, minx: float, maxy: float, scale: float) -> str:
    polygons = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]
    paths: list[str] = []
    for polygon in polygons:
        if not isinstance(polygon, Polygon) or polygon.is_empty:
            continue
        paths.append(ring_to_path(polygon.exterior.coords, minx, maxy, scale))
        for interior in polygon.interiors:
            paths.append(ring_to_path(interior.coords, minx, maxy, scale))
    return " ".join(paths)


def point_xy(x: float, y: float, minx: float, maxy: float, scale: float) -> dict[str, float]:
    return {
        "x": round(PADDING + (x - minx) * scale, 1),
        "y": round(PADDING + (maxy - y) * scale, 1),
    }


def export_web_map_data() -> Path:
    counties_path = REPO_ROOT / "data" / "raw" / "tiger" / "tl_2025_us_county.zip"
    risk = pd.read_csv(REPO_ROOT / "data" / "processed" / "water_system_risk_scores.csv", dtype={"pwsid": str})
    master = pd.read_csv(
        REPO_ROOT / "data" / "processed" / "water_system_master.csv",
        dtype={"pwsid": str, "county_fips": str},
    )
    geography = pd.read_csv(
        REPO_ROOT / "data" / "processed" / "water_system_geography.csv",
        dtype={"pwsid": str, "county_fips": str},
    )

    systems = (
        risk.merge(master[["pwsid", "county_fips"]], on="pwsid", how="left")
        .merge(
            geography[["pwsid", "latitude", "longitude", "spatial_confidence"]],
            on="pwsid",
            how="left",
        )
        .copy()
    )
    systems["high_review"] = systems["risk_tier"].isin(["Critical Review", "High Review"])
    systems["review_marker"] = systems["risk_tier"].isin(["Critical Review", "High Review", "Moderate Review"])
    systems["low_spatial"] = systems["spatial_confidence"].isin(["low", "unknown"])

    summary = (
        systems.groupby("county_fips", dropna=False)
        .agg(
            system_count=("pwsid", "count"),
            high_review_count=("high_review", "sum"),
            moderate_plus_count=("review_marker", "sum"),
            avg_score=("overall_risk_score", "mean"),
            max_score=("overall_risk_score", "max"),
            low_spatial_count=("low_spatial", "sum"),
            population_served=("population_served", "sum"),
        )
        .reset_index()
    )

    counties = gpd.read_file(f"zip://{counties_path}")
    counties = counties[counties["STATEFP"].isin(target_state_fips())].to_crs(5070)
    counties["geometry"] = counties.geometry.simplify(700, preserve_topology=True)
    counties = counties.merge(summary, left_on="GEOID", right_on="county_fips", how="left")
    counties["county_fips"] = counties["GEOID"]
    counties["county_name"] = counties["NAME"] + " County"

    for column in [
        "system_count",
        "high_review_count",
        "moderate_plus_count",
        "low_spatial_count",
        "population_served",
    ]:
        counties[column] = counties[column].fillna(0).astype(int)
    for column in ["avg_score", "max_score"]:
        counties[column] = counties[column].fillna(0).round(2)

    minx, miny, maxx, maxy = counties.total_bounds
    scale = min((WIDTH - PADDING * 2) / (maxx - minx), (HEIGHT - PADDING * 2) / (maxy - miny))
    actual_width = round((maxx - minx) * scale + PADDING * 2)
    actual_height = round((maxy - miny) * scale + PADDING * 2)

    county_rows = []
    for row in counties.sort_values("county_name").itertuples():
        county_rows.append(
            {
                "countyFips": row.county_fips,
                "county": row.county_name,
                "path": geometry_to_path(row.geometry, minx, maxy, scale),
                "systemCount": int(row.system_count),
                "highReviewCount": int(row.high_review_count),
                "moderatePlusCount": int(row.moderate_plus_count),
                "avgScore": float(row.avg_score),
                "maxScore": float(row.max_score),
                "lowSpatialCount": int(row.low_spatial_count),
                "populationServed": int(row.population_served),
            }
        )

    points_source = systems[systems["latitude"].notna() & systems["longitude"].notna()].copy()
    points_gdf = gpd.GeoDataFrame(
        points_source,
        geometry=gpd.points_from_xy(points_source["longitude"], points_source["latitude"]),
        crs=4326,
    ).to_crs(5070)

    marker_rows = []
    for row in points_gdf.sort_values(["rank_statewide", "pwsid"]).itertuples():
        xy = point_xy(row.geometry.x, row.geometry.y, minx, maxy, scale)
        marker_rows.append(
            {
                "pwsid": row.pwsid,
                "countyFips": row.county_fips if isinstance(row.county_fips, str) else "",
                "x": xy["x"],
                "y": xy["y"],
                "tier": row.risk_tier,
                "score": float(row.overall_risk_score),
                "rank": int(row.rank_statewide),
            }
        )

    top_by_county = {}
    for county_fips, group in systems.dropna(subset=["county_fips"]).groupby("county_fips"):
        top_by_county[county_fips] = [
            {
                "pwsid": row.pwsid,
                "name": row.pws_name,
                "score": float(row.overall_risk_score),
                "tier": row.risk_tier,
                "rank": int(row.rank_statewide),
            }
            for row in group.sort_values(["rank_statewide", "pwsid"]).head(8).itertuples()
        ]

    output = {
        "viewBox": f"0 0 {actual_width} {actual_height}",
        "width": actual_width,
        "height": actual_height,
        "counties": county_rows,
        "markers": marker_rows,
        "topByCounty": top_by_county,
        "legend": {
            "metric": "High/Critical Review systems",
            "breaks": [
                {"label": "0", "min": 0, "max": 0, "color": "#edf2ef"},
                {"label": "1-2", "min": 1, "max": 2, "color": "#b9d8cd"},
                {"label": "3-5", "min": 3, "max": 5, "color": "#66a89a"},
                {"label": "6-9", "min": 6, "max": 9, "color": "#d1953a"},
                {"label": "10+", "min": 10, "max": None, "color": "#9c3322"},
            ],
        },
    }

    output_path = REPO_ROOT / "web" / "data" / "ohio_map.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    print(f"Wrote {output_path} ({len(county_rows)} counties, {len(marker_rows)} markers)")
    return output_path


if __name__ == "__main__":
    export_web_map_data()
