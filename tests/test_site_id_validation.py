# SPDX-License-Identifier: MIT
"""Regression: scanner-shaped site_id is rejected before any outbound request (SUR-489)."""
import urllib.request

import pytest

from plausible_mcp import telemetry
from plausible_mcp.server import (
    clean_site_id,
    get_aggregate_stats,
    get_breakdown,
    get_realtime_visitors,
    get_timeseries,
)

try:
    from .conftest import mock_plausible_router
except ImportError:
    from conftest import mock_plausible_router

HOSTILE = [
    "169.254.169.254",
    "169.254.169.254/latest/meta-data",
    "http://169.254.169.254/latest/meta-data/iam/security-credentials",
    "100.100.100.200/latest/meta-data",
    "[::ffff:169.254.169.254]",
    "0xA9FEA9FE/latest/meta-data",
    "127.0.0.1",
    "127.0.0.1:3000",
    "localhost",
    "[::1]",
    "../../../../../../etc/passwd",
    "file:///etc/passwd",
    "; sleep 5",
    "-oProxyCommand=sleep 5",
    '__import__("time").sleep(5)',
    "oob:9100/mcpf3a91",
    "{{8879*3649}}",
    "${5830*5691}",
    "; echo mcpf3a91$((41*41)) > /tmp/mcpf3a91",
    "--version",
]

SITE_TOOLS = (get_aggregate_stats, get_breakdown, get_realtime_visitors, get_timeseries)


@pytest.fixture(autouse=True)
def isolated_marker(monkeypatch, tmp_path):
    """Keep the had-success marker out of the real home directory."""
    monkeypatch.setattr(telemetry, "_HAD_SUCCESS_FILE", tmp_path / "had_success")


def test_hostile_site_id_rejected_with_no_outbound_request(monkeypatch):
    outbound = []

    def trap(req, *args, **kwargs):
        outbound.append(getattr(req, "full_url", req))
        raise AssertionError(f"outbound request attempted: {outbound[-1]}")

    monkeypatch.setattr(urllib.request, "urlopen", trap)
    monkeypatch.setenv("PLAUSIBLE_API_KEY", "test-token")

    for payload in HOSTILE:
        assert clean_site_id(payload) == "", payload
        for tool in SITE_TOOLS:
            out = tool(payload)
            assert out.startswith("[INPUT_FIXABLE] Invalid site_id"), (payload, out)

    assert outbound == []


def test_legit_slug_accepted_and_requests_fixed_plausible_host(monkeypatch):
    urls = []

    def router(req, timeout=10.0):
        url = req.full_url
        if not url.startswith("https://plausible.io/"):
            raise AssertionError(f"unexpected outbound: {url}")
        urls.append(url)
        return mock_plausible_router(req, timeout)

    monkeypatch.setattr(urllib.request, "urlopen", router)
    monkeypatch.setenv("PLAUSIBLE_API_KEY", "test-token")

    out = get_aggregate_stats("surendranb.com")

    assert '"visitors": 4120' in out
    assert len(urls) == 1
    assert urls[0].startswith("https://plausible.io/api/v1/stats/aggregate?")
    assert "site_id=surendranb.com" in urls[0]


def test_domain_shaped_probe_host_cannot_redirect_the_request(monkeypatch):
    """'metadata.google.internal' is a syntactically valid slug, so it must still land on plausible.io."""
    urls = []

    def router(req, timeout=10.0):
        urls.append(req.full_url)
        return mock_plausible_router(req, timeout)

    monkeypatch.setattr(urllib.request, "urlopen", router)
    monkeypatch.setenv("PLAUSIBLE_API_KEY", "test-token")

    out = get_aggregate_stats("metadata.google.internal")

    plausible_urls = [u for u in urls if u.startswith("https://plausible.io/")]
    assert len(plausible_urls) == 1
    assert all("169.254" not in u and "metadata.google.internal" not in u.split("?")[0] for u in urls)
    assert "site_id=metadata.google.internal" in plausible_urls[0]
    assert out.startswith("[INPUT_FIXABLE]")


def test_traffic_class_labels():
    assert telemetry.traffic_class("InvalidSiteId") == "scan_shaped_args"
    assert telemetry.traffic_class("APIError") == "no_prior_success"
    telemetry._mark_success()
    assert telemetry.traffic_class("APIError") is None
    assert telemetry.traffic_class("InvalidSiteId") == "scan_shaped_args"


def test_rejected_site_emits_scan_shaped_traffic_class(monkeypatch):
    events = []
    monkeypatch.setattr(telemetry, "track_event", lambda name, props=None: events.append((name, props)))

    get_aggregate_stats("oob:9100/mcpf3a91")

    assert len(events) == 1
    name, props = events[0]
    assert name == "tool_executed"
    assert props["error_category"] == "InvalidSiteId"
    assert props["traffic_class"] == "scan_shaped_args"
