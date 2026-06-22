-- Idempotent schema for the Water System Risk Index API.
-- Safe to run repeatedly: every object uses IF NOT EXISTS.
-- Optional pg_trgm trigram indexes are applied separately, best-effort,
-- by the CLI (see schema_trgm.sql) so this core schema never hard-fails.

CREATE TABLE IF NOT EXISTS water_systems (
    pwsid                         text PRIMARY KEY,
    name                          text NOT NULL,
    county                        text NOT NULL,
    population                    integer,
    size_class                    text,
    owner_type                    text,
    water_source                  text,
    activity_status               text,
    service_connections           integer,
    score                         double precision,
    tier                          text,
    rank_statewide                integer,
    rank_county                   integer,
    driver_1                      text,
    driver_2                      text,
    driver_3                      text,
    explanation                   text,
    latitude                      double precision,
    longitude                     double precision,
    spatial_confidence            text,
    geometry_source_tier          text,
    boundary_type                 text,
    boundary_provider             text,
    match_method                  text,
    area_sqkm                     double precision,
    spatial_limitation_note       text,
    source_protection_status      text DEFAULT 'none',
    source_protection_kinds       text,
    geo_join_confidence           text,
    svi                           double precision,
    drought_exposure              double precision,
    severe_drought_weeks          integer,
    violations_36m                integer,
    health_violations_36m         integer,
    open_violation                boolean,
    violation_trend               text,
    enforcement_36m               integer,
    formal_actions_60m            integer,
    recent_enforcement            boolean,
    funding_gap_flag              text,
    funding_match_confidence      text,
    funding_notes                 text,
    data_quality_flags            text,
    component_compliance          double precision,
    component_enforcement         double precision,
    component_vulnerability       double precision,
    component_drought             double precision,
    component_funding_gap         double precision,
    component_small_system        double precision,
    component_data_quality_penalty double precision
);

-- Columns we filter and sort on.
CREATE INDEX IF NOT EXISTS idx_water_systems_tier ON water_systems (tier);
CREATE INDEX IF NOT EXISTS idx_water_systems_county ON water_systems (county);
CREATE INDEX IF NOT EXISTS idx_water_systems_score ON water_systems (score);
CREATE INDEX IF NOT EXISTS idx_water_systems_rank ON water_systems (rank_statewide);
CREATE INDEX IF NOT EXISTS idx_water_systems_spatial ON water_systems (spatial_confidence);
CREATE INDEX IF NOT EXISTS idx_water_systems_size ON water_systems (size_class);

-- Single-row metadata block (model version, notes, validation counts).
CREATE TABLE IF NOT EXISTS app_metadata (
    id   integer PRIMARY KEY DEFAULT 1,
    data jsonb NOT NULL,
    CONSTRAINT app_metadata_singleton CHECK (id = 1)
);

-- Simplified service-area boundary geometry (GeoJSON in jsonb; no PostGIS in Phase 1).
-- PostGIS is a documented future enhancement for national-scale spatial queries.
CREATE TABLE IF NOT EXISTS water_system_boundaries (
    pwsid             text PRIMARY KEY REFERENCES water_systems(pwsid),
    boundary_type     text,
    boundary_provider text,
    match_method      text,
    area_sqkm         double precision,
    min_lon           double precision,
    min_lat           double precision,
    max_lon           double precision,
    max_lat           double precision,
    geometry          jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_boundaries_type ON water_system_boundaries (boundary_type);
CREATE INDEX IF NOT EXISTS idx_boundaries_bbox ON water_system_boundaries (min_lon, max_lon, min_lat, max_lat);

-- Phase 2: Ohio EPA source-water protection (SWAP) areas. These describe where a
-- system's water supply is protected (around wells/intakes) and are kept separate
-- from service-area boundaries (who may receive water). No FK: SWAP may reference
-- systems outside the scored set. One geometry per (pwsid, area_kind) after dissolve.
CREATE TABLE IF NOT EXISTS water_system_swap_areas (
    pwsid     text,
    area_kind text,
    sys_name  text,
    county    text,
    area_sqkm double precision,
    min_lon   double precision,
    min_lat   double precision,
    max_lon   double precision,
    max_lat   double precision,
    geometry  jsonb NOT NULL,
    PRIMARY KEY (pwsid, area_kind)
);
CREATE INDEX IF NOT EXISTS idx_swap_pwsid ON water_system_swap_areas (pwsid);
CREATE INDEX IF NOT EXISTS idx_swap_kind ON water_system_swap_areas (area_kind);
CREATE INDEX IF NOT EXISTS idx_swap_bbox ON water_system_swap_areas (min_lon, max_lon, min_lat, max_lat);

-- Temporal layer: one score/tier row per system per scoring run. Unlike the other
-- tables this is NOT truncated on load; snapshots accumulate so trends (newly
-- escalated systems, score deltas) can be computed across refreshes.
CREATE TABLE IF NOT EXISTS score_snapshots (
    score_date date NOT NULL,
    pwsid      text NOT NULL,
    score      double precision,
    tier       text,
    PRIMARY KEY (score_date, pwsid)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON score_snapshots (score_date);

-- The data-quality / validation check results.
CREATE TABLE IF NOT EXISTS validation_checks (
    check_name    text PRIMARY KEY,
    status        text,
    severity      text,
    rows_affected integer,
    notes         text
);
