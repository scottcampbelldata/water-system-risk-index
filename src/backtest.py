"""Backtest / outcome validation for the review-priority score.

Does a higher review-priority score actually predict future problems? We freeze a
cutoff date T, recompute the time-varying components (compliance, enforcement)
using ONLY records on or before T (no leakage), combine them with the documented
weights to produce a score-as-of-T, and then measure whether high-scored systems
had a *subsequent* health-based violation in the following window.

Metrics: ROC AUC, precision@k and lift over the base rate, compared against naive
baselines (prior violation count, population served). Outputs a JSON report and a
precision@k chart. This converts hand-chosen weights into a measurable claim.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from build_features import violation_base
from utils import REPO_ROOT, load_yaml

CUTOFF = pd.Timestamp("2023-12-31")
HORIZON_MONTHS = 24  # outcome window after the cutoff
TOP_K = [50, 100, 200, 500]


def _window(records: pd.DataFrame, date_col: str, end: pd.Timestamp, months: int) -> pd.DataFrame:
    start = end - pd.DateOffset(months=months)
    return records[records[date_col].le(end) & records[date_col].gt(start)]


def compliance_component_asof(records: pd.DataFrame, cutoff: pd.Timestamp) -> float:
    """Mirror of build_features.build_compliance_summary, evaluated as of `cutoff`."""
    recent36 = _window(records, "violation_event_date", cutoff, 36)
    recent60 = _window(records, "violation_event_date", cutoff, 60)
    repeat_count = (
        int(recent60.duplicated(["violation_code", "contaminant_code"], keep=False).sum()) if not recent60.empty else 0
    )
    open_flag = bool(recent60["is_open_violation"].any()) if not recent60.empty else False
    return min(
        100,
        len(recent36) * 5
        + int(recent36["is_health_based"].sum()) * 12
        + int(recent36["is_monitoring_reporting"].sum()) * 3
        + repeat_count * 4
        + (20 if open_flag else 0)
        + (float(recent60["violation_severity_score"].max()) * 0.25 if not recent60.empty else 0),
    )


def enforcement_component_asof(records: pd.DataFrame, cutoff: pd.Timestamp) -> float:
    """Mirror of build_features.build_enforcement_summary, evaluated as of `cutoff`."""
    recent36 = _window(records, "enforcement_date", cutoff, 36)
    recent60 = _window(records, "enforcement_date", cutoff, 60)
    formal = int(recent60["enf_action_category"].eq("Formal").sum()) if not recent60.empty else 0
    informal = int(recent60["enf_action_category"].eq("Informal").sum()) if not recent60.empty else 0
    penalty = (
        int(recent60["enforcement_action_type_code"].fillna("").str.contains("PEN|PN", case=False).sum())
        if not recent60.empty
        else 0
    )
    return min(100, len(recent36) * 8 + formal * 16 + informal * 5 + penalty * 20 + (10 if len(recent36) else 0))


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank-based ROC AUC (Mann-Whitney). Ties handled via average ranks."""
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = (i + 1 + j + 1) / 2
        i = j + 1
    n_pos = labels.sum()
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    sum_pos = ranks[labels == 1].sum()
    return float((sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def precision_at_k(scores: np.ndarray, labels: np.ndarray, k: int) -> float:
    idx = np.argsort(-scores, kind="mergesort")[:k]
    return float(labels[idx].mean())


def run_backtest(cutoff: pd.Timestamp = CUTOFF, horizon_months: int = HORIZON_MONTHS) -> dict:
    weights = load_yaml(REPO_ROOT / "config" / "scoring_weights.yaml")["overall_weights"]
    risk = pd.read_csv(REPO_ROOT / "data" / "processed" / "water_system_risk_scores.csv", dtype={"pwsid": str})
    viol_all = violation_base()
    viol = viol_all[viol_all["violation_event_date"].notna()]
    # Enforcement records are the rows carrying an enforcement action, mirroring
    # build_enforcement_summary (filter on enforcement_id), NOT a copy of all
    # violations. enforcement_component_asof windows these by enforcement_date.
    if "enforcement_id" in viol_all.columns:
        enf = viol_all[viol_all["enforcement_id"].notna()].copy()
    else:
        enf = viol_all.iloc[0:0].copy()
    if "enforcement_date" in enf.columns:
        enf["enforcement_date"] = pd.to_datetime(enf["enforcement_date"], errors="coerce", format="mixed")
    else:
        enf["enforcement_date"] = pd.NaT

    horizon_end = cutoff + pd.DateOffset(months=horizon_months)

    # Time-invariant components from the current model (proxy), keyed by pwsid.
    static_cols = [
        "vulnerability_component",
        "drought_component",
        "funding_gap_component",
        "small_system_component",
        "data_quality_penalty",
    ]
    static = risk.set_index("pwsid")[static_cols]

    by_pwsid_v = dict(tuple(viol.groupby("pwsid")))
    by_pwsid_e = dict(tuple(enf.groupby("pwsid")))

    rows = []
    for pwsid in risk["pwsid"].unique():
        vrec = by_pwsid_v.get(pwsid, viol.iloc[0:0])
        erec = by_pwsid_e.get(pwsid, enf.iloc[0:0])
        comp = compliance_component_asof(vrec, cutoff)
        enf_c = enforcement_component_asof(erec, cutoff)
        st = static.loc[pwsid] if pwsid in static.index else pd.Series(dict.fromkeys(static_cols, 0))
        score = (
            comp * weights["compliance_risk_component"]
            + enf_c * weights["enforcement_risk_component"]
            + float(st["vulnerability_component"]) * weights["vulnerability_component"]
            + float(st["drought_component"]) * weights["drought_component"]
            + float(st["funding_gap_component"]) * weights["funding_gap_component"]
            + float(st["small_system_component"]) * weights["small_system_component"]
            + float(st["data_quality_penalty"]) * weights["data_quality_penalty"]
        )
        # Outcome: a NEW health-based violation in (cutoff, cutoff+horizon].
        future = vrec[vrec["violation_event_date"].gt(cutoff) & vrec["violation_event_date"].le(horizon_end)]
        outcome = int(future["is_health_based"].any())
        prior36 = len(_window(vrec, "violation_event_date", cutoff, 36))
        rows.append(
            {
                "pwsid": pwsid,
                "score_asof": max(0.0, min(100.0, score)),
                "compliance_asof": comp,
                "prior36_violations": prior36,
                "outcome": outcome,
            }
        )

    df = pd.DataFrame(rows).merge(risk[["pwsid", "population_served"]], on="pwsid", how="left")
    labels = df["outcome"].to_numpy()
    base_rate = float(labels.mean())

    def metrics_for(col: str) -> dict:
        scores = df[col].fillna(0).to_numpy(dtype=float)
        return {
            "auc": round(roc_auc(scores, labels), 4),
            "precision_at_k": {str(k): round(precision_at_k(scores, labels, k), 4) for k in TOP_K},
            "lift_at_k": {
                str(k): round(precision_at_k(scores, labels, k) / base_rate, 2) if base_rate else None for k in TOP_K
            },
        }

    report = {
        "cutoff": cutoff.date().isoformat(),
        "horizon_months": horizon_months,
        "outcome": "at_least_one_health_based_violation_after_cutoff",
        "n_systems": int(len(df)),
        "n_positive": int(labels.sum()),
        "base_rate": round(base_rate, 4),
        "model_score_asof": metrics_for("score_asof"),
        "baseline_prior_violations": metrics_for("prior36_violations"),
        "baseline_population": metrics_for("population_served"),
    }

    out_dir = REPO_ROOT / "data" / "processed"
    (out_dir / "backtest_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _plot(df, base_rate)

    print(json.dumps(report, indent=2))
    return report


def _plot(df: pd.DataFrame, base_rate: float) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    ks = list(range(25, 1001, 25))
    labels = df["outcome"].to_numpy()
    prec_model = [precision_at_k(df["score_asof"].to_numpy(float), labels, k) for k in ks]
    prec_prior = [precision_at_k(df["prior36_violations"].fillna(0).to_numpy(float), labels, k) for k in ks]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(ks, prec_model, label="Review-priority score (as-of)", color="#14746f", linewidth=2)
    ax.plot(ks, prec_prior, label="Prior 36m violation count", color="#b98322", linewidth=1.5, linestyle="--")
    ax.axhline(base_rate, color="#64748b", linestyle=":", label=f"Base rate ({base_rate:.0%})")
    ax.set_xlabel("Top-K systems by score")
    ax.set_ylabel("Share with a subsequent health-based violation")
    ax.set_title("Backtest: does the score predict future health-based violations?")
    ax.legend()
    ax.grid(alpha=0.3)
    charts = REPO_ROOT / "outputs" / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(charts / "backtest_precision_at_k.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    run_backtest()
