# Technical Implementation Plan

## Objective

Build a reproducible Ohio prototype that transforms public drinking water, funding, vulnerability, drought, and geography data into explainable Power BI-ready review-priority datasets.

## Working Principles

- Preserve source identifiers and raw files.
- Record source lineage, retrieval date, file size, and local path.
- Prefer Ohio-filtered interim outputs before national scaling.
- Treat unmatched funding and uncertain geography as data limitations, not findings.
- Keep scoring assumptions in `config/scoring_weights.yaml`.
- Keep source paths and refresh metadata in `config/sources.yaml`.

## Phase Plan

### Phase 1: Project Setup

Create the repository structure, dependencies, source configuration, scoring configuration, README, and first working ingestion script.

Deliverables:

- `requirements.txt`
- `README.md`
- `config/sources.yaml`
- `config/scoring_weights.yaml`
- `src/download_data.py`
- `data/interim/source_inventory.csv`
- `data/raw/data_source_manifest.csv`

### Phase 2: Source Inventory

Generate a source inventory table with:

- `source_name`
- `agency`
- `dataset_description`
- `grain`
- `geographic_level`
- `refresh_frequency`
- `key_fields`
- `known_limitations`
- `local_raw_path`
- `processed_output_path`

### Phase 3: Ingestion

Implement one source at a time:

1. Drought Monitor Ohio county API export
2. TIGER Ohio tract and county boundaries
3. Manually staged SVI county/tract files
4. EPA ECHO SDWA zip, with Ohio extraction
5. EPA service areas, with confidence flags
6. EPA SRF portal export, with matching confidence

The ingestion script must not overwrite raw files unless `--force` is used.

### Phase 4: Source-Specific Loaders

Each loader will:

- Read raw files.
- Standardize column names to snake_case.
- Preserve original IDs and names.
- Create clean join keys.
- Convert dates.
- Write CSV and Parquet interim outputs.
- Print row counts and key null counts.

### Phase 5: Master and Feature Tables

Build:

- `water_system_master`
- `water_system_compliance_summary`
- `water_system_enforcement_summary`
- `water_system_funding_summary`
- `water_system_geography`
- vulnerability and drought components

### Phase 6: Risk Scoring

Normalize components to 0-100, apply configured weights, rank statewide/county, assign risk tiers, and generate explanation text plus top drivers.

### Phase 7: Validation and Power BI Export

Create required validation checks and export star-schema-friendly files:

- `FactRiskScores`
- `DimWaterSystem`
- `FactViolationsSummary`
- `FactEnforcementSummary`
- `FactFundingSummary`
- `DimGeography`
- `DimRiskTier`
- `DataQualityReport`

### Phase 8: Portfolio Story

Write the case study after the Ohio prototype produces real outputs. The case study should emphasize decision-support value, lineage, limitations, and next steps.

## MVP Done Definition

The MVP is done when the pipeline runs from raw/staged data to final Power BI CSVs, every score is explainable, assumptions are documented, data quality flags are present, and a hiring manager can understand the project from the README and case study.
