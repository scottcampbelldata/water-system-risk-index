"""FastAPI service for the Water System Risk Index.

Serves the data that the static frontend (Cloudflare Pages) used to bundle as a
27 MB JSON file. All filtering, sorting and pagination happens server-side so the
browser only pulls what it displays.
"""

from __future__ import annotations

from typing import Any

import json
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from waterapi import __version__
from waterapi.config import settings
from waterapi.db.engine import get_engine
from waterapi.observability import RequestLoggingMiddleware, metrics, setup_logging

setup_logging(settings.water_log_level)
logger = logging.getLogger("waterapi")

app = FastAPI(title="Water System Risk Index API", version=__version__)

# Per-request structured logging + in-memory metrics (see GET /metrics).
app.add_middleware(RequestLoggingMiddleware)

# Compress responses (notably the /map/boundaries GeoJSON FeatureCollection).
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Explicit production origin(s) from settings, plus any localhost/127.0.0.1 port
# for local development (regex).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET"],
    allow_headers=["*"],
)

TIER_ORDER = ["Critical Review", "High Review", "Moderate Review", "Monitor", "Lower Priority"]
HIGH_TIERS = ("Critical Review", "High Review")

# Geography filter buckets -> geometry_source_tier values.
GEOGRAPHY_BUCKETS = {
    "verified": ["verified_service_area_boundary"],
    "modeled": ["modeled_service_area_boundary"],
    "approximate": ["validated_system_coordinate", "city_or_zip_centroid", "county_centroid"],
    "unmatched": ["unmatched"],
}
MATCHED_TIERS = ("verified_service_area_boundary", "modeled_service_area_boundary")

GEOMETRY_LABELS = {
    "verified_service_area_boundary": "System-Sourced Service Area",
    "modeled_service_area_boundary": "Modeled Service Area",
    "validated_system_coordinate": "Approximate Location",
    "city_or_zip_centroid": "Approximate Location",
    "county_centroid": "Approximate Location",
    "unmatched": "Unmatched Geography",
}

# Sort keys exposed to the API mapped to physical columns.
SORT_COLUMNS = {
    "rank": "rank_statewide",
    "score": "score",
    "name": "name",
    "county": "county",
    "tier": "tier",
    "population": "population",
}

COMPONENT_KEYS = {
    "compliance_risk_component": "component_compliance",
    "enforcement_risk_component": "component_enforcement",
    "vulnerability_component": "component_vulnerability",
    "drought_component": "component_drought",
    "funding_gap_component": "component_funding_gap",
    "small_system_component": "component_small_system",
    "data_quality_penalty": "component_data_quality_penalty",
}


def _system_to_dict(row: Any) -> dict[str, Any]:
    """Map a water_systems row to the camelCase shape the frontend expects."""
    m = row._mapping
    return {
        "pwsid": m["pwsid"],
        "name": m["name"],
        "county": m["county"],
        "population": m["population"],
        "sizeClass": m["size_class"],
        "ownerType": m["owner_type"],
        "waterSource": m["water_source"],
        "activityStatus": m["activity_status"],
        "serviceConnections": m["service_connections"],
        "score": m["score"],
        "tier": m["tier"],
        "rankStatewide": m["rank_statewide"],
        "rankCounty": m["rank_county"],
        "drivers": [m["driver_1"], m["driver_2"], m["driver_3"]],
        "explanation": m["explanation"],
        "latitude": m["latitude"],
        "longitude": m["longitude"],
        "geometrySourceTier": m["geometry_source_tier"],
        "boundaryType": m["boundary_type"],
        "boundaryProvider": m["boundary_provider"],
        "matchMethod": m["match_method"],
        "areaSqKm": m["area_sqkm"],
        "spatialConfidence": m["spatial_confidence"],
        "spatialLimitationNote": m["spatial_limitation_note"],
        "sourceProtectionStatus": m["source_protection_status"],
        "sourceProtectionKinds": m["source_protection_kinds"],
        "geoJoinConfidence": m["geo_join_confidence"],
        "svi": m["svi"],
        "droughtExposure": m["drought_exposure"],
        "severeDroughtWeeks": m["severe_drought_weeks"],
        "violations36m": m["violations_36m"],
        "healthViolations36m": m["health_violations_36m"],
        "openViolation": m["open_violation"],
        "violationTrend": m["violation_trend"],
        "enforcement36m": m["enforcement_36m"],
        "formalActions60m": m["formal_actions_60m"],
        "recentEnforcement": m["recent_enforcement"],
        "fundingGapFlag": m["funding_gap_flag"],
        "fundingMatchConfidence": m["funding_match_confidence"],
        "fundingNotes": m["funding_notes"],
        "dataQualityFlags": m["data_quality_flags"],
        "components": {key: m[column] for key, column in COMPONENT_KEYS.items()},
    }


def _filters(
    q: str | None, county: str | None, tier: str | None, size: str | None, geography: str | None
) -> tuple[str, dict[str, Any]]:
    """Build a shared WHERE clause + bound params from the dashboard filters."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if q:
        clauses.append("(pwsid ILIKE :q OR name ILIKE :q OR county ILIKE :q)")
        params["q"] = f"%{q}%"
    if county:
        clauses.append("county = :county")
        params["county"] = county
    if tier:
        clauses.append("tier = :tier")
        params["tier"] = tier
    if size:
        clauses.append("size_class = :size")
        params["size"] = size
    if geography and geography in GEOGRAPHY_BUCKETS:
        tiers = GEOGRAPHY_BUCKETS[geography]
        placeholders = ", ".join(f":geo{i}" for i in range(len(tiers)))
        clauses.append(f"geometry_source_tier IN ({placeholders})")
        params.update({f"geo{i}": value for i, value in enumerate(tiers)})
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__}


@app.get("/metrics")
def get_metrics() -> dict[str, Any]:
    """Lightweight request metrics (counts, status classes, p50/p95 latency by route)."""
    return metrics.snapshot()


@app.get("/metadata")
def metadata() -> dict[str, Any]:
    engine = get_engine()
    with engine.connect() as conn:
        meta_row = conn.execute(text("SELECT data FROM app_metadata WHERE id = 1")).fetchone()
        checks = conn.execute(
            text(
                "SELECT check_name, status, severity, rows_affected, notes "
                "FROM validation_checks ORDER BY check_name"
            )
        ).mappings().all()
    if not meta_row:
        raise HTTPException(status_code=503, detail="Metadata not loaded. Run the loader.")
    with engine.connect() as conn:
        county_rows = conn.execute(
            text("SELECT DISTINCT county FROM water_systems ORDER BY county")
        ).scalars().all()
    payload = dict(meta_row[0])
    payload["validation"] = [dict(check) for check in checks]
    payload["counties"] = list(county_rows)
    return payload


@app.get("/tiers")
def tiers() -> list[dict[str, Any]]:
    """Statewide (unfiltered) tier counts, in dashboard tier order."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT tier, COUNT(*) AS systems FROM water_systems GROUP BY tier")
        ).mappings().all()
    counts = {row["tier"]: row["systems"] for row in rows}
    return [{"tier": tier, "systems": int(counts.get(tier, 0))} for tier in TIER_ORDER]


@app.get("/summary")
def summary(
    q: str | None = None,
    county: str | None = None,
    tier: str | None = None,
    size: str | None = None,
    geography: str | None = None,
) -> dict[str, Any]:
    """Filter-aware aggregates that drive the metric cards and both charts."""
    where, params = _filters(q, county, tier, size, geography)
    engine = get_engine()
    with engine.connect() as conn:
        metrics = conn.execute(
            text(
                f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE tier IN ('Critical Review', 'High Review')) AS high_review,
                    COUNT(*) FILTER (WHERE tier = 'Critical Review') AS critical_review,
                    COUNT(*) FILTER (WHERE geometry_source_tier = 'verified_service_area_boundary') AS verified_service_areas,
                    COUNT(*) FILTER (WHERE geometry_source_tier = 'modeled_service_area_boundary') AS modeled_service_areas,
                    COUNT(*) FILTER (WHERE geometry_source_tier IN ('validated_system_coordinate', 'city_or_zip_centroid', 'county_centroid')) AS approximate_locations,
                    COUNT(*) FILTER (WHERE geometry_source_tier = 'unmatched') AS unmatched_geography,
                    COUNT(*) FILTER (WHERE source_protection_status = 'available') AS source_protection_available
                FROM water_systems{where}
                """
            ),
            params,
        ).mappings().one()

        tier_rows = conn.execute(
            text(f"SELECT tier, COUNT(*) AS systems FROM water_systems{where} GROUP BY tier"),
            params,
        ).mappings().all()
        tier_counts = {row["tier"]: row["systems"] for row in tier_rows}

        county_rows = conn.execute(
            text(
                f"""
                SELECT county,
                       COUNT(*) FILTER (WHERE tier IN ('Critical Review', 'High Review')) AS high_review_systems
                FROM water_systems{where}
                GROUP BY county
                HAVING COUNT(*) FILTER (WHERE tier IN ('Critical Review', 'High Review')) > 0
                ORDER BY high_review_systems DESC, county ASC
                LIMIT 12
                """
            ),
            params,
        ).mappings().all()

    return {
        "total": int(metrics["total"]),
        "highReview": int(metrics["high_review"]),
        "criticalReview": int(metrics["critical_review"]),
        "geography": {
            "verifiedServiceAreas": int(metrics["verified_service_areas"]),
            "modeledServiceAreas": int(metrics["modeled_service_areas"]),
            "approximateLocations": int(metrics["approximate_locations"]),
            "unmatchedGeography": int(metrics["unmatched_geography"]),
            "sourceProtectionAvailable": int(metrics["source_protection_available"]),
        },
        "tiers": [{"tier": tier, "systems": int(tier_counts.get(tier, 0))} for tier in TIER_ORDER],
        "topCounties": [
            {"county": row["county"], "highReviewSystems": int(row["high_review_systems"])}
            for row in county_rows
        ],
    }


@app.get("/systems")
def systems(
    q: str | None = None,
    county: str | None = None,
    tier: str | None = None,
    size: str | None = None,
    geography: str | None = None,
    sort: str = "rank",
    order: str = "asc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Filtered, sorted, paginated systems plus the total match count."""
    sort_column = SORT_COLUMNS.get(sort, "rank_statewide")
    direction = "DESC" if order.lower() == "desc" else "ASC"
    where, params = _filters(q, county, tier, size, geography)
    offset = (page - 1) * page_size

    engine = get_engine()
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM water_systems{where}"), params
        ).scalar_one()
        rows = conn.execute(
            text(
                f"SELECT * FROM water_systems{where} "
                f"ORDER BY {sort_column} {direction}, rank_statewide ASC "
                f"LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        ).all()

    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [_system_to_dict(row) for row in rows],
    }


def _geography_evidence(m: Any) -> dict[str, Any]:
    tier = m["geometry_source_tier"]
    primary = {
        "verified_service_area_boundary": "EPA service-area polygon (system-sourced)",
        "modeled_service_area_boundary": "EPA service-area polygon (modeled)",
        "county_centroid": "County centroid (approximate)",
        "unmatched": "No geography matched",
    }.get(tier, "Approximate location")
    return {
        "primaryGeometry": primary,
        "geometrySourceTier": tier,
        "boundaryType": m["boundary_type"],
        "boundaryProvider": m["boundary_provider"],
        "matchMethod": m["match_method"],
        "areaSqKm": m["area_sqkm"],
        "spatialConfidence": m["spatial_confidence"],
        "sourceProtectionStatus": m["source_protection_status"],
        "sourceProtectionKinds": m["source_protection_kinds"],
        "limitationNote": m["spatial_limitation_note"],
    }


@app.get("/systems/{pwsid}")
def system_detail(pwsid: str) -> dict[str, Any]:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM water_systems WHERE pwsid = :pwsid"), {"pwsid": pwsid}
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"System {pwsid} not found")
    payload = _system_to_dict(row)
    payload["geographyEvidence"] = _geography_evidence(row._mapping)
    return payload


@app.get("/map/points")
def map_points(
    q: str | None = None,
    county: str | None = None,
    tier: str | None = None,
    size: str | None = None,
    geography: str | None = None,
) -> list[dict[str, Any]]:
    """Lightweight markers for every filtered system with usable coordinates."""
    where, params = _filters(q, county, tier, size, geography)
    coord_clause = "latitude IS NOT NULL AND longitude IS NOT NULL"
    where = f"{where} AND {coord_clause}" if where else f" WHERE {coord_clause}"
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT pwsid, name, county, latitude, longitude, tier, score,
                       rank_statewide, population, spatial_confidence, geometry_source_tier,
                       driver_1, driver_2
                FROM water_systems{where}
                ORDER BY rank_statewide ASC
                """
            ),
            params,
        ).mappings().all()
    return [
        {
            "pwsid": row["pwsid"],
            "name": row["name"],
            "county": row["county"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "tier": row["tier"],
            "score": row["score"],
            "rankStatewide": row["rank_statewide"],
            "population": row["population"],
            "spatialConfidence": row["spatial_confidence"],
            "geometrySourceTier": row["geometry_source_tier"],
            "drivers": [row["driver_1"], row["driver_2"]],
        }
        for row in rows
    ]


@app.get("/map/boundaries")
def map_boundaries(
    q: str | None = None,
    county: str | None = None,
    tier: str | None = None,
    size: str | None = None,
    geography: str | None = None,
) -> dict[str, Any]:
    """GeoJSON FeatureCollection of simplified service-area polygons for the filtered set.

    Only systems with a service-area boundary (verified/modeled tiers) are returned.
    Responses are gzip-compressed by middleware; payload size is logged.
    """
    where, params = _filters(q, county, tier, size, geography)
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT b.pwsid, b.boundary_type, s.name, s.tier, s.geometry_source_tier, b.geometry
                FROM water_system_boundaries b
                JOIN (
                    SELECT pwsid, name, county, tier, size_class, geometry_source_tier
                    FROM water_systems{where}
                ) s ON b.pwsid = s.pwsid
                ORDER BY s.tier
                """
            ),
            params,
        ).mappings().all()

    features = [
        {
            "type": "Feature",
            "properties": {
                "pwsid": row["pwsid"],
                "name": row["name"],
                "tier": row["tier"],
                "boundaryType": row["boundary_type"],
                "geometrySourceTier": row["geometry_source_tier"],
            },
            "geometry": row["geometry"],
        }
        for row in rows
    ]
    collection = {"type": "FeatureCollection", "features": features}
    payload_bytes = len(json.dumps(collection, separators=(",", ":")))
    logger.info("map_boundaries: %d features, %.2f MB uncompressed", len(features), payload_bytes / 1_000_000)
    return collection


@app.get("/map/swap")
def map_swap(
    q: str | None = None,
    county: str | None = None,
    tier: str | None = None,
    size: str | None = None,
    geography: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    """GeoJSON FeatureCollection of Ohio EPA source-water protection (SWAP) areas
    for systems in the current filter. Source-protection areas (where supply is
    protected) are distinct from service-area boundaries (who receives water).
    Off by default on the map and loaded on demand; gzip-compressed.
    """
    where, params = _filters(q, county, tier, size, geography)
    kind_clause = ""
    if kind:
        kind_clause = " AND a.area_kind = :kind"
        params = {**params, "kind": kind}
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT a.pwsid, a.area_kind, a.sys_name, a.area_sqkm, a.geometry
                FROM water_system_swap_areas a
                JOIN (SELECT pwsid FROM water_systems{where}) w ON a.pwsid = w.pwsid
                WHERE TRUE{kind_clause}
                ORDER BY a.area_kind
                """
            ),
            params,
        ).mappings().all()

    features = [
        {
            "type": "Feature",
            "properties": {
                "pwsid": row["pwsid"],
                "areaKind": row["area_kind"],
                "name": row["sys_name"],
                "areaSqKm": row["area_sqkm"],
            },
            "geometry": row["geometry"],
        }
        for row in rows
    ]
    collection = {"type": "FeatureCollection", "features": features}
    payload_bytes = len(json.dumps(collection, separators=(",", ":")))
    logger.info("map_swap: %d features, %.2f MB uncompressed", len(features), payload_bytes / 1_000_000)
    return collection
