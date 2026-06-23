# Methodology Notes

## Purpose

The Water System Risk & Funding Priority Index is an explainable screening model for prioritizing public drinking water systems for review. It is designed for portfolio analytics, technical assistance planning, grant-support targeting, and BI demonstration.

It is not a regulatory determination, legal finding, engineering siting tool, official risk assessment, or claim that any system provides unsafe water.

## Ohio MVP Run

- Prototype state: Ohio
- Records scored: 16,339 Ohio public water system records
- Service-area boundaries: 1,077 EPA polygons (207 system-sourced, 870 modeled)
- Source-water protection (SWAP): 7,390 Ohio EPA areas covering 3,751 systems
- Model version: 0.1.0
- Validation: 22 checks (expanded from 13 to cover geometry source tier, boundary
  dissolve, count reconciliation, simplification quality, and SWAP areas)
- Final scoring output: `data/processed/water_system_risk_scores.csv`
- Power BI fact table: `data/powerbi/FactRiskScores.csv`

## Component Scores

Each component is normalized to 0-100 before weighting:

| Component | Weight | Notes |
|---|---:|---|
| Compliance risk | 0.30 | Recent, repeated, health-based, and unresolved violations carry more weight. |
| Enforcement risk | 0.15 | Formal and recent actions carry more weight than informal or older actions. |
| Vulnerability | 0.20 | County-level CDC/ATSDR SVI percentile fallback in the MVP. |
| Drought exposure | 0.10 | U.S. Drought Monitor county exposure over the last 52 weeks. |
| Funding gap | 0.15 | Possible review signal only; unmatched SRF data is not proof of no funding. |
| Small system | 0.10 | Analytical size thresholds configured in `config/scoring_weights.yaml`. |
| Data quality penalty | -0.05 | Penalizes missing or low-confidence data. |

## Risk Tiers

- Critical Review: score >= 80
- High Review: score >= 65 and < 80
- Moderate Review: score >= 45 and < 65
- Monitor: score >= 25 and < 45
- Lower Priority: score < 25

## Geography and Spatial Confidence

Each record is mapped using the most precise geometry available, and the geometry
source is tracked explicitly. Real EPA service-area polygons are used where they
exist; the original geometry is preserved in an audit artifact and a topology-
simplified copy is served to the map.

| Geometry source tier | User-facing label | Spatial confidence |
|---|---|---|
| `verified_service_area_boundary` (EPA `Symbology_Field = System Sourced`) | System-Sourced Service Area | very_high |
| `modeled_service_area_boundary` (EPA modeled) | Modeled Service Area | medium_high |
| `validated_system_coordinate` | Approximate Location | medium |
| `city_or_zip_centroid` | Approximate Location | low |
| `county_centroid` | Approximate Location | very_low |
| `unmatched` | Unmatched Geography | unknown |

Modeled EPA boundaries are screening/visualization context, not legal service-area
determinations, and are not labeled "verified." In the current Ohio run, 1,077 of
16,339 records have a service-area polygon (207 system-sourced, 870 modeled); the
remainder fall back to county centroids or are unmatched.

Source-water protection areas (SWAP) are kept strictly separate from service-area
boundaries: a service area describes who may receive water, while a SWAP area
describes where the supply is protected around wells or surface-water intakes.
Ohio EPA SWAP polygons (groundwater protection areas, inner management zones, and
inland / Lake Erie / Ohio River surface-water areas) are loaded as a distinct
overlay - 7,390 dissolved areas covering 3,751 systems - and surfaced per system
as a `source_protection_status` of `available` or `none`. Facility points
(wells/intakes/treatment plants) are deferred: no public Ohio source publishes
usable coordinates.

## Key Assumptions

- SDWA quarterly snapshots are filtered to Ohio PWSIDs and latest inventory records are used for the master table.
- Violation rows are deduplicated by `pwsid` and `violation_id` before compliance counts to avoid inflation from repeated enforcement rows.
- Enforcement rows are deduplicated by `pwsid` and `enforcement_id`.
- EPA service-area boundaries are used where matched; otherwise county centroids are used and marked as low confidence.
- SVI and drought are joined at county level in the MVP, even when service areas are available.
- No SRF portal export was staged in this run, so funding records are marked `unmatched` with a documented limitation.

## Appropriate Use

Use this model to screen for systems that may deserve review, support, funding research, or follow-up analysis.

Do not use it to claim a system is unsafe, dangerous, contaminated, legally noncompliant, or unfunded.
