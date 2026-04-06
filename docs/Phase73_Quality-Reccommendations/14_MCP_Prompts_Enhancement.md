# Phase 73 Task 6 — Enhance MCP Prompts

> Date: 2026-04-05 | Expanding CoDRAG's MCP prompts from 3 to 5 structured workflows

---

## 1. Motivation

CoDRAG's MCP prompts (exposed via `prompts/list` and `prompts/get`) are the user-initiated workflow templates that MCP clients surface as slash commands (e.g., `/codrag-review` in Claude Code, Cursor, etc.). They prime conversations with structured multi-step instructions that guide agents through CoDRAG's tools in a coherent sequence.

The original set of 3 prompts (`codrag-analyze`, `codrag-review`, `codrag-plan`) covered architecture analysis, code review, and change planning. However, two common workflows were missing:

1. **Onboarding** — A first-contact orientation prompt for agents (or humans) new to a codebase. The old `codrag-analyze` was close but framed as "analyze the architecture" rather than "orient me to this codebase." The distinction matters: onboarding should produce a mental model, not a critique.

2. **Investigation** — A deep-dive prompt for understanding a specific topic (e.g., "how does authentication work?"). This is distinct from search (which returns code matches) and from review (which evaluates a specific file). Investigation traces a concept across modules, dependencies, and data flow patterns.

3. **Health check** — A codebase health prompt that leverages `codrag_audit` findings and structural context to produce prioritized, actionable recommendations. The old prompts had no audit integration at all.

Additionally, the existing `codrag-review` prompt lacked a `file_path` argument, making it unclear which file should be reviewed. The new version requires `file_path` and makes `scope` optional with clear values (`file`, `module`, `blast-radius`).

---

## 2. Changes Made

### 2.1 `_PROMPTS` Class Variable (server.py)

**Before:** 3 prompts — `codrag-analyze`, `codrag-review`, `codrag-plan`

**After:** 5 prompts — `codrag-onboard`, `codrag-review`, `codrag-plan`, `codrag-investigate`, `codrag-health`

| Prompt | Arguments | Purpose |
|--------|-----------|---------|
| `codrag-onboard` | (none) | Orient to codebase: structural overview, hub files, entry points, attention areas |
| `codrag-review` | `file_path` (required), `scope` (optional) | Structural code review with blast radius awareness |
| `codrag-plan` | `change` (required) | Impact-aware change planning with dependency ordering |
| `codrag-investigate` | `query` (required) | Deep-dive into a topic: search, trace, module context, mental model |
| `codrag-health` | `focus` (optional) | Codebase health check with audit findings and prioritized fixes |

Key changes to existing prompts:
- **`codrag-analyze` removed from the list** but retained as backward-compatible alias in `handle_prompts_get` (redirects to `codrag-onboard`)
- **`codrag-review` gained `file_path`** as a required argument, making it explicit which file is being reviewed
- **`codrag-plan` description updated** from `--` to `—` for typographic consistency

### 2.2 `handle_prompts_get` Method (server.py)

The method was rewritten to handle 5 prompts plus the backward-compat alias. Each prompt returns a `role: "user"` message with a 5-step workflow template.

**Design decisions in the prompt templates:**

1. **Each prompt leads with a CoDRAG tool call.** The first step in every workflow is a CoDRAG MCP tool call (`codrag`, `codrag_search`, `codrag_impact`, or `codrag_audit`). This ensures the agent gets structural context before reasoning.

2. **Steps are numbered 1-5.** Consistent structure across all prompts. The final step always produces a concrete deliverable (summary, plan, mental model, health report).

3. **Tool calls are explicit.** Instead of saying "understand the dependencies," the templates say "Call `codrag_impact` on the file." This reduces ambiguity and increases the chance that agents actually use the tools.

4. **`codrag-investigate` leads with search, not overview.** Unlike other prompts that start with `codrag` for structural context, investigate starts with `codrag_search` because the user has a specific query. Overview comes second to provide structural framing around the search results.

5. **`codrag-health` integrates `codrag_audit`.** This is the only prompt that explicitly invokes the audit tool. The optional `focus` argument lets users narrow to debt, complexity, coverage, or architecture.

6. **Backward compatibility for `codrag-analyze`.** The old prompt name recursively calls `handle_prompts_get` with `codrag-onboard` as the name, preserving any integrations that reference the old name.

### 2.3 Prompt Template Details

#### codrag-onboard

```
Orient me to this codebase using CoDRAG.

1. Call `codrag` to get the structural overview (modules, hub files, connections).
2. Summarize the architecture: what are the main components and how do they connect?
3. Identify the most important files (hub files) and explain their role.
4. List the key entry points and data flow patterns.
5. Note any areas that need attention (from audit findings if available).
```

This replaces `codrag-analyze`. The framing shift from "analyze" to "orient" changes the agent's output from a critique to a navigational map. Step 5 optionally pulls in audit findings, bridging the onboard and health workflows.

#### codrag-review

```
Review `{file_path}` (scope: {scope}) using CoDRAG's structural understanding.

1. Call `codrag_impact` on the file to understand its dependencies and dependents.
2. Call `codrag_search` to find related code and patterns.
3. Check for bugs, style issues, missing error handling, and structural problems.
4. Consider how changes here would affect connected files.
5. Provide concrete improvement suggestions with file references.
```

Now requires `file_path`, which gets interpolated into the template. The scope parameter defaults to `file` but supports `module` (review the containing module) and `blast-radius` (review everything the file affects). Step 5 is new — the old version stopped at "consider how changes would affect connected files" without asking for concrete suggestions.

#### codrag-plan

```
Plan this change: {change}

1. Call `codrag` for structural overview of the codebase.
2. Call `codrag_impact` on files that will be modified to understand the blast radius.
3. Call `codrag_search` to find related code that may need updates.
4. Create a step-by-step implementation plan that accounts for all dependencies.
5. List all files that need changes, in the order they should be modified.
```

Unchanged from the previous version. This prompt was already well-structured.

#### codrag-investigate (NEW)

```
Help me understand: {query}

1. Call `codrag_search` to find relevant code and documentation.
2. Call `codrag` for module structure around the relevant area.
3. Call `codrag_impact` on key files to trace the dependency graph.
4. Explain how the pieces connect — data flow, call chains, design patterns.
5. Summarize with a clear mental model I can use going forward.
```

The `query` argument is required and accepts natural language (e.g., "authentication flow", "how caching works", "what happens when a user signs up"). Step 5 explicitly asks for a mental model — the deliverable is understanding, not a list of files.

#### codrag-health (NEW)

```
Check the health of this codebase using CoDRAG.{focus_text}

1. Call `codrag_audit` to get current findings.
2. Call `codrag` for structural context — hub files and module dependencies.
3. Prioritize findings by impact: what's most likely to cause problems?
4. For the top 3 findings, suggest concrete fixes with file references.
5. Summarize the overall health: what's good, what needs work.
```

The optional `focus` argument narrows the audit scope. When provided, it appears as " Focus on: {focus}." after the opening line. Valid values are `debt`, `complexity`, `coverage`, and `architecture`, though the argument is free-form. Step 4 limits recommendations to the top 3 to avoid overwhelming the user.

---

## 3. Files Modified

| File | Change |
|------|--------|
| `src/codrag/mcp/server.py` | Replaced `_PROMPTS` (3 prompts -> 5), rewrote `handle_prompts_get` (3 branches -> 6 including backward compat) |
| `tests/test_mcp_server.py` | Added 4 tests: `test_prompts_list_has_all_prompts`, `test_prompt_onboard_returns_messages`, `test_prompt_investigate_uses_query`, `test_prompt_analyze_backward_compat` |

---

## 4. Test Coverage

Four new tests were added to `tests/test_mcp_server.py`:

| Test | What It Verifies |
|------|-----------------|
| `test_prompts_list_has_all_prompts` | `handle_prompts_list` returns all 5 prompt names: onboard, review, plan, investigate, health |
| `test_prompt_onboard_returns_messages` | `handle_prompts_get` for `codrag-onboard` returns a valid message structure with `role: "user"` |
| `test_prompt_investigate_uses_query` | `handle_prompts_get` for `codrag-investigate` interpolates the `query` argument into the message text |
| `test_prompt_analyze_backward_compat` | `handle_prompts_get` for the old `codrag-analyze` name redirects to `codrag-onboard` content (contains "Orient") |

All tests construct an `MCPServer` instance via `__new__` to avoid needing a running daemon, then set the minimal required instance attributes.

**Test run output:**
```
tests/test_mcp_server.py::test_prompts_list_has_all_prompts PASSED
tests/test_mcp_server.py::test_prompt_onboard_returns_messages PASSED
tests/test_mcp_server.py::test_prompt_investigate_uses_query PASSED
tests/test_mcp_server.py::test_prompt_analyze_backward_compat PASSED

4 passed in 0.38s
```

---

## 5. Relationship to Design Doc (12_MCP_Ecosystem_Optimization_Design.md)

This implementation directly fulfills Section 4.3 of the MCP Ecosystem Optimization Design document, which specified these exact 5 prompts with their argument signatures:

| Design Doc Spec | Implementation |
|----------------|----------------|
| `codrag-onboard` — none | Implemented, returns 5-step orientation workflow |
| `codrag-review` — `file_path` (required), `scope` (optional) | Implemented with `file`, `module`, `blast-radius` scope values |
| `codrag-plan` — `change` (required) | Retained from previous version, unchanged |
| `codrag-investigate` — `query` (required) | Implemented, search-first workflow with mental model deliverable |
| `codrag-health` — `focus` (optional) | Implemented with audit integration and top-3 recommendation limit |

**Not yet implemented from the design doc:**
- Prompt resource embedding (returning `resource` content type alongside `text` to embed live atlas/module data) — tracked as future enhancement
- Argument auto-completion via MCP completion API — requires `completion/complete` handler
- `.claude/skills/codrag.md` parity — skills and prompts serve different audiences per design doc

---

## 6. Cross-Client Compatibility

MCP prompts are a spec-level primitive supported by all MCP clients. These prompts will surface in:

| Client | How Prompts Appear |
|--------|-------------------|
| Claude Code | `/codrag-onboard`, `/codrag-review`, etc. in the slash command menu |
| Cursor | Prompt picker in chat panel |
| Windsurf | MCP prompt integration |
| VS Code (Copilot) | MCP prompt support (when available) |
| Gemini CLI | MCP prompt support |

No client-specific code is needed. The `prompts/list` and `prompts/get` handlers are protocol-level and work identically across all clients.
