"""Tests for Phase 120 scope parameter additions to MCP tool schemas."""
from __future__ import annotations

import json

from prep.mcp_tools import TOOLS


def _all_schemas():
    if isinstance(TOOLS, dict):
        for name, defn in TOOLS.items():
            yield name, defn
    else:
        for defn in TOOLS:
            yield defn["name"], defn


def test_scope_param_present_on_phase120_tools():
    expected = {"prep", "prep_search", "prep_impact", "prep_concepts", "prep_observe"}
    found_with_scope: set[str] = set()
    for name, defn in _all_schemas():
        props = defn.get("inputSchema", {}).get("properties", {})
        if "scope" in props and name in expected:
            # confirm shape and that the Phase 120 named-scope description is present
            assert props["scope"]["type"] == "string"
            assert "scope" in props["scope"].get("description", "").lower(), (
                f"{name}: scope description does not mention 'scope': "
                f"{props['scope']['description']!r}"
            )
            found_with_scope.add(name)
    assert expected.issubset(found_with_scope), f"missing scope param on: {expected - found_with_scope}"


def test_prep_audit_scope_unchanged():
    """prep_audit's existing scope param means 'limit scan to path' — must NOT
    be replaced with the named-scope description."""
    for name, defn in _all_schemas():
        if name != "prep_audit":
            continue
        props = defn.get("inputSchema", {}).get("properties", {})
        if "scope" in props:
            desc = props["scope"]["description"].lower()
            # Old description should still indicate "structural scan" or "directory path"
            assert "scan" in desc or "directory" in desc or "file or directory path" in desc, (
                f"prep_audit scope description was overwritten: {props['scope']['description']!r}"
            )


def test_prep_search_role_description_updated():
    for name, defn in _all_schemas():
        if name != "prep_search":
            continue
        props = defn.get("inputSchema", {}).get("properties", {})
        if "role" not in props:
            continue
        desc = props["role"]["description"].lower()
        # New wording mentions projection / weights, NOT "filtered to only include"
        assert "filtered" not in desc, f"role description still has Phase 67 wording: {desc!r}"
        assert "projection" in desc or "weight" in desc, (
            f"role description doesn't mention projection: {desc!r}"
        )


def test_all_schemas_json_serializable():
    for _name, defn in _all_schemas():
        json.dumps(defn)  # should not raise
