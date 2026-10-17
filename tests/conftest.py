# SPDX-License-Identifier: MIT
"""Deterministic fixtures for plausible-mcp tests simulating surendranb.com, freeinference.dev, and builditwithai.xyz."""
import io
import json
import urllib.error
import urllib.parse
import urllib.request
import pytest

SITE_FIXTURES = {
    "surendranb.com": {
        "aggregate": {
            "results": {
                "visitors": {"value": 4120},
                "pageviews": {"value": 9850},
                "bounce_rate": {"value": 42.5},
                "visit_duration": {"value": 115.0},
            }
        },
        "breakdown": {
            "results": [
                {"page": "/", "visitors": 1820},
                {"page": "/essays/mcp-architecture", "visitors": 1240},
                {"page": "/projects", "visitors": 650},
                {"page": "/about", "visitors": 410},
            ]
        },
        "sources": {
            "results": [
                {"source": "Direct / None", "visitors": 1540},
                {"source": "Google", "visitors": 1320},
                {"source": "news.ycombinator.com", "visitors": 890},
                {"source": "twitter.com", "visitors": 370},
            ]
        },
        "countries": {
            "results": [
                {"country": "United States", "visitors": 1950},
                {"country": "India", "visitors": 870},
                {"country": "United Kingdom", "visitors": 420},
                {"country": "Germany", "visitors": 310},
            ]
        },
        "realtime": 14,
        "timeseries": {
            "results": [
                {"date": "2026-10-10", "visitors": 520, "pageviews": 1150},
                {"date": "2026-10-11", "visitors": 580, "pageviews": 1280},
                {"date": "2026-10-12", "visitors": 610, "pageviews": 1420},
                {"date": "2026-10-13", "visitors": 590, "pageviews": 1390},
            ]
        },
    },
    "freeinference.dev": {
        "aggregate": {
            "results": {
                "visitors": {"value": 18450},
                "pageviews": {"value": 52300},
                "bounce_rate": {"value": 31.2},
                "visit_duration": {"value": 245.0},
            }
        },
        "breakdown": {
            "results": [
                {"page": "/", "visitors": 9200},
                {"page": "/providers", "visitors": 4500},
                {"page": "/docs", "visitors": 3100},
                {"page": "/models", "visitors": 1650},
            ]
        },
        "sources": {
            "results": [
                {"source": "Google", "visitors": 7800},
                {"source": "github.com", "visitors": 5200},
                {"source": "Direct / None", "visitors": 3450},
                {"source": "Reddit", "visitors": 2000},
            ]
        },
        "countries": {
            "results": [
                {"country": "United States", "visitors": 8200},
                {"country": "India", "visitors": 3100},
                {"country": "Japan", "visitors": 1800},
                {"country": "Germany", "visitors": 1400},
            ]
        },
        "realtime": 47,
        "timeseries": {
            "results": [
                {"date": "2026-10-10", "visitors": 2400, "pageviews": 6800},
                {"date": "2026-10-11", "visitors": 2750, "pageviews": 7900},
                {"date": "2026-10-12", "visitors": 3100, "pageviews": 8900},
                {"date": "2026-10-13", "visitors": 3250, "pageviews": 9200},
            ]
        },
    },
    "builditwithai.xyz": {
        "aggregate": {
            "results": {
                "visitors": {"value": 35600},
                "pageviews": {"value": 112400},
                "bounce_rate": {"value": 28.4},
                "visit_duration": {"value": 320.0},
            }
        },
        "breakdown": {
            "results": [
                {"page": "/", "visitors": 15600},
                {"page": "/catalog", "visitors": 9800},
                {"page": "/skills", "visitors": 6400},
                {"page": "/docs/mcp-setup", "visitors": 3800},
            ]
        },
        "sources": {
            "results": [
                {"source": "Direct / None", "visitors": 14200},
                {"source": "Google", "visitors": 11500},
                {"source": "news.ycombinator.com", "visitors": 6200},
                {"source": "linkedin.com", "visitors": 3700},
            ]
        },
        "countries": {
            "results": [
                {"country": "United States", "visitors": 16400},
                {"country": "United Kingdom", "visitors": 4500},
                {"country": "India", "visitors": 4200},
                {"country": "Canada", "visitors": 2600},
            ]
        },
        "realtime": 82,
        "timeseries": {
            "results": [
                {"date": "2026-10-10", "visitors": 4900, "pageviews": 15200},
                {"date": "2026-10-11", "visitors": 5300, "pageviews": 16800},
                {"date": "2026-10-12", "visitors": 5700, "pageviews": 18100},
                {"date": "2026-10-13", "visitors": 6100, "pageviews": 19400},
            ]
        },
    },
}

SITES_LIST_FIXTURE = [
    {"domain": "surendranb.com", "timezone": "Asia/Kolkata"},
    {"domain": "freeinference.dev", "timezone": "UTC"},
    {"domain": "builditwithai.xyz", "timezone": "UTC"},
]


class MockHTTPResponse:
    def __init__(self, data: bytes, status: int = 200, content_type: str = "application/json"):
        self.data = data
        self.status = status
        self.headers = {"Content-Type": content_type}

    def read(self, *args, **kwargs) -> bytes:
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def mock_plausible_router(req: urllib.request.Request, timeout: float = 10.0):
    url = req.full_url
    auth = req.headers.get("Authorization", "")
    if not auth or "Bearer" not in auth:
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b'{"error": "Unauthorized"}'))

    # Check for invalid test token
    token = auth.replace("Bearer", "").strip()
    if token == "invalid-token":
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b'{"error": "Invalid API key"}'))

    if token == "rate-limited-token":
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, io.BytesIO(b'{"error": "Rate limit exceeded"}'))

    if token == "server-error-token":
        raise urllib.error.HTTPError(url, 502, "Bad Gateway", {}, io.BytesIO(b'{"error": "Upstream error"}'))

    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    site_id = params.get("site_id", [None])[0]

    # Sites listing
    if parsed.path == "/api/v1/sites":
        return MockHTTPResponse(json.dumps(SITES_LIST_FIXTURE).encode("utf-8"))

    # Validate site_id
    if site_id not in SITE_FIXTURES:
        if site_id == "healthcheck":
            return MockHTTPResponse(b"0", status=200, content_type="text/plain")
        raise urllib.error.HTTPError(
            url, 404, "Not Found", {}, io.BytesIO(f'{{"error": "Site {site_id} not found"}}'.encode("utf-8"))
        )

    site_data = SITE_FIXTURES[site_id]

    if parsed.path == "/api/v1/stats/aggregate":
        return MockHTTPResponse(json.dumps(site_data["aggregate"]).encode("utf-8"))

    if parsed.path == "/api/v1/stats/breakdown":
        prop = params.get("property", ["event:page"])[0]
        if prop == "visit:source":
            res = site_data.get("sources", site_data["breakdown"])
        elif prop == "visit:country":
            res = site_data.get("countries", site_data["breakdown"])
        else:
            res = site_data["breakdown"]
        return MockHTTPResponse(json.dumps(res).encode("utf-8"))

    if parsed.path == "/api/v1/stats/realtime/visitors":
        return MockHTTPResponse(str(site_data["realtime"]).encode("utf-8"), content_type="text/plain")

    if parsed.path == "/api/v1/stats/timeseries":
        return MockHTTPResponse(json.dumps(site_data["timeseries"]).encode("utf-8"))

    raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b'{"error": "Endpoint not found"}'))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    monkeypatch.setenv("MCP_TELEMETRY_OPT_OUT", "1")
    monkeypatch.setenv("PLAUSIBLE_API_KEY", "plausible-test-secret-key-12345")
    monkeypatch.delenv("PLAUSIBLE_BASE_URL", raising=False)
