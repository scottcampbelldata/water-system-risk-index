# Power BI Data Dictionary

## Model Tables

| Power BI table | Source file | Grain | Purpose |
|---|---|---|---|
| FactRiskScores | `data/powerbi/FactRiskScores.csv` | One row per PWSID | Final score, tier, rank, drivers, and explanation. |
| DimWaterSystem | `data/powerbi/DimWaterSystem.csv` | One row per PWSID | System profile, size, source water, owner, activity, and data quality flags. |
| FactViolationsSummary | `data/powerbi/FactViolationsSummary.csv` | One row per PWSID | Compliance history features and compliance component. |
| FactEnforcementSummary | `data/powerbi/FactEnforcementSummary.csv` | One row per PWSID | Enforcement history features and enforcement component. |
| FactFundingSummary | `data/powerbi/FactFundingSummary.csv` | One row per PWSID | SRF funding match summary and matching confidence. |
| DimGeography | `data/powerbi/DimGeography.csv` | One row per PWSID | Best available geography, SVI, drought, and spatial confidence. |
| DimRiskTier | `data/powerbi/DimRiskTier.csv` | One row per tier | Sort order and minimum score thresholds. |
| DimDate | `data/powerbi/DimDate.csv` | One row per score date | Date helper table. |
| DataQualityReport | `data/powerbi/DataQualityReport.csv` | One row per validation check | Pipeline validation status and notes. |

## Key Columns

| Table | Column | Data type | Business definition | Source / transformation |
|---|---|---|---|---|
| DimWaterSystem | pwsid | Text | Public Water System ID. | EPA ECHO SDWA `PWSID`. |
| DimWaterSystem | pws_name | Text | Reported public water system name. | EPA ECHO SDWA latest PWS snapshot. |
| DimWaterSystem | county | Text | Reported county or county list. | SDWA geographic areas; may be blank. |
| DimWaterSystem | population_served | Number | Reported population served. | SDWA `POPULATION_SERVED_COUNT`. |
| DimWaterSystem | system_size_class | Text | Analytical size class. | Configured thresholds in `scoring_weights.yaml`. |
| DimWaterSystem | spatial_confidence | Text | Confidence in mapped location. | EPA service-area match or county fallback logic. |
| FactViolationsSummary | total_violations_36m | Whole number | Violation count in the last 36 months. | Deduplicated SDWA violations. |
| FactViolationsSummary | health_based_violations_36m | Whole number | Recent health-based violation count. | SDWA `IS_HEALTH_BASED_IND = Y`. |
| FactViolationsSummary | open_violation_flag | Boolean | Whether recent records include addressed/unaddressed open status. | SDWA violation status. |
| FactViolationsSummary | compliance_risk_component | Number | Normalized compliance component. | Weighted violation severity/count logic. |
| FactEnforcementSummary | enforcement_actions_36m | Whole number | Recent enforcement action count. | Deduplicated SDWA enforcement IDs. |
| FactEnforcementSummary | formal_actions_60m | Whole number | Formal actions in 60 months. | SDWA `ENF_ACTION_CATEGORY`. |
| FactEnforcementSummary | enforcement_risk_component | Number | Normalized enforcement component. | Formal, informal, penalty, recency logic. |
| FactFundingSummary | funding_match_confidence | Text | Confidence level of SRF match. | Exact/fuzzy/staged matching; `unmatched` if no staged match. |
| FactFundingSummary | funding_gap_flag | Text | Funding review indicator. | Does not prove lack of funding. |
| DimGeography | latitude | Number | Best available latitude. | EPA service-area centroid or county centroid fallback. |
| DimGeography | longitude | Number | Best available longitude. | EPA service-area centroid or county centroid fallback. |
| DimGeography | geo_join_confidence | Text | Join confidence for geography-derived features. | Service-area or county fallback. |
| DimGeography | overall_svi_percentile | Number | County SVI overall percentile. | CDC/ATSDR SVI 2022 county data. |
| DimGeography | drought_component | Number | Normalized recent drought component. | U.S. Drought Monitor county statistics. |
| FactRiskScores | overall_risk_score | Number | Weighted review-priority score. | Sum of normalized components and data quality penalty. |
| FactRiskScores | risk_tier | Text | Executive-friendly review tier. | Thresholds in `scoring_weights.yaml`. |
| FactRiskScores | rank_statewide | Whole number | Statewide score rank. | Dense rank descending. |
| FactRiskScores | explanation_text | Text | Plain-language explanation. | Top drivers plus spatial/funding caveats. |
| DataQualityReport | status | Text | Pass/fail validation status. | `src/validate_outputs.py`. |

## Relationships

Recommended relationships:

- `DimWaterSystem[pwsid]` one-to-one or one-to-many to all fact tables on `pwsid`
- `FactRiskScores[risk_tier]` many-to-one to `DimRiskTier[risk_tier]`
- `FactRiskScores[score_date]` many-to-one to `DimDate[date]`

Set `DimRiskTier[sort_order]` as the sort column for `risk_tier`.
