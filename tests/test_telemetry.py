# SPDX-License-Identifier: MIT
"""Unit tests for telemetry.py Schema v2."""
import pytest
from plausible_mcp.telemetry import (
    SERVER_NAME,
    SCHEMA_VERSION,
    GATEWAY_URLS,
    scrub_props,
    _telemetry_disabled,
    track_event,
    track_tool_call,
)


def test_telemetry_schema_constants():
    assert SERVER_NAME == "plausible-mcp"
    assert SCHEMA_VERSION == 2
    assert len(GATEWAY_URLS) == 2
    assert "https://plausible.builditwithai.xyz/e" in GATEWAY_URLS
    assert "https://plausible-mcp-install-telemetry.reachsuren.workers.dev/e" in GATEWAY_URLS


def test_telemetry_opt_out(monkeypatch):
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    assert _telemetry_disabled() is True

    monkeypatch.setenv("DO_NOT_TRACK", "0")
    monkeypatch.setenv("MCP_TELEMETRY_OPT_OUT", "true")
    assert _telemetry_disabled() is True


def test_scrub_props():
    props = {
        "api_key": "secret-key-1234",
        "token": "token-5678",
        "authorization": "Bearer xyz",
        "tool_name": "get_aggregate_stats",
        "site_id": "surendranb.com",
    }
    clean = scrub_props(props)
    assert clean["api_key"] == "[REDACTED]"
    assert clean["token"] == "[REDACTED]"
    assert clean["authorization"] == "[REDACTED]"
    assert clean["tool_name"] == "get_aggregate_stats"
    assert clean["site_id"] == "surendranb.com"


def test_track_tool_call_smoke():
    # Should not crash even when telemetry is disabled
    track_tool_call("test_tool", 45.2, "success", rows_returned=10)
    track_tool_call("failing_tool", 12.0, "error", error_category="TestError", error_message="Failed intentionally")
