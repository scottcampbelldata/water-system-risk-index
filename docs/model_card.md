# Model Card — Water System Review-Priority Score

A concise, evidence-based description of what the model is, how well it works, where
it is fair, and where it must not be used. Quantitative results are reproducible from
`src/backtest.py`, `src/sensitivity.py`, and `src/fairness_audit.py`
(reports written to `data/processed/*_report.json`).

## Model details

- **Name / version:** Water System Risk & Funding Priority Index, model 0.1.0
- **Type:** Transparent, explainable weighted-sum screening score (0–100), not a
  black-box or trained classifier. Weights are documented in
  `config/scoring_weights.yaml`.
- **Geography / scope:** Ohio prototype, 16,339 public water system records.
- **Inputs:** EPA ECHO SDWA compliance & enforcement, CDC/ATSDR SVI, U.S. Drought
  Monitor, EPA service-area + Ohio EPA SWAP geography, EPA SRF funding (when staged).

## Intended use

- **Appropriate:** prioritizing which small systems may deserve *earlier review,
  technical assistance, funding research, or resilience planning*. A screening aid
  for analysts and planners.
- **Out of scope / prohibited:** regulatory determinations, legal findings,
  engineering siting, official safety conclusions, claims that any system is unsafe,
  or **enforcement targeting**. The score directs *support*, not penalties.

## Quantitative validation (backtest)

We froze a cutoff of **2023-12-31**, recomputed the time-varying components
(compliance, enforcement) using only records on or before that date — no leakage —
scored each system, and measured whether high-scored systems had a **subsequent
health-based violation** in the following 24 months.

- Base rate: **2.07%** of systems (338 of 16,339) had a subsequent health-based violation.
- **Model score-as-of-T: ROC AUC 0.74**; the **top 100** systems by score were
  **~9.7× more likely** than the base rate to have a subsequent health-based
  violation (precision@100 ≈ 20% vs. 2.07%).
- **Honest comparison:** the model roughly **ties** a simple "prior 36-month
  violation count" baseline (AUC 0.735) and does not beat it on this single outcome.
  The model's value-add is *combining* compliance, enforcement, vulnerability,
  drought, and funding signals with explainability and an equity lens — not
  out-predicting a violations counter. Population-served alone is a weak predictor
  (precision@100 ≈ 6%).

See `outputs/charts/backtest_precision_at_k.png`.

## Robustness (sensitivity analysis)

500 Monte Carlo trials perturbing every weight by ±20% (renormalized):

- **Spearman rank correlation vs. baseline: mean 0.95** (min 0.85, p05 0.89).
- **Top-100 retention: mean 0.95** (min 0.85).
- **Review-tier assignments never changed** across all 500 trials (tier-change rate 0.0).
- **Component influence** (removing each): vulnerability and compliance drive the
  ranking most (removing vulnerability drops top-100 retention to 0.52, compliance to
  0.28); the **funding-gap component currently adds no ranking signal** because no
  Ohio SRF export was staged in this run (a documented limitation).

The rankings are not fragile to the analytical weight choices.

## Fairness analysis

Social vulnerability (SVI) is **both** a deliberate input (20% weight, to prioritize
under-resourced communities for support) **and** a fairness axis. We checked whether
the model merely re-flags vulnerable communities:

- Overall score vs. SVI correlation: **0.34** (moderate, expected from the input).
- **Objective compliance component vs. SVI correlation: 0.03 (≈ zero).** Vulnerable
  systems do **not** carry systematically more violations in this data.
- Score with the vulnerability input removed vs. SVI: **−0.10** (essentially
  uncorrelated).
- High-review rate rises by SVI quartile (0.4% → 2.1%), driven entirely by the
  intentional equity weighting, not by a covert demographic proxy.

**Interpretation:** the model is not laundering demographics into an objective risk
signal; the SVI tilt is the transparent, intended equity weighting. This is why the
tool is scoped to *support/funding*, where prioritizing vulnerable communities is
appropriate, and explicitly **not** to enforcement.

## Limitations

- Source data (ECHO SDWA) is not real-time; quarterly snapshots lag state records.
- County-level SVI and drought are fallback context, not household exposure.
- The funding-gap signal is inert until Ohio SRF project data is staged.
- The backtest validates one outcome (subsequent health-based violation); other
  outcomes (infrastructure failure, affordability) are not measured.
- Weights are analytical assumptions; they are robust (above) but should be reviewed
  with subject-matter experts before operational use.

## Reproducing the evidence

```powershell
python src/backtest.py         # -> data/processed/backtest_report.json + chart
python src/sensitivity.py      # -> data/processed/sensitivity_report.json
python src/fairness_audit.py   # -> data/processed/fairness_report.json
```
