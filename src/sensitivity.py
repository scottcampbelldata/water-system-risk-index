"""Sensitivity & robustness analysis for the review-priority score.

The component weights are analytical assumptions. This quantifies how much the
rankings actually depend on them, two ways:

1. Monte Carlo: perturb every weight by up to +/-20% (renormalized), recompute the
   ranking, and measure stability (Spearman rank correlation vs. baseline, retention
   of the top 100, and how often a system changes review tier).
2. One-at-a-time: zero each component in turn to see which drive the ranking.

A senior reviewer wants to know the hand-picked weights are not fragile; this shows
the ranking is stable under reasonable weight uncertainty.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from utils import REPO_ROOT, load_yaml

COMPONENTS = [
    "compliance_risk_component",
    "enforcement_risk_component",
    "vulnerability_component",
    "drought_component",
    "funding_gap_component",
    "small_system_component",
    "data_quality_penalty",
]
TIERS = [(80, "Critical Review"), (65, "High Review"), (45, "Moderate Review"), (25, "Monitor"), (0, "Lower Priority")]
N_TRIALS = 500
PERTURB = 0.20
TOP_K = 100


def _score(comp: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return np.clip(comp @ weights, 0, 100)


def _ranks(scores: np.ndarray) -> np.ndarray:
    # dense-rank descending -> position (lower = higher priority); use argsort for stability
    order = np.argsort(-scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(len(scores))
    return ranks


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    # Spearman = Pearson on ranks; inputs are already rank vectors.
    a = a - a.mean()
    b = b - b.mean()
    denom = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / denom) if denom else float("nan")


def _tier(scores: np.ndarray) -> np.ndarray:
    out = np.empty(len(scores), dtype=object)
    out[:] = "Lower Priority"
    for threshold, name in TIERS:
        out[scores >= threshold] = name
    return out


def run_sensitivity(n_trials: int = N_TRIALS, perturb: float = PERTURB, seed: int = 7) -> dict:
    risk = pd.read_csv(REPO_ROOT / "data" / "processed" / "water_system_risk_scores.csv", dtype={"pwsid": str})
    comp = risk[COMPONENTS].fillna(0).to_numpy(dtype=float)
    weight_map = load_yaml(REPO_ROOT / "config" / "scoring_weights.yaml")["overall_weights"]
    base_w = np.array([weight_map[c] for c in COMPONENTS], dtype=float)

    base_scores = _score(comp, base_w)
    base_ranks = _ranks(base_scores)
    base_tiers = _tier(base_scores)
    base_top = set(np.argsort(-base_scores, kind="mergesort")[:TOP_K])

    rng = np.random.default_rng(seed)
    spearmans, retentions, tier_changes = [], [], []
    for _ in range(n_trials):
        factors = 1 + rng.uniform(-perturb, perturb, size=base_w.shape)
        w = base_w * factors
        scores = _score(comp, w)
        spearmans.append(_spearman(base_ranks, _ranks(scores)))
        top = set(np.argsort(-scores, kind="mergesort")[:TOP_K])
        retentions.append(len(base_top & top) / TOP_K)
        tier_changes.append(float((_tier(scores) != base_tiers).mean()))

    # One-at-a-time component influence: zero each weight, measure ranking impact.
    one_at_a_time = {}
    for i, name in enumerate(COMPONENTS):
        w = base_w.copy()
        w[i] = 0.0
        scores = _score(comp, w)
        top = set(np.argsort(-scores, kind="mergesort")[:TOP_K])
        one_at_a_time[name] = {
            "spearman_vs_base": round(_spearman(base_ranks, _ranks(scores)), 4),
            "top100_retained": round(len(base_top & top) / TOP_K, 3),
        }

    report = {
        "n_trials": n_trials,
        "weight_perturbation": f"+/-{int(perturb * 100)}%",
        "top_k": TOP_K,
        "monte_carlo": {
            "spearman_rank_correlation": {"mean": round(float(np.mean(spearmans)), 4), "min": round(float(np.min(spearmans)), 4), "p05": round(float(np.percentile(spearmans, 5)), 4)},
            "top100_retention": {"mean": round(float(np.mean(retentions)), 4), "min": round(float(np.min(retentions)), 4), "p05": round(float(np.percentile(retentions, 5)), 4)},
            "tier_change_rate": {"mean": round(float(np.mean(tier_changes)), 4), "max": round(float(np.max(tier_changes)), 4)},
        },
        "component_influence_when_removed": one_at_a_time,
    }
    (REPO_ROOT / "data" / "processed" / "sensitivity_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run_sensitivity()
