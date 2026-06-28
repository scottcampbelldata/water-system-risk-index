# Limitations

This project is a transparent, public-data **screening** model. It must not be used
as a regulatory determination, engineering siting tool, legal finding, official risk
assessment, enforcement-targeting tool, or statement that any water system is unsafe.
The score directs *support and review*, not penalties. See the
[model card](model_card.md) for the quantitative validation, fairness analysis, and
intended-use boundaries, and the [methodology](methodology.md) for component
definitions and weights.

## Quantitative caveats (from the model card)

- **The model roughly ties a simple baseline on the validated outcome.** In the
  no-leakage backtest (cutoff 2023-12-31, 24-month horizon) the score reaches
  **ROC AUC ≈ 0.74**, essentially matching a "prior 36-month violation count"
  baseline (≈ 0.735). Its value-add is *combining* signals with explainability and
  an equity lens, not out-predicting a violations counter. Do not oversell it as a
  predictive breakthrough.
- **The funding-gap component is currently inert.** No Ohio SRF project export was
  staged in this run, so every system carries the same "unknown" funding signal and
  the component adds no ranking information (confirmed by the sensitivity analysis).
  It is plumbing waiting for data, not a working feature yet.
- **Rankings are robust to the weight choices** (Spearman ≈ 0.95 under ±20% weight
  perturbation, tier assignments stable), but the weights themselves are analytical
  assumptions that require subject-matter review before operational use.

## Data and modeling limitations

- ECHO SDWA data are refreshed periodically and are **not** real-time state records;
  quarterly SDWIS snapshots lag and require care to avoid double-counting inventory
  rows.
- Vulnerability (SVI) and drought are joined at the **county** level, which masks
  within-county variation; they are resilience/equity context, not household-level
  exposure or a drinking-water-quality finding.
- Service-area geometry is mixed quality: ~1,077 of 16,339 systems have an EPA
  service-area polygon (207 system-sourced, 870 modeled); the rest fall back to
  county centroids or are unmatched. Geometry source and confidence are tracked
  explicitly per record, and modeled polygons are never labeled "verified."
- SRF project records may lack PWSIDs, so funding matching confidence is made
  explicit; a missing match is **not** proof a system received no funding.
- The backtest validates a **single** outcome (a subsequent health-based violation).
  Other outcomes - infrastructure failure, affordability, source contamination - are
  not measured.
