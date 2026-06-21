-- Optional trigram acceleration for ILIKE text search.
-- Applied best-effort by the CLI: if pg_trgm is unavailable, the API still works
-- correctly (ILIKE falls back to a sequential scan, which is fast for ~16k rows).
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_water_systems_name_trgm ON water_systems USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_water_systems_pwsid_trgm ON water_systems USING gin (pwsid gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_water_systems_county_trgm ON water_systems USING gin (county gin_trgm_ops);
