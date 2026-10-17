# SPDX-License-Identifier: MIT
"""Dynamic skills layer for plausible-mcp: fetches playbook instructions dynamically from GitHub with local fallback."""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import List

from plausible_mcp.telemetry import track_event, track_tool_call

SKILLS_URL = "https://raw.githubusercontent.com/surendranb/plausible-mcp/main/skills"


def _get_local_skills_dir() -> Path:
    # 1. Check package-bundled skills/
    candidate1 = Path(__file__).resolve().parent / "skills"
    if candidate1.exists() and candidate1.is_dir():
        return candidate1
    # 2. Check repo root skills/
    candidate2 = Path(__file__).resolve().parent.parent.parent / "skills"
    if candidate2.exists() and candidate2.is_dir():
        return candidate2
    return candidate1


def get_available_skill_names() -> List[str]:
    local_dir = _get_local_skills_dir()
    if local_dir.exists() and local_dir.is_dir():
        names = sorted(p.stem for p in local_dir.glob("*.md"))
        if names:
            return names
    return ["plausible-overview", "analytics-recipes"]


def skills_list() -> str:
    """List available Plausible Analytics operational skills and playbooks (dynamic, GitHub-first)."""
    t0 = time.perf_counter()
    names = get_available_skill_names()
    track_event("skill_read", {"action": "skills_list", "count": len(names)})
    track_tool_call("skills_list", (time.perf_counter() - t0) * 1000, "success", rows_returned=len(names))
    return json.dumps({
        "skills": names,
        "source": "github+local",
        "description": "Call skill_read(name='<skill_name>') to load full methodology and recipes."
    }, indent=2)


def skill_read(name: str) -> str:
    """Fetch SKILL.md content by name from GitHub, with fallback to local files."""
    t0 = time.perf_counter()
    safe = "".join(c for c in (name or "").strip() if c.isalnum() or c in ("_", "-"))
    if not safe:
        err = "[INPUT_FIXABLE] Empty skill name provided. Call skills_list() first to see available skills."
        track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "error", error_category="ValidationError", error_message=err)
        return err

    # Try GitHub remote fetch first (dynamic fleet updates)
    github_url = f"{SKILLS_URL}/{safe}.md"
    try:
        req = urllib.request.Request(
            github_url,
            headers={"User-Agent": "plausible-mcp"}
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            text = resp.read().decode("utf-8", "replace")
            track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "success", rows_returned=1, result_chars=len(text))
            track_event("skill_read", {"skill": safe, "source": "github"})
            return text
    except Exception:
        pass

    # Fallback to local files
    local_file = _get_local_skills_dir() / f"{safe}.md"
    if local_file.exists():
        try:
            text = local_file.read_text(encoding="utf-8")
            track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "success", rows_returned=1, result_chars=len(text))
            track_event("skill_read", {"skill": safe, "source": "local"})
            return text
        except Exception as e:
            err = f"[TRANSIENT] Failed to read local skill file '{safe}.md': {e}"
            track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "error", error_category="IOError", error_message=err)
            return err

    candidates = ", ".join(get_available_skill_names())
    err = f"[INPUT_FIXABLE] Unknown skill '{name}'. Available skills: [{candidates}]. Call skills_list() to refresh candidates."
    track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "error", error_category="NotFoundError", error_message=err)
    return err
