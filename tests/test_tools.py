# SPDX-License-Identifier: MIT
"""Unit tests for plausible-mcp tools verifying aggregate, breakdown, realtime, timeseries, and doctor."""
import json
import urllib.request
import pytest

from plausible_mcp.server import (
    get_aggregate_stats,
    get_breakdown,
    get_realtime_visitors,
    get_timeseries,
    doctor,
    clean_site_id,
    resolve_date_params,
    resolve_property,
)
try:
    from .conftest import mock_plausible_router
except ImportError:
    from conftest import mock_plausible_router


@pytest.fixture(autouse=True)
def patch_urllib(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", mock_plausible_router)


def test_clean_site_id():
    assert clean_site_id("https://surendranb.com/") == "surendranb.com"
    assert clean_site_id("http://freeinference.dev") == "freeinference.dev"
    assert clean_site_id("builditwithai.xyz") == "builditwithai.xyz"
    assert clean_site_id("") == ""


def test_resolve_date_params():
    p, d = resolve_date_params("30d")
    assert p == "30d" and d is None

    p, d = resolve_date_params("today")
    assert p == "day" and d is None

    p, d = resolve_date_params("2026-09-01,2026-09-30")
    assert p == "custom" and d == "2026-09-01,2026-09-30"


def test_resolve_property():
    prop, err = resolve_property("page")
    assert prop == "event:page" and err is None

    prop, err = resolve_property("source")
    assert prop == "visit:source" and err is None

    prop, err = resolve_property("country")
    assert prop == "visit:country" and err is None

    prop, err = resolve_property("event:props:author")
    assert prop == "event:props:author" and err is None

    prop, err = resolve_property("invalid_random_dimension")
    assert prop is None and "[INPUT_FIXABLE]" in err


def test_aggregate_stats_deterministic_fixtures():
    # 1. surendranb.com
    res1 = get_aggregate_stats("surendranb.com", date_range="30d")
    data1 = json.loads(res1)
    assert data1["site_id"] == "surendranb.com"
    assert data1["totals"]["visitors"] == 4120
    assert data1["totals"]["pageviews"] == 9850
    assert data1["totals"]["bounce_rate"] == 42.5
    assert data1["totals"]["visit_duration"] == 115.0

    # 2. freeinference.dev
    res2 = get_aggregate_stats("freeinference.dev", date_range="7d")
    data2 = json.loads(res2)
    assert data2["site_id"] == "freeinference.dev"
    assert data2["totals"]["visitors"] == 18450
    assert data2["totals"]["pageviews"] == 52300

    # 3. builditwithai.xyz
    res3 = get_aggregate_stats("https://builditwithai.xyz/", date_range="30d")
    data3 = json.loads(res3)
    assert data3["site_id"] == "builditwithai.xyz"
    assert data3["totals"]["visitors"] == 35600
    assert data3["totals"]["pageviews"] == 112400


def test_breakdown_pages_and_sources():
    # Pages breakdown
    res_page = get_breakdown("surendranb.com", property_name="page")
    data_page = json.loads(res_page)
    assert data_page["property"] == "event:page"
    assert len(data_page["results"]) >= 4
    assert data_page["results"][0]["page"] == "/"
    assert data_page["results"][0]["visitors"] == 1820

    # Sources breakdown
    res_source = get_breakdown("freeinference.dev", property_name="source")
    data_source = json.loads(res_source)
    assert data_source["property"] == "visit:source"
    assert data_source["results"][0]["source"] == "Google"
    assert data_source["results"][0]["visitors"] == 7800

    # Countries breakdown
    res_country = get_breakdown("builditwithai.xyz", property_name="country")
    data_country = json.loads(res_country)
    assert data_country["property"] == "visit:country"
    assert data_country["results"][0]["country"] == "United States"


def test_realtime_visitors():
    r1 = get_realtime_visitors("surendranb.com")
    d1 = json.loads(r1)
    assert d1["site_id"] == "surendranb.com"
    assert d1["realtime_visitors"] == 14

    r2 = get_realtime_visitors("freeinference.dev")
    d2 = json.loads(r2)
    assert d2["realtime_visitors"] == 47

    r3 = get_realtime_visitors("builditwithai.xyz")
    d3 = json.loads(r3)
    assert d3["realtime_visitors"] == 82


def test_timeseries():
    ts = get_timeseries("surendranb.com", date_range="30d", interval="date")
    data = json.loads(ts)
    assert data["site_id"] == "surendranb.com"
    assert data["interval"] == "date"
    assert len(data["timeseries"]) == 4
    assert data["timeseries"][0]["date"] == "2026-10-10"
    assert data["timeseries"][0]["visitors"] == 520


def test_doctor_healthy():
    doc = doctor()
    data = json.loads(doc)
    assert data["status"] == "healthy"
    assert data["token_valid"] is True
    assert "surendranb.com" in data["sample_sites"]
    assert "freeinference.dev" in data["sample_sites"]
    assert "builditwithai.xyz" in data["sample_sites"]


def test_self_hosted_config(monkeypatch):
    monkeypatch.setenv("PLAUSIBLE_BASE_URL", "https://analytics.internal.corp")
    doc = doctor()
    data = json.loads(doc)
    assert data["endpoint"] == "https://analytics.internal.corp"


# Error classification tests
def test_error_missing_site_id():
    out = get_aggregate_stats("")
    assert "[INPUT_FIXABLE]" in out

    out_breakdown = get_breakdown("")
    assert "[INPUT_FIXABLE]" in out_breakdown


def test_error_unknown_property():
    out = get_breakdown("surendranb.com", property_name="nonexistent_metric_prop")
    assert "[INPUT_FIXABLE]" in out


def test_error_missing_token(monkeypatch):
    monkeypatch.delenv("PLAUSIBLE_API_KEY", raising=False)
    monkeypatch.delenv("PLAUSIBLE_TOKEN", raising=False)
    out = get_aggregate_stats("surendranb.com")
    assert "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]" in out
    assert "No Plausible API key provided" in out


def test_error_invalid_token():
    out = get_aggregate_stats("surendranb.com", token="invalid-token")
    assert "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]" in out
    assert "Authentication failed" in out


def test_error_rate_limited():
    out = get_aggregate_stats("surendranb.com", token="rate-limited-token")
    assert "[TRANSIENT]" in out
    assert "rate limit" in out.lower()


def test_error_server_down():
    out = get_aggregate_stats("surendranb.com", token="server-error-token")
    assert "[TRANSIENT]" in out
    assert "server returned error" in out.lower()
