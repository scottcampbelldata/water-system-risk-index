import pandas as pd

from src.score_risk import data_quality_penalty, funding_gap_component


def test_missing_geography_creates_data_quality_penalty():
    row = pd.Series(
        {
            "data_quality_flags": "missing_population_served | unknown_spatial_confidence",
            "spatial_confidence": "unknown",
            "funding_match_confidence": "unmatched",
        }
    )
    assert data_quality_penalty(row) >= 40


def test_unmatched_funding_does_not_falsely_imply_no_funding():
    unknown = funding_gap_component("unknown_no_staged_srf_record", "unmatched")
    matched_recent = funding_gap_component("recent_matched_project", "exact_pwsid_match")
    assert unknown > matched_recent
    assert unknown < 60
