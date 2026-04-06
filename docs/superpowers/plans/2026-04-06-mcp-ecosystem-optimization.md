# MCP Ecosystem Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align CoDRAG's MCP primitives with the MCP spec's three control models — tools for agent-initiated actions, resources for user-browsable data, prompts for structured workflows — so CoDRAG feels native in Claude Code and every other MCP client.

**Architecture:** Enhance the existing MCP server (`src/codrag/mcp/server.py`) which already has resource/prompt handler scaffolding. Add tool annotations to `mcp_tools.py`. Add atlas content hashing to `rules_generator.py`. Expand resource content generators and prompt templates. All changes are additive — no breaking changes to existing tool callers.

**Tech Stack:** Python 3.11+, FastAPI, hashlib, existing MCP protocol handlers in `server.py`

**Spec:** `docs/Phase73_Quality-Reccommendations/12_MCP_Ecosystem_Optimization_Design.md`

---

## File Map

| File | Responsibility | Action |
|---|---|---|
| `src/codrag/mcp_tools.py` | Tool schema definitions + annotations | Modify: add `title`, `destructiveHint`, `idempotentHint` |
| `src/codrag/mcp/server.py` | MCP protocol handlers (tools, resources, prompts) | Modify: expand resources, enhance prompts, atlas hash, listChanged |
| `src/codrag/core/rules_generator.py` | CLAUDE.md / AGENTS.md generation | Modify: embed atlas hash, add permission hint |
| `tests/test_mcp_server.py` | MCP server unit tests | Modify: add annotation, resource, prompt tests |
| `tests/test_rules_generator.py` | Rules generator tests | Modify (or create): atlas hash tests |

---

## Task 1: Add Missing Tool Annotations

**Files:**
- Modify: `src/codrag/mcp_tools.py:25-318`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write test for tool annotations**

```python
# In tests/test_mcp_server.py (or tests/test_mcp_tools.py if it exists)
from codrag.mcp_tools import TOOLS


def test_all_tools_have_title():
    """Every production tool must have a title annotation for UI display."""
    for tool in TOOLS:
        annotations = tool.get("annotations", {})
        assert "title" in annotations, f"Tool {tool['name']} missing 'title' annotation"
        assert isinstance(annotations["title"], str)
        assert len(annotations["title"]) > 0


def test_all_tools_have_destructive_hint():
    """Every tool must declare destructiveHint (none are destructive)."""
    for tool in TOOLS:
        annotations = tool.get("annotations", {})
        assert "destructiveHint" in annotations, f"Tool {tool['name']} missing 'destructiveHint'"
        assert annotations["destructiveHint"] is False, f"Tool {tool['name']} should not be destructive"


def test_readonly_tools_have_idempotent_hint():
    """Read-only tools should declare idempotentHint=True."""
    readonly_tools = [t for t in TOOLS if t.get("annotations", {}).get("readOnlyHint")]
    for tool in readonly_tools:
        annotations = tool.get("annotations", {})
        assert annotations.get("idempotentHint") is True, (
            f"Read-only tool {tool['name']} should be idempotent"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_mcp_server.py -v -k "test_all_tools_have_title or test_all_tools_have_destructive or test_readonly_tools_have_idempotent" --no-header`
Expected: FAIL — `title`, `destructiveHint`, `idempotentHint` not yet set

- [ ] **Step 3: Add annotations to all tools in mcp_tools.py**

In `src/codrag/mcp_tools.py`, update each tool's `annotations` dict:

```python
# Tool 1: codrag (line 55)
"annotations": {
    "title": "CoDRAG: Codebase Context",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
},

# Tool 2: codrag_search (line 113)
"annotations": {
    "title": "CoDRAG: Code Search",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
},

# Tool 3: codrag_impact (line 152)
"annotations": {
    "title": "CoDRAG: Impact Analysis",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
},

# Tool 4: codrag_audit (line 208)
"annotations": {
    "title": "CoDRAG: Codebase Audit",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
},

# Tool 5: codrag_observe (line 264)
"annotations": {
    "title": "CoDRAG: Observations",
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
},

# Tool 6: codrag_concepts (line 317)
"annotations": {
    "title": "CoDRAG: Concepts",
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
},
```

Also update the dev alias `codrag_context` (line 341):
```python
"annotations": {
    "title": "CoDRAG: Context (Dev)",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
},
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_mcp_server.py -v -k "test_all_tools_have_title or test_all_tools_have_destructive or test_readonly_tools_have_idempotent" --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/mcp_tools.py tests/test_mcp_server.py
git commit -m "feat(mcp): add title, destructiveHint, idempotentHint annotations to all tools"
```

---

## Task 2: Enable listChanged Notifications

**Files:**
- Modify: `src/codrag/mcp/server.py:2048-2054`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write test for listChanged capability**

```python
def test_capabilities_declare_list_changed():
    """Server capabilities should declare listChanged=True for resources and prompts."""
    from codrag.mcp.server import CodragMCPServer

    server = CodragMCPServer.__new__(CodragMCPServer)
    server.__init__()

    # Simulate initialize to get capabilities
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        server.handle_initialize({"protocolVersion": "2025-06-18", "capabilities": {}})
    )

    caps = result["capabilities"]
    assert caps["resources"]["listChanged"] is True
    assert caps["prompts"]["listChanged"] is True
    assert caps["tools"]["listChanged"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_mcp_server.py::test_capabilities_declare_list_changed -v --no-header`
Expected: FAIL — currently `False`

- [ ] **Step 3: Flip listChanged to True**

In `src/codrag/mcp/server.py`, find the capabilities dict in `handle_initialize` (around line 2050):

```python
# BEFORE:
"capabilities": {
    "tools": {"listChanged": False},
    "resources": {"subscribe": False, "listChanged": False},
    "prompts": {"listChanged": False},
},

# AFTER:
"capabilities": {
    "tools": {"listChanged": True},
    "resources": {"subscribe": False, "listChanged": True},
    "prompts": {"listChanged": True},
},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_mcp_server.py::test_capabilities_declare_list_changed -v --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/mcp/server.py tests/test_mcp_server.py
git commit -m "feat(mcp): enable listChanged notifications for tools, resources, and prompts"
```

---

## Task 3: Atlas Content Hash in CLAUDE.md

**Files:**
- Modify: `src/codrag/core/rules_generator.py:327-460` (`_build_managed_content`)
- Modify: `src/codrag/mcp/server.py:207-260` (`_project_has_rules_file` area)
- Test: `tests/test_rules_generator.py` (create if needed)

- [ ] **Step 1: Write test for atlas hash embedding**

```python
# tests/test_rules_generator_hash.py
import hashlib

from codrag.core.rules_generator import _build_managed_content, _CLAUDE_MARKER_START


def test_managed_content_includes_atlas_hash():
    """The managed content block should include a hash of the atlas content."""
    atlas = "IDENTITY: Test project\nSTACK: Python"
    content = _build_managed_content(
        project_name="test",
        atlas_content=atlas,
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    expected_hash = hashlib.sha256(atlas.strip().encode()).hexdigest()[:12]
    assert f"codrag-atlas-hash:{expected_hash}" in content


def test_managed_content_no_hash_when_no_atlas():
    """No hash comment when atlas is empty."""
    content = _build_managed_content(
        project_name="test",
        atlas_content="",
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    assert "codrag-atlas-hash" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_rules_generator_hash.py -v --no-header`
Expected: FAIL — no hash in output yet

- [ ] **Step 3: Embed atlas hash in _build_managed_content**

In `src/codrag/core/rules_generator.py`, at the top of `_build_managed_content` (after line 336), add the hash import and computation. Then embed the hash comment right after the `_CLAUDE_MARKER_START` in the `generate_claude_rules` function (or in `_build_managed_content` near the atlas section).

The cleanest place: in `_build_managed_content`, right before the atlas section (around line 417):

```python
import hashlib

# ... inside _build_managed_content, around line 416:

    # Atlas section (if available)
    if atlas_content and atlas_content.strip():
        # Embed content hash for freshness detection by MCP server
        atlas_hash = hashlib.sha256(atlas_content.strip().encode()).hexdigest()[:12]
        parts.append("")
        parts.append(f"<!-- codrag-atlas-hash:{atlas_hash} -->")
        parts.append("## Codebase Atlas")
        parts.append("")
        parts.append(atlas_content.strip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_rules_generator_hash.py -v --no-header`
Expected: PASS

- [ ] **Step 5: Write test for hash comparison in MCP server**

```python
# tests/test_mcp_atlas_hash.py
import hashlib


def test_extract_atlas_hash_from_rules_content():
    """The MCP server should be able to extract the atlas hash from rules file content."""
    from codrag.mcp.server import CodragMCPServer

    atlas = "IDENTITY: Test\nSTACK: Python"
    expected_hash = hashlib.sha256(atlas.strip().encode()).hexdigest()[:12]

    rules_content = f"<!-- codrag-atlas-hash:{expected_hash} -->\n## Codebase Atlas\n{atlas}"

    # Test the extraction helper
    extracted = CodragMCPServer._extract_atlas_hash(rules_content)
    assert extracted == expected_hash


def test_extract_atlas_hash_missing():
    """Returns None when no hash comment is present."""
    from codrag.mcp.server import CodragMCPServer

    extracted = CodragMCPServer._extract_atlas_hash("## Just some content")
    assert extracted is None
```

- [ ] **Step 6: Implement hash extraction in MCP server**

In `src/codrag/mcp/server.py`, add a static method to `CodragMCPServer`:

```python
import re

@staticmethod
def _extract_atlas_hash(content: str) -> str | None:
    """Extract the atlas content hash from a rules file.

    Looks for <!-- codrag-atlas-hash:XXXX --> comment.
    Returns the hash string or None if not found.
    """
    match = re.search(r"codrag-atlas-hash:([a-f0-9]{12})", content)
    return match.group(1) if match else None
```

- [ ] **Step 7: Run all hash tests**

Run: `.venv/bin/pytest tests/test_rules_generator_hash.py tests/test_mcp_atlas_hash.py -v --no-header`
Expected: PASS

- [ ] **Step 8: Wire hash comparison into tool_context**

In `src/codrag/mcp/server.py`, in the `_project_has_rules_file` method (or a new `_get_rules_atlas_hash` method), when reading the rules file content to check for markers, also extract and cache the atlas hash. Then in `tool_context()`, after the existing `has_rules` check (around line 933-944), add:

```python
# In tool_context(), after has_rules check:
rules_atlas_hash = self._get_cached_atlas_hash(project_id)
if rules_atlas_hash:
    current_atlas_hash = hashlib.sha256(
        (atlas_content or "").strip().encode()
    ).hexdigest()[:12]
    if rules_atlas_hash == current_atlas_hash:
        # Atlas in rules file is current — skip it in response
        payload["include_atlas"] = False
```

This extends the existing ISSUE-6 optimization with precise hash matching instead of just "rules file exists".

- [ ] **Step 9: Commit**

```bash
git add src/codrag/core/rules_generator.py src/codrag/mcp/server.py tests/test_rules_generator_hash.py tests/test_mcp_atlas_hash.py
git commit -m "feat(mcp): atlas content hash for precise freshness detection in CLAUDE.md"
```

---

## Task 4: Add Permission Hint to AGENTS.md

**Files:**
- Modify: `src/codrag/core/rules_generator.py:396-414`
- Test: `tests/test_rules_generator_hash.py` (add a test)

- [ ] **Step 1: Write test**

```python
def test_managed_content_includes_permission_hint():
    """The managed content should include auto-approve configuration hint."""
    content = _build_managed_content(
        project_name="test",
        atlas_content="",
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    assert '"allow": ["mcp__codrag"]' in content or "mcp__codrag" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_rules_generator_hash.py::test_managed_content_includes_permission_hint -v --no-header`
Expected: FAIL

- [ ] **Step 3: Add permission hint to managed content**

In `src/codrag/core/rules_generator.py`, after the "All CoDRAG tools are read-only" line (around line 413), add:

```python
    parts.append("")
    parts.append(
        "### Auto-Approve Configuration\n"
        "To skip approval prompts for CoDRAG's read-only tools, add to your settings:\n"
        '```json\n'
        '{ "permissions": { "allow": ["mcp__codrag"] } }\n'
        '```\n'
        "In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_rules_generator_hash.py::test_managed_content_includes_permission_hint -v --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/rules_generator.py tests/test_rules_generator_hash.py
git commit -m "feat(agents): add auto-approve permission hint to generated rules files"
```

---

## Task 5: Expand MCP Resources

**Files:**
- Modify: `src/codrag/mcp/server.py:2092-2320` (resource handlers + generators)
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write tests for expanded resource list**

```python
import asyncio
import pytest


@pytest.fixture
def mock_server():
    """Create a CodragMCPServer with mocked API calls."""
    from unittest.mock import AsyncMock, patch
    from codrag.mcp.server import CodragMCPServer

    server = CodragMCPServer.__new__(CodragMCPServer)
    server.__init__()
    server._client_name = "claude-code"
    server._resolve_project_id = AsyncMock(return_value="test-project")
    return server


def test_resources_list_has_all_resources(mock_server):
    """Resource list should include atlas, structure, modules, audit, concepts, focus, health."""
    result = asyncio.get_event_loop().run_until_complete(
        mock_server.handle_resources_list({})
    )
    resource_names = {r["name"] for r in result["resources"]}
    expected = {
        "Codebase Atlas",
        "Codebase Structure",
        "Module Map",
        "Audit Findings",
        "Concepts",
        "Focus Areas",
        "Index Health",
    }
    assert expected.issubset(resource_names), f"Missing: {expected - resource_names}"


def test_resources_list_includes_audience(mock_server):
    """Resources should declare their audience annotation."""
    result = asyncio.get_event_loop().run_until_complete(
        mock_server.handle_resources_list({})
    )
    for resource in result["resources"]:
        assert "annotations" in resource, f"Resource {resource['name']} missing annotations"
        assert "audience" in resource["annotations"], f"Resource {resource['name']} missing audience"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_mcp_server.py -v -k "test_resources_list" --no-header`
Expected: FAIL — missing resources (modules, audit, concepts, focus) and no annotations

- [ ] **Step 3: Expand handle_resources_list**

In `src/codrag/mcp/server.py`, replace the `handle_resources_list` method (line 2092). Add the new resources and annotations:

```python
async def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle resources/list request.

    Returns lightweight resource descriptors. Resources provide on-demand
    context the user can attach via @ mention (no tool call needed).
    """
    try:
        project_id = await self._resolve_project_id()
    except Exception:
        project_id = "default"

    return {
        "resources": [
            {
                "uri": f"codrag://{project_id}/atlas",
                "name": "Codebase Atlas",
                "description": "Architectural overview: identity, stack, workspace map, cross-cutting concerns.",
                "mimeType": "text/markdown",
                "annotations": {"audience": ["assistant"]},
            },
            {
                "uri": f"codrag://{project_id}/structure",
                "name": "Codebase Structure",
                "description": "Hub files with connection counts and structural roles.",
                "mimeType": "text/markdown",
                "annotations": {"audience": ["assistant"]},
            },
            {
                "uri": f"codrag://{project_id}/modules",
                "name": "Module Map",
                "description": "Module list with file counts, dependencies, and summaries.",
                "mimeType": "text/markdown",
                "annotations": {"audience": ["assistant"]},
            },
            {
                "uri": f"codrag://{project_id}/audit",
                "name": "Audit Findings",
                "description": "Latest codebase health findings: architecture, quality, tech debt.",
                "mimeType": "text/markdown",
                "annotations": {"audience": ["user", "assistant"]},
            },
            {
                "uri": f"codrag://{project_id}/concepts",
                "name": "Concepts",
                "description": "High-level codebase concepts: business rationale, design decisions, domain knowledge.",
                "mimeType": "text/markdown",
                "annotations": {"audience": ["assistant"]},
            },
            {
                "uri": f"codrag://{project_id}/focus",
                "name": "Focus Areas",
                "description": "User-selected focus areas with content excerpts.",
                "mimeType": "text/markdown",
                "annotations": {"audience": ["assistant"]},
            },
            {
                "uri": f"codrag://{project_id}/health",
                "name": "Index Health",
                "description": "Index freshness, coverage, and build status.",
                "mimeType": "text/markdown",
                "annotations": {"audience": ["user", "assistant"]},
            },
        ]
    }
```

- [ ] **Step 4: Run resource list tests**

Run: `.venv/bin/pytest tests/test_mcp_server.py -v -k "test_resources_list" --no-header`
Expected: PASS

- [ ] **Step 5: Write new resource content generators**

Add these methods to `CodragMCPServer` in `src/codrag/mcp/server.py`, after the existing `_resource_health` method (around line 2320):

```python
async def _resource_modules(self, project_id: str) -> str:
    """Module map with summaries. Tier-adaptive."""
    try:
        ctx_data = await self._api_post(
            f"/projects/{project_id}/context",
            {"query": "", "max_chars": self._get_context_budget() // 2, "include_atlas": False},
        )
        if not isinstance(ctx_data, dict):
            return "(Module data not available)"

        modules = ctx_data.get("modules", [])
        if not modules:
            return "(No modules detected yet -- run the pipeline to Stage 7+)"

        parts = ["## Module Map\n"]
        for mod in modules:
            if isinstance(mod, dict):
                name = mod.get("name", "unnamed")
                count = mod.get("file_count", 0)
                summary = mod.get("summary", "")
                parts.append(f"- **{name}** ({count} files): {summary}")
        return "\n".join(parts)
    except Exception as e:
        return f"(Module map unavailable: {e})"

async def _resource_audit(self, project_id: str) -> str:
    """Latest audit findings summary."""
    try:
        data = await self._api_get(f"/projects/{project_id}/audit/findings")
        if not isinstance(data, dict):
            return "(No audit data available -- run `codrag_audit` first)"

        findings = data.get("findings", [])
        if not findings:
            return "(No audit findings -- codebase looks healthy!)"

        parts = [f"## Audit Findings ({len(findings)} issues)\n"]
        for f in findings[:20]:
            if isinstance(f, dict):
                severity = f.get("severity", "info")
                title = f.get("title", "untitled")
                fid = f.get("id", "")
                parts.append(f"- [{severity.upper()}] {title} ({fid})")
        if len(findings) > 20:
            parts.append(f"- ... +{len(findings) - 20} more")
        return "\n".join(parts)
    except Exception as e:
        return f"(Audit data unavailable: {e})"

async def _resource_concepts(self, project_id: str) -> str:
    """Epistemic knowledge layer summary."""
    try:
        data = await self._api_get(f"/projects/{project_id}/concepts")
        if not isinstance(data, dict):
            return "(No concepts available)"

        concepts = data.get("concepts", [])
        if not concepts:
            return "(No concepts saved yet -- use `codrag_concepts` to add them)"

        # Group by category
        by_cat: Dict[str, list] = {}
        for c in concepts:
            if isinstance(c, dict):
                cat = c.get("category", "technical")
                by_cat.setdefault(cat, []).append(c)

        parts = [f"## Codebase Concepts ({len(concepts)} total)\n"]
        for cat, items in sorted(by_cat.items()):
            parts.append(f"### {cat.title()} ({len(items)})")
            for item in items[:5]:
                title = item.get("title", "untitled")
                parts.append(f"- {title}")
            if len(items) > 5:
                parts.append(f"- ... +{len(items) - 5} more")
            parts.append("")
        return "\n".join(parts)
    except Exception as e:
        return f"(Concepts unavailable: {e})"

async def _resource_focus(self, project_id: str) -> str:
    """User's selected focus areas."""
    try:
        data = await self._api_get(f"/projects/{project_id}/included_paths")
        paths = (data or {}).get("included_paths", []) if isinstance(data, dict) else []

        if not paths:
            return "(No focus areas selected -- configure in dashboard or CLI)"

        parts = [f"## Focus Areas ({len(paths)} paths)\n"]
        for p in paths[:20]:
            parts.append(f"- `{p}`")
        if len(paths) > 20:
            parts.append(f"- ... +{len(paths) - 20} more")
        return "\n".join(parts)
    except Exception as e:
        return f"(Focus areas unavailable: {e})"
```

- [ ] **Step 6: Wire new resources into handle_resources_read**

In `src/codrag/mcp/server.py`, in the `handle_resources_read` method (around line 2161), add routing for the new resource types:

```python
# Add these elif branches after the existing ones:
elif resource_type == "modules":
    content = await self._resource_modules(project_id)
elif resource_type == "audit":
    content = await self._resource_audit(project_id)
elif resource_type == "concepts":
    content = await self._resource_concepts(project_id)
elif resource_type == "focus":
    content = await self._resource_focus(project_id)
```

- [ ] **Step 7: Write integration test for resource read**

```python
def test_resource_read_routes_all_types(mock_server):
    """All declared resource types should be routable in handle_resources_read."""
    from unittest.mock import AsyncMock

    mock_server._api_get = AsyncMock(return_value={"index": {"exists": True}})
    mock_server._api_post = AsyncMock(return_value={"context": "", "modules": []})

    resource_types = ["atlas", "structure", "modules", "audit", "concepts", "focus", "health"]
    for rtype in resource_types:
        result = asyncio.get_event_loop().run_until_complete(
            mock_server.handle_resources_read({"uri": f"codrag://test-project/{rtype}"})
        )
        assert "contents" in result, f"Resource type '{rtype}' failed to return contents"
        assert len(result["contents"]) > 0
```

- [ ] **Step 8: Run all resource tests**

Run: `.venv/bin/pytest tests/test_mcp_server.py -v -k "resource" --no-header`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/codrag/mcp/server.py tests/test_mcp_server.py
git commit -m "feat(mcp): expand resources to 7 types — atlas, structure, modules, audit, concepts, focus, health"
```

---

## Task 6: Enhance MCP Prompts

**Files:**
- Modify: `src/codrag/mcp/server.py:2322-2440` (prompts section)
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write tests for enhanced prompts**

```python
def test_prompts_list_has_all_prompts(mock_server):
    """Prompt list should include onboard, review, plan, investigate, health."""
    result = asyncio.get_event_loop().run_until_complete(
        mock_server.handle_prompts_list({})
    )
    prompt_names = {p["name"] for p in result["prompts"]}
    expected = {"codrag-onboard", "codrag-review", "codrag-plan", "codrag-investigate", "codrag-health"}
    assert expected.issubset(prompt_names), f"Missing: {expected - prompt_names}"


def test_prompt_onboard_returns_messages(mock_server):
    """The onboard prompt should return structured messages."""
    result = asyncio.get_event_loop().run_until_complete(
        mock_server.handle_prompts_get({"name": "codrag-onboard", "arguments": {}})
    )
    assert "messages" in result
    assert len(result["messages"]) > 0
    assert result["messages"][0]["role"] == "user"


def test_prompt_investigate_requires_query(mock_server):
    """The investigate prompt should use the query argument."""
    result = asyncio.get_event_loop().run_until_complete(
        mock_server.handle_prompts_get({
            "name": "codrag-investigate",
            "arguments": {"query": "authentication flow"},
        })
    )
    assert "authentication flow" in result["messages"][0]["content"]["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_mcp_server.py -v -k "test_prompt" --no-header`
Expected: FAIL — missing `codrag-onboard`, `codrag-investigate`, `codrag-health`

- [ ] **Step 3: Update _PROMPTS list and handle_prompts_get**

In `src/codrag/mcp/server.py`, replace the `_PROMPTS` class variable (line 2324):

```python
_PROMPTS = [
    {
        "name": "codrag-onboard",
        "description": "Orient to this codebase — get structural overview, key modules, and hub files",
        "arguments": [],
    },
    {
        "name": "codrag-review",
        "description": "Review a file with structural awareness — blast radius, dependencies, and related code",
        "arguments": [
            {
                "name": "file_path",
                "description": "Path of the file to review",
                "required": True,
            },
            {
                "name": "scope",
                "description": "Review scope: 'file' (default), 'module', or 'blast-radius'",
                "required": False,
            },
        ],
    },
    {
        "name": "codrag-plan",
        "description": "Plan a change with impact analysis — understand what files are affected before editing",
        "arguments": [
            {
                "name": "change",
                "description": "Description of the change you want to make",
                "required": True,
            },
        ],
    },
    {
        "name": "codrag-investigate",
        "description": "Deep-dive into a topic — search, trace expansion, and module context",
        "arguments": [
            {
                "name": "query",
                "description": "What you want to understand (e.g., 'authentication flow', 'how caching works')",
                "required": True,
            },
        ],
    },
    {
        "name": "codrag-health",
        "description": "Check codebase health — audit findings, tech debt, and improvement recommendations",
        "arguments": [
            {
                "name": "focus",
                "description": "Optional focus area: 'debt', 'complexity', 'coverage', 'architecture'",
                "required": False,
            },
        ],
    },
]
```

Then update `handle_prompts_get` to handle the new/renamed prompts:

```python
async def handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle prompts/get request."""
    name = params.get("name", "")
    arguments = params.get("arguments", {})

    if name == "codrag-onboard":
        return {
            "description": "Codebase orientation",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Orient me to this codebase using CoDRAG.\n\n"
                            "1. Call `codrag` to get the structural overview (modules, hub files, connections).\n"
                            "2. Summarize the architecture: what are the main components and how do they connect?\n"
                            "3. Identify the most important files (hub files) and explain their role.\n"
                            "4. List the key entry points and data flow patterns.\n"
                            "5. Note any areas that need attention (from audit findings if available)."
                        ),
                    },
                }
            ],
        }

    elif name == "codrag-review":
        file_path = arguments.get("file_path", "the current file")
        scope = arguments.get("scope", "file")
        return {
            "description": "Structural code review",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Review `{file_path}` (scope: {scope}) using CoDRAG's structural understanding.\n\n"
                            "1. Call `codrag_impact` on the file to understand its dependencies and dependents.\n"
                            "2. Call `codrag_search` to find related code and patterns.\n"
                            "3. Check for bugs, style issues, missing error handling, and structural problems.\n"
                            "4. Consider how changes here would affect connected files.\n"
                            "5. Provide concrete improvement suggestions with file references."
                        ),
                    },
                }
            ],
        }

    elif name == "codrag-plan":
        change = arguments.get("change", "the proposed change")
        return {
            "description": "Change planning with impact analysis",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Plan this change: {change}\n\n"
                            "1. Call `codrag` for structural overview of the codebase.\n"
                            "2. Call `codrag_impact` on files that will be modified to understand the blast radius.\n"
                            "3. Call `codrag_search` to find related code that may need updates.\n"
                            "4. Create a step-by-step implementation plan that accounts for all dependencies.\n"
                            "5. List all files that need changes, in the order they should be modified."
                        ),
                    },
                }
            ],
        }

    elif name == "codrag-investigate":
        query = arguments.get("query", "this topic")
        return {
            "description": "Deep investigation with structural context",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Help me understand: {query}\n\n"
                            "1. Call `codrag_search` to find relevant code and documentation.\n"
                            "2. Call `codrag` for module structure around the relevant area.\n"
                            "3. Call `codrag_impact` on key files to trace the dependency graph.\n"
                            "4. Explain how the pieces connect — data flow, call chains, design patterns.\n"
                            "5. Summarize with a clear mental model I can use going forward."
                        ),
                    },
                }
            ],
        }

    elif name == "codrag-health":
        focus = arguments.get("focus", "")
        focus_text = f" Focus on: {focus}." if focus else ""
        return {
            "description": "Codebase health check",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Check the health of this codebase using CoDRAG.{focus_text}\n\n"
                            "1. Call `codrag_audit` to get current findings.\n"
                            "2. Call `codrag` for structural context — hub files and module dependencies.\n"
                            "3. Prioritize findings by impact: what's most likely to cause problems?\n"
                            "4. For the top 3 findings, suggest concrete fixes with file references.\n"
                            "5. Summarize the overall health: what's good, what needs work."
                        ),
                    },
                }
            ],
        }

    # Backward compat: old prompt names
    elif name == "codrag-analyze":
        # Redirect to onboard
        return await self.handle_prompts_get({"name": "codrag-onboard", "arguments": arguments})

    else:
        raise MethodNotFoundError(f"Unknown prompt: {name}")
```

- [ ] **Step 4: Run prompt tests**

Run: `.venv/bin/pytest tests/test_mcp_server.py -v -k "test_prompt" --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/mcp/server.py tests/test_mcp_server.py
git commit -m "feat(mcp): enhance prompts — onboard, review, plan, investigate, health workflows"
```

---

## Task 7: Update Generated Rules Files

**Files:**
- Modify: `src/codrag/core/rules_generator.py:396-460`
- Test: `tests/test_rules_generator_hash.py`

- [ ] **Step 1: Write test for resource/prompt mentions in managed content**

```python
def test_managed_content_mentions_resources():
    """Generated content should inform agents about available MCP resources."""
    content = _build_managed_content(
        project_name="test",
        atlas_content="IDENTITY: Test",
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    assert "resource" in content.lower() or "@codrag" in content


def test_managed_content_mentions_prompts():
    """Generated content should inform agents about available MCP prompts."""
    content = _build_managed_content(
        project_name="test",
        atlas_content="IDENTITY: Test",
        included_paths=None,
        is_preliminary=False,
        stats=None,
        project_id="test-id",
    )
    assert "codrag-onboard" in content or "prompt" in content.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_rules_generator_hash.py -v -k "test_managed_content_mentions" --no-header`
Expected: FAIL

- [ ] **Step 3: Add resource and prompt hints to managed content**

In `src/codrag/core/rules_generator.py`, after the tool calling rules section (around line 460), add:

```python
    # MCP Resources and Prompts
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
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_rules_generator_hash.py -v -k "test_managed_content_mentions" --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/rules_generator.py tests/test_rules_generator_hash.py
git commit -m "feat(agents): add resource and prompt documentation to generated rules files"
```

---

## Task 8: Run Full Test Suite

**Files:**
- All modified files from Tasks 1-7

- [ ] **Step 1: Run the full MCP test suite**

Run: `.venv/bin/pytest tests/test_mcp_server.py tests/test_mcp_budget_caps.py tests/test_context_tier.py -v --no-header`
Expected: All tests PASS

- [ ] **Step 2: Run rules generator tests**

Run: `.venv/bin/pytest tests/test_rules_generator_hash.py tests/test_mcp_atlas_hash.py -v --no-header`
Expected: All tests PASS

- [ ] **Step 3: Run ruff lint check**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && .venv/bin/ruff check src/codrag/mcp_tools.py src/codrag/mcp/server.py src/codrag/core/rules_generator.py`
Expected: No errors (or fix any that appear)

- [ ] **Step 4: Run mypy type check on modified files**

Run: `cd /Volumes/4TB-BAD/HumanAI/CoDRAG && .venv/bin/mypy src/codrag/mcp_tools.py src/codrag/mcp/server.py src/codrag/core/rules_generator.py --ignore-missing-imports`
Expected: No errors

- [ ] **Step 5: Commit any lint/type fixes**

```bash
git add -u
git commit -m "fix: resolve lint and type errors from MCP ecosystem changes"
```

---

## Summary

| Task | What | Files | Est. |
|------|------|-------|------|
| 1 | Tool annotations (title, destructiveHint, idempotentHint) | `mcp_tools.py` | 5 min |
| 2 | Enable listChanged notifications | `server.py` | 3 min |
| 3 | Atlas content hash in CLAUDE.md | `rules_generator.py`, `server.py` | 15 min |
| 4 | Permission hint in AGENTS.md | `rules_generator.py` | 5 min |
| 5 | Expand MCP resources (4 new + annotations) | `server.py` | 20 min |
| 6 | Enhance MCP prompts (2 new + rename) | `server.py` | 15 min |
| 7 | Update generated rules files | `rules_generator.py` | 10 min |
| 8 | Full test suite + lint | All | 5 min |

**Total: 8 tasks, ~78 minutes of implementation**

All changes are additive. No breaking changes to existing tool callers. Backward compat alias for `codrag-analyze` → `codrag-onboard` is included.
