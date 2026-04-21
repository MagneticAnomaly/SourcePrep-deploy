"""Tests for MCP collaboration resource content generators."""
import pytest

from prep.mcp.collaboration_handlers import (
    get_collaboration_resources,
    format_activity_resource,
    format_memory_resource,
    format_delta_resource,
    format_conflicts_resource,
    parse_collaboration_uri,
    get_collaboration_prompts,
    get_collaboration_prompt_messages,
)


# ── URI parsing ─────────────────────────────────────────────


def test_parse_uri_delta():
    assert parse_collaboration_uri("delta") == ("delta", {})


def test_parse_uri_memory_with_role():
    result = parse_collaboration_uri("memory/researcher")
    assert result == ("memory", {"role": "researcher"})


def test_parse_uri_agent_findings():
    result = parse_collaboration_uri("agents/custodian/findings")
    assert result == ("agent_findings", {"role": "custodian"})


def test_parse_uri_unknown():
    assert parse_collaboration_uri("structure") is None


def test_parse_uri_memory_no_role():
    assert parse_collaboration_uri("memory/") is None


def test_parse_uri_activity_not_routed():
    """activity is no longer an MCP resource (served via Paperclip)."""
    assert parse_collaboration_uri("activity") is None


def test_parse_uri_conflicts_not_routed():
    """conflicts are pushed to Paperclip, not served as MCP resource."""
    assert parse_collaboration_uri("conflicts") is None


# ── Resource list ───────────────────────────────────────────


def test_get_collaboration_resources_returns_3():
    resources = get_collaboration_resources("proj-1")
    assert len(resources) == 3
    uris = {r["uri"] for r in resources}
    assert "codrag://proj-1/delta" in uris
    # activity and conflicts should NOT be in the list
    assert not any("activity" in u for u in uris)
    assert not any("conflicts" in u for u in uris)


# ── Formatters (kept as internal utils) ─────────────────────


def test_format_activity_empty():
    md = format_activity_resource([])
    assert "No recent activity" in md


def test_format_activity_with_entries():
    entries = [
        {
            "agent_role": "pi/watchdog", "action": "delta_scan",
            "summary": "3 new findings", "created_at": 1712400000.0,
        },
    ]
    md = format_activity_resource(entries)
    assert "pi/watchdog" in md
    assert "3 new findings" in md


def test_format_memory_empty():
    md = format_memory_resource("researcher", [])
    assert "No observations" in md


def test_format_memory_with_observations():
    obs = [
        {
            "content": "Auth uses JWT", "created_at": 1712400000.0,
            "file_path": "src/auth.py", "category": "pattern",
        },
    ]
    md = format_memory_resource("researcher", obs)
    assert "Auth uses JWT" in md
    assert "src/auth.py" in md


def test_format_delta_empty():
    delta = {
        "is_empty": True,
        "hub_changes": [], "module_changes": [],
    }
    md = format_delta_resource(delta)
    assert "No structural changes" in md


def test_format_delta_with_changes():
    delta = {
        "is_empty": False,
        "hub_changes": [
            {"path": "src/gateway.py", "change": "new",
             "dependents_count": 14, "rank": 2},
        ],
        "module_changes": [
            {"name": "gateway", "change": "new", "file_count": 4},
        ],
    }
    md = format_delta_resource(delta)
    assert "src/gateway.py" in md
    assert "gateway" in md


def test_format_conflicts_empty():
    md = format_conflicts_resource([])
    assert "No active conflicts" in md


def test_format_conflicts_with_data():
    conflicts = [
        {
            "file_path": "src/auth.py",
            "agent_a": "researcher",
            "agent_a_assessment": "Keep it",
            "agent_b": "custodian",
            "agent_b_assessment": "Delete it",
            "conflict_type": "contradictory",
            "resolution": "deferred",
        },
    ]
    md = format_conflicts_resource(conflicts)
    assert "src/auth.py" in md
    assert "researcher" in md
    assert "custodian" in md


# ── Prompts ─────────────────────────────────────────────────


def test_get_collaboration_prompts_returns_3():
    prompts = get_collaboration_prompts()
    assert len(prompts) == 3
    names = {p["name"] for p in prompts}
    assert names == {"codrag-handoff", "codrag-scope", "codrag-enrich"}


def test_prompt_handoff_returns_messages():
    result = get_collaboration_prompt_messages(
        "codrag-handoff",
        {"from_role": "researcher", "to_role": "custodian"},
    )
    assert result is not None
    text = result["messages"][0]["content"]["text"]
    assert "researcher" in text
    # Should reference delta, not activity/conflicts
    assert "@codrag://delta" in text
    assert "@codrag://activity" not in text
    assert "@codrag://conflicts" not in text


def test_prompt_scope_returns_messages():
    result = get_collaboration_prompt_messages(
        "codrag-scope", {"role": "researcher"},
    )
    assert result is not None
    text = result["messages"][0]["content"]["text"]
    assert "researcher" in text
    assert "@codrag://conflicts" not in text


def test_prompt_enrich_returns_messages():
    result = get_collaboration_prompt_messages(
        "codrag-enrich", {},
    )
    assert result is not None
    text = result["messages"][0]["content"]["text"]
    assert "codrag_audit" in text
    assert "codrag_impact" in text
    assert "hub files" in text


def test_prompt_triage_no_longer_exists():
    result = get_collaboration_prompt_messages("codrag-triage", {})
    assert result is None


def test_prompt_unknown_returns_none():
    result = get_collaboration_prompt_messages("codrag-unknown", {})
    assert result is None
