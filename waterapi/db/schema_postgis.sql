-- Optional PostGIS upgrade for national-scale spatial queries.
--
-- Phase 1/2 store geometry as GeoJSON in jsonb (no PostGIS required), which is
-- ideal for a single-state screening tool. For national scale (hundreds of
-- thousands of polygons) and true spatial filtering (bbox / point-in-polygon),
-- run this on a PostGIS-enabled Postgres AFTER loading data. It adds real geometry
-- columns derived from the stored GeoJSON, with GiST spatial indexes.
--
--   psql "$DATABASE_URL" -f waterapi/db/schema_postgis.sql
--
-- The application's default jsonb path keeps working; this enables ST_Intersects-
-- based viewport queries to replace the Python bbox filter for large datasets.

CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE water_system_boundaries ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);
UPDATE water_system_boundaries
   SET geom = ST_SetSRID(ST_GeomFromGeoJSON(geometry::text), 4326)
 WHERE geom IS NULL;
CREATE INDEX IF NOT EXISTS idx_boundaries_geom ON water_system_boundaries USING gist (geom);

ALTER TABLE water_system_swap_areas ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);
UPDATE water_system_swap_areas
   SET geom = ST_SetSRID(ST_GeomFromGeoJSON(geometry::text), 4326)
 WHERE geom IS NULL;
CREATE INDEX IF NOT EXISTS idx_swap_geom ON water_system_swap_areas USING gist (geom);

-- Example viewport query enabled by the above:
--   SELECT pwsid FROM water_system_boundaries
--   WHERE geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326);
