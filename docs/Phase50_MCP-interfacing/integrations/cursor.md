# Cursor Integration Research

> How Cursor consumes MCP, what its system prompt looks like, and how Prep should optimize for it.

**Status:** UPDATED with deep-dive findings
**Last updated:** 2026-03-14 (deep dive update)

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Type** | IDE (VS Code fork) |
| **Vendor** | Anysphere |
| **Model** | Claude Sonnet 3.5/4, GPT-4o, custom (user-selectable) |
| **MCP Spec** | Full (tools, resources, prompts, roots, elicitation, apps) |
| **Transport** | stdio, SSE |
| **Rules File** | `.cursor/rules/*.mdc` (YAML frontmatter) |
| **AGENTS.md** | YES (confirmed on agents.md site) |
| **Tool Limit** | ~40 tools sent to agent (confirmed in docs) |
| **Market Share** | Largest AI IDE by user base |

---

## 2. MCP Implementation Details

### Supported Primitives
- **Tools**: Full support. Agent automatically uses MCP tools when relevant. Includes Plan Mode.
- **Resources**: Supported. "The model determines when it needs additional context, then requests specific resources." Resources are NOT auto-injected.
- **Prompts**: Supported. Appear as slash commands in chat.
- **Roots**: Supported. Server can inquire about workspace URIs.
- **Elicitation**: Supported. Server can request additional information from users.
- **Apps**: Supported. Interactive UI views returned by MCP tools.

### Tool Discovery
- All MCP tool definitions are injected into the system prompt on every turn
- Each tool's `name`, `description`, and `inputSchema` consume system prompt tokens
- Prep's 5 consolidated tools (~1,400 tokens) fit well within the 40-tool budget

### Confirmation Model
- Default: user must approve each MCP tool call
- Can be set to auto-run per server in Settings > Features > MCP
- Prep recommendation: enable auto-run (all Prep tools are read-only)

**PITFALL: YOLO Mode Does NOT Auto-Approve MCP Tools**
Cursor's "YOLO mode" (auto-run terminal commands) does NOT auto-approve MCP tool calls.
This is confirmed from the Cursor forum as a known limitation/feature request.
Users will assume YOLO = everything auto-runs. Prep setup docs MUST say:
"YOLO mode is not enough. Go to Settings > Features > MCP > enable auto-run for the prep server."

### Schema Processing
- Cursor validates tool schemas against its internal requirements
- Unknown: whether Cursor strips `$schema` or `additionalProperties` (Gemini CLI does)

### MCP Server Instructions
- **UNKNOWN**: Cursor docs do not mention support for the `instructions` field in server capabilities
- **Research needed**: Empirical test -- add instructions to Prep's initialize response and check if Cursor appends them to the system prompt

---

## 3. System Prompt & Context Architecture

### Base System Prompt
- Cursor's system prompt instructs the AI about available tools (built-in + MCP)
- Built-in tools include: `read_file`, `edit_file`, `grep_search`, `run_command`, `codebase_search`, etc.
- Estimated built-in tool overhead: ~2,000 tokens
- Agent mode has a more detailed system prompt than normal chat mode

### Native Tools That Compete With Prep
| Cursor Native | Prep Equivalent | Competition Level |
|--------------|-------------------|------------------|
| `codebase_search` | `prep_search` | HIGH -- similar purpose, AI prefers native |
| `read_file` | `prep` (hub file content) | MEDIUM -- different granularity |
| `grep_search` | `prep_search` | MEDIUM -- Prep adds structure |
| `list_dir` | `prep` (module overview) | LOW -- different purpose |

### Key Insight: AI Prefers Native Tools
Cursor's AI has been trained/prompted to use its own tools. MCP tools are "additional" and will be called less frequently unless:
1. The rules file explicitly instructs "call prep FIRST"
2. The tool description includes clear activation criteria
3. The user mentions Prep or structural context

---

## 4. Rules File: `.cursor/rules/prep.mdc`

### Format
```yaml
---
description: Short description
globs: ["**/*"]        # which files this applies to
alwaysApply: true      # inject on every prompt
---
<markdown content>
```

### Rule Types
- **Always Apply**: injected into every prompt (this is what Prep needs)
- **Apply Intelligently**: model decides based on context
- **Apply to Specific Files**: only when matching files are referenced
- **Apply Manually**: user must explicitly invoke

### Precedence
Team Rules > Project Rules > User Rules

### Prep Template
```yaml
---
description: Prep structural codebase intelligence
alwaysApply: true
---

You have access to Prep, a structural code intelligence system.
ALWAYS call `prep` (no arguments) at the START of every task.
This gives you module structure, hub files, and focus areas.

For specific code searches, use `prep_search` with a natural language query.
Before making changes, use `prep_impact` to check dependencies.

## Codebase Atlas
[auto-generated from atlas.json]

## Focus Areas
[auto-generated from included_paths]

Last indexed: [timestamp] | [node_count] nodes, [edge_count] edges | [coverage]% coverage
```

---

## 5. Context Interpretation

### Response Format
- Cursor's AI processes markdown well (it's the native format for its system prompt)
- JSON responses require parsing -- adds cognitive overhead for the model
- Code blocks are preserved and rendered correctly
- **Recommendation**: Return clean markdown, not JSON

### Multi-Turn Behavior
- Context window depends on selected model (128K for Claude, varies for others)
- Earlier tool responses scroll out in long conversations
- Atlas in rules file persists across all turns (alwaysApply)

### Parallel Tool Calls
- Cursor's agent mode supports parallel tool calls
- Prep's rules file should encourage: "Call `prep` and `prep_search` in parallel on first prompt"

---

## 6. Prep Optimization Checklist

- [x] Phase 50 README covers Cursor basics
- [ ] Empirically test: does Cursor support MCP server `instructions`?
- [ ] Empirically test: does Cursor auto-inject MCP resources into context?
- [ ] Empirically test: what is `clientInfo.name` in Cursor's initialize request?
- [ ] Test auto-approve setup for Prep server
- [ ] Verify `.cursor/rules/prep.mdc` injection with `alwaysApply: true`
- [ ] Test parallel `prep` + `prep_search` calls
- [ ] Measure token overhead of Prep tools in Cursor's system prompt

---

## 7. Risk Assessment

| Risk | Severity | Notes |
|------|----------|-------|
| AI prefers native `codebase_search` over `prep_search` | HIGH | Rules file mitigates. Tool description must differentiate. |
| **YOLO mode doesn't auto-approve MCP** | **HIGH** | Users will be confused. Explicit setup docs required. |
| Tool approval fatigue | MEDIUM | Auto-approve setup in docs. |
| Rules file overwritten by user | LOW | Marker-based split preserves user content. |
| AGENTS.md + .mdc conflict | LOW | Both can coexist. .mdc takes precedence in Cursor. |
