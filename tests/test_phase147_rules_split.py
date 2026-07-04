"""Phase 147: static-pointer + gitignored volatile context split.

Tracked rules files must converge to a fixed point (no timestamp, atlas,
stats, or project_id), with all volatile content in the gitignored
.sourceprep/AGENT_CONTEXT.md. See
docs/Phase147_Managed-Rules-Churn/PROPOSAL_static-pointer-volatile-context-v2.md
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import time
from pathlib import Path

from prep.core.rules_generator import (
    _build_static_instructions,
    _build_volatile_context,
    _ensure_gitignore_entry,
    _write,
    detect_and_regenerate,
    write_rules_file,
)

_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

_VOLATILE_ARGS = dict(
    project_name="proj",
    atlas_content="IDENTITY: Test project\nSTACK: Python",
    included_paths=["src/"],
    is_preliminary=False,
    stats={"node_count": 7, "edge_count": 9},
    project_id="pid-1234",
)


# ── Split: static side ──────────────────────────────────────────────


def test_static_instructions_deterministic_and_volatile_free():
    for target in ("claude", "cursor", "universal"):
        a = _build_static_instructions(target)
        b = _build_static_instructions(target)
        assert a == b, f"non-deterministic static output for {target}"
        assert not _ISO_RE.search(a), f"timestamp leaked into static ({target})"
        assert "prep_project_id" not in a
        assert "prep-atlas-hash" not in a
        assert "Last updated" not in a
        assert "Codebase Atlas" not in a
        assert "## Focus Areas" not in a
        # Core instructions still present
        assert "prep_search" in a
        assert "prep_impact" in a


def test_static_universal_keeps_verbose_sections():
    content = _build_static_instructions("universal")
    assert "Tool Calling Rules" in content
    assert "MCP Resources" in content
    # Phase 119 concurrency hint must survive the split
    assert "Concurrency limits" in content


def test_static_cline_trigger_block_survives_in_writer(tmp_path):
    write_rules_file(
        project_path=tmp_path, project_name="t", atlas_content="IDENTITY: X",
        ide="cline", project_id="pid",
    )
    content = (tmp_path / ".clinerules").read_text()
    assert "keyword" in content.lower() or "use the SourcePrep MCP tools" in content


# ── Split: volatile side ────────────────────────────────────────────


def test_volatile_context_contains_all_dynamic_sections():
    content = _build_volatile_context(**_VOLATILE_ARGS)
    first_line = content.splitlines()[0]
    assert "SourcePrep structural codebase intelligence" in first_line
    assert "Last updated:" in content
    assert "7 nodes" in content
    assert "prep_project_id: pid-1234" in content
    expected_hash = hashlib.sha256(
        _VOLATILE_ARGS["atlas_content"].strip().encode()
    ).hexdigest()[:12]
    assert f"prep-atlas-hash:{expected_hash}" in content
    assert "## Codebase Atlas" in content
    assert "## Focus Areas" in content


def test_volatile_context_omits_sections_cleanly_when_absent():
    content = _build_volatile_context(
        project_name="p", atlas_content="", included_paths=None,
        is_preliminary=False, stats=None, project_id=None,
    )
    assert "Last updated:" in content
    assert "prep_project_id" not in content
    assert "prep-atlas-hash" not in content
    assert "## Codebase Atlas" not in content
    assert "## Focus Areas" not in content


# ── Pointer wiring per target ───────────────────────────────────────


def test_claude_pointer_is_bare_import(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Mine\n\nUser prose.\n")
    write_rules_file(
        project_path=tmp_path, project_name="t",
        atlas_content="IDENTITY: X", ide="claude", project_id="pid",
    )
    content = (tmp_path / "CLAUDE.md").read_text()
    # Bare import on its own line — never backticked (backticks disable
    # Claude Code import parsing) and never fenced.
    assert "\n@.sourceprep/AGENT_CONTEXT.md\n" in content
    assert "`@.sourceprep" not in content
    # No volatile bytes in the tracked file
    assert "Last updated:" not in content
    assert "prep-atlas-hash" not in content
    assert "IDENTITY: X" not in content
    assert "pid" not in content.replace("pid", "pid") or "prep_project_id" not in content
    # User prose preserved
    assert "User prose." in content


def test_gemini_pointer_is_bare_import(tmp_path):
    (tmp_path / "GEMINI.md").write_text("# Mine\n")
    write_rules_file(
        project_path=tmp_path, project_name="t",
        atlas_content="IDENTITY: X", ide="gemini", project_id="pid",
    )
    content = (tmp_path / "GEMINI.md").read_text()
    assert "\n@.sourceprep/AGENT_CONTEXT.md\n" in content
    assert "Last updated:" not in content


def test_read_pointer_targets_have_instruction_not_volatile(tmp_path):
    for ide, rel in (
        ("agents_md", "AGENTS.md"),
        ("cursor", ".cursor/rules/prep.mdc"),
        ("copilot", ".github/copilot-instructions.md"),
        ("cline", ".clinerules"),
        ("roo_code", ".roo/rules/prep.md"),
        ("windsurf", ".windsurf/rules/prep.md"),
    ):
        target_dir = tmp_path / ide
        target_dir.mkdir()
        write_rules_file(
            project_path=target_dir, project_name="t",
            atlas_content="IDENTITY: X", ide=ide, project_id="pid",
        )
        content = (target_dir / rel).read_text()
        assert ".sourceprep/AGENT_CONTEXT.md" in content, f"no pointer in {rel}"
        assert "Last updated:" not in content, f"volatile leaked into {rel}"
        assert "prep-atlas-hash" not in content, f"atlas hash leaked into {rel}"
        assert "IDENTITY: X" not in content, f"atlas text leaked into {rel}"


def test_volatile_file_written_alongside(tmp_path):
    results = write_rules_file(
        project_path=tmp_path, project_name="t",
        atlas_content="IDENTITY: X", ide="agents_md", project_id="pid",
    )
    assert results.get("agent_context") is True
    ctx = tmp_path / ".sourceprep" / "AGENT_CONTEXT.md"
    assert ctx.exists()
    assert "IDENTITY: X" in ctx.read_text()


# ── Gitignore management ────────────────────────────────────────────


def test_gitignore_noop_without_git_repo(tmp_path):
    assert _ensure_gitignore_entry(tmp_path) is False
    assert not (tmp_path / ".gitignore").exists()


def test_gitignore_noop_when_blanket_covered(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text(".sourceprep/\n")
    assert _ensure_gitignore_entry(tmp_path) is False
    assert (tmp_path / ".gitignore").read_text() == ".sourceprep/\n"


def test_gitignore_respects_negation(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("!.sourceprep/AGENT_CONTEXT.md\n")
    assert _ensure_gitignore_entry(tmp_path) is False
    assert "AGENT_CONTEXT" not in (tmp_path / ".gitignore").read_text().replace(
        "!.sourceprep/AGENT_CONTEXT.md", ""
    )


def test_gitignore_appends_once(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    assert _ensure_gitignore_entry(tmp_path) is True
    content = (tmp_path / ".gitignore").read_text()
    assert ".sourceprep/AGENT_CONTEXT.md" in content
    assert "node_modules/" in content
    # Idempotent
    assert _ensure_gitignore_entry(tmp_path) is False
    assert (tmp_path / ".gitignore").read_text() == content


# ── No-op write guard ───────────────────────────────────────────────


def test_write_skips_identical_content(tmp_path):
    f = tmp_path / "x.md"
    _write(f, "same\n")
    first = f.stat().st_mtime_ns
    time.sleep(0.02)
    _write(f, "same\n")
    assert f.stat().st_mtime_ns == first
    _write(f, "different\n")
    assert f.read_text() == "different\n"


# ── Self-heal: legacy fat block → slim ──────────────────────────────


def test_detect_and_regenerate_slims_legacy_fat_block(tmp_path):
    legacy = (
        "# My project\n\n"
        "<!-- prep-managed-start -->\n"
        "## SourcePrep Integration\n\n"
        "Last updated: 2026-01-01T00:00:00Z | 5 nodes\n\n"
        "## Codebase Atlas\nIDENTITY: Old fat atlas\n"
        "<!-- prep-managed-end -->\n"
        "\nTrailing user text.\n"
    )
    (tmp_path / "AGENTS.md").write_text(legacy)
    results = detect_and_regenerate("no-such-project", tmp_path, "t")
    assert results.get("agents_md") is True
    content = (tmp_path / "AGENTS.md").read_text()
    assert ".sourceprep/AGENT_CONTEXT.md" in content
    assert "Old fat atlas" not in content
    assert "Trailing user text." in content
    # Second run: everything up to date
    assert detect_and_regenerate("no-such-project", tmp_path, "t") == {}


# ── The FM-1 kill shot: git status stays clean across regens ────────


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout


def test_git_status_clean_after_regeneration_with_changed_atlas(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "CLAUDE.md").write_text("# Mine\n")
    write_rules_file(
        project_path=tmp_path, project_name="t",
        atlas_content="IDENTITY: v1", ide="all", project_id="pid",
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "baseline")
    # Regenerate with a CHANGED atlas — only the gitignored file may change
    write_rules_file(
        project_path=tmp_path, project_name="t",
        atlas_content="IDENTITY: v2 changed", ide="all", project_id="pid",
    )
    status = _git(tmp_path, "status", "--porcelain")
    assert status.strip() == "", f"tracked files churned:\n{status}"
    assert "IDENTITY: v2 changed" in (
        tmp_path / ".sourceprep" / "AGENT_CONTEXT.md"
    ).read_text()


# ── W1: MCP server reads the hash from the context file ─────────────


def test_mcp_context_file_hash_extraction(tmp_path):
    from prep.mcp.server import MCPServer

    assert MCPServer._get_context_file_atlas_hash(tmp_path) is None
    ctx_dir = tmp_path / ".sourceprep"
    ctx_dir.mkdir()
    (ctx_dir / "AGENT_CONTEXT.md").write_text(
        "<!-- prep-atlas-hash:abc123def456 -->\n## Codebase Atlas\nX\n"
    )
    assert MCPServer._get_context_file_atlas_hash(tmp_path) == "abc123def456"
