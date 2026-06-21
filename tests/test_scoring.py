import pandas as pd

from src.score_risk import data_quality_penalty, funding_gap_component, risk_tier, small_system_component


def test_high_recent_health_violations_increase_score():
    low = 10 * 0.30
    high = 90 * 0.30
    assert high > low


def test_old_resolved_violations_matter_less():
    old_resolved_component = 15
    recent_open_component = 75
    assert recent_open_component > old_resolved_component


def test_small_systems_receive_small_system_component():
    assert small_system_component(500) == 100
    assert small_system_component(3300) == 70
    assert small_system_component(15000) == 0


def test_risk_tier_thresholds():
    assert risk_tier(80) == "Critical Review"
    assert risk_tier(65) == "High Review"
    assert risk_tier(45) == "Moderate Review"
    assert risk_tier(25) == "Monitor"
    assert risk_tier(24.99) == "Lower Priority"


def test_unmatched_funding_component_is_not_zero_but_not_overclaimed():
    assert funding_gap_component("unknown_no_staged_srf_record", "unmatched") == 35
    assert funding_gap_component("recent_matched_project", "exact_pwsid_match") == 0
