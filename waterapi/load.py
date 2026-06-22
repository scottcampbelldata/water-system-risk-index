"""Idempotent loader: seed Postgres from the pipeline's app_data.json.

The web export (``src/export_web_app_data.py``) writes ``data/processed/app_data.json``
from the processed CSVs. This loader reads that file and replaces the contents of
the ``water_systems``, ``app_metadata`` and ``validation_checks`` tables inside a
single transaction, so a data refresh is simply:

    python src/export_web_app_data.py   # regenerate the seed
    python -m waterapi.cli load         # reload Postgres

Re-running is safe and produces the same result every time.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from waterapi.config import settings
from waterapi.db.engine import get_engine

COMPONENT_MAP = {
    "component_compliance": "compliance_risk_component",
    "component_enforcement": "enforcement_risk_component",
    "component_vulnerability": "vulnerability_component",
    "component_drought": "drought_component",
    "component_funding_gap": "funding_gap_component",
    "component_small_system": "small_system_component",
    "component_data_quality_penalty": "data_quality_penalty",
}

SYSTEM_INSERT = text(
    """
    INSERT INTO water_systems (
        pwsid, name, county, population, size_class, owner_type, water_source,
        activity_status, service_connections, score, tier, rank_statewide, rank_county,
        driver_1, driver_2, driver_3, explanation, latitude, longitude,
        spatial_confidence, geometry_source_tier, boundary_type, boundary_provider,
        match_method, area_sqkm, spatial_limitation_note, geo_join_confidence, svi, drought_exposure,
        severe_drought_weeks, violations_36m, health_violations_36m, open_violation,
        violation_trend, enforcement_36m, formal_actions_60m, recent_enforcement,
        funding_gap_flag, funding_match_confidence, funding_notes, data_quality_flags,
        component_compliance, component_enforcement, component_vulnerability,
        component_drought, component_funding_gap, component_small_system,
        component_data_quality_penalty
    ) VALUES (
        :pwsid, :name, :county, :population, :size_class, :owner_type, :water_source,
        :activity_status, :service_connections, :score, :tier, :rank_statewide, :rank_county,
        :driver_1, :driver_2, :driver_3, :explanation, :latitude, :longitude,
        :spatial_confidence, :geometry_source_tier, :boundary_type, :boundary_provider,
        :match_method, :area_sqkm, :spatial_limitation_note, :geo_join_confidence, :svi, :drought_exposure,
        :severe_drought_weeks, :violations_36m, :health_violations_36m, :open_violation,
        :violation_trend, :enforcement_36m, :formal_actions_60m, :recent_enforcement,
        :funding_gap_flag, :funding_match_confidence, :funding_notes, :data_quality_flags,
        :component_compliance, :component_enforcement, :component_vulnerability,
        :component_drought, :component_funding_gap, :component_small_system,
        :component_data_quality_penalty
    )
    """
)

VALIDATION_INSERT = text(
    """
    INSERT INTO validation_checks (check_name, status, severity, rows_affected, notes)
    VALUES (:check_name, :status, :severity, :rows_affected, :notes)
    """
)

METADATA_INSERT = text("INSERT INTO app_metadata (id, data) VALUES (1, :data)")

SNAPSHOT_INSERT = text(
    "INSERT INTO score_snapshots (score_date, pwsid, score, tier) VALUES (:score_date, :pwsid, :score, :tier)"
)

BOUNDARY_INSERT = text(
    """
    INSERT INTO water_system_boundaries
        (pwsid, boundary_type, boundary_provider, match_method, area_sqkm, min_lon, min_lat, max_lon, max_lat, geometry)
    VALUES (:pwsid, :boundary_type, :boundary_provider, :match_method, :area_sqkm,
            :min_lon, :min_lat, :max_lon, :max_lat, CAST(:geometry AS jsonb))
    """
)

SWAP_INSERT = text(
    """
    INSERT INTO water_system_swap_areas
        (pwsid, area_kind, sys_name, county, area_sqkm, min_lon, min_lat, max_lon, max_lat, geometry)
    VALUES (:pwsid, :area_kind, :sys_name, :county, :area_sqkm,
            :min_lon, :min_lat, :max_lon, :max_lat, CAST(:geometry AS jsonb))
    ON CONFLICT (pwsid, area_kind) DO NOTHING
    """
)


def _bbox(geometry: dict | None) -> dict:
    """Bounding box (min/max lon/lat) of a GeoJSON Polygon/MultiPolygon."""
    lons: list[float] = []
    lats: list[float] = []

    def walk(coords):
        if isinstance(coords, (list, tuple)):
            if coords and isinstance(coords[0], (int, float)):
                lons.append(coords[0])
                lats.append(coords[1])
            else:
                for c in coords:
                    walk(c)

    if geometry:
        walk(geometry.get("coordinates"))
    if not lons:
        return {"min_lon": None, "min_lat": None, "max_lon": None, "max_lat": None}
    return {"min_lon": min(lons), "min_lat": min(lats), "max_lon": max(lons), "max_lat": max(lats)}


def _system_row(system: dict) -> dict:
    drivers = system.get("drivers") or []
    drivers = (list(drivers) + [None, None, None])[:3]
    components = system.get("components") or {}
    row = {
        "pwsid": system["pwsid"],
        "name": system["name"],
        "county": system["county"],
        "population": system.get("population"),
        "size_class": system.get("sizeClass"),
        "owner_type": system.get("ownerType"),
        "water_source": system.get("waterSource"),
        "activity_status": system.get("activityStatus"),
        "service_connections": system.get("serviceConnections"),
        "score": system.get("score"),
        "tier": system.get("tier"),
        "rank_statewide": system.get("rankStatewide"),
        "rank_county": system.get("rankCounty"),
        "driver_1": drivers[0],
        "driver_2": drivers[1],
        "driver_3": drivers[2],
        "explanation": system.get("explanation"),
        "latitude": system.get("latitude"),
        "longitude": system.get("longitude"),
        "spatial_confidence": system.get("spatialConfidence"),
        "geometry_source_tier": system.get("geometrySourceTier"),
        "boundary_type": system.get("boundaryType"),
        "boundary_provider": system.get("boundaryProvider"),
        "match_method": system.get("matchMethod"),
        "area_sqkm": system.get("areaSqKm"),
        "spatial_limitation_note": system.get("spatialLimitationNote"),
        "geo_join_confidence": system.get("geoJoinConfidence"),
        "svi": system.get("svi"),
        "drought_exposure": system.get("droughtExposure"),
        "severe_drought_weeks": system.get("severeDroughtWeeks"),
        "violations_36m": system.get("violations36m"),
        "health_violations_36m": system.get("healthViolations36m"),
        "open_violation": system.get("openViolation"),
        "violation_trend": system.get("violationTrend"),
        "enforcement_36m": system.get("enforcement36m"),
        "formal_actions_60m": system.get("formalActions60m"),
        "recent_enforcement": system.get("recentEnforcement"),
        "funding_gap_flag": system.get("fundingGapFlag"),
        "funding_match_confidence": system.get("fundingMatchConfidence"),
        "funding_notes": system.get("fundingNotes"),
        "data_quality_flags": system.get("dataQualityFlags"),
    }
    for column, source_key in COMPONENT_MAP.items():
        row[column] = components.get(source_key)
    return row


def load(seed_path: Path | None = None) -> int:
    """Replace all table contents from the seed JSON. Returns row count."""
    path = seed_path or settings.seed_path
    if not path.exists():
        raise FileNotFoundError(
            f"Seed file not found: {path}. Run 'python src/export_web_app_data.py' first."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    systems = payload.get("systems", [])
    metadata = payload.get("metadata", {})
    validation = payload.get("validation", [])

    boundaries_path = path.parent / "boundaries.json"
    boundary_rows = []
    if boundaries_path.exists():
        boundaries = json.loads(boundaries_path.read_text(encoding="utf-8"))
        boundary_rows = [
            {
                "pwsid": pwsid,
                "boundary_type": entry.get("boundaryType"),
                "boundary_provider": entry.get("boundaryProvider"),
                "match_method": entry.get("matchMethod"),
                "area_sqkm": entry.get("areaSqKm"),
                "geometry": json.dumps(entry.get("geometry"), separators=(",", ":")),
                **_bbox(entry.get("geometry")),
            }
            for pwsid, entry in boundaries.items()
        ]

    # Phase 2 SWAP source-water protection areas (optional — present once loaded).
    swap_path = path.parent / "swap_areas.json"
    swap_rows = []
    if swap_path.exists():
        swap = json.loads(swap_path.read_text(encoding="utf-8"))
        swap_rows = [
            {
                "pwsid": area.get("pwsid"),
                "area_kind": area.get("areaKind"),
                "sys_name": area.get("sysName"),
                "county": area.get("county"),
                "area_sqkm": area.get("areaSqKm"),
                "geometry": json.dumps(area.get("geometry"), separators=(",", ":")),
                **_bbox(area.get("geometry")),
            }
            for area in swap
        ]

    system_rows = [_system_row(system) for system in systems]
    validation_rows = [
        {
            "check_name": row.get("check_name"),
            "status": row.get("status"),
            "severity": row.get("severity"),
            "rows_affected": row.get("rows_affected"),
            "notes": row.get("notes"),
        }
        for row in validation
    ]

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE water_system_swap_areas, water_system_boundaries, water_systems, app_metadata, validation_checks")
        )
        if system_rows:
            conn.execute(SYSTEM_INSERT, system_rows)
        if boundary_rows:
            conn.execute(BOUNDARY_INSERT, boundary_rows)
        if swap_rows:
            conn.execute(SWAP_INSERT, swap_rows)
            # Flag systems that have at least one matching source-protection area,
            # and record which kinds (only meaningful now that SWAP is loaded).
            conn.execute(
                text(
                    """
                    UPDATE water_systems w SET
                        source_protection_status = 'available',
                        source_protection_kinds = sub.kinds
                    FROM (
                        SELECT pwsid, string_agg(DISTINCT area_kind, '|' ORDER BY area_kind) AS kinds
                        FROM water_system_swap_areas GROUP BY pwsid
                    ) sub
                    WHERE w.pwsid = sub.pwsid
                    """
                )
            )
        conn.execute(METADATA_INSERT, {"data": json.dumps(metadata)})
        if validation_rows:
            conn.execute(VALIDATION_INSERT, validation_rows)

        # Temporal snapshot: upsert this run's scores by score_date (accumulates).
        score_date = metadata.get("scoreDate")
        if score_date and systems:
            conn.execute(text("DELETE FROM score_snapshots WHERE score_date = :d"), {"d": score_date})
            conn.execute(
                SNAPSHOT_INSERT,
                [{"score_date": score_date, "pwsid": s["pwsid"], "score": s.get("score"), "tier": s.get("tier")} for s in systems],
            )

    print(
        f"Loaded {len(system_rows):,} systems, {len(boundary_rows):,} boundaries, "
        f"{len(swap_rows):,} SWAP areas, {len(validation_rows)} validation checks from {path}"
    )
    return len(system_rows)


if __name__ == "__main__":
    load()
