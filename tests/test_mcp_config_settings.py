"""Tests for .claude/settings.json auto-approve generation."""
import json

from codrag.mcp_config import install_mcp_to_workspace


def test_claude_settings_json_created(tmp_path):
    """install_mcp_to_workspace should create .claude/settings.json with auto-approve."""
    result = install_mcp_to_workspace(
        tmp_path,
        runtimes=["claude-code"],
    )
    settings_path = tmp_path / ".claude" / "settings.json"
    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert "mcp__codrag" in data.get("permissions", {}).get("allow", [])


def test_claude_settings_json_merges_existing(tmp_path):
    """Should merge into existing settings.json without clobbering."""
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    existing = {
        "permissions": {
            "allow": ["Bash"],
            "deny": ["rm -rf"]
        },
        "model": "opus"
    }
    (settings_dir / "settings.json").write_text(json.dumps(existing))

    install_mcp_to_workspace(tmp_path, runtimes=["claude-code"])

    data = json.loads((settings_dir / "settings.json").read_text())
    assert "Bash" in data["permissions"]["allow"]
    assert "rm -rf" in data["permissions"]["deny"]
    assert "opus" == data["model"]
    assert "mcp__codrag" in data["permissions"]["allow"]


def test_claude_settings_json_no_duplicate(tmp_path):
    """Should not add mcp__codrag if it already exists."""
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    existing = {"permissions": {"allow": ["mcp__codrag", "Bash"]}}
    (settings_dir / "settings.json").write_text(json.dumps(existing))

    install_mcp_to_workspace(tmp_path, runtimes=["claude-code"])

    data = json.loads((settings_dir / "settings.json").read_text())
    count = data["permissions"]["allow"].count("mcp__codrag")
    assert count == 1
