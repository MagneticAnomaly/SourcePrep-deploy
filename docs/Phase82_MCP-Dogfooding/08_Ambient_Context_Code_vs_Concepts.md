# 08 — Ambient Context: Code vs Concepts

## The Tension

The `codrag` ambient tool currently serves two distinct context needs in a single response:

1. **Structural context** — module boundaries, file relationships, dependency graph, entry points. This is *code-first* knowledge: "what connects to what."
2. **Conceptual context** — design rationale, strategic decisions, planning documents, architectural intent. This is *idea-first* knowledge: "why things are the way they are."

The current implementation blends both. The module summaries are structural. The hub file excerpts (Phase 62 research docs) are conceptual. Both are valuable — but they serve different agent needs at different moments, and bundling them creates a "neither fish nor fowl" problem.

## The Original Critique Was Wrong (Partly)

The initial dogfooding feedback said: "Hub file selection favors docs over code — coding agents need code hubs, not research papers."

This was too hasty. The Phase 62 research docs *are* high-value context:
- The epistemology doc explains CoDRAG's identity and architecture at a level that code alone cannot convey
- The universal adapter doc explains *why* the MCP server is designed the way it is
- Strategic pivot decisions explain why certain features were removed or deprioritized

An agent that only sees code structure but doesn't understand these decisions will make worse choices. The problem isn't that conceptual context is surfaced — it's that:

1. **It's mixed with structural context** in a way that makes both harder to parse
2. **`codrag_concepts` already exists** as the dedicated tool for this exact purpose, but it's empty
3. **There's no clear division of labor** between what `codrag` ambient context provides and what `codrag_concepts` should provide

## The Real Question: Where Should Strategic Knowledge Live?

### Option A: Keep It in `codrag` Ambient (Status Quo)
Hub file excerpts continue to include research docs and planning materials alongside code modules.

**Pros:**
- Agents get strategic context automatically without knowing to ask for it
- No adoption barrier — works today
- Planning docs genuinely have high in-degree (many things reference them)

**Cons:**
- Mixes two concerns, making neither optimal
- Token budget spent on strategic context reduces space for structural context
- Agents doing pure code tasks get conceptual context they don't need
- The `codrag_concepts` tool becomes redundant/unused

### Option B: Migrate Strategic Knowledge to `codrag_concepts`
The `codrag` ambient tool focuses purely on code structure. Strategic knowledge moves to `codrag_concepts` which agents call when they need the "why."

**Pros:**
- Clean separation of concerns
- Each tool does one thing well
- Agents can choose: "I need code structure" vs "I need design rationale"
- Token budgets for each are independently manageable
- `codrag_concepts` gets a real purpose

**Cons:**
- Agents that don't call `codrag_concepts` miss strategic context entirely
- The biggest failure mode in CoDRAG adoption is agents ignoring tools — adding another required call makes this worse
- Requires populating the concepts store (currently empty)

### Option C: Layered Ambient Context (Recommended)
The `codrag` ambient tool returns **code structure by default** but includes a **concepts summary** section that's a compressed pointer to the strategic knowledge.

```
## Modules in Scope
[structural context — module summaries, file counts, entry points]

## Code Hubs
[high-in-degree CODE files — server.py, orchestrator.py, index.py]

## Active Concepts (3)
- "Strategic pivot to knowledge provider" — CoDRAG stopped building PM features 
  (Phase 62). Focus: opportunity discovery, not task management.
- "Dual-agent architecture" — Claude Code (complex/architectural) + Pi (routine/batch). 
  CoDRAG serves both.
- "A2A protocol adoption" — Google A2A alongside MCP for universal agent discovery.
→ Call codrag_concepts() for full context on any concept.
```

**Why this works:**
- Code structure remains the primary content (agents are coding)
- Strategic concepts are *summarized* (1-2 lines each), not excerpted in full
- The summary acts as a menu — agents see what's available and pull the full concept only when relevant
- `codrag_concepts` becomes the drill-down tool, not a separate workflow
- Token budget is predictable: concepts summary is ~300 tokens regardless of how many concepts exist

## How This Changes the Concepts Tool

For Option C to work, `codrag_concepts` needs to be populated. There are two paths:

### Path 1: Manual Population (Low Effort)
The 10 observations in `codrag_observe` are almost all strategic decisions. Many of them are *already* concept-grade knowledge:
- "Strategic pivot to knowledge provider" (Phase 62 doc 7)
- "Dual-agent architecture validated" (Phase 62 doc 8)
- "Dashboard redesign decision" (Phase 62 doc 9)
- "A2A protocol adoption" (Phase 62 doc 10)

A one-time migration script could promote these to concepts:
```python
# Pseudo-code
for obs in observations:
    if obs.category == "decision" and is_strategic(obs):
        concepts.save(
            title=extract_title(obs),
            content=obs.content,
            category="decision" if architectural else "domain",
            anchors=obs.file_paths,
        )
```

### Path 2: Auto-Population from Indexed Content (Medium Effort)
The atlas generator already identifies cross-cutting concerns and hub files. It could also extract concepts from:
- Phase research docs (docs/Phase*/) — these ARE the strategic knowledge
- README files with "why" sections
- CLAUDE.md's architectural descriptions

The extraction could happen during Stage 10 (Atlas Generation):
1. Scan indexed docs for decision language ("we decided", "the strategy is", "this was chosen because")
2. Extract key concepts with LLM summarization
3. Store as concepts with file anchors for staleness tracking

### Path 3: Hybrid — Bootstrap Manually, Auto-Refresh (Recommended)
1. **Bootstrap:** Manually promote the top 5-10 strategic decisions from observations to concepts
2. **Auto-detect new concepts:** During atlas generation, flag new strategic content that isn't yet a concept
3. **Agent-driven capture:** When agents encounter strategic decisions during work (e.g., "I chose approach X because Y"), the agent saves them as concepts via `codrag_concepts(action="save")`
4. **Staleness:** File anchors trigger concept review when referenced files change significantly

## What Changes in the Codebase

### For `codrag` ambient tool:
- **Hub file selection** (`src/codrag/core/atlas/generator.py`): Weight code import edges higher than doc reference edges. Code files with high import in-degree become "Code Hubs." Docs with high reference in-degree become "Knowledge Hubs" but are handled separately.
- **Concepts summary section** (`src/codrag/mcp/server.py`, `tool_context`): After modules and hub files, add a "Active Concepts" section that pulls the top N concepts (by recency or relevance) and renders 1-2 line summaries.

### For `codrag_concepts`:
- **Bootstrap script** or manual population to seed initial concepts from existing observations
- **Integration with atlas generator** for auto-detection of new strategic content
- **Summary rendering** for the `codrag` ambient injection

### For `codrag_observe`:
- **Clearer role distinction**: Observations are what happened (temporal, anchored to events). Concepts are why things are the way they are (durable, anchored to decisions). An observation like "Phase 66 COMPLETE — Pi Agent has 7 scenarios" is an observation. "Pi Agent uses pure Python analysis with zero LLM requirement because routine tasks shouldn't depend on model availability" is a concept.

## The Observe / Concepts Boundary (Clarified)

| Dimension | `codrag_observe` | `codrag_concepts` |
|-----------|------------------|-------------------|
| **Nature** | Temporal — "what happened" | Durable — "why things are this way" |
| **Lifespan** | Short to medium — may become stale | Long — remains valid until explicitly superseded |
| **Trigger** | Events: bug found, decision made, pattern noticed | Reflection: design rationale, domain knowledge, constraints |
| **Examples** | "Phase 66 complete — 7 scenarios built" | "CoDRAG is a knowledge provider, not a PM tool" |
| | "Circular dep found between queue.py and events.py" | "Agents/ depends on services/ depends on core/, never reverse" |
| | "Eric prefers no Co-Authored-By in commits" | "The ActionItem model is the universal output abstraction" |
| **Consumer** | Agents doing related work — "what should I know?" | All agents — "what are the guiding principles?" |
| **In ambient context** | Injected by `working_dir` proximity in search | Summarized in `codrag` ambient overview |

The key insight: observations decay. Concepts persist. An observation that has remained true for 3+ phases and guides future decisions is a concept waiting to be promoted.

## Recommendation

1. **Immediately:** Seed `codrag_concepts` with the top 5 strategic decisions from observations
2. **Next:** Add a "Active Concepts" summary section to the `codrag` ambient response (Option C)
3. **Later:** Build auto-detection of concept-grade content during atlas generation
4. **Ongoing:** Document the observe/concepts boundary in tool descriptions so agents and humans use the right tool

This turns `codrag` into the structural + conceptual orientation tool (compressed), `codrag_concepts` into the strategic knowledge drill-down, and `codrag_observe` into the event/session log. Each tool has a clear, non-overlapping purpose.
