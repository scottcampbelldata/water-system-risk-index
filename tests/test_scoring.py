"""Unit tests for the scoring primitives in src/score_risk.py.

These exercise the real functions (not arithmetic stand-ins) so the suite fails if
the scoring logic regresses.
"""

import pandas as pd

from src.score_risk import (
    data_quality_penalty,
    funding_gap_component,
    risk_tier,
    small_system_component,
    top_drivers,
)


def test_small_systems_receive_higher_small_system_component():
    # Smaller systems carry more capacity risk, so the component is
    # non-increasing as population grows across the documented thresholds.
    assert small_system_component(500) == 100
    assert small_system_component(3300) == 70
    assert small_system_component(10000) == 30
    assert small_system_component(15000) == 0
    # Missing population is treated as a mid-range unknown, not zero.
    assert small_system_component(float("nan")) == 50


def test_small_system_component_is_monotonic_non_increasing():
    populations = [100, 500, 3300, 10000, 25000]
    values = [small_system_component(p) for p in populations]
    assert values == sorted(values, reverse=True)


def test_risk_tier_thresholds_are_inclusive_lower_bounds():
    assert risk_tier(100) == "Critical Review"
    assert risk_tier(80) == "Critical Review"
    assert risk_tier(79.99) == "High Review"
    assert risk_tier(65) == "High Review"
    assert risk_tier(45) == "Moderate Review"
    assert risk_tier(25) == "Monitor"
    assert risk_tier(24.99) == "Lower Priority"
    assert risk_tier(0) == "Lower Priority"


def test_unmatched_funding_is_not_zero_but_not_overclaimed():
    # A recent matched project means no funding gap.
    assert funding_gap_component("recent_matched_project", "exact_pwsid_match") == 0
    # An unknown (no staged record) is a moderate gap, not the full penalty.
    assert funding_gap_component("unknown_no_staged_srf_record", "unmatched") == 35
    # A confident name/county match that still found no recent project is the
    # strongest funding-gap signal.
    assert funding_gap_component("", "fuzzy_name_county_match") == 60


def test_data_quality_penalty_accumulates_and_caps_at_100():
    clean = pd.Series(
        {"data_quality_flags": "", "spatial_confidence": "high", "funding_match_confidence": "exact_pwsid_match"}
    )
    assert data_quality_penalty(clean) == 0

    messy = pd.Series(
        {
            "data_quality_flags": "missing_population_served | missing_county",
            "spatial_confidence": "unknown",
            "funding_match_confidence": "unmatched",
        }
    )
    # 15 + 10 + 20 + 5 = 50
    assert data_quality_penalty(messy) == 50
    assert data_quality_penalty(messy) <= 100


def test_top_drivers_excludes_data_quality_penalty():
    # Even when the data-quality penalty is the largest raw component, it must not
    # appear as a "driver" of higher priority (it has a negative weight and lowers
    # the score). Regression guard for the top_drivers fix.
    row = pd.Series(
        {
            "compliance_risk_component": 80,
            "enforcement_risk_component": 10,
            "vulnerability_component": 60,
            "drought_component": 5,
            "funding_gap_component": 40,
            "small_system_component": 70,
            "data_quality_penalty": 100,
        }
    )
    drivers = top_drivers(row)
    assert "data quality limitations" not in drivers
    assert len(drivers) == 3
    # Highest positive components come first.
    assert drivers[0] == "recent compliance history"
    assert drivers[1] == "small system capacity context"
    assert drivers[2] == "community vulnerability"
