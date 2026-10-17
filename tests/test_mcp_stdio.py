# SPDX-License-Identifier: MIT
"""Native MCP protocol stdio JSON-RPC test verifying initialize, tools/list, and tools/call."""
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest


def test_mcp_stdio_protocol_handshake():
    root = Path(__file__).resolve().parent.parent
    src_dir = root / "src"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(src_dir)
    env["DO_NOT_TRACK"] = "1"
    env["MCP_TELEMETRY_OPT_OUT"] = "1"
    env["PLAUSIBLE_API_KEY"] = "dummy-test-key"

    proc = subprocess.Popen(
        [sys.executable, "-m", "plausible_mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
        env=env,
    )

    try:
        # 1. Send initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-stdio-client", "version": "1.0.0"},
            },
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()

        init_resp_line = proc.stdout.readline()
        assert init_resp_line, "Server did not respond to initialize"
        init_resp = json.loads(init_resp_line)
        assert init_resp.get("id") == 1
        assert "result" in init_resp
        server_info = init_resp["result"].get("serverInfo", {})
        assert server_info.get("name") == "plausible-mcp"

        # 2. Send notifications/initialized
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write(json.dumps(notif) + "\n")
        proc.stdin.flush()

        # 3. Send tools/list
        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        proc.stdin.write(json.dumps(tools_req) + "\n")
        proc.stdin.flush()

        tools_resp_line = proc.stdout.readline()
        assert tools_resp_line, "Server did not respond to tools/list"
        tools_resp = json.loads(tools_resp_line)
        assert tools_resp.get("id") == 2
        tools = tools_resp.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}

        expected_tools = {
            "get_aggregate_stats",
            "get_breakdown",
            "get_realtime_visitors",
            "get_timeseries",
            "doctor",
            "skills_list",
            "skill_read",
        }
        for et in expected_tools:
            assert et in tool_names, f"Expected tool '{et}' missing from tools/list"

        # 4. Call skills_list tool over stdio
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "skills_list", "arguments": {}},
        }
        proc.stdin.write(json.dumps(call_req) + "\n")
        proc.stdin.flush()

        call_resp_line = proc.stdout.readline()
        assert call_resp_line, "Server did not respond to tools/call"
        call_resp = json.loads(call_resp_line)
        assert call_resp.get("id") == 3
        content = call_resp.get("result", {}).get("content", [])
        assert len(content) > 0
        text_out = content[0].get("text", "")
        assert "plausible-overview" in text_out
        assert "analytics-recipes" in text_out

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
