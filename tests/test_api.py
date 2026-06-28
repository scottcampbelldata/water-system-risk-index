"""Unit tests for the pure (DB-free) helpers in waterapi.api.main.

Endpoint behavior against a live database is covered by the api-integration job in
CI (TestClient + Postgres). These tests cover the SQL-building and parsing logic
that is easy to get wrong and does not need a database: the shared filter clause,
bbox parsing, and the geography bucket mapping. All generated SQL uses bound
parameters (never string-interpolated user input), which these tests assert.
"""

import pytest
from fastapi import HTTPException

from waterapi.api.main import GEOGRAPHY_BUCKETS, _bbox_clause, _filters


def test_filters_empty_returns_no_where():
    where, params = _filters(None, None, None, None, None)
    assert where == ""
    assert params == {}


def test_filters_search_is_parameterized():
    where, params = _filters("ada", None, None, None, None)
    assert "ILIKE :q" in where
    # The user value is bound, not interpolated into the SQL string.
    assert "ada" not in where
    assert params["q"] == "%ada%"


def test_filters_combines_clauses_with_and():
    where, params = _filters(None, "Franklin", "Critical Review", "small", None)
    assert where.startswith(" WHERE ")
    assert where.count(" AND ") == 2
    assert params == {"county": "Franklin", "tier": "Critical Review", "size": "small"}


def test_filters_geography_bucket_expands_to_bound_in_list():
    where, params = _filters(None, None, None, None, "approximate")
    expected = GEOGRAPHY_BUCKETS["approximate"]
    assert "geometry_source_tier IN (" in where
    assert [params[f"geo{i}"] for i in range(len(expected))] == expected


def test_filters_unknown_geography_bucket_is_ignored():
    where, params = _filters(None, None, None, None, "not-a-bucket")
    assert where == ""
    assert params == {}


def test_bbox_clause_none_is_empty():
    clause, params = _bbox_clause(None, "b")
    assert clause == ""
    assert params == {}


def test_bbox_clause_parses_and_binds():
    clause, params = _bbox_clause("-84.5,38.0,-80.5,42.0", "b")
    assert "b.min_lon <= :qmaxlon" in clause
    assert params == {"qminlon": -84.5, "qminlat": 38.0, "qmaxlon": -80.5, "qmaxlat": 42.0}


@pytest.mark.parametrize("bad", ["not-a-bbox", "1,2,3", "1,2,3,four"])
def test_bbox_clause_rejects_malformed_input(bad):
    with pytest.raises(HTTPException) as exc:
        _bbox_clause(bad, "b")
    assert exc.value.status_code == 400


def test_bbox_clause_empty_string_is_treated_as_absent():
    # An empty bbox is "no viewport filter", not a malformed request.
    assert _bbox_clause("", "b") == ("", {})
