"""Unit tests for the as-of feature computations used by the backtest.

build_features.build_compliance_summary / build_enforcement_summary read interim
parquet and write CSVs (integration-level), so we test their no-leakage mirrors in
backtest.py, which take a DataFrame directly. These are the functions whose logic
actually drives the validated score, so they are the highest-value unit targets.
"""

import pandas as pd

from src.backtest import compliance_component_asof, enforcement_component_asof, precision_at_k, roc_auc


def _viol(event_dates, health=False, open_=False, severity=25):
    return pd.DataFrame(
        {
            "violation_event_date": pd.to_datetime(list(event_dates)),
            "is_health_based": [health] * len(event_dates),
            "is_open_violation": [open_] * len(event_dates),
            "is_monitoring_reporting": [False] * len(event_dates),
            "violation_code": ["V"] * len(event_dates),
            "contaminant_code": ["C"] * len(event_dates),
            "violation_severity_score": [severity] * len(event_dates),
        }
    )


def test_compliance_component_zero_with_no_records():
    cutoff = pd.Timestamp("2023-12-31")
    assert compliance_component_asof(_viol([]), cutoff) == 0


def test_compliance_component_ignores_violations_after_cutoff():
    cutoff = pd.Timestamp("2023-12-31")
    # All events are AFTER the cutoff -> no leakage, component is 0.
    future = _viol(["2024-06-01", "2024-09-01"], health=True, open_=True)
    assert compliance_component_asof(future, cutoff) == 0


def test_compliance_component_rewards_recent_health_and_open():
    cutoff = pd.Timestamp("2023-12-31")
    benign = _viol(["2023-01-01", "2023-02-01"])
    severe = _viol(["2023-01-01", "2023-02-01"], health=True, open_=True, severity=100)
    assert compliance_component_asof(severe, cutoff) > compliance_component_asof(benign, cutoff)


def test_compliance_component_is_capped_at_100():
    cutoff = pd.Timestamp("2023-12-31")
    many = _viol([f"2023-{m:02d}-01" for m in range(1, 13)], health=True, open_=True, severity=100)
    assert compliance_component_asof(many, cutoff) <= 100


def _enf(dates, category="Formal", type_code="PEN"):
    return pd.DataFrame(
        {
            "enforcement_date": pd.to_datetime(list(dates)),
            "enf_action_category": [category] * len(dates),
            "enforcement_action_type_code": [type_code] * len(dates),
        }
    )


def test_enforcement_component_formal_outweighs_informal():
    cutoff = pd.Timestamp("2023-12-31")
    formal = _enf(["2023-06-01"], category="Formal", type_code="X")
    informal = _enf(["2023-06-01"], category="Informal", type_code="X")
    assert enforcement_component_asof(formal, cutoff) > enforcement_component_asof(informal, cutoff)


def test_enforcement_component_zero_with_no_records():
    cutoff = pd.Timestamp("2023-12-31")
    assert enforcement_component_asof(_enf([]), cutoff) == 0


def test_roc_auc_perfect_and_random():
    # Perfect separation -> AUC 1.0
    scores = pd.Series([0.1, 0.2, 0.9, 0.95]).to_numpy()
    labels = pd.Series([0, 0, 1, 1]).to_numpy()
    assert roc_auc(scores, labels) == 1.0
    # Inverted -> AUC 0.0
    assert roc_auc(scores, 1 - labels) == 0.0


def test_precision_at_k_ranks_by_score():
    scores = pd.Series([0.9, 0.8, 0.1, 0.05]).to_numpy()
    labels = pd.Series([1, 1, 0, 0]).to_numpy()
    assert precision_at_k(scores, labels, 2) == 1.0
    assert precision_at_k(scores, labels, 4) == 0.5
