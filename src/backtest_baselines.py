"""Baseline comparison for the review-priority backtest.

The published backtest reports the weighted index only against a loosely
described baseline. The index CONSUMES prior compliance history (the
compliance component is 30% of the weight and the enforcement component is
another 15%), so the honest question is: how much of the lift survives once
prior-violation-count alone is run as a single-feature model on the identical
split?

This script rebuilds the as-of-T score exactly the way src/backtest.py does,
then scores several rankers on the SAME systems, the SAME cutoff and the SAME
outcome labels:

  1. score_asof            - the full weighted index as of the cutoff
  2. prior36_violations    - THE BASELINE: count of violations in the 36 months
                             before the cutoff. One feature. No weights.
  3. prior36_health        - count of health-based violations in the same window
  4. compliance_asof       - the index's own compliance component, alone
  5. static_only           - the index with compliance and enforcement removed
                             (i.e. the part that is NOT prior history)
  6. population_served     - size baseline

Bootstrap resampling gives a confidence interval on the AUC difference between
the index and the single-feature baseline so "beats" is not asserted on a
third-decimal gap.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = REPO_ROOT / "data" / "raw" / "echo_sdwis" / "SDWA_latest_downloads.zip"
CUTOFF = pd.Timestamp("2023-12-31")
HORIZON_MONTHS = 24
TOP_K = [50, 100, 200, 500]
N_BOOT = 2000
SEED = 20260728

VALID_OPEN_STATUSES = {"Addressed", "Unaddressed"}


# --------------------------------------------------------------------------
# Source data: Ohio slice of the ECHO SDWA national download.
# --------------------------------------------------------------------------
def snake(value: str) -> str:
    import re

    value = value.strip().replace("%", "pct")
    value = re.sub(r"[^0-9A-Za-z]+", "_", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"_+", "_", value).strip("_").lower()


def read_state_slice(member_name: str, state_prefix: str = "OH", chunksize: int = 250_000) -> pd.DataFrame:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        member = next(n for n in archive.namelist() if n.endswith(member_name))
        chunks = []
        with archive.open(member) as fh:
            for chunk in pd.read_csv(fh, dtype=str, chunksize=chunksize, low_memory=False):
                if "PWSID" in chunk.columns:
                    chunk = chunk[chunk["PWSID"].fillna("").str.startswith(state_prefix)]
                if not chunk.empty:
                    chunks.append(chunk)
    if not chunks:
        return pd.DataFrame()
    out = pd.concat(chunks, ignore_index=True)
    out.columns = [snake(c) for c in out.columns]
    return out


def violation_base(raw: pd.DataFrame) -> pd.DataFrame:
    """Mirror of src/build_features.violation_base."""
    viol = raw.copy()
    for column in [
        "non_compl_per_begin_date",
        "non_compl_per_end_date",
        "calculated_rtc_date",
        "viol_first_reported_date",
        "viol_last_reported_date",
    ]:
        viol[column] = pd.to_datetime(viol[column], errors="coerce", format="mixed")
    viol["violation_event_date"] = viol["non_compl_per_begin_date"].fillna(viol["viol_first_reported_date"])
    viol["is_open_violation"] = viol["violation_status"].isin(VALID_OPEN_STATUSES)
    viol["is_health_based"] = viol["is_health_based_ind"].eq("Y")
    viol["is_monitoring_reporting"] = viol["violation_category_code"].isin(["MR", "MON", "RPT"])
    viol["is_major_mr"] = viol["is_major_viol_ind"].eq("Y")
    severity = np.select(
        [
            viol["is_health_based"] & viol["is_open_violation"],
            viol["violation_category_code"].isin(["MCL", "MRDL"]),
            viol["violation_category_code"].eq("TT"),
            viol["is_monitoring_reporting"] & viol["is_major_mr"],
            viol["is_monitoring_reporting"],
            viol["violation_status"].eq("Archived"),
        ],
        [100, 90, 85, 55, 35, 10],
        default=25,
    )
    viol["violation_severity_score"] = severity
    return viol.drop_duplicates(["pwsid", "violation_id"])


# --------------------------------------------------------------------------
# As-of-T components (verbatim logic from src/backtest.py).
# --------------------------------------------------------------------------
def _window(records: pd.DataFrame, date_col: str, end: pd.Timestamp, months: int) -> pd.DataFrame:
    start = end - pd.DateOffset(months=months)
    return records[records[date_col].le(end) & records[date_col].gt(start)]


def compliance_component_asof(records: pd.DataFrame, cutoff: pd.Timestamp) -> float:
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


# --------------------------------------------------------------------------
# Metrics.
# --------------------------------------------------------------------------
def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
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


def precision_at_k(scores: np.ndarray, labels: np.ndarray, k: int, rng: np.random.Generator | None = None) -> float:
    """Top-k precision.

    Ties at the k-th boundary matter a lot here: prior-violation-count is a
    small integer, so hundreds of systems can share the cut value and
    mergesort's stable order would silently pick whichever happened to be
    loaded first. When an rng is supplied we break ties at random, which is the
    honest expected value of an arbitrary tie-break.
    """
    if rng is None:
        idx = np.argsort(-scores, kind="mergesort")[:k]
    else:
        jitter = rng.random(len(scores))
        idx = np.lexsort((jitter, -scores))[:k]
    return float(labels[idx].mean())


def expected_precision_at_k(scores: np.ndarray, labels: np.ndarray, k: int, trials: int = 200) -> float:
    rng = np.random.default_rng(SEED)
    return float(np.mean([precision_at_k(scores, labels, k, rng) for _ in range(trials)]))


def metrics_for(scores: np.ndarray, labels: np.ndarray, base_rate: float) -> dict:
    return {
        "auc": round(roc_auc(scores, labels), 4),
        "precision_at_k": {str(k): round(expected_precision_at_k(scores, labels, k), 4) for k in TOP_K},
        "lift_at_k": {
            str(k): round(expected_precision_at_k(scores, labels, k) / base_rate, 2) if base_rate else None
            for k in TOP_K
        },
        "precision_at_k_stable_tiebreak": {str(k): round(precision_at_k(scores, labels, k), 4) for k in TOP_K},
    }


def bootstrap_auc_delta(a: np.ndarray, b: np.ndarray, labels: np.ndarray, n: int = N_BOOT) -> dict:
    """Paired bootstrap over systems of AUC(a) - AUC(b)."""
    rng = np.random.default_rng(SEED)
    m = len(labels)
    deltas = []
    for _ in range(n):
        idx = rng.integers(0, m, m)
        lb = labels[idx]
        if lb.sum() == 0 or lb.sum() == len(lb):
            continue
        deltas.append(roc_auc(a[idx], lb) - roc_auc(b[idx], lb))
    deltas = np.array(deltas)
    return {
        "point_estimate": round(float(roc_auc(a, labels) - roc_auc(b, labels)), 4),
        "ci95_low": round(float(np.percentile(deltas, 2.5)), 4),
        "ci95_high": round(float(np.percentile(deltas, 97.5)), 4),
        "share_of_resamples_where_index_wins": round(float((deltas > 0).mean()), 4),
        "n_resamples": int(len(deltas)),
    }


# --------------------------------------------------------------------------
def main() -> None:
    if not ZIP_PATH.exists():
        sys.exit(f"BLOCKED: missing raw SDWA zip at {ZIP_PATH}")

    weights = yaml.safe_load((REPO_ROOT / "config" / "scoring_weights.yaml").read_text(encoding="utf-8"))[
        "overall_weights"
    ]
    risk = pd.read_csv(REPO_ROOT / "data" / "processed" / "water_system_risk_scores.csv", dtype={"pwsid": str})

    print(f"reading Ohio slice from {ZIP_PATH.name} ...", flush=True)
    raw = read_state_slice("SDWA_VIOLATIONS_ENFORCEMENT.csv")
    print(f"raw OH violation/enforcement rows: {len(raw):,}", flush=True)

    viol_all = violation_base(raw)
    viol = viol_all[viol_all["violation_event_date"].notna()]
    enf = viol_all[viol_all["enforcement_id"].notna()].copy()
    enf["enforcement_date"] = pd.to_datetime(enf["enforcement_date"], errors="coerce", format="mixed")

    horizon_end = CUTOFF + pd.DateOffset(months=HORIZON_MONTHS)
    static_cols = [
        "vulnerability_component",
        "drought_component",
        "funding_gap_component",
        "small_system_component",
        "data_quality_penalty",
    ]
    static = risk.set_index("pwsid")[static_cols]

    by_v = dict(tuple(viol.groupby("pwsid")))
    by_e = dict(tuple(enf.groupby("pwsid")))
    empty_v, empty_e = viol.iloc[0:0], enf.iloc[0:0]

    rows = []
    for pwsid in risk["pwsid"].unique():
        vrec = by_v.get(pwsid, empty_v)
        erec = by_e.get(pwsid, empty_e)
        comp = compliance_component_asof(vrec, CUTOFF)
        enf_c = enforcement_component_asof(erec, CUTOFF)
        st = static.loc[pwsid] if pwsid in static.index else pd.Series(dict.fromkeys(static_cols, 0))
        static_part = (
            float(st["vulnerability_component"]) * weights["vulnerability_component"]
            + float(st["drought_component"]) * weights["drought_component"]
            + float(st["funding_gap_component"]) * weights["funding_gap_component"]
            + float(st["small_system_component"]) * weights["small_system_component"]
            + float(st["data_quality_penalty"]) * weights["data_quality_penalty"]
        )
        score = (
            comp * weights["compliance_risk_component"] + enf_c * weights["enforcement_risk_component"] + static_part
        )
        future = vrec[vrec["violation_event_date"].gt(CUTOFF) & vrec["violation_event_date"].le(horizon_end)]
        prior36 = _window(vrec, "violation_event_date", CUTOFF, 36)
        rows.append(
            {
                "pwsid": pwsid,
                "score_asof": max(0.0, min(100.0, score)),
                "static_only": static_part,
                "compliance_asof": comp,
                "enforcement_asof": enf_c,
                "prior36_violations": len(prior36),
                "prior36_health": int(prior36["is_health_based"].sum()) if len(prior36) else 0,
                "outcome": int(future["is_health_based"].any()),
            }
        )

    df = pd.DataFrame(rows).merge(risk[["pwsid", "population_served"]], on="pwsid", how="left")
    labels = df["outcome"].to_numpy()
    base_rate = float(labels.mean())

    rankers = [
        "score_asof",
        "prior36_violations",
        "prior36_health",
        "compliance_asof",
        "static_only",
        "population_served",
    ]
    report = {
        "reconstruction_note": (
            "Rebuilt from a freshly downloaded ECHO SDWA national file, not the "
            "original run's frozen snapshot. Static (non-history) components are "
            "reused from data/processed/water_system_risk_scores.csv."
        ),
        "cutoff": CUTOFF.date().isoformat(),
        "horizon_months": HORIZON_MONTHS,
        "outcome": "at_least_one_health_based_violation_after_cutoff",
        "n_systems": int(len(df)),
        "n_positive": int(labels.sum()),
        "base_rate": round(base_rate, 4),
        "rankers": {c: metrics_for(df[c].fillna(0).to_numpy(dtype=float), labels, base_rate) for c in rankers},
        "auc_delta_index_minus_prior_violation_baseline": bootstrap_auc_delta(
            df["score_asof"].to_numpy(float),
            df["prior36_violations"].fillna(0).to_numpy(float),
            labels,
        ),
        "spearman_index_vs_prior_violations": round(
            float(df["score_asof"].corr(df["prior36_violations"], method="spearman")), 4
        ),
    }

    out = REPO_ROOT / "data" / "processed" / "backtest_baseline_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    df.to_csv(REPO_ROOT / "data" / "processed" / "backtest_baseline_rows.csv", index=False)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
