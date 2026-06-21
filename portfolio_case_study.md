# Water System Risk & Funding Priority Index

## 1. Project Title

Water System Risk & Funding Priority Index

## 2. One-Sentence Summary

An explainable public-data decision-support model that prioritizes Ohio public drinking water systems for review based on compliance history, enforcement history, vulnerability, drought exposure, funding match gaps, small-system context, and data quality.

## 3. Business Problem

Public-sector analysts, planners, grant writers, and infrastructure consultants need a transparent way to decide which small water systems may deserve earlier review for compliance support, technical assistance, infrastructure funding research, or resilience planning.

## 4. Why This Problem Matters

Small systems can have limited staff capacity and fewer resources for grant pursuit, reporting, infrastructure planning, and resilience analysis. A reproducible screening model can focus attention while preserving humility about what public data can and cannot prove.

## 5. Data Sources

- EPA ECHO SDWA national download: system inventory, violations, enforcement, facilities, geographic areas, service areas, site visits, and reference codes.
- EPA Public Water System Service Area FeatureServer: Ohio service-area boundaries where available.
- CDC/ATSDR SVI 2022 county data: social vulnerability context.
- Census TIGER/Line 2025 counties and tracts: boundary and centroid support.
- U.S. Drought Monitor county API: 52-week county drought exposure.
- EPA SRF Public Portal: supported as a staged input; no Ohio SRF export was staged in this run.

## 6. Data Model

The final Power BI model uses `pwsid` as the central join key:

- `DimWaterSystem`
- `DimGeography`
- `FactRiskScores`
- `FactViolationsSummary`
- `FactEnforcementSummary`
- `FactFundingSummary`
- `DimRiskTier`
- `DimDate`
- `DataQualityReport`

## 7. Scoring Methodology

The model normalizes each component to 0-100 and applies transparent weights stored in `config/scoring_weights.yaml`:

- Compliance: 30%
- Enforcement: 15%
- Vulnerability: 20%
- Drought: 10%
- Funding gap: 15%
- Small-system context: 10%
- Data quality penalty: -5%

Violation scoring distinguishes health-based violations, monitoring/reporting violations, resolved records, open records, severity, recency, and repetition.

## 8. Dashboard Design

The dashboard wireframe includes executive summary, statewide map, compliance/enforcement, funding gap, vulnerability/drought, system detail, and methodology/limitations pages. The dashboard itself is intentionally not built in this phase.

## 9. Key Findings From Ohio Prototype

This run scored 16,339 Ohio public water system records.

Review tier distribution:

- High Review: 188
- Moderate Review: 756
- Monitor: 6,723
- Lower Priority: 8,672
- Critical Review: 0

System size context:

- Very small: 14,693
- Small: 1,229
- Medium: 210
- Large: 207

Geometry source (mapping precision):

- System-Sourced Service Area (EPA system/state/local polygon): 207
- Modeled Service Area (EPA-modeled polygon): 870
- Approximate Location (county centroid fallback): 15,070
- Unmatched Geography: 192

The large share of approximate geography is an important analytical finding: many systems can be scored from SDWA records, but only 1,077 (6.6%) have an EPA service-area polygon. Modeled boundaries are treated as screening context, not verified service-area determinations.

A separate **source-water protection (SWAP)** overlay adds Ohio EPA protection polygons — 7,390 areas covering 3,751 systems — kept strictly distinct from service areas: a service area is who may receive water, while a SWAP area is where the supply is protected around wells and intakes. Facility points (wells/intakes/treatment plants) are deferred because no public Ohio source publishes usable coordinates.

### Sample findings

These observations come directly from the scored Ohio prototype:

1. **County concentration.** Columbiana County had the largest number of high-review records (13), followed by Mahoning and Summit counties (11 each). High-review records are spread across many counties rather than concentrated in a single metro area.
2. **Size pattern in the highest tiers.** Every one of the 188 High Review records was a small, very small, or medium system; no large system reached the High Review tier. Small systems also showed the highest high-review rate (2.5%, versus 1.0% for very small, 1.9% for medium, and 0% for large), consistent with the project's focus on smaller systems that often have less staff and grant capacity.
3. **Geometry source is tracked, not hidden.** Only 1,077 of 16,339 records (6.6%) have an EPA service-area polygon (207 system-sourced, 870 modeled); the other 15,262 fall back to county centroids or are unmatched and are labeled "Approximate Location." Each system carries an explicit geometry-source tier and confidence so modeled or centroid placement is never overinterpreted as a verified service-area boundary.

These are screening observations from public data, not regulatory findings about any individual system.

## 10. Validation and Limitations

Validation passed 22 checks (expanded from 13), including duplicate PWSID detection, score bounds, required columns, valid risk tiers, valid geometry source tiers and spatial confidence, valid funding match confidence, row-count consistency, a geometry suite (one boundary geometry per PWSID after dissolve, boundary count reconciliation to the EPA source, simplified-geometry area-delta within threshold, parseable GeoJSON for matched systems, a valid map-boundaries FeatureCollection), and a SWAP suite (parseable source-water protection geometry, count reconciliation, and per-system coverage).

Limitations:

- ECHO SDWA data are not real-time.
- County-level SVI and drought are fallback context, not household-level exposure.
- County centroid mapping is suitable for screening only.
- Unmatched SRF records do not prove a system received no funding.
- Model weights are analytical assumptions and should be reviewed with subject-matter experts before operational use.

## 11. What I Would Improve Next

- Stage and match Ohio SRF project exports from the EPA SRF Public Portal.
- Add tract-level SVI using service-area intersections.
- Add PostGIS for national-scale spatial processing.
- Add automated refresh and GitHub Actions validation.
- Add a Power BI data quality page.
- Compare the transparent score to an explainable ML model only after a validated target/outcome is defined.

## 12. Skills Demonstrated

- Public-data data engineering
- GIS feature extraction and centroid fallback logic
- SDWA compliance and enforcement feature engineering
- Transparent scoring model design
- BI-ready dimensional export
- Data quality validation
- Portfolio storytelling with documented limitations
