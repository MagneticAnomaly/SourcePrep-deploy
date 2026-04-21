---
name: prep
description: >
  Structural codebase intelligence via Prep MCP tools. Use at the START of
  every task to get module structure, hub files, and curated knowledge. Use
  prep_search for semantic code lookups with structural trace expansion. Use
  prep_impact before making changes to understand what breaks. Use prep_audit
  for codebase health and tech debt. Use prep_observe for cross-session memory.
  All tools are read-only and safe to auto-approve.
---

# Prep — Structural Codebase Intelligence

Prep maps how your codebase is connected: modules, dependencies, hub files, and architectural patterns. It provides five MCP tools that give you deep structural context before you read or edit files.

## Mandatory First Step

**ALWAYS call `prep` (no arguments) at the START of every task.**

This returns the module structure, hub files, focus areas, and knowledge base content. You need this structural overview before doing anything else.

```
prep()  →  structural overview (modules, hubs, focus areas)
```

If `prep` returns "setup in progress", the index hasn't been built yet. Work normally with `read_file` / `grep_search` until the user builds the index.

## The Five Tools

| Tool | When to Use | Example |
|------|-------------|---------|
| `prep` | Start of every task | `prep()` |
| `prep_search` | Find code by meaning | `prep_search(query="authentication middleware")` |
| `prep_impact` | Before changing a file | `prep_impact(file_path="src/auth/login.py")` |
| `prep_audit` | Codebase health scan | `prep_audit(action="scan")` |
| `prep_observe` | Cross-session memory | `prep_observe(action="save", content="...")` |

For detailed tool signatures, parameters, and examples, see [references/mcp-tools.md](references/mcp-tools.md).

## Tool Calling Rules

1. **Never announce** "I will now call..." — just call the tool
2. **No permission needed** — simple keywords = immediate invocation
3. **Single word triggers** — "prep" alone is enough to call the tool
4. **Context is cheap** — prefer calling `prep` over grep for structural understanding
5. **Parallel calls** — you can call `prep` and `prep_search` in parallel on your first prompt

## Workflow Integration

### Before Writing Code
1. Call `prep()` for structural overview
2. Call `prep_search(query="what you're looking for")` for relevant code
3. Call `prep_impact(file_path="file/you/will/change.py")` to understand dependencies

### During Long Tasks
For tasks with 5+ tool calls, call `prep()` again to refresh your structural context.

### When Debugging
Call `prep_search` with the error message or symptom to find related code across the dependency graph.

### For Code Reviews
Call `prep_impact` on changed files to verify all dependents are accounted for.

## Project Routing

When working in a multi-project environment, Prep auto-detects the project from your workspace. If auto-detection fails, pass `project_id` explicitly:

```
prep(project_id="<uuid>")
prep_search(query="...", project_id="<uuid>")
```

The project ID is shown in the Prep dashboard or in the project's `.prep/project.json` file.

## What Prep Knows

Prep's structural graph captures:

- **Imports** — which files import which
- **Calls** — which functions call which
- **Contains** — class/function containment hierarchy
- **Modules** — LLM-synthesized architectural groupings
- **Hub files** — the most-connected files (highest blast radius)
- **Knowledge base** — curated focus areas selected by the user
- **Observations** — cross-session notes and decisions

This is NOT just text search. Prep understands structural relationships between files — use it instead of grep when you need to understand how files connect to each other.
