# SPDX-License-Identifier: MIT
"""Unit tests for skills.py dynamic skills layer."""
import json
import pytest

from plausible_mcp.skills import skills_list, skill_read


def test_skills_list():
    res = skills_list()
    data = json.loads(res)
    assert "skills" in data
    assert "plausible-overview" in data["skills"]
    assert "analytics-recipes" in data["skills"]


def test_skill_read_local_fallback():
    content = skill_read("plausible-overview")
    assert "Plausible Analytics Overview" in content
    assert "Privacy-First Architecture" in content

    recipes = skill_read("analytics-recipes")
    assert "Analytics Recipes" in recipes
    assert "Recipe 1" in recipes


def test_skill_read_unknown():
    res = skill_read("non-existent-skill")
    assert "[INPUT_FIXABLE]" in res
    assert "Unknown skill" in res


def test_skill_read_empty():
    res = skill_read("")
    assert "[INPUT_FIXABLE]" in res
    assert "Empty skill name" in res
