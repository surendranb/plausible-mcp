# SPDX-License-Identifier: MIT
"""Plausible Analytics MCP server: privacy-first website statistics, real-time visitors, breakdowns, and trendlines for AI agents."""
from __future__ import annotations

import datetime
import functools
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from plausible_mcp import skills
from plausible_mcp.telemetry import (
    MCP_SERVER_VERSION,
    announce_and_fire_boot_events,
    track_event,
    track_tool_call,
)

# ---------------------------------------------------------------------------
# Fleet update checker (async, non-blocking, 24h TTL)
# ---------------------------------------------------------------------------
_FLEET_CACHE_FILE = Path.home() / ".cache" / "mcp_fleet_updates.json"
_UPDATE_CHECK_TTL = 86400  # 24 hours


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        clean = re.sub(r"[^\d.]", "", v)
        return tuple(int(p) for p in clean.split(".") if p.isdigit())
    except Exception:
        return (0,)


def check_server_update(package_name: str, current_version: str, force_check: bool = False) -> dict:
    now = time.time()
    cache = {}
    if _FLEET_CACHE_FILE.exists():
        try:
            cache = json.loads(_FLEET_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    entry = cache.get(package_name, {})
    last_check = entry.get("last_checked", 0)
    latest_version = entry.get("latest_version", current_version)

    if force_check or (now - last_check > _UPDATE_CHECK_TTL):
        try:
            req = urllib.request.Request(
                f"https://pypi.org/pypi/{package_name}/json",
                headers={"User-Agent": f"{package_name}/{current_version}"},
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latest_version = data.get("info", {}).get("version", current_version)
                entry["latest_version"] = latest_version
                entry["last_checked"] = now
                cache[package_name] = entry
                _FLEET_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                tmp = _FLEET_CACHE_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(cache), encoding="utf-8")
                tmp.replace(_FLEET_CACHE_FILE)
        except Exception:
            pass

    has_update = _parse_version(latest_version) > _parse_version(current_version)
    cmd = f"uvx --refresh {package_name}"
    msg = (
        f"An updated version of {package_name} is available (v{latest_version}, current: v{current_version}). "
        f"Inform the user to run '{cmd}' to update."
        if has_update
        else f"{package_name} is up to date (v{current_version})."
    )
    return {
        "server": package_name,
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": has_update,
        "upgrade_command": cmd if has_update else None,
        "message": msg,
    }


# ---------------------------------------------------------------------------
# Plausible Client & Error Absorption Layer
# ---------------------------------------------------------------------------
PROPERTY_ALIASES = {
    "page": "event:page",
    "pages": "event:page",
    "url": "event:page",
    "path": "event:page",
    "source": "visit:source",
    "sources": "visit:source",
    "referrer": "visit:source",
    "traffic_source": "visit:source",
    "country": "visit:country",
    "countries": "visit:country",
    "geo": "visit:country",
    "location": "visit:country",
    "browser": "visit:browser",
    "browsers": "visit:browser",
    "os": "visit:os",
    "operating_system": "visit:os",
    "device": "visit:device",
    "devices": "visit:device",
    "device_type": "visit:device",
    "entry_page": "event:entry_page",
    "landing_page": "event:entry_page",
    "exit_page": "event:exit_page",
    "medium": "visit:medium",
    "utm_medium": "visit:medium",
    "campaign": "visit:campaign",
    "utm_campaign": "visit:campaign",
    "city": "visit:city",
    "region": "visit:region",
    "goal": "event:goal",
}

VALID_PROPERTIES = {
    "event:page",
    "visit:source",
    "visit:country",
    "visit:browser",
    "visit:os",
    "visit:device",
    "event:entry_page",
    "event:exit_page",
    "visit:medium",
    "visit:campaign",
    "visit:city",
    "visit:region",
    "event:goal",
}


def get_base_url() -> str:
    url = os.getenv("PLAUSIBLE_BASE_URL", "https://plausible.io").strip()
    return url.rstrip("/")


def resolve_token(token: Optional[str] = None) -> Optional[str]:
    if token and token.strip():
        return token.strip()
    env_token = os.getenv("PLAUSIBLE_API_KEY") or os.getenv("PLAUSIBLE_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()
    return None


def clean_site_id(site_id: str) -> str:
    cleaned = (site_id or "").strip()
    cleaned = re.sub(r"^https?://", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.rstrip("/")
    return cleaned


def resolve_date_params(date_range: str) -> tuple[str, Optional[str]]:
    dr = (date_range or "30d").strip()
    if dr.lower() == "today":
        return "day", None
    if dr.lower() == "yesterday":
        yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        return "day", yesterday_str
    if dr in ("day", "7d", "30d", "month", "6mo", "12mo"):
        return dr, None
    if "," in dr:
        return "custom", dr
    if re.match(r"^\d{4}-\d{2}-\d{2}$", dr):
        return "day", dr
    return dr, None


def resolve_property(property_name: str) -> tuple[Optional[str], Optional[str]]:
    p = (property_name or "event:page").strip().lower()
    if p in PROPERTY_ALIASES:
        return PROPERTY_ALIASES[p], None
    if p in VALID_PROPERTIES or p.startswith("event:props:") or p.startswith("event:") or p.startswith("visit:"):
        return p, None
    allowed = ", ".join(sorted(VALID_PROPERTIES))
    return None, f"[INPUT_FIXABLE] Unknown property '{property_name}'. Allowed properties: {allowed}, or custom event:props:<name>."


def make_plausible_request(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
    site_id: Optional[str] = None,
) -> tuple[Optional[Any], Optional[str]]:
    """
    Executes HTTP request against Plausible API with comprehensive error absorption.
    Returns (data, None) on success or (None, error_string) on failure.
    """
    active_token = resolve_token(token)
    if not active_token:
        err = (
            "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] No Plausible API key provided. "
            "Set the PLAUSIBLE_API_KEY environment variable or pass token=<key>. "
            "Guided instructions: Log in to your Plausible account (Cloud or self-hosted) -> "
            "Click on your profile avatar -> Settings -> API Keys -> Click '+ New Key' -> "
            "Copy the generated token and export PLAUSIBLE_API_KEY='your_token'."
        )
        return None, err

    base_url = get_base_url()
    url = f"{base_url}{endpoint}"
    if params:
        query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query_string:
            url = f"{url}?{query_string}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {active_token}",
            "User-Agent": f"plausible-mcp/{MCP_SERVER_VERSION}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", "replace").strip()
            if "application/json" in content_type:
                return json.loads(raw), None
            # Some endpoints like /api/v1/stats/realtime/visitors return plain text integer
            try:
                return json.loads(raw), None
            except Exception:
                return raw, None

    except urllib.error.HTTPError as e:
        status_code = e.code
        try:
            err_body = e.read().decode("utf-8", "replace").strip()
        except Exception:
            err_body = str(e)

        if status_code in (401, 403):
            site_info = f" for site '{site_id}'" if site_id else ""
            return None, (
                f"[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] Authentication failed (HTTP {status_code}){site_info}. "
                f"The provided API key is invalid, revoked, or lacks permission to view stats. "
                f"Guided instructions: Go to Plausible Settings -> API Keys -> Create a new key with access to your site "
                f"and update PLAUSIBLE_API_KEY."
            )
        if status_code in (400, 404, 422):
            return None, (
                f"[INPUT_FIXABLE] Plausible API error (HTTP {status_code}): {err_body}. "
                f"Please verify site_id ('{site_id}'), parameters, and date formats."
            )
        if status_code == 429:
            return None, "[TRANSIENT] Plausible API rate limit reached (HTTP 429). Retry after a short backoff."
        if status_code >= 500:
            return None, f"[TRANSIENT] Plausible server returned error HTTP {status_code}: {err_body}. Upstream issue; retry shortly."
        return None, f"[INPUT_FIXABLE] Plausible API returned HTTP {status_code}: {err_body}."

    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return None, (
            f"[TRANSIENT] Network connectivity issue connecting to Plausible at {base_url}: {e}. "
            f"Check your connection or self-hosted endpoint status and retry."
        )
    except Exception as e:
        return None, f"[TRANSIENT] Unexpected error during Plausible API call: {e}"


# ---------------------------------------------------------------------------
# MCP Server Instantiation
# ---------------------------------------------------------------------------
mcp = FastMCP("plausible-mcp")


@mcp.tool()
def get_aggregate_stats(
    site_id: str,
    date_range: str = "30d",
    metrics: Optional[List[str]] = None,
    token: Optional[str] = None,
) -> str:
    """
    Get aggregate website performance totals: visitors, pageviews, bounce_rate, and visit_duration.

    Args:
        site_id: Domain name of the site in Plausible (e.g. 'surendranb.com', 'freeinference.dev').
        date_range: Time period ('day', 'today', 'yesterday', '7d', '30d', 'month', '6mo', '12mo', or 'YYYY-MM-DD,YYYY-MM-DD'). Default '30d'.
        metrics: Optional list of metrics (e.g. ['visitors', 'pageviews', 'bounce_rate', 'visit_duration', 'visits']). Defaults to standard 4 metrics.
        token: Optional Plausible API token. If omitted, uses PLAUSIBLE_API_KEY environment variable.
    """
    t0 = time.perf_counter()
    site = clean_site_id(site_id)
    if not site:
        out = "[INPUT_FIXABLE] Missing site_id. Please provide the site domain name (e.g. 'surendranb.com')."
        track_tool_call("get_aggregate_stats", (time.perf_counter() - t0) * 1000, "error", error_category="ValidationError", error_message=out)
        return out

    period, date = resolve_date_params(date_range)
    metric_list = metrics or ["visitors", "pageviews", "bounce_rate", "visit_duration"]
    metrics_str = ",".join(metric_list)

    params: Dict[str, Any] = {
        "site_id": site,
        "period": period,
        "metrics": metrics_str,
    }
    if date:
        params["date"] = date

    data, err = make_plausible_request("/api/v1/stats/aggregate", params=params, token=token, site_id=site)
    if err:
        track_tool_call("get_aggregate_stats", (time.perf_counter() - t0) * 1000, "error", error_category="APIError", error_message=err)
        return err

    # Flatten nested {"results": {"visitors": {"value": 100}, ...}} for easy model consumption
    raw_results = data.get("results", {}) if isinstance(data, dict) else {}
    flattened_totals: Dict[str, Any] = {}
    if isinstance(raw_results, dict):
        for k, v in raw_results.items():
            if isinstance(v, dict) and "value" in v:
                flattened_totals[k] = v["value"]
            else:
                flattened_totals[k] = v

    out_obj = {
        "site_id": site,
        "date_range": date_range,
        "period": period,
        "metrics": metric_list,
        "totals": flattened_totals,
        "raw_results": raw_results,
    }
    res_str = json.dumps(out_obj, indent=2)
    track_tool_call("get_aggregate_stats", (time.perf_counter() - t0) * 1000, "success", rows_returned=len(flattened_totals), result_chars=len(res_str))
    return res_str


@mcp.tool()
def get_breakdown(
    site_id: str,
    property_name: str = "event:page",
    date_range: str = "30d",
    limit: int = 20,
    token: Optional[str] = None,
) -> str:
    """
    Get metrics breakdown by dimension: pages, sources, countries, browsers, operating systems, or devices.

    Args:
        site_id: Domain name of the site in Plausible (e.g. 'surendranb.com').
        property_name: Dimension to segment by. Accepts aliases: 'page', 'source', 'country', 'browser', 'os', 'device', 'entry_page', 'exit_page', 'city', 'region', or full Plausible names like 'event:page', 'visit:source'.
        date_range: Time period ('day', '7d', '30d', 'month', '6mo', '12mo', or 'YYYY-MM-DD,YYYY-MM-DD'). Default '30d'.
        limit: Maximum number of rows to return (default 20, max 100).
        token: Optional Plausible API token. If omitted, uses PLAUSIBLE_API_KEY environment variable.
    """
    t0 = time.perf_counter()
    site = clean_site_id(site_id)
    if not site:
        out = "[INPUT_FIXABLE] Missing site_id. Please provide the site domain name (e.g. 'surendranb.com')."
        track_tool_call("get_breakdown", (time.perf_counter() - t0) * 1000, "error", error_category="ValidationError", error_message=out)
        return out

    prop, prop_err = resolve_property(property_name)
    if prop_err:
        track_tool_call("get_breakdown", (time.perf_counter() - t0) * 1000, "error", error_category="ValidationError", error_message=prop_err)
        return prop_err

    period, date = resolve_date_params(date_range)
    clamped_limit = max(1, min(int(limit or 20), 100))

    params: Dict[str, Any] = {
        "site_id": site,
        "property": prop,
        "period": period,
        "limit": clamped_limit,
    }
    if date:
        params["date"] = date

    data, err = make_plausible_request("/api/v1/stats/breakdown", params=params, token=token, site_id=site)
    if err:
        track_tool_call("get_breakdown", (time.perf_counter() - t0) * 1000, "error", error_category="APIError", error_message=err)
        return err

    results = data.get("results", []) if isinstance(data, dict) else data
    if not isinstance(results, list):
        results = [results]

    out_obj = {
        "site_id": site,
        "property": prop,
        "date_range": date_range,
        "period": period,
        "total_returned": len(results),
        "results": results,
    }
    res_str = json.dumps(out_obj, indent=2)
    track_tool_call("get_breakdown", (time.perf_counter() - t0) * 1000, "success", rows_returned=len(results), result_chars=len(res_str))
    return res_str


@mcp.tool()
def get_realtime_visitors(
    site_id: str,
    token: Optional[str] = None,
) -> str:
    """
    Get the current count of active real-time visitors on the website right now.

    Args:
        site_id: Domain name of the site in Plausible (e.g. 'surendranb.com').
        token: Optional Plausible API token. If omitted, uses PLAUSIBLE_API_KEY environment variable.
    """
    t0 = time.perf_counter()
    site = clean_site_id(site_id)
    if not site:
        out = "[INPUT_FIXABLE] Missing site_id. Please provide the site domain name (e.g. 'surendranb.com')."
        track_tool_call("get_realtime_visitors", (time.perf_counter() - t0) * 1000, "error", error_category="ValidationError", error_message=out)
        return out

    params = {"site_id": site}
    data, err = make_plausible_request("/api/v1/stats/realtime/visitors", params=params, token=token, site_id=site)
    if err:
        track_tool_call("get_realtime_visitors", (time.perf_counter() - t0) * 1000, "error", error_category="APIError", error_message=err)
        return err

    # Endpoint returns an integer (e.g. 21) or {"visitors": 21}
    count = 0
    if isinstance(data, int):
        count = data
    elif isinstance(data, dict) and "visitors" in data:
        count = int(data["visitors"])
    elif isinstance(data, str) and data.isdigit():
        count = int(data)

    out_obj = {
        "site_id": site,
        "realtime_visitors": count,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    res_str = json.dumps(out_obj, indent=2)
    track_tool_call("get_realtime_visitors", (time.perf_counter() - t0) * 1000, "success", rows_returned=1, result_chars=len(res_str))
    return res_str


@mcp.tool()
def get_timeseries(
    site_id: str,
    date_range: str = "30d",
    interval: str = "date",
    token: Optional[str] = None,
) -> str:
    """
    Get historical timeseries trendlines (visitors, pageviews) over time for plotting charts.

    Args:
        site_id: Domain name of the site in Plausible (e.g. 'surendranb.com').
        date_range: Time period ('day', '7d', '30d', 'month', '6mo', '12mo', or 'YYYY-MM-DD,YYYY-MM-DD'). Default '30d'.
        interval: Aggregation bucket: 'date' (daily) or 'month' (monthly). Default 'date'.
        token: Optional Plausible API token. If omitted, uses PLAUSIBLE_API_KEY environment variable.
    """
    t0 = time.perf_counter()
    site = clean_site_id(site_id)
    if not site:
        out = "[INPUT_FIXABLE] Missing site_id. Please provide the site domain name (e.g. 'surendranb.com')."
        track_tool_call("get_timeseries", (time.perf_counter() - t0) * 1000, "error", error_category="ValidationError", error_message=out)
        return out

    period, date = resolve_date_params(date_range)
    params: Dict[str, Any] = {
        "site_id": site,
        "period": period,
        "interval": interval or "date",
    }
    if date:
        params["date"] = date

    data, err = make_plausible_request("/api/v1/stats/timeseries", params=params, token=token, site_id=site)
    if err:
        track_tool_call("get_timeseries", (time.perf_counter() - t0) * 1000, "error", error_category="APIError", error_message=err)
        return err

    results = data.get("results", []) if isinstance(data, dict) else data
    if not isinstance(results, list):
        results = [results]

    out_obj = {
        "site_id": site,
        "date_range": date_range,
        "period": period,
        "interval": interval,
        "data_points": len(results),
        "timeseries": results,
    }
    res_str = json.dumps(out_obj, indent=2)
    track_tool_call("get_timeseries", (time.perf_counter() - t0) * 1000, "success", rows_returned=len(results), result_chars=len(res_str))
    return res_str


@mcp.tool()
def doctor(token: Optional[str] = None) -> str:
    """
    Test connectivity to Plausible Cloud or self-hosted instance (PLAUSIBLE_BASE_URL) and validate API token.

    Args:
        token: Optional Plausible API token to test. If omitted, tests PLAUSIBLE_API_KEY from environment.
    """
    t0 = time.perf_counter()
    base_url = get_base_url()
    active_token = resolve_token(token)

    if not active_token:
        out = (
            "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] No Plausible API key found. "
            "Set the PLAUSIBLE_API_KEY environment variable or pass token parameter. "
            "Guided instructions: Log in to Plausible (Cloud or self-hosted) -> Settings -> API Keys -> "
            "Click '+ New Key' -> Copy token and export PLAUSIBLE_API_KEY='your_token'."
        )
        track_tool_call("doctor", (time.perf_counter() - t0) * 1000, "error", error_category="AuthMissing", error_message=out)
        return out

    # Test 1: Try /api/v1/sites to list authorized domains
    data, err = make_plausible_request("/api/v1/sites", token=active_token)
    if err is None:
        site_list = []
        if isinstance(data, list):
            site_list = [s.get("domain") or s.get("id") for s in data if isinstance(s, dict)]
        elif isinstance(data, dict) and "sites" in data:
            site_list = [s.get("domain") or s.get("id") for s in data.get("sites", []) if isinstance(s, dict)]

        out_obj = {
            "status": "healthy",
            "endpoint": base_url,
            "token_valid": True,
            "sites_accessible": len(site_list),
            "sample_sites": site_list[:10],
            "message": "Connected successfully to Plausible API. Token is valid.",
        }
        res_str = json.dumps(out_obj, indent=2)
        track_tool_call("doctor", (time.perf_counter() - t0) * 1000, "success", rows_returned=len(site_list), result_chars=len(res_str))
        return res_str

    # If /api/v1/sites returned 404 (some self-hosted instances only expose stats), fallback check
    if "[INPUT_FIXABLE]" in err and "404" in err:
        fallback_data, fallback_err = make_plausible_request("/api/v1/stats/realtime/visitors?site_id=healthcheck", token=active_token)
        # If fallback returns 400 or success, auth passed
        if fallback_err is None or "HTTP 400" in fallback_err:
            out_obj = {
                "status": "healthy",
                "endpoint": base_url,
                "token_valid": True,
                "note": "Sites listing endpoint not available on this instance, but stats auth confirmed.",
                "message": "Connected successfully to Plausible API.",
            }
            res_str = json.dumps(out_obj, indent=2)
            track_tool_call("doctor", (time.perf_counter() - t0) * 1000, "success", rows_returned=1, result_chars=len(res_str))
            return res_str

    track_tool_call("doctor", (time.perf_counter() - t0) * 1000, "error", error_category="DoctorCheckFailed", error_message=err)
    return err


@mcp.tool()
def skills_list() -> str:
    """List available Plausible Analytics operational skills and playbooks."""
    return skills.skills_list()


@mcp.tool()
def skill_read(name: str) -> str:
    """
    Fetch guidance and analytical playbooks for Plausible Analytics by name.

    Args:
        name: Name of skill to read (e.g. 'plausible-overview', 'analytics-recipes'). Call skills_list() to view all.
    """
    return skills.skill_read(name)


@mcp.tool()
def check_for_updates() -> str:
    """Check PyPI for newer versions of plausible-mcp and get upgrade instructions."""
    res = check_server_update("plausible-mcp", MCP_SERVER_VERSION, force_check=True)
    return json.dumps(res, indent=2)


def main():
    announce_and_fire_boot_events()
    track_event("mcp_started", {})
    mcp.run()


if __name__ == "__main__":
    main()
