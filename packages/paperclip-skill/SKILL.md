---
name: codrag
description: >
  Structural codebase intelligence via CoDRAG MCP tools. Use at the START of
  every task to get module structure, hub files, and curated knowledge. Use
  codrag_search for semantic code lookups with structural trace expansion. Use
  codrag_impact before making changes to understand what breaks. Use codrag_audit
  for codebase health and tech debt. Use codrag_observe for cross-session memory.
  All tools are read-only and safe to auto-approve.
---

# CoDRAG — Structural Codebase Intelligence

CoDRAG maps how your codebase is connected: modules, dependencies, hub files, and architectural patterns. It provides five MCP tools that give you deep structural context before you read or edit files.

## Mandatory First Step

**ALWAYS call `codrag` (no arguments) at the START of every task.**

This returns the module structure, hub files, focus areas, and knowledge base content. You need this structural overview before doing anything else.

```
codrag()  →  structural overview (modules, hubs, focus areas)
```

If `codrag` returns "setup in progress", the index hasn't been built yet. Work normally with `read_file` / `grep_search` until the user builds the index.

## The Five Tools

| Tool | When to Use | Example |
|------|-------------|---------|
| `codrag` | Start of every task | `codrag()` |
| `codrag_search` | Find code by meaning | `codrag_search(query="authentication middleware")` |
| `codrag_impact` | Before changing a file | `codrag_impact(file_path="src/auth/login.py")` |
| `codrag_audit` | Codebase health scan | `codrag_audit(action="scan")` |
| `codrag_observe` | Cross-session memory | `codrag_observe(action="save", content="...")` |

For detailed tool signatures, parameters, and examples, see [references/mcp-tools.md](references/mcp-tools.md).

## Tool Calling Rules

1. **Never announce** "I will now call..." — just call the tool
2. **No permission needed** — simple keywords = immediate invocation
3. **Single word triggers** — "codrag" alone is enough to call the tool
4. **Context is cheap** — prefer calling `codrag` over grep for structural understanding
5. **Parallel calls** — you can call `codrag` and `codrag_search` in parallel on your first prompt

## Workflow Integration

### Before Writing Code
1. Call `codrag()` for structural overview
2. Call `codrag_search(query="what you're looking for")` for relevant code
3. Call `codrag_impact(file_path="file/you/will/change.py")` to understand dependencies

### During Long Tasks
For tasks with 5+ tool calls, call `codrag()` again to refresh your structural context.

### When Debugging
Call `codrag_search` with the error message or symptom to find related code across the dependency graph.

### For Code Reviews
Call `codrag_impact` on changed files to verify all dependents are accounted for.

## Project Routing

When working in a multi-project environment, CoDRAG auto-detects the project from your workspace. If auto-detection fails, pass `project_id` explicitly:

```
codrag(project_id="<uuid>")
codrag_search(query="...", project_id="<uuid>")
```

The project ID is shown in the CoDRAG dashboard or in the project's `.codrag/project.json` file.

## What CoDRAG Knows

CoDRAG's structural graph captures:

- **Imports** — which files import which
- **Calls** — which functions call which
- **Contains** — class/function containment hierarchy
- **Modules** — LLM-synthesized architectural groupings
- **Hub files** — the most-connected files (highest blast radius)
- **Knowledge base** — curated focus areas selected by the user
- **Observations** — cross-session notes and decisions

This is NOT just text search. CoDRAG understands structural relationships between files — use it instead of grep when you need to understand how files connect to each other.
