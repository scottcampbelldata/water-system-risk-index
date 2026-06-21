# Water System Risk & Funding Priority Index

Senior-level portfolio analytics project for identifying small public drinking water systems that may deserve review for compliance support, technical assistance, infrastructure funding, or resilience planning.

This project is an explainable screening model built from public data. It is not a regulatory claim, legal finding, engineering siting tool, official risk assessment, or statement that any water system is unsafe.

## Business Question

Which small public drinking water systems should be reviewed first based on compliance history, enforcement history, population served, social vulnerability, drought exposure, service area uncertainty, and possible funding gaps?

## Prototype Scope

- Prototype state: Ohio
- Initial goal: produce clean CSV/Parquet analytical outputs that Power BI can import
- Scaling design: source configuration and pipeline modules are organized so additional states can be added later
- Dashboard status: not built yet; the first milestone is the data pipeline foundation

## Data Sources

The first release is designed around these public sources:

- EPA ECHO SDWA national download for public water systems, violations, enforcement, site visits/evaluations, facilities, service areas, geographic areas, and reference codes
- EPA Public Water System Service Area boundaries, using service-area geometries where available and fallbacks where not available
- EPA SRF Public Portal and Ohio DWSRF documents for funding records where project-level data can be downloaded or staged
- CDC/ATSDR Social Vulnerability Index
- Census TIGER/Line county and tract boundaries
- U.S. Drought Monitor county statistics API

Large national files are intentionally marked as large or manual in `config/sources.yaml` so the Ohio pipeline can be developed without pulling unnecessary data.

## Setup

This project is designed for Windows 11 and plain Python scripts. Do not create a virtual environment for the first version.

Expected Python:

```powershell
C:\Python312\python.exe --version
```

If Python is installed elsewhere, use the `python` launcher or the installed Python path consistently.

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create folders and source inventory:

```powershell
python src/download_data.py --inventory-only
```

Download one manageable source at a time:

```powershell
python src/download_data.py --source us_drought_monitor_ohio_county_52w
python src/download_data.py --source census_tiger_counties
```

Large sources such as the EPA SDWA national zip are skipped unless explicitly requested:

```powershell
python src/download_data.py --source epa_echo_sdwis --include-large
```

Use `--force` to overwrite an existing raw file.

## Manual Source Staging

Some sources are portal-based or large national files. If a source is marked `manual` in `config/sources.yaml`, download it from the listed landing page and place it at the configured `local_raw_path`. The pipeline will record whether the expected file is present.

Current manual or cautious sources:

- EPA Public Water System Service Area boundaries
- EPA SRF Public Portal project exports
- CDC/ATSDR SVI files if a direct official CSV endpoint is unavailable

## Planned Analytical Outputs

The MVP will produce these Power BI-ready files:

- `water_system_master.csv`
- `water_system_compliance_summary.csv`
- `water_system_enforcement_summary.csv`
- `water_system_funding_summary.csv`
- `water_system_geography.csv`
- `water_system_risk_scores.csv`
- `data_quality_report.csv`
- `methodology_notes.md`
- `portfolio_case_study.md`
- `powerbi_data_dictionary.md`

## Modeling Language

The model uses terms such as review priority, compliance support priority, infrastructure funding review, technical assistance candidate, and data-driven screening.

It does not label a system as dangerous, unsafe, contaminated, or legally noncompliant beyond what source data explicitly reports.

## Project Status

Ohio MVP complete.

Current run produced:

- 16,339 Ohio public water system records scored
- 1,077 EPA service-area boundary polygons preserved and mapped (207 system-sourced, 870 modeled)
- 7 processed analytical outputs
- 9 Power BI-ready CSV exports
- 19 validation checks, all passing (expanded from 13 to cover geometry source, dissolve, and simplification quality)
- Portfolio charts in `outputs/charts/`

Run the complete pipeline:

```powershell
python src/run_pipeline.py
```

Run tests:

```powershell
python -m pytest -q
```

Power BI import files are in `data/powerbi/`.

## Web Application Architecture

The dashboard is deployed as a full-stack app (mirroring the `grid` app):

- **Frontend** — static bundle in [`web/`](web/) on **Cloudflare Pages**
  (`water-risk.example.com`). It fetches everything from the API; it ships no
  data file. The previous 27 MB `app_data.json` is gone from `web/` (it was both a
  Cloudflare 25 MiB/file blocker and a poor upfront-load experience for 16k rows).
- **Backend** — **FastAPI + Postgres** in [`waterapi/`](waterapi/) on the VPS
  (`water-api.example.com`), behind nginx + certbot, supervised by systemd.
  Filtering, sorting and pagination happen server-side, so the browser pulls only
  what it displays.

Data flow:

```text
processed CSVs ──(src/export_web_app_data.py)──> data/processed/app_data.json
                                                          │ (seed)
                                          (waterapi load) ▼
                                                      Postgres
                                                          │
                                              (FastAPI waterapi.api) 
                                                          │  HTTP/JSON
                                                   static web/ frontend
```

### API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | health check |
| `GET /metadata` | metadata block, validation list, county list |
| `GET /summary` | filter-aware metric + chart aggregates (total, geography breakdown, tier counts, top counties) |
| `GET /tiers` | statewide tier counts |
| `GET /map/boundaries` | gzip GeoJSON FeatureCollection of simplified service-area polygons for the filtered set |
| `GET /systems` | filtered / sorted / paginated systems + total count |
| `GET /systems/{pwsid}` | single system detail |
| `GET /map/points` | lightweight map markers for the current filter |

Shared filter query params: `q`, `county`, `tier`, `size`, `geography`.
`/systems` also accepts `sort`, `order`, `page`, `page_size`.

### Geography & service-area boundaries

The map renders real **EPA Public Water System service-area polygons** where
available, not just centroids. The pipeline preserves the original geometry in an
audit artifact and stores a topology-simplified copy (5 m tolerance, area-delta
validated) as GeoJSON in Postgres (`water_system_boundaries`, `jsonb`). PostGIS is
intentionally not required for Phase 1 and is documented as a future national-scale
enhancement.

Each record is assigned a geometry-source tier (most to least precise):

| Tier (stored) | User-facing label | Confidence |
|---------------|-------------------|------------|
| `verified_service_area_boundary` | System-Sourced Service Area | very_high |
| `modeled_service_area_boundary` | Modeled Service Area | medium_high |
| `validated_system_coordinate` | Approximate Location | medium |
| `city_or_zip_centroid` | Approximate Location | low |
| `county_centroid` | Approximate Location | very_low |
| `unmatched` | Unmatched Geography | unknown |

Modeled EPA polygons are deliberately **not** labeled "verified." Service-area
boundaries (who may receive water) are kept semantically separate from
source-water protection areas (where supply is protected); the latter is a planned
**Phase 2** overlay and is not loaded yet. Facility points (wells/intakes/treatment
plants) are deferred because no public Ohio source publishes usable coordinates.

The frontend exposes map layer controls (records, service-area boundaries, county
boundaries) and a per-system **geography evidence** panel (primary geometry,
boundary type, provider, PWSID match, area, confidence, source-protection status,
limitation note).

### Run the backend locally

```powershell
python -m pip install -r requirements-api.txt
copy .env.example .env          # then edit PGPASSWORD etc.
python -m waterapi.cli init-db  # create tables + indexes (idempotent)
python -m waterapi.cli load     # seed Postgres from data/processed/app_data.json
python -m waterapi.cli serve    # uvicorn on http://127.0.0.1:8000
```

Map data (`web/data/ohio_map.json`, `web/data/ohio_counties.geojson`) stays as a
static asset — both are well under 25 MiB and the live map only needs API marker
points.

Full database create + seed + deploy steps (systemd, nginx, certbot, Cloudflare
Pages): see [`docs/deploy.md`](docs/deploy.md).
