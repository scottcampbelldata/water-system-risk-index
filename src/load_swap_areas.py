"""Load Ohio EPA Source Water Assessment & Protection (SWAP) areas - Phase 2.

These are source-water protection polygons (the area that supplies water to a well
or surface-water intake), NOT customer service-area boundaries. They are kept
semantically separate from service areas and shown as a distinct overlay.

Source: Ohio EPA ArcGIS MapServer
  https://geo.epa.ohio.gov/arcgis/rest/services/DrinkingWater/SWAP/MapServer

Layers (all polygons, all carry pwsid):
  0 Inner Management Zones (groundwater)         -> inner_management_zone
  1 Source Water Protection Areas (groundwater)  -> groundwater_swpa
  2 Inland (surface water)                        -> surface_water_inland
  3 Lake Erie (surface water)                     -> surface_water_lake_erie
  4 Ohio River (surface water)                    -> surface_water_ohio_river
  5 Ohio River (surface water)                    -> surface_water_ohio_river

Outputs:
  data/raw/swap/swap_L{id}.geojson               (raw per-layer download; gitignored)
  data/interim/swap_areas_audit.parquet          (dissolved ORIGINAL geometry)
  data/processed/swap_areas.json                 (simplified seed for the API)
  data/interim/swap_report.json                  (QA report)
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from utils import REPO_ROOT

MAPSERVER = "https://geo.epa.ohio.gov/arcgis/rest/services/DrinkingWater/SWAP/MapServer"
AREA_KIND = {
    0: "inner_management_zone",
    1: "groundwater_swpa",
    2: "surface_water_inland",
    3: "surface_water_lake_erie",
    4: "surface_water_ohio_river",
    5: "surface_water_ohio_river",
}
PAGE = 1000
EQUAL_AREA_CRS = 5070
WGS84 = 4326
SIMPLIFY_TOLERANCE_M = 5.0
RAW_DIR = REPO_ROOT / "data" / "raw" / "swap"


def _fetch_layer(layer_id: int, force: bool = False) -> Path:
    """Download one SWAP layer as GeoJSON (paginated), saving a combined file."""
    out_path = RAW_DIR / f"swap_L{layer_id}.geojson"
    if out_path.exists() and not force:
        return out_path
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    features: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": str(WGS84),
            "f": "geojson",
            "resultOffset": str(offset),
            "resultRecordCount": str(PAGE),
        }
        url = f"{MAPSERVER}/{layer_id}/query?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "water-risk-index/0.1"})
        with urllib.request.urlopen(req, timeout=90) as response:
            payload = json.loads(response.read())
        batch = payload.get("features", [])
        features.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
        time.sleep(0.2)
    collection = {"type": "FeatureCollection", "features": features}
    out_path.write_text(json.dumps(collection), encoding="utf-8")
    print(f"  layer {layer_id} ({AREA_KIND[layer_id]}): {len(features)} features")
    return out_path


def load_swap_areas(force_download: bool = False) -> pd.DataFrame:
    print("Downloading Ohio EPA SWAP layers ...")
    frames = []
    raw_counts: dict[str, int] = {}
    for layer_id, kind in AREA_KIND.items():
        path = _fetch_layer(layer_id, force=force_download)
        gdf = gpd.read_file(path)
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
        if gdf.empty:
            continue
        columns = {c.lower(): c for c in gdf.columns}
        gdf["pwsid"] = gdf[columns.get("pwsid", "pwsid")].astype(str).str.upper().str.strip()
        gdf["sys_name"] = gdf[columns["sys_name"]] if "sys_name" in columns else None
        gdf["county"] = gdf[columns["county"]] if "county" in columns else None
        gdf["area_kind"] = kind
        raw_counts[f"L{layer_id}_{kind}"] = raw_counts.get(f"L{layer_id}_{kind}", 0) + len(gdf)
        frames.append(gdf[["pwsid", "sys_name", "county", "area_kind", "geometry"]])

    combined = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=WGS84)
    combined = combined[combined["pwsid"].str.len() > 0].copy()
    raw_total = len(combined)
    distinct_pwsids = combined["pwsid"].nunique()

    # Dissolve to one geometry per (pwsid, area_kind) so a system's multiple wells
    # of the same kind collapse into a single MultiPolygon.
    attributes = (
        combined.sort_values("pwsid")
        .groupby(["pwsid", "area_kind"], as_index=False)
        .agg(sys_name=("sys_name", "first"), county=("county", "first"))
    )
    dissolved = combined.dissolve(by=["pwsid", "area_kind"], as_index=False, aggfunc="first")[
        ["pwsid", "area_kind", "geometry"]
    ]
    dissolved = dissolved.merge(attributes, on=["pwsid", "area_kind"], how="left")

    projected = dissolved.to_crs(EQUAL_AREA_CRS)
    original_area = projected.geometry.area
    simplified_proj = projected.geometry.simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=True)
    simplified_area = simplified_proj.area
    simplified_wgs = gpd.GeoSeries(simplified_proj, crs=EQUAL_AREA_CRS).to_crs(WGS84)
    area_delta = ((original_area - simplified_area).abs() / original_area.replace(0, pd.NA)).fillna(0.0)
    dissolved["area_sqkm"] = (original_area / 1_000_000).round(4).values

    interim = REPO_ROOT / "data" / "interim"
    interim.mkdir(parents=True, exist_ok=True)
    dissolved.to_parquet(interim / "swap_areas_audit.parquet")

    seed = [
        {
            "pwsid": row.pwsid,
            "areaKind": row.area_kind,
            "sysName": (None if pd.isna(row.sys_name) else str(row.sys_name)),
            "county": (None if pd.isna(row.county) else str(row.county)),
            "areaSqKm": float(row.area_sqkm) if not pd.isna(row.area_sqkm) else None,
            "geometry": geom,
        }
        for row, geom in zip(
            dissolved.itertuples(index=False),
            (mapping(g) for g in simplified_wgs.values),
            strict=False,
        )
    ]
    seed_path = REPO_ROOT / "data" / "processed" / "swap_areas.json"
    seed_path.write_text(json.dumps(seed, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    report = {
        "raw_feature_count": int(raw_total),
        "raw_counts_by_layer": raw_counts,
        "distinct_pwsids": int(distinct_pwsids),
        "dissolved_output_count": int(len(dissolved)),
        "area_kinds": dissolved["area_kind"].value_counts().to_dict(),
        "simplification": {
            "tolerance_m": SIMPLIFY_TOLERANCE_M,
            "avg_area_delta": float(area_delta.mean()),
            "max_area_delta": float(area_delta.max()),
            "count_over_threshold": int((area_delta > 0.05).sum()),
        },
    }
    (interim / "swap_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"SWAP: raw={raw_total} distinct_pwsid={distinct_pwsids} dissolved={len(dissolved)} "
        f"seed={seed_path} ({seed_path.stat().st_size / 1_000_000:.1f} MB)"
    )
    print(f"area kinds: {report['area_kinds']}")
    return dissolved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Ohio EPA SWAP source-water protection areas.")
    parser.add_argument("--force-download", action="store_true", help="Re-download even if raw files exist.")
    args = parser.parse_args()
    load_swap_areas(force_download=args.force_download)
