# Methodology Notes

## Purpose

The Water System Risk & Funding Priority Index is an explainable screening model for prioritizing public drinking water systems for review. It is designed for portfolio analytics, technical assistance planning, grant-support targeting, and BI demonstration.

It is not a regulatory determination, legal finding, engineering siting tool, official risk assessment, or claim that any system provides unsafe water.

## Ohio MVP Run

- Prototype state: Ohio
- Systems scored: 16,339
- Model version: 0.1.0
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
