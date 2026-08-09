"""Follow-up tests on the saved backtest rows (no re-parse of the 4 GB source).

Answers three questions the headline table raises:
  A. Is the index's edge over prior-violation-count real, or noise?
  B. Does the index beat its OWN compliance component used alone?
  C. How much of the index's ranking is just prior history?
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = 20260728
TOP_K = [50, 100, 200, 500]


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
    sum_pos = ranks[labels == 1].sum()
    return float((sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def boot_delta(a: np.ndarray, b: np.ndarray, labels: np.ndarray, n: int = 2000) -> dict:
    rng = np.random.default_rng(SEED)
    m = len(labels)
    deltas: list[float] = []
    for _ in range(n):
        idx = rng.integers(0, m, m)
        lb = labels[idx]
        if lb.sum() in (0, len(lb)):
            continue
        deltas.append(roc_auc(a[idx], lb) - roc_auc(b[idx], lb))
    delta_array = np.asarray(deltas, dtype=float)
    return {
        "point": round(float(roc_auc(a, labels) - roc_auc(b, labels)), 4),
        "ci95": [
            round(float(np.percentile(delta_array, 2.5)), 4),
            round(float(np.percentile(delta_array, 97.5)), 4),
        ],
        "p_first_wins": round(float((delta_array > 0).mean()), 4),
    }


def overlap_at_k(a: np.ndarray, b: np.ndarray, k: int) -> float:
    return len(set(np.argsort(-a, kind="mergesort")[:k]) & set(np.argsort(-b, kind="mergesort")[:k])) / k


def main() -> None:
    df = pd.read_csv(REPO_ROOT / "data" / "processed" / "backtest_baseline_rows.csv", dtype={"pwsid": str})
    y = df["outcome"].to_numpy()
    idx = df["score_asof"].to_numpy(float)
    prior = df["prior36_violations"].fillna(0).to_numpy(float)
    comp = df["compliance_asof"].to_numpy(float)

    out = {
        "n_systems": int(len(df)),
        "n_positive": int(y.sum()),
        "base_rate": round(float(y.mean()), 4),
        "auc": {
            "weighted_index": round(roc_auc(idx, y), 4),
            "prior36_violation_count_single_feature": round(roc_auc(prior, y), 4),
            "compliance_component_single_feature": round(roc_auc(comp, y), 4),
        },
        "A_index_vs_prior_violation_count": boot_delta(idx, prior, y),
        "B_index_vs_own_compliance_component": boot_delta(idx, comp, y),
        "C_compliance_component_vs_prior_violation_count": boot_delta(comp, prior, y),
        "top_k_overlap_index_vs_prior_violations": {str(k): round(overlap_at_k(idx, prior, k), 3) for k in TOP_K},
        "top_k_overlap_index_vs_compliance_component": {str(k): round(overlap_at_k(idx, comp, k), 3) for k in TOP_K},
        "share_of_index_weight_that_is_prior_history": 0.45,
    }
    print(json.dumps(out, indent=2))
    (REPO_ROOT / "data" / "processed" / "backtest_baseline_followup.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
