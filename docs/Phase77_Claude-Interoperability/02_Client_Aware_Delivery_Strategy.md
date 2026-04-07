# Phase 77.2: Client-Aware Content Delivery Strategy

## The Problem

CoDRAG currently has **two layers** of content delivery, and neither is client-aware:

### Layer 1: Rules Files (Static, at `codrag init` time)

`rules_generator.py:_detect_targets()` scans the project root for IDE markers (`.cursor/`, `CLAUDE.md`, `.windsurf/`, etc.) and writes **all detected** formats. This is fine — it's a one-time file write, not a context cost.

But the **content** of every file is identical: `_build_managed_content()` returns the same ~170-line block for Claude Code, Cursor, Cline, AGENTS.md, and everyone else. This is wasteful because:

- Claude Code users don't need "In Cursor: add to MCP settings" instructions
- Cursor users don't need "In Claude Code: add to `.claude/settings.json`" instructions
- AGENTS.md readers don't need slash-command hints for any specific IDE
- The auto-approve snippet references `.claude/settings.json` even in Cursor rules

### Layer 2: MCP Tool Responses (Dynamic, per-call)

The MCP server detects `clientInfo.name` at initialize and uses it for **one thing**: context budget sizing. The actual tool response content is identical regardless of client. This is mostly fine — the structural data is the same — but there's opportunity:

- The `instructions` field in server info is one-size-fits-all
- The `codrag` ambient context tool could tailor its preamble/hints per client
- Prompts and resources are client-agnostic (correct, since the MCP spec is universal)

---

## Strategy: Simple Client-Aware Content, Not a Framework

The goal is NOT to build a complex adapter layer. It's to stop sending irrelevant content. Three changes, ordered by impact:

### Change 1: Split `_build_managed_content()` by Target (Rules Layer)

**Current:** One function, one output for all IDEs.

**Proposed:** Keep `_build_managed_content()` as the universal core, but add a `target` parameter that trims or swaps IDE-specific sections.

```python
def _build_managed_content(
    project_name: str,
    atlas_content: str,
    included_paths: Optional[List[str]],
    is_preliminary: bool,
    stats: Optional[Dict[str, Any]],
    project_id: Optional[str] = None,
    target: str = "universal",  # NEW: "claude", "cursor", "universal"
) -> str:
```

**What changes per target:**

| Section | `claude` | `cursor` | `universal` (AGENTS.md) |
|---------|----------|----------|------------------------|
| Project ID routing | Yes | Yes | Yes |
| Tool table (compact) | Yes | Yes | Yes |
| Atlas embed | Yes | Yes | Yes |
| Focus areas | Yes | Yes | Yes |
| Auto-approve snippet | `.claude/settings.json` | Omit (Cursor has its own UI) | Generic "add to your IDE settings" |
| Slash-command hints | `/mcp__codrag__*` | Omit | Omit |
| MCP resources `@` hint | Yes (Claude Code supports `@`) | Omit | Omit |
| "No announcements" rule | Yes (Claude responds to this) | Varies | Generic |
| Parallel call hint | Yes | Omit (IDE controls this) | Omit |
| Long-task refresh hint | Yes | Yes | Yes |

**Implementation:** ~30 lines of `if target == "claude"` / `elif` in the existing function. Not a new abstraction.

**Token savings:** The universal block is ~170 lines. The Claude-specific block should be ~60-80 lines. That's 50%+ reduction in static context per session.

### Change 2: Client-Aware `instructions` Field (MCP Layer)

**Current:** One hardcoded string in `handle_initialize()` return.

**Proposed:** Use `self._client_name` (already detected at initialize time) to return a tailored string.

```python
# In handle_initialize(), after client detection:
if "claude" in self._client_name.lower():
    instructions = (
        "CoDRAG maps how your codebase is connected. "
        "All tools are read-only and safe to auto-approve. "
        "Call `codrag` at the start of every task. "
        "Use `codrag_search` for semantic code lookups. "
        "Use `codrag_impact` before modifying hub files."
    )
else:
    instructions = (
        "CoDRAG maps how your codebase is connected -- modules, dependencies, "
        "hub files, and architectural patterns. All tools are read-only. "
        "Call `codrag` at the start of every task for structural overview. "
        "Use `codrag_search` for code queries with dependency expansion. "
        "Use `codrag_impact` before changes to see what breaks. "
        "Use `codrag_audit` for codebase health findings. "
        "Categories: code structure, architecture, dependencies, navigation."
    )
```

**Why shorter for Claude Code?** Claude Code users already have CLAUDE.md with full instructions. The MCP `instructions` field is redundant context. Keep it minimal — just enough for the agent to know what CoDRAG is and that it's safe.

**For unknown clients:** Keep the verbose version. They might not have any rules file.

### Change 3: First-Call Preamble Adaptation (MCP Layer)

**Current:** The `codrag` tool response starts with `[project: {name}]` then dumps modules, atlas, etc.

**Proposed:** For Claude Code specifically, skip the tool-usage instructions in the response body. Claude Code already has CLAUDE.md + MCP instructions telling it how to use the tools. Repeating "call codrag_search for code lookups" in the tool response is triple-telling.

For unknown clients, keep the instructions in the response — they might have nothing else.

**Implementation:** Check `self._client_name` in the `tool_context()` handler. Add/skip a preamble block.

---

## Priority Order

This aligns with your stated priority:

### Priority 1: Claude Code
- Split `_build_managed_content(target="claude")` — compact, Claude-specific
- Trim MCP `instructions` for Claude Code clients
- Skip redundant tool-usage preamble in `codrag` responses for Claude Code
- Generate `.claude/settings.json` auto-approve
- Generate `.claude/skills/` for key workflows

### Priority 2: General MCP / Paperclip
- `_build_managed_content(target="universal")` stays verbose (AGENTS.md)
- MCP `instructions` stays verbose for unknown clients
- Paperclip: treat as "universal" — it reads AGENTS.md and MCP instructions
- No special Paperclip rules file needed (Paperclip reads AGENTS.md natively)

### Priority 3: IDE Clients (Cursor, Windsurf, etc.)
- `_build_managed_content(target="cursor")` — strip Claude-specific hints
- Keep IDE-specific writers as-is (they work, just need content trimming)
- Lower priority because these IDEs have their own MCP UIs

---

## What NOT to Build

- **No adapter framework.** No `class ClientAdapter` with subclasses. Just `if/elif` in 2-3 places.
- **No client capability negotiation.** We don't need to query what the client supports. We know from the name.
- **No per-client tool schemas.** All clients get the same 6 tools. The tools themselves are client-agnostic.
- **No per-client resource/prompt filtering.** MCP spec doesn't support this and it's not needed.
- **No runtime rules generation.** Rules files are written once at init/update time. Don't regenerate them on every MCP connection.

---

## Files to Modify

| File | Change | LOC |
|------|--------|-----|
| `src/codrag/core/rules_generator.py:328-496` | Add `target` param to `_build_managed_content()`, trim per-target | ~30 |
| `src/codrag/core/rules_generator.py:89-119` | Pass `target` to writers based on IDE name | ~5 |
| `src/codrag/mcp/server.py:2166-2174` | Client-aware `instructions` field | ~10 |
| `src/codrag/mcp/server.py` (tool_context) | Skip preamble for Claude Code clients | ~10 |

**Total: ~55 lines changed.** Simple.

---

## Verification

1. Run `codrag rules --update` on this project, diff the CLAUDE.md and AGENTS.md outputs — CLAUDE.md should be noticeably shorter
2. Connect Claude Code to the MCP server, check the `system-reminder` for the trimmed instructions
3. Call `codrag` from Claude Code, verify no redundant "how to use CoDRAG" preamble in response
4. Connect Cursor to the same server, verify it still gets the verbose instructions and full preamble
