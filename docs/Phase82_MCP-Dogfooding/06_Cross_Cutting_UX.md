# 06 — Cross-Cutting UX and Architecture Opportunities

These patterns span multiple tools and represent systemic improvements to the CoDRAG MCP experience.

---

## PATTERN 1: Output Format Inconsistency

### The Problem
Three different output formats across 5 tools:

| Tool | Format | Example |
|------|--------|---------|
| `codrag` | Rich markdown with tables, headers, code blocks | Module summaries, pipeline diagram |
| `codrag_search` | Markdown with metadata annotations | `[query terms: X✓ Y✗]`, confidence scores |
| `codrag_impact` (dependents) | Clean markdown lists | "Direct dependents (14): ..." |
| `codrag_impact` (all/deps) | **Raw JSON** | `{"nodes": [...], "edges": [...]}` |
| `codrag_audit` | Markdown with severity badges | `[critical]`, `[warning]`, `[info]` |

An agent consuming these tools has to handle 3 different parsing expectations. The raw JSON from `codrag_impact(direction="all")` is the worst offender — it requires mental JSON parsing that no other tool demands.

### The Fix
Standardize on a common output envelope:
```
[project: CoDRAG]
[tool: codrag_impact | target: server.py | direction: all]

## Summary
{1-2 sentence natural language summary}

## Details
{tool-specific formatted content}

## Metadata
{structured data for programmatic use — confidence, counts, etc.}
```

Every tool should have a human-readable summary section and a structured metadata section. The JSON raw data can live in metadata for agents that want to parse it, but the primary content should always be readable markdown.

---

## PATTERN 2: No Progressive Disclosure

### The Problem
Every tool dumps maximum context on every call:
- `codrag`: Full module summaries + full hub excerpts (~4K tokens)
- `codrag_search`: Full file content for matched chunks (~3K tokens)
- `codrag_audit`: 15+ findings with full descriptions (~3K tokens)
- `codrag_audit report`: All findings in the category (~5K+ tokens)
- `codrag_impact`: All nodes and edges, including stdlib

There's no way to say "give me the headline" before committing to the full context.

### The Fix
Add a `detail` parameter to all tools with three levels:

| Level | Description | Token budget |
|-------|-------------|-------------|
| `summary` | One-paragraph answer, key metrics only | ~500 tokens |
| `standard` (default) | Current behavior | ~2-4K tokens |
| `full` | Everything, including extended metadata | ~5-8K tokens |

Example for `codrag_audit(detail="summary")`:
```
[project: CoDRAG] 100 findings (32 critical, 2 warning, 66 info).
Top issues: react.tsx bottleneck (6 modules affected), 
queue.py↔events.py circular dep, orchestrator.py at 2459 lines.
Use codrag_audit(category="architecture") for details.
```

This would save 2.5K tokens on the initial call while giving the agent enough to decide whether to drill down.

---

## PATTERN 3: Token Budget Unawareness

### The Problem
CoDRAG's MCP server has per-client character limits (documented in `server.py:123-138`), but individual tool responses don't respect a caller-specified budget. An agent with 4K tokens of context budget can't tell `codrag_search` "fit your answer in 2K tokens."

The role atlas truncation (`server.py:1154`, 2000 chars) is a hardcoded limit, not a negotiated one. Different agents have wildly different context budgets — Claude Code (200K context) vs Cursor (varies) vs Copilot (8K tool response limit).

### The Fix
Accept a `max_tokens` parameter on all tools. Use it to:
1. Truncate code snippets intelligently (show signatures, not full bodies)
2. Limit the number of findings/results returned
3. Prefer summaries over full content when budget is tight

The existing per-client limits in `server.py:123-138` are a good foundation — extend them to be per-call configurable.

---

## PATTERN 4: No Cross-Tool References

### The Problem
Each tool operates in isolation:
- `codrag_audit` identifies `react.tsx` as a bottleneck
- `codrag_impact` can analyze `react.tsx` dependents
- But `codrag_audit` doesn't say "run `codrag_impact(file_path='react.tsx')` for details"

The tools don't cross-reference each other, even when the natural follow-up action is obvious.

### The Fix
Add "Next steps" suggestions to tool outputs:
```
## Next Steps
- Run `codrag_impact(file_path="packages/ui/src/api/react.tsx")` 
  to see which modules would be affected by refactoring
- Run `codrag_search(query="react.tsx api hooks")` to understand 
  what this file provides
```

This turns the tool suite into a guided workflow rather than 5 independent endpoints. Agents (and humans) naturally follow suggested next actions.

---

## PATTERN 5: Stale Index Detection

### The Problem
There's no signal in tool responses about whether the index is current. If I modified 50 files since the last index build, every tool response is based on stale data — but nothing warns me.

The watcher (`src/codrag/core/watcher.py`) tracks file changes and triggers rebuilds, but the MCP tool responses don't include freshness information.

### The Fix
Add a staleness indicator to every tool response:
```
[index: fresh | last build: 2m ago | 0 unindexed files]
```
or:
```
[index: stale | last build: 4h ago | 23 modified files pending]
⚠ Results may not reflect recent changes. 
Consider rebuilding: codrag build
```

This is especially important for `codrag_impact` — if the index is stale, dependency information could be wrong.

---

## PATTERN 6: No "I Don't Know" Signal

### The Problem
When `codrag_search` can't find a good match, it still returns something — the best available result, even if confidence is low. There's no clear "I searched and found nothing relevant" response.

When `codrag_impact` has a sparse graph for a file, it returns what edges exist without noting "this file's graph is incomplete — only 3 of ~20 expected imports are traced."

### The Fix
Be explicit about uncertainty:
```
[retrieval confidence: low | top score: 0.42 | below threshold 0.60]
⚠ No strong matches found for "quantum computing in auth module."
The closest result may not be relevant. Consider rephrasing or 
using grep for exact string matching.
```

For impact analysis:
```
[graph completeness: partial | 3 of ~18 imports resolved]
⚠ This file has many imports that aren't in the trace graph.
Results show a subset of actual dependencies.
```

Explicit uncertainty is more useful than confident-looking incomplete results.

---

## PATTERN 7: MCP Tool Descriptions Could Drive Better Usage

### The Problem
The tool descriptions in `mcp_tools.py` are good but could do more to prevent misuse. For example:
- `codrag_search` with `type=symbol` — agents expect code context but get bare paths
- `codrag_impact` with `direction=all` — agents expect the same format as `direction=dependents`
- `codrag_audit` without a `category` — agents get 100 findings when they probably want 10

### The Fix
Add usage hints to tool parameter descriptions:
```python
{
    "name": "type",
    "description": "Search mode. 'context' returns code snippets with semantic 
    analysis. 'symbol' returns file locations only (use Read tool to see code). 
    Prefer 'context' unless you only need to locate a known function name."
}
```

This steers agents toward the right parameter choices before they waste a tool call.
