# plausible-mcp

[![PyPI version](https://img.shields.io/pypi/v/plausible-mcp.svg)](https://pypi.org/project/plausible-mcp/)
[![npm version](https://img.shields.io/npm/v/plausible-analytics-mcp.svg)](https://www.npmjs.com/package/plausible-analytics-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Fast, privacy-first [Plausible Analytics](https://plausible.io) Model Context Protocol (MCP) server for AI coding agents and LLM harnesses. Works seamlessly with both Plausible Cloud and self-hosted Plausible installations.

## Quick Start

### Run with uvx (Python)
```bash
export PLAUSIBLE_API_KEY="your_api_key_here"
uvx plausible-mcp
```

### Run with npx (Node / npm bridge)
```bash
export PLAUSIBLE_API_KEY="your_api_key_here"
npx -y plausible-analytics-mcp
```

## Environment Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PLAUSIBLE_API_KEY` | Your Plausible Stats/Sites API token | Required (or pass via tool `token` arg) |
| `PLAUSIBLE_BASE_URL` | Base URL for self-hosted Plausible | `https://plausible.io` |
| `DO_NOT_TRACK` | Set to `1` to disable anonymous telemetry | `0` |

### Getting an API Key
1. Log in to Plausible (Cloud or your self-hosted instance).
2. Go to **Settings** (user profile menu) -> **API Keys**.
3. Click **+ New Key**, name it `mcp-agent`, and copy the token.
4. Export as `PLAUSIBLE_API_KEY="your_token"`.

## Available Tools

| Tool | Description |
| :--- | :--- |
| `get_aggregate_stats(site_id, date_range="30d", metrics=None, token=None)` | High-level visitor, pageview, bounce rate, and session duration totals |
| `get_breakdown(site_id, property_name="event:page", date_range="30d", limit=20, token=None)` | Segment metrics by pages, traffic sources, countries, browsers, OS, devices |
| `get_realtime_visitors(site_id, token=None)` | Current count of active visitors on the site right now |
| `get_timeseries(site_id, date_range="30d", interval="date", token=None)` | Daily or monthly trendline data points for chart generation |
| `doctor(token=None)` | Test Plausible API connectivity and validate the configured API token |
| `skills_list()` | List dynamic analytics playbooks and methodology guides |
| `skill_read(name)` | Fetch full markdown playbook by name (e.g. `plausible-overview`, `analytics-recipes`) |
| `check_for_updates()` | Check PyPI for newer versions and view upgrade commands |

## Error Absorption Standard

Errors returned to agents are explicitly classified:
- `[INPUT_FIXABLE]`: Parameter errors (e.g., misspelled site_id, unknown dimension). Fix arguments and retry.
- `[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]`: Missing, expired, or unauthorized API key. Prompt user with guided setup steps.
- `[TRANSIENT]`: Upstream rate limits (HTTP 429) or network hiccups. Wait briefly and retry.

## MCP Client Setup

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "plausible": {
      "command": "uvx",
      "args": ["plausible-mcp"],
      "env": {
        "PLAUSIBLE_API_KEY": "YOUR_PLAUSIBLE_API_KEY"
      }
    }
  }
}
```

Or using the npm bridge:
```json
{
  "mcpServers": {
    "plausible": {
      "command": "npx",
      "args": ["-y", "plausible-analytics-mcp"],
      "env": {
        "PLAUSIBLE_API_KEY": "YOUR_PLAUSIBLE_API_KEY"
      }
    }
  }
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.
