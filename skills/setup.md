# Setting Up Plausible Analytics MCP Server

This guide walks through generating and configuring an API key and site ID for the Plausible Analytics MCP Server (Cloud or Self-Hosted).

Official Plausible Documentation: [Plausible Stats API Reference](https://plausible.io/docs/stats-api)

---

## 1. Prerequisites
* A Plausible Analytics account on [plausible.io](https://plausible.io) or your own self-hosted Plausible instance.
* Your Site ID (the domain registered in Plausible, e.g. `example.com`).

---

## 2. API Key Generation Steps (2 Minutes)

1. Log in to [Plausible Analytics](https://plausible.io) (or your self-hosted instance).
2. Click your user avatar in the top right and select **Settings**.
3. In the left navigation, click **API Keys**.
4. Click **+ New Key**.
5. Give the key a descriptive name (e.g. `plausible-mcp-agent`).
6. Select the sites you wish to grant access to (or select **All sites**).
7. Click **Create** and copy your API key immediately (Plausible only displays it once).

---

## 3. Configuring Your MCP Client

### Environment Variables
* `PLAUSIBLE_API_KEY`: Your Plausible API token generated above.
* `PLAUSIBLE_BASE_URL`: (Optional) Base URL if using self-hosted Plausible (defaults to `https://plausible.io`).

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "plausible": {
      "command": "uvx",
      "args": ["plausible-mcp"],
      "env": {
        "PLAUSIBLE_API_KEY": "your_api_key_here",
        "PLAUSIBLE_BASE_URL": "https://plausible.io"
      }
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "plausible": {
      "command": "uvx",
      "args": ["plausible-mcp"],
      "env": {
        "PLAUSIBLE_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Command Line / CLI Testing
```bash
export PLAUSIBLE_API_KEY="your_api_key_here"
uvx plausible-mcp
```

---

## 4. Verification

Run the `test_connection` tool to verify your token and network connectivity:
```python
test_connection()
```
Expected output:
```json
{
  "status": "connected",
  "base_url": "https://plausible.io",
  "authenticated": true
}
```

---

## 5. Troubleshooting & Error Codes

| Error | Cause | Remediation |
|---|---|---|
| `401 Unauthorized` | Invalid or missing `PLAUSIBLE_API_KEY` | Generate a fresh API key under Settings > API Keys. |
| `403 Forbidden` | API key lacks permission for the requested `site_id` | Re-issue the API key with access to that specific domain. |
| `404 Not Found` | Site ID does not exist | Verify the domain name matches exactly what is configured in Plausible. |
| `Connection Error` | Self-hosted instance unreachable | Check `PLAUSIBLE_BASE_URL` (must include `https://` or `http://` without trailing slash). |
