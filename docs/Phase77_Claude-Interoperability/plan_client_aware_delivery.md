# Client-Aware Content Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop CoDRAG from wasting agent context by sending identical ~170-line content blocks to every client. Claude Code gets a compact format, AGENTS.md stays universal, and the MCP server tailors instructions per detected client.

**Architecture:** Add a `target` parameter to `_build_managed_content()` that selects between `"claude"` (compact, ~60 lines), `"cursor"` (no Claude-specific hints), and `"universal"` (full verbose, for AGENTS.md). The MCP server's `handle_initialize` uses the already-detected `_client_name` to shorten the `instructions` field for clients that have rules files. No new classes, no adapter framework — just `if/elif` branches in 3 places.

**Tech Stack:** Python (rules_generator.py, server.py), pytest

---

### Task 1: Add `target` Parameter to `_build_managed_content()`

**Files:**
- Modify: `src/codrag/core/rules_generator.py:328-496`
- Test: `tests/test_rules_generator_targets.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for client-aware content delivery in rules generator."""
import hashlib

from codrag.core.rules_generator import _build_managed_content


# -- Shared fixture args --
_BASE_ARGS = dict(
    project_name="test-project",
    atlas_content="IDENTITY: Test project\nSTACK: Python, React",
    included_paths=["src/main.py", "src/utils.py"],
    is_preliminary=False,
    stats={"node_count": 42, "edge_count": 100, "coverage_pct": 85},
    project_id="aaaa-bbbb-cccc-dddd",
)


def test_universal_target_is_default():
    """Without target param, output matches current behavior (universal)."""
    content = _build_managed_content(**_BASE_ARGS)
    # Universal includes all sections: resources, prompts, auto-approve with IDE list
    assert "MCP Resources" in content
    assert "MCP Prompts" in content
    assert "In Claude Code:" in content or "In Cursor:" in content


def test_claude_target_omits_cursor_references():
    """Claude target should not mention Cursor or other IDEs."""
    content = _build_managed_content(**_BASE_ARGS, target="claude")
    assert "Cursor" not in content
    assert "Windsurf" not in content


def test_claude_target_is_compact():
    """Claude target should be noticeably shorter than universal."""
    universal = _build_managed_content(**_BASE_ARGS, target="universal")
    claude = _build_managed_content(**_BASE_ARGS, target="claude")
    # Claude should be at least 30% shorter
    assert len(claude) < len(universal) * 0.75


def test_claude_target_keeps_essentials():
    """Claude target must still include project_id routing and tool table."""
    content = _build_managed_content(**_BASE_ARGS, target="claude")
    assert "aaaa-bbbb-cccc-dddd" in content
    assert "codrag_search" in content
    assert "codrag_impact" in content
    assert "Codebase Atlas" in content
    assert "Focus Areas" in content


def test_claude_target_includes_claude_specific_hints():
    """Claude target should include Claude Code specific features."""
    content = _build_managed_content(**_BASE_ARGS, target="claude")
    # Should mention @ resources and / prompts (Claude Code supports both)
    assert "@" in content or "resources" in content.lower()


def test_claude_target_has_compact_auto_approve():
    """Claude target auto-approve references .claude/settings.json only."""
    content = _build_managed_content(**_BASE_ARGS, target="claude")
    assert "mcp__codrag" in content
    assert ".claude/settings.json" in content


def test_universal_target_has_generic_auto_approve():
    """Universal target mentions multiple IDEs for auto-approve."""
    content = _build_managed_content(**_BASE_ARGS, target="universal")
    assert "mcp__codrag" in content


def test_cursor_target_omits_claude_hints():
    """Cursor target should not mention slash commands or .claude/ paths."""
    content = _build_managed_content(**_BASE_ARGS, target="cursor")
    assert "/mcp__codrag" not in content
    assert ".claude/settings.json" not in content


def test_atlas_hash_preserved_for_all_targets():
    """All targets should embed the atlas hash when atlas is present."""
    for target in ("claude", "cursor", "universal"):
        content = _build_managed_content(**_BASE_ARGS, target=target)
        expected_hash = hashlib.sha256(
            _BASE_ARGS["atlas_content"].strip().encode()
        ).hexdigest()[:12]
        assert f"codrag-atlas-hash:{expected_hash}" in content, f"Missing hash for target={target}"


def test_no_project_id_still_works():
    """All targets should handle missing project_id gracefully."""
    args = {**_BASE_ARGS, "project_id": None}
    for target in ("claude", "cursor", "universal"):
        content = _build_managed_content(**args, target=target)
        assert "codrag" in content.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_rules_generator_targets.py -v`
Expected: Multiple FAILs — `_build_managed_content()` doesn't accept `target` yet.

- [ ] **Step 3: Implement target-aware `_build_managed_content()`**

In `src/codrag/core/rules_generator.py`, modify the function signature and add branching logic. The key change is splitting the body into shared sections (always included) and target-specific sections.

```python
def _build_managed_content(
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
    target: str = "universal",  # "claude", "cursor", "universal"
) -> str:
    """Build the CoDRAG-managed content block.

    Args:
        target: Content profile.
            "claude" — compact, Claude Code-specific (~60 lines)
            "cursor" — no Claude-specific hints
            "universal" — verbose, for AGENTS.md (default, backward-compat)
    """
    parts: List[str] = []

    # ── Header (all targets) ──
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stat_parts = [f"Last updated: {now}"]
    if stats:
        if stats.get("node_count"):
            stat_parts.append(f"{stats['node_count']} nodes")
        if stats.get("edge_count"):
            stat_parts.append(f"{stats['edge_count']} edges")
        if stats.get("coverage_pct") is not None:
            stat_parts.append(f"{stats['coverage_pct']}% coverage")
    if is_preliminary:
        stat_parts.append("Full analysis in progress")
    parts.append(" | ".join(stat_parts))
    parts.append("")

    # ── Project ID routing (all targets) ──
    if project_id:
        parts.append(f"codrag_project_id: {project_id}")
        parts.append("")
        parts.append(
            f"**ROUTING: When calling ANY CoDRAG tool, ALWAYS include "
            f"`project_id: \"{project_id}\"` in the arguments.**"
        )
        parts.append("")

    # ── Tool table (all targets — compact reference) ──
    parts.append("## Tools")
    parts.append("| Tool | When to Use |")
    parts.append("|------|-------------|")
    parts.append("| `codrag` | START of every task — structural overview, modules, hub files |")
    parts.append("| `codrag_search` | Find code by meaning, not just string match |")
    parts.append("| `codrag_impact` | BEFORE editing — check what depends on a file |")
    parts.append("| `codrag_audit` | Codebase health, tech debt, refactoring guidance |")
    parts.append("| `codrag_observe` | Save/retrieve cross-session notes |")
    parts.append("| `codrag_concepts` | Record/query business rationale and design decisions |")
    parts.append("")
    parts.append("Call `codrag` first. Call `codrag_impact` before modifying hub files.")
    parts.append("All read-only tools are safe to auto-approve.")
    parts.append("")

    # ── Target-specific instructions ──
    if target == "claude":
        # Claude Code: compact. CLAUDE.md is already loaded, no need for
        # verbose instructions. Mention Claude-specific features only.
        parts.append("### Auto-Approve")
        parts.append(
            "Add to `.claude/settings.json`:\n"
            '```json\n'
            '{ "permissions": { "allow": ["mcp__codrag"] } }\n'
            '```'
        )
        parts.append("")
        parts.append(
            "Use `@` to browse CoDRAG resources (atlas, modules, audit). "
            "Use `/mcp__codrag__codrag-onboard` for guided orientation."
        )
    elif target == "cursor":
        # Cursor: no Claude-specific features, no slash commands
        parts.append(
            "For specific code lookups, use `codrag_search` with a natural language query.\n"
            "CoDRAG understands structural relationships — use it instead of\n"
            "grep when you need to understand how files connect."
        )
    else:
        # Universal (AGENTS.md): verbose, multi-IDE
        parts.append(
            "You have access to CoDRAG, a structural code intelligence system.\n"
            "ALWAYS call `codrag` (no arguments) at the START of every task.\n"
            "This gives you module structure, hub files, and the user's selected focus areas."
        )
        parts.append("")
        parts.append(
            "For specific code lookups, use `codrag_search` with a natural language query.\n"
            "Before making changes to a file, use `codrag_impact` to understand dependencies.\n"
            "CoDRAG understands structural relationships between files -- use it instead of\n"
            "grep when you need to understand how files connect to each other."
        )
        parts.append("")
        parts.append(
            "For codebase health and tech debt, use `codrag_audit`.\n"
            "For cross-session memory, use `codrag_observe` to save/retrieve notes.\n"
            "All CoDRAG tools are read-only and safe to auto-approve."
        )
        parts.append("")
        parts.append(
            "### Auto-Approve Configuration\n"
            "To skip approval prompts for CoDRAG's read-only tools, add to your settings:\n"
            '```json\n'
            '{ "permissions": { "allow": ["mcp__codrag"] } }\n'
            '```\n'
            "In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings."
        )

    # ── Atlas (all targets) ──
    if atlas_content and atlas_content.strip():
        atlas_hash = hashlib.sha256(atlas_content.strip().encode()).hexdigest()[:12]
        parts.append("")
        parts.append(f"<!-- codrag-atlas-hash:{atlas_hash} -->")
        parts.append("## Codebase Atlas")
        parts.append("")
        parts.append(atlas_content.strip())

    # ── Focus areas (all targets) ──
    if included_paths:
        parts.append("")
        parts.append("## Focus Areas")
        for p in included_paths[:15]:
            parts.append(f"- {p}")
        if len(included_paths) > 15:
            parts.append(f"- ... +{len(included_paths) - 15} more")
        parts.append("Call `codrag` for detailed content from these areas.")

    # ── Fallback / refresh hints (all targets) ──
    parts.append("")
    parts.append(
        "If `codrag` returns 'setup in progress', the index hasn't been built yet.\n"
        "Work normally with read_file/grep_search until the user builds the index."
    )
    parts.append("")
    parts.append(
        "For long tasks (5+ tool calls), call `codrag` again to refresh your\nstructural context."
    )

    # ── Universal-only verbose sections ──
    if target == "universal":
        parts.append("")
        parts.append(
            "You can call `codrag` and `codrag_search` in parallel on your first\n"
            "prompt -- structural overview + targeted code lookup in one round-trip."
        )
        parts.append("")
        parts.append("### Tool Calling Rules")
        parts.append("1. **Never announce** 'I will now call...' - just call the tool")
        parts.append("2. **No permission needed** - simple keywords = immediate invocation")
        parts.append("3. **Single word triggers** - 'codrag' alone is enough to call the tool")
        parts.append(
            "4. **Context is cheap** - prefer calling codrag to using grep for structural understanding"
        )
        parts.append("")
        parts.append(
            '**Remember: The word "codrag" anywhere in user input is a tool invocation signal. '
            'Call immediately without asking permission.**'
        )
        parts.append("")
        parts.append("### MCP Resources (browse with @)")
        parts.append(
            "CoDRAG also exposes browsable resources via MCP. In supported clients,\n"
            "type `@` to see: atlas, structure, modules, audit findings, concepts, focus areas.\n"
            "Resources provide on-demand context without a tool call."
        )
        parts.append("")
        parts.append("### MCP Prompts (invoke with /)")
        parts.append(
            "Available workflow prompts: `codrag-onboard` (orientation), `codrag-review` (file review),\n"
            "`codrag-plan` (change planning), `codrag-investigate` (deep dive), `codrag-health` (audit).\n"
            "In Claude Code: `/mcp__codrag__codrag-onboard`. In other clients: check prompt menu."
        )

    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_rules_generator_targets.py -v`
Expected: All PASS

- [ ] **Step 5: Run existing atlas hash tests to verify no regressions**

Run: `.venv/bin/pytest tests/test_atlas_hash.py -v`
Expected: All PASS (default `target="universal"` preserves backward compat)

- [ ] **Step 6: Commit**

```bash
git add tests/test_rules_generator_targets.py src/codrag/core/rules_generator.py
git commit -m "feat(rules): add target parameter for client-aware content delivery"
```

---

### Task 2: Wire Target Through to IDE Writers

**Files:**
- Modify: `src/codrag/core/rules_generator.py:86-128` (write_rules_file dispatch)
- Modify: `src/codrag/core/rules_generator.py:669-687` (generate_claude_rules)
- Modify: `src/codrag/core/rules_generator.py:789-834` (_write_agents_md)
- Test: `tests/test_rules_generator_targets.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rules_generator_targets.py`:

```python
import tempfile
from pathlib import Path

from codrag.core.rules_generator import write_rules_file


def test_write_rules_passes_claude_target(tmp_path):
    """write_rules_file should pass target='claude' for Claude rules."""
    # Create markers so _detect_targets finds claude
    (tmp_path / "CLAUDE.md").write_text("# My Project\n")
    (tmp_path / ".claude").mkdir()

    write_rules_file(
        project_path=tmp_path,
        project_name="test",
        atlas_content="IDENTITY: Test",
        ide="claude",
        project_id="test-id",
    )
    claude_md = (tmp_path / "CLAUDE.md").read_text()
    # Claude target should NOT contain the verbose universal sections
    assert "Tool Calling Rules" not in claude_md
    assert "codrag" in claude_md.lower()


def test_write_rules_passes_universal_target_for_agents_md(tmp_path):
    """AGENTS.md should always use the universal target."""
    write_rules_file(
        project_path=tmp_path,
        project_name="test",
        atlas_content="IDENTITY: Test",
        ide="agents_md",
        project_id="test-id",
    )
    agents_md = (tmp_path / "AGENTS.md").read_text()
    # Universal includes the verbose sections
    assert "Tool Calling Rules" in agents_md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_rules_generator_targets.py::test_write_rules_passes_claude_target -v`
Expected: FAIL — writers don't pass `target` yet.

- [ ] **Step 3: Wire target into writers**

In `generate_claude_rules()` (line 669), pass `target="claude"`:

```python
def generate_claude_rules(
    project_name: str,
    atlas_content: str = "",
    included_paths: Optional[List[str]] = None,
    is_preliminary: bool = False,
    stats: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> str:
    """Generate CoDRAG section for CLAUDE.md."""
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
        target="claude",
    )
    return f"{_CLAUDE_MARKER_START}\n# CoDRAG Integration\n\n{managed}\n{_CLAUDE_MARKER_END}"
```

In `_write_agents_md()` (line 804), pass `target="universal"` (explicit, for clarity):

```python
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
        target="universal",
    )
```

In `generate_cursor_rules()` (line 511), pass `target="cursor"`:

```python
    managed = _build_managed_content(
        project_name,
        atlas_content,
        included_paths,
        is_preliminary,
        stats,
        project_id=project_id,
        target="cursor",
    )
```

All other writers (`_write_windsurf_rules`, `_write_cline_rules`, `_write_roo_rules`, `_write_copilot_rules`, `_write_generic_md`) can keep `target="universal"` (the default) since they have no client-specific optimizations yet.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_rules_generator_targets.py -v`
Expected: All PASS

- [ ] **Step 5: Run full atlas hash test suite for regressions**

Run: `.venv/bin/pytest tests/test_atlas_hash.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/codrag/core/rules_generator.py tests/test_rules_generator_targets.py
git commit -m "feat(rules): wire target param through IDE writers"
```

---

### Task 3: Client-Aware MCP Server Instructions

**Files:**
- Modify: `src/codrag/mcp/server.py:2152-2175` (handle_initialize return)
- Test: `tests/test_mcp_instructions.py` (new)

- [ ] **Step 1: Write the failing test**

```python
"""Tests for client-aware MCP server instructions."""
import pytest

from codrag.mcp.server import MCPServer


@pytest.fixture
def server():
    """Create a minimal MCPServer instance for testing."""
    s = MCPServer.__new__(MCPServer)
    s._client_name = "unknown"
    s._client_version = ""
    s._initialize_roots = []
    s._codrag_called = False
    s._rules_atlas_hash_cache = {}
    return s


def test_instructions_short_for_claude(server):
    """Claude Code clients should get compact instructions."""
    server._client_name = "claude-code"
    instructions = server._build_instructions()
    # Should be under 250 chars (compact)
    assert len(instructions) < 300
    assert "codrag" in instructions.lower()
    assert "read-only" in instructions.lower() or "auto-approve" in instructions.lower()


def test_instructions_verbose_for_unknown(server):
    """Unknown clients should get the full instructions."""
    server._client_name = "unknown"
    instructions = server._build_instructions()
    # Should include tool-by-tool guidance
    assert "codrag_search" in instructions
    assert "codrag_impact" in instructions
    assert "codrag_audit" in instructions


def test_instructions_verbose_for_cursor(server):
    """Cursor gets verbose instructions (its rules file may not exist)."""
    server._client_name = "cursor"
    instructions = server._build_instructions()
    assert "codrag_search" in instructions


def test_instructions_short_for_gemini(server):
    """Gemini CLI gets compact instructions (it reads GEMINI.md)."""
    server._client_name = "gemini"
    instructions = server._build_instructions()
    assert len(instructions) < 300
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mcp_instructions.py -v`
Expected: FAIL — `_build_instructions()` method doesn't exist.

- [ ] **Step 3: Implement `_build_instructions()` and wire it**

In `src/codrag/mcp/server.py`, add the method to `MCPServer`:

```python
def _build_instructions(self) -> str:
    """Return MCP server instructions tailored to the detected client.

    Clients with their own rules files (Claude Code → CLAUDE.md,
    Gemini → GEMINI.md) get a compact version since the detailed
    tool guidance is already in their system prompt. Unknown clients
    get verbose instructions as their only guidance.
    """
    client_lower = self._client_name.lower()
    # Clients that have dedicated rules files with full instructions
    has_rules_file = any(
        p in client_lower for p in ("claude", "gemini")
    )
    if has_rules_file:
        return (
            "CoDRAG provides structural codebase intelligence. "
            "All tools are read-only and safe to auto-approve. "
            "Call `codrag` at the start of every task for orientation."
        )
    return (
        "CoDRAG maps how your codebase is connected -- modules, dependencies, "
        "hub files, and architectural patterns. All tools are read-only. "
        "Call `codrag` at the start of every task for structural overview. "
        "Use `codrag_search` for code queries with dependency expansion. "
        "Use `codrag_impact` before changes to see what breaks. "
        "Use `codrag_audit` for codebase health findings. "
        "Categories: code structure, architecture, dependencies, navigation."
    )
```

Then in `handle_initialize()` (line 2166), replace the hardcoded string:

```python
            "instructions": self._build_instructions(),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_mcp_instructions.py -v`
Expected: All PASS

- [ ] **Step 5: Run existing MCP tests for regressions**

Run: `.venv/bin/pytest tests/test_mcp_server.py tests/test_mcp_budget_caps.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/codrag/mcp/server.py tests/test_mcp_instructions.py
git commit -m "feat(mcp): client-aware instructions — compact for Claude/Gemini, verbose for others"
```

---

### Task 4: Generate `.claude/settings.json` Auto-Approve on Init

**Files:**
- Modify: `src/codrag/mcp_config.py:120-230` (install_mcp_to_workspace)
- Test: `tests/test_mcp_config_settings.py` (new)

- [ ] **Step 1: Write the failing test**

```python
"""Tests for .claude/settings.json auto-approve generation."""
import json
from pathlib import Path

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
    # Preserved existing
    assert "Bash" in data["permissions"]["allow"]
    assert "rm -rf" in data["permissions"]["deny"]
    assert "opus" == data["model"]
    # Added ours
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mcp_config_settings.py -v`
Expected: FAIL — `install_mcp_to_workspace` doesn't write settings.json.

- [ ] **Step 3: Implement settings.json generation**

Add a new function in `src/codrag/mcp_config.py`:

```python
def _ensure_claude_settings(workspace_path: Path) -> Optional[str]:
    """Ensure .claude/settings.json has mcp__codrag auto-approve.

    Merges into existing file if present. Returns the file path if
    written, None if skipped (already configured).
    """
    settings_dir = workspace_path / ".claude"
    settings_file = settings_dir / "settings.json"

    existing: Dict[str, Any] = {}
    if settings_file.exists():
        try:
            existing = json.loads(settings_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    perms = existing.setdefault("permissions", {})
    allow_list = perms.setdefault("allow", [])

    if "mcp__codrag" in allow_list:
        return None  # Already configured

    allow_list.append("mcp__codrag")

    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(existing, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote Claude Code auto-approve: %s", settings_file)
    return str(settings_file)
```

Then in `install_mcp_to_workspace`, after the main loop (before the return), add:

```python
    # Claude Code: also write settings.json with auto-approve
    if "claude-code" in targets:
        settings_path = _ensure_claude_settings(ws)
        if settings_path:
            written.append(settings_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_mcp_config_settings.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/mcp_config.py tests/test_mcp_config_settings.py
git commit -m "feat(config): auto-generate .claude/settings.json with mcp__codrag auto-approve"
```

---

### Task 5: Update Existing Tests and Run Full Suite

**Files:**
- Modify: `tests/test_atlas_hash.py` (if any assertions break due to content changes)

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest tests/test_atlas_hash.py tests/test_rules_generator_targets.py tests/test_mcp_instructions.py tests/test_mcp_config_settings.py -v`
Expected: All PASS

- [ ] **Step 2: Check that existing `test_managed_content_mentions_resources` still passes**

The `test_managed_content_mentions_resources` test in `test_atlas_hash.py` calls `_build_managed_content()` without `target` — it uses the default `"universal"`, which still includes "MCP Resources". Should still pass.

Run: `.venv/bin/pytest tests/test_atlas_hash.py -v`
Expected: All PASS. If any fail, the issue is that the default behavior changed. Fix by ensuring `target="universal"` exactly preserves the old output.

- [ ] **Step 3: If any tests fail, fix them**

The most likely failure is `test_managed_content_includes_permission_hint` — it checks for `mcp__codrag` in the output, which is present in all targets. Should pass.

If `test_managed_content_mentions_resources` fails, it's because the universal output restructured. Update the test to match the new format (resources are still mentioned, just in a different location).

- [ ] **Step 4: Commit any test fixes**

```bash
git add tests/
git commit -m "fix(tests): update assertions for client-aware content format"
```

---

### Task 6: Regenerate This Project's CLAUDE.md (Dogfood)

**Files:**
- No code changes — this is a verification/dogfood step

- [ ] **Step 1: Run rules regeneration for this project**

Run: `.venv/bin/python -c "from codrag.core.rules_generator import write_rules_file; from pathlib import Path; print(write_rules_file(Path('.'), 'CoDRAG', ide='claude', project_id='1d6f0b35-45cb-427b-ae9d-aac3c6371a4b'))"`
Expected: `{'claude': True}`

- [ ] **Step 2: Inspect the regenerated CLAUDE.md managed section**

Run: `grep -c '^' CLAUDE.md` to count lines.
Expected: The managed section (between `codrag-managed-start` and `codrag-managed-end`) should be noticeably shorter than before (~60-80 lines vs ~170).

- [ ] **Step 3: Verify the compact format is correct**

Check that:
- Project ID routing is present
- Tool table is present
- Atlas is embedded
- Focus areas are listed
- No Cursor/Windsurf/generic IDE references
- Auto-approve references `.claude/settings.json` only

- [ ] **Step 4: Also regenerate AGENTS.md and verify it's still verbose**

Run: `.venv/bin/python -c "from codrag.core.rules_generator import write_rules_file; from pathlib import Path; print(write_rules_file(Path('.'), 'CoDRAG', ide='agents_md', project_id='1d6f0b35-45cb-427b-ae9d-aac3c6371a4b'))"`
Expected: `{'agents_md': True}`

Check that AGENTS.md still has "Tool Calling Rules", "MCP Resources", "MCP Prompts" sections.

- [ ] **Step 5: Commit the regenerated files**

```bash
git add CLAUDE.md AGENTS.md
git commit -m "chore: regenerate CLAUDE.md (compact) and AGENTS.md (universal) with Phase 77 delivery"
```
