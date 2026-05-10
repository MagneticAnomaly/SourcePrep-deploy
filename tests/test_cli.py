"""
Tests for prep.cli — all CLI commands.

All daemon HTTP calls are mocked so these run without a live server.
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from prep.cli import app

runner = CliRunner()


# ── Helpers ──────────────────────────────────────────────────────

def _mock_response(data=None, status_code=200, json_data=None):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    elif data is not None:
        resp.json.return_value = {"success": True, "data": data}
    else:
        resp.json.return_value = {"success": True, "data": {}}
    resp.raise_for_status.return_value = None
    if status_code >= 400:
        from requests.exceptions import HTTPError
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


def _envelope(data):
    return {"success": True, "data": data}


# ── version ──────────────────────────────────────────────────────

def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Prep v" in result.output


# ── serve (just checks it tries to start) ────────────────────────

def test_serve_help():
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "Start the Prep daemon" in result.output


# ── add ──────────────────────────────────────────────────────────

@patch("prep.cli.requests.post")
def test_add_project(mock_post):
    mock_post.return_value = _mock_response(data={
        "project": {"id": "proj_123", "name": "myapp", "path": "/tmp/myapp", "mode": "standalone"}
    })
    result = runner.invoke(app, ["add", "/tmp/myapp", "--name", "myapp"])
    assert result.exit_code == 0
    assert "Project added" in result.output
    assert "proj_123" in result.output


@patch("prep.cli.requests.post")
def test_add_custom_mode_requires_index_path(mock_post):
    result = runner.invoke(app, ["add", "/tmp/myapp", "--mode", "custom"])
    assert result.exit_code == 1
    assert "index-path is required" in result.output


# ── list ─────────────────────────────────────────────────────────

@patch("prep.cli._get_json")
def test_list_projects(mock_get):
    mock_get.return_value = {
        "projects": [
            {"id": "p1", "name": "Alpha", "path": "/a", "mode": "standalone", "created_at": "2026-01-01T00:00:00"},
            {"id": "p2", "name": "Beta", "path": "/b", "mode": "embedded", "created_at": "2026-01-02T00:00:00"},
        ]
    }
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Alpha" in result.output
    assert "Beta" in result.output


@patch("prep.cli._get_json")
def test_list_empty(mock_get):
    mock_get.return_value = {"projects": []}
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No projects found" in result.output


# ── remove / delete ──────────────────────────────────────────────

@patch("prep.cli.requests.delete")
def test_remove_project(mock_delete):
    mock_delete.return_value = _mock_response(json_data={"success": True, "purged": False})
    result = runner.invoke(app, ["remove", "proj_123"])
    assert result.exit_code == 0
    assert "removed" in result.output


@patch("prep.cli.requests.delete")
def test_delete_is_alias_for_remove(mock_delete):
    mock_delete.return_value = _mock_response(json_data={"success": True, "purged": True})
    result = runner.invoke(app, ["delete", "proj_123", "--purge"])
    assert result.exit_code == 0
    assert "removed" in result.output
    assert "purged" in result.output


# ── status ───────────────────────────────────────────────────────

@patch("prep.cli._get_json")
def test_status_with_index(mock_get):
    # _resolve_project returns early when project_id is given, so only /status call
    mock_get.return_value = {
        "index": {"exists": True, "total_chunks": 500, "embedding_model": "nomic", "last_build_at": "2026-01-01"},
        "trace": {"exists": True, "enabled": True, "counts": {"nodes": 100, "edges": 200}},
        "building": False,
    }
    result = runner.invoke(app, ["status", "p1"])
    assert result.exit_code == 0
    assert "Ready" in result.output


@patch("prep.cli._get_json")
def test_status_no_index(mock_get):
    mock_get.return_value = {
        "index": {"exists": False},
        "trace": {"exists": False, "enabled": False},
        "building": False,
    }
    result = runner.invoke(app, ["status", "p1"])
    assert result.exit_code == 0
    assert "Not Built" in result.output


# ── build ────────────────────────────────────────────────────────

@patch("prep.cli._post_json")
def test_build_started(mock_post):
    mock_post.return_value = {"started": True}
    result = runner.invoke(app, ["build", "p1"])
    assert result.exit_code == 0
    assert "Build started" in result.output


# ── search ───────────────────────────────────────────────────────

@patch("prep.cli._post_json")
def test_search_results(mock_post):
    mock_post.return_value = {
        "results": [
            {"source_path": "src/main.py", "score": 0.85, "preview": "def main():", "span": {"start_line": 1, "end_line": 10}},
        ]
    }
    result = runner.invoke(app, ["search", "how does auth work", "--project", "p1"])
    assert result.exit_code == 0
    assert "src/main.py" in result.output
    assert "0.850" in result.output


@patch("prep.cli._post_json")
def test_search_no_results(mock_post):
    mock_post.return_value = {"results": []}
    result = runner.invoke(app, ["search", "nonexistent", "--project", "p1"])
    assert result.exit_code == 0
    assert "No results" in result.output


# ── context ──────────────────────────────────────────────────────

@patch("prep.cli._post_json")
def test_context_assembly(mock_post):
    mock_post.return_value = {
        "context": "# Source: src/main.py\ndef main(): pass",
        "chunks": [{"id": "c1"}],
        "total_chars": 100,
        "estimated_tokens": 25,
    }
    result = runner.invoke(app, ["context", "how does auth work", "--project", "p1"])
    assert result.exit_code == 0
    assert "Context Assembly Stats" in result.output


@patch("prep.cli._post_json")
def test_context_raw_mode(mock_post):
    mock_post.return_value = {"context": "raw context output", "chunks": [], "total_chars": 18, "estimated_tokens": 5}
    result = runner.invoke(app, ["context", "query", "--project", "p1", "--raw"])
    assert result.exit_code == 0
    assert "raw context output" in result.output
    # Raw mode should NOT show the stats panel
    assert "Context Assembly Stats" not in result.output


# ── config ───────────────────────────────────────────────────────

@patch("prep.cli._get_json")
def test_config_show_all(mock_get):
    mock_get.return_value = {"llm_config": {"embedding": {"source": "native"}}}
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Current configuration" in result.output
    assert "native" in result.output


@patch("prep.cli._get_json")
def test_config_get_key(mock_get):
    mock_get.return_value = {"llm_config": {"embedding": {"source": "native"}}}
    result = runner.invoke(app, ["config", "llm_config.embedding.source"])
    assert result.exit_code == 0
    assert "native" in result.output


@patch("prep.cli._get_json")
def test_config_get_missing_key(mock_get):
    mock_get.return_value = {"llm_config": {}}
    result = runner.invoke(app, ["config", "nonexistent.key"])
    assert result.exit_code == 0
    assert "not found" in result.output


@patch("prep.cli.requests.put")
@patch("prep.cli._get_json")
def test_config_set_key(mock_get, mock_put):
    mock_put.return_value = _mock_response(data={})
    result = runner.invoke(app, ["config", "llm_config.embedding.source", "ollama"])
    assert result.exit_code == 0
    assert "Set llm_config.embedding.source" in result.output
    # Verify the PUT was called with correct nested structure
    call_args = mock_put.call_args
    body = call_args.kwargs.get("json") or call_args[1].get("json")
    assert body == {"llm_config": {"embedding": {"source": "ollama"}}}


# ── mcp-config ───────────────────────────────────────────────────

@patch("prep.mcp_config.generate_mcp_configs")
def test_mcp_config_single_ide(mock_gen):
    mock_gen.return_value = {
        "cursor": {
            "file": ".cursor/mcp.json",
            "config": {"mcpServers": {"prep": {"command": "prep", "args": ["mcp"]}}},
        }
    }
    result = runner.invoke(app, ["mcp-config", "--ide", "cursor"])
    assert result.exit_code == 0
    assert "prep" in result.output


@patch("prep.mcp_config.generate_mcp_configs")
def test_mcp_config_all_ides(mock_gen):
    mock_gen.return_value = {
        "cursor": {"file": ".cursor/mcp.json", "config": {"mcpServers": {}}},
        "vscode": {"file": ".vscode/mcp.json", "config": {"mcpServers": {}}},
    }
    result = runner.invoke(app, ["mcp-config", "--ide", "all"])
    assert result.exit_code == 0
    assert "CURSOR" in result.output
    assert "VSCODE" in result.output


# ── ui ───────────────────────────────────────────────────────────

@patch("webbrowser.open")
def test_ui_opens_browser(mock_open):
    result = runner.invoke(app, ["ui"])
    assert result.exit_code == 0
    mock_open.assert_called_once_with("http://localhost:8400/ui")


# ── _unwrap_envelope ─────────────────────────────────────────────

def test_unwrap_envelope_success():
    from prep.cli import _unwrap_envelope
    result = _unwrap_envelope({"success": True, "data": {"key": "value"}})
    assert result == {"key": "value"}


def test_unwrap_envelope_passthrough():
    from prep.cli import _unwrap_envelope
    result = _unwrap_envelope({"some": "dict"})
    assert result == {"some": "dict"}


# ── _resolve_project ─────────────────────────────────────────────

@patch("prep.cli._get_json")
def test_resolve_project_explicit_id(mock_get):
    from prep.cli import _resolve_project
    result = _resolve_project("http://localhost:8400", project_id="proj_123")
    assert result == "proj_123"
    mock_get.assert_not_called()


@patch("prep.cli._get_json")
def test_resolve_project_single_project(mock_get):
    from prep.cli import _resolve_project
    mock_get.return_value = {"projects": [{"id": "only_one", "path": "/somewhere"}]}
    result = _resolve_project("http://localhost:8400")
    assert result == "only_one"


@patch("prep.cli._get_json")
def test_resolve_project_no_projects(mock_get):
    from prep.cli import _resolve_project
    from click.exceptions import Exit
    mock_get.return_value = {"projects": []}
    with pytest.raises(Exit):
        _resolve_project("http://localhost:8400")


# ── _base_url ────────────────────────────────────────────────────

def test_base_url():
    from prep.cli import _base_url
    assert _base_url("127.0.0.1", 8400) == "http://127.0.0.1:8400"
    assert _base_url("0.0.0.0", 9000) == "http://0.0.0.0:9000"


# ── connection error handling ────────────────────────────────────

@patch("prep.cli._get_json")
def test_list_connection_error(mock_get):
    from requests.exceptions import ConnectionError
    mock_get.side_effect = ConnectionError("refused")
    result = runner.invoke(app, ["list"])
    assert result.exit_code != 0


# ── reset ────────────────────────────────────────────────────────

@patch("prep.cli._delete_json")
@patch("prep.cli._get_json")
def test_full_reset_with_confirmation(mock_get, mock_delete):
    mock_get.return_value = {"projects": [{"id": "p1", "name": "X", "path": "/x"}]}
    mock_delete.return_value = {"deleted": ["documents.json", "embeddings.npy"], "errors": []}
    result = runner.invoke(app, ["reset", "--project", "p1", "--yes"])
    assert result.exit_code == 0
    assert "Full reset complete" in result.output


# ── help text ────────────────────────────────────────────────────

def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Prep" in result.output


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output
    assert "add" in result.output
    assert "build" in result.output
    assert "search" in result.output
    assert "context" in result.output


# ── rules-regenerate ─────────────────────────────────────────────

def test_rules_regenerate_help():
    result = runner.invoke(app, ["rules-regenerate", "--help"])
    assert result.exit_code == 0
    assert "AGENTS.md" in result.output
    assert "CLAUDE.md" in result.output
    assert "--ide" in result.output


def test_rules_regenerate_no_pointer_errors(tmp_path):
    """Bare directory with no .sourceprep/ pointer should error cleanly."""
    result = runner.invoke(
        app, ["rules-regenerate", "--path", str(tmp_path)]
    )
    assert result.exit_code != 0
    assert "No SourcePrep project pointer" in result.output


def test_rules_regenerate_dry_run_lists_targets(tmp_path):
    """Dry-run prints would-be targets, writes nothing."""
    sp_dir = tmp_path / ".sourceprep"
    sp_dir.mkdir()
    (sp_dir / "project.json").write_text('{"id": "test-id", "mode": "embedded"}')
    (tmp_path / "CLAUDE.md").write_text("# Hand-written\n")

    result = runner.invoke(
        app,
        ["rules-regenerate", "--path", str(tmp_path), "--dry-run"],
    )
    assert result.exit_code == 0
    assert "Dry run" in result.output
    assert "agents_md" in result.output  # always present
    assert "claude" in result.output      # detected via CLAUDE.md
    # Dry run must not modify files
    assert (tmp_path / "AGENTS.md").exists() is False
    assert (tmp_path / "CLAUDE.md").read_text() == "# Hand-written\n"


def test_rules_regenerate_writes_claude_only(tmp_path):
    """--ide claude writes CLAUDE.md and preserves hand-written content."""
    sp_dir = tmp_path / ".sourceprep"
    sp_dir.mkdir()
    (sp_dir / "project.json").write_text(
        '{"id": "test-id-123", "mode": "embedded"}'
    )
    (tmp_path / "CLAUDE.md").write_text("# My Project\n\nHand-written body.\n")

    result = runner.invoke(
        app,
        ["rules-regenerate", "--path", str(tmp_path), "--ide", "claude"],
    )
    assert result.exit_code == 0, result.output

    claude_md = (tmp_path / "CLAUDE.md").read_text()
    assert "# My Project" in claude_md
    assert "Hand-written body" in claude_md
    assert "<!-- prep-managed-start -->" in claude_md
    assert "<!-- prep-managed-end -->" in claude_md
    assert "ALWAYS call `prep`" in claude_md  # imperative line landed
    assert "test-id-123" in claude_md         # project_id routing
