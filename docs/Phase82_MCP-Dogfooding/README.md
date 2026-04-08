# Phase 82 — MCP Dogfooding: Honest Tool Assessment

**Date:** 2026-04-07
**Author:** Claude Opus 4.6 (dogfooding as a CoDRAG consumer)
**Method:** Live MCP tool calls against CoDRAG's own index, evaluated from the perspective of an AI coding agent trying to use the tools productively.

## Purpose

CoDRAG's CLAUDE.md says: *"Every call to these tools is also a test of the product. If results are unhelpful, incomplete, or wrong, that is actionable product feedback."*

This phase takes that seriously. Every CoDRAG MCP tool was exercised with realistic queries, edge cases, and parameter combinations. Results were evaluated on:

1. **Signal quality** — Does the result help me accomplish a coding task?
2. **Noise ratio** — How much irrelevant content do I have to wade through?
3. **Consistency** — Are similar queries handled similarly? Is output format predictable?
4. **Actionability** — Can I act on the result, or do I need to make additional calls?
5. **Completeness** — Are important edges, nodes, or findings missing?

## Tools Tested

| Tool | Calls Made | Overall Grade | Primary Issue |
|------|-----------|---------------|---------------|
| `codrag` | 2 (default + role="intern") | B+ | Role projection broken; hub selection favors docs over code |
| `codrag_search` | 3 (semantic, symbol, working_dir) | B | Symbol search returns no context; semantic misses on "build pipeline" |
| `codrag_impact` | 2 (server.py, mcp_tools.py) | C+ | Raw JSON output; stdlib noise; missing internal edges |
| `codrag_audit` | 2 (scan + report) | B- | Severity inflation; duplicate findings; generic remediation |
| `codrag_observe` | 1 (get) | A- | Works well; decision-heavy but useful |
| `codrag_concepts` | 1 (get) | N/A | Empty — feature not adopted yet |

## Documents

| Doc | Contents |
|-----|----------|
| [01_codrag_Tool.md](01_codrag_Tool.md) | Structural overview tool — role projection, hub selection, dedup |
| [02_codrag_search.md](02_codrag_search.md) | Semantic search — symbol context, intent matching, confidence |
| [03_codrag_impact.md](03_codrag_impact.md) | Dependency analysis — JSON format, stdlib noise, missing edges |
| [04_codrag_audit.md](04_codrag_audit.md) | Codebase health — severity model, dedup, remediation quality |
| [05_codrag_observe_concepts.md](05_codrag_observe_concepts.md) | Memory tools — observe richness, concepts adoption |
| [06_Cross_Cutting_UX.md](06_Cross_Cutting_UX.md) | Cross-tool patterns: output format, token budget, progressive disclosure |
| [07_Prioritized_Fix_Plan.md](07_Prioritized_Fix_Plan.md) | Ranked fix list with code pointers and effort estimates |
| [08_Ambient_Context_Code_vs_Concepts.md](08_Ambient_Context_Code_vs_Concepts.md) | Deep dive: structural vs conceptual context, observe/concepts boundary, Option C layered approach |
| [09_Ideas_Backlog.md](09_Ideas_Backlog.md) | Unfiltered ideas for MCP tool improvements — features, UX, new tools, integrations |
| [10_Search_Intelligence.md](10_Search_Intelligence.md) | Deep dive: making semantic search smarter — intent detection, multi-modal retrieval, feedback loops |
| [11_Agent_Workflow_Patterns.md](11_Agent_Workflow_Patterns.md) | How agents actually use tools in practice — observed patterns, anti-patterns, workflow templates |
| [12_Competitive_Landscape.md](12_Competitive_Landscape.md) | What other codebase intelligence tools do that CoDRAG could learn from |

## Key Findings (Executive Summary)

### What's Working Well
- **Module summaries** from `codrag` give real orientation value — the 11-stage pipeline description alone saves significant exploration time
- **Semantic search** lands good hits when the query maps cleanly to actual code concepts (0.83-0.86 confidence scores)
- **Cross-session observations** (`codrag_observe`) are genuinely valuable — the decision history tells a story that git log cannot
- **The audit scanner** finds real architectural issues (circular deps, coupling hotspots, bottleneck files)

### What Needs Fixing
1. **Role-based atlas projection** returns irrelevant Storybook `.d.ts` files instead of role-appropriate content
2. **`codrag_impact` returns raw JSON** while all other tools return formatted markdown — breaks agent UX
3. **Impact analysis is dominated by stdlib imports** (`json`, `os`, `logging`) that add no value
4. **Audit severity is inflated** — `package-lock.json` flagged as "critical", same bottleneck reported 6x across modules
5. **Symbol search returns bare file paths** — no function signatures, no code context, no line numbers
6. **Ambient context mixes structural and conceptual knowledge** without separation — see [08_Ambient_Context_Code_vs_Concepts.md](08_Ambient_Context_Code_vs_Concepts.md) for the deeper analysis

### Strategic Opportunities
- **Progressive disclosure** — all tools dump maximum context; none offer "give me the 3 most important things"
- **Token budget awareness** — a single `codrag_audit report` can return 10K+ tokens of large-file warnings about lock files
- **Cross-tool coherence** — `codrag_impact` and `codrag_audit` both identify bottleneck files but don't cross-reference each other
