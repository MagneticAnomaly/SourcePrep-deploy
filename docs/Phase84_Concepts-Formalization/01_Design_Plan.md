# Phase 84 — Concepts Formalization: From Theoretical to Load-Bearing

**Date:** 2026-04-08
**Status:** Design finalized
**Scope:** Make `codrag_concepts` reliable and structured enough to power Phase 83's concept violation detection and Phase 87's immune system. Core features: structured data model, typing/editing, observation promotion, anchor system, doc linking. LLM-assisted generation is experimental (high priority).
**Dependencies:** Phase 83 (audit redesign creates the demand for concept violations)
**Predecessor:** Phase 82 docs 05 (observe/concepts analysis) and 08 (ambient context: code vs concepts)

---

## Executive Summary

`codrag_concepts` is currently the most theoretical of CoDRAG's tools. It stores and retrieves design decisions, domain knowledge, and architectural rationale — but the data model is loose, there's no validation, and the boundary between concepts and observations is blurry. Phase 82 doc 05 graded concepts as "N/A" — purpose unclear relative to observe.

Phase 83's audit redesign changes this. Structural mode needs to detect **concept violations** — situations where code diverges from stated architectural intent. Phase 87's immune system needs concepts as **antibody definitions** — patterns that should trigger warnings when violated. Both require concepts to be:

1. **Structured** — not free-text blobs, but assertions with clear subjects, predicates, and scopes
2. **Anchored** — tied to specific files, modules, or symbols so violations can be detected
3. **Statused** — active, deprecated, proposed, so stale concepts don't generate false violations
4. **Queryable** — efficient lookup by file, module, or category for real-time enrichment

This phase formalizes concepts from "a place to write notes about design decisions" into "a structured knowledge base that powers automated architectural enforcement."

### Key Design Decisions

- **Concepts feed the dashboard overlay** — displayed as a grid in MVP, design iterable later
- **Paperclip goal mapping is partial** — some concepts map naturally to Paperclip goals, not a 1:1 bridge
- **Doc linking is a core feature** — concepts link to files, docs, folders (e.g., "Design System" concept links to core component files, Storybook root, relevant docs). Links are addable/removable.
- **Typing/editing is core** — manual concept creation and editing ships in this phase
- **LLM-assisted concept generation is experimental** — behind the global experimental toggle, high priority but not MVP
- **Observation → concept promotion** — human confirms/edits assertion before saving. Start with human review, measure auto-extraction quality over time.
- **Keep basic, revisit for robust UI** — the data model and core interactions ship now; rich visualization and advanced UI come in a future phase

---

## Design

### The Core Problem: What Is a Concept?

Phase 82 doc 08 identified the boundary:
- **Observations** are temporal: "what happened" — events, decisions made, patterns noticed. They have timestamps and decay in relevance.
- **Concepts** are durable: "why things are this way" — design rationale, domain knowledge, constraints. They remain true until explicitly superseded.

The problem is that the current data model doesn't enforce this distinction. A concept stored as "We decided to use SQLite for the project registry" is really an observation (a decision event). A concept stored as "The project registry must be single-file-portable, which is why it uses SQLite" is an actual concept — it encodes *rationale* and *constraint*.

### Concept Data Model v2

```
Concept:
  id: uuid
  title: string              # Human-readable name
  assertion: string           # The core claim (testable statement)
  rationale: string           # Why this is true / why this decision was made
  category: enum              # architecture | domain | constraint | pattern | convention
  status: enum                # active | proposed | deprecated | superseded
  superseded_by: uuid | null  # Link to replacement concept
  anchors: Anchor[]           # What code this concept applies to
  created_at: datetime
  updated_at: datetime
  source: string | null       # Where this concept came from (observation, discussion, PR, doc)
  doc_links: DocLink[]         # Linked documentation, source files, folders
```

**Anchor:**
```
Anchor:
  type: enum                  # file | module | directory | glob
  target: string              # "src/codrag/mcp/server.py" | "mcp" | "src/codrag/core/*"
  relationship: enum          # defines | constrains | explains | warns
```

Symbol-level anchoring deferred — file/module/directory/glob covers all MVP use cases. Can be added later if a concrete need arises.

**Linked Documentation:**
```
DocLink:
  path: string                # File or directory path, relative to project root
  label: string | null        # Optional display label (e.g., "Storybook root")
  type: enum                  # source | doc | config | external
```

Concepts can link to grounded documentation — source files, doc folders, config files, or external references. Example: a "Design System" concept links to `packages/ui/src/components/`, `packages/ui/.storybook/`, and `docs/design-system.md`. Links are addable and removable through both MCP and dashboard UI.

### Category Taxonomy

| Category | Purpose | Example |
|----------|---------|---------|
| **architecture** | Structural decisions about how the system is organized | "MCP server proxies all calls through HTTP daemon — no direct index access" |
| **domain** | Business/product knowledge that shapes implementation | "CoDRAG indexes must be portable — no dependency on external databases" |
| **constraint** | Hard limits that must not be violated | "Pi Agent must never import LLM client libraries — zero-LLM architecture" |
| **pattern** | Established approaches to recurring problems | "All MCP tool handlers follow the dispatch pattern: parse params → validate → call API → format response" |
| **convention** | Team/project norms for consistency | "All MCP tool responses include a `_meta` block with timing and freshness info" |

### Assertion as Testable Statement

The key design choice: every concept must have an `assertion` field that is a **testable statement**. This is what enables concept violation detection:

| Assertion | How to Test | Violation Example |
|-----------|-------------|-------------------|
| "server.py dispatches all MCP tool calls through HTTP API, not direct function calls" | Check import graph: server.py should not import core modules directly | server.py imports `codrag.core.code_index` directly |
| "Pi Agent has zero LLM dependencies" | Check import graph: pi_agent.py should not import llm_client or any LLM SDK | pi_agent.py adds `from codrag.core.llm_client import ...` |
| "Dashboard state is derived from SSE events, not direct API polling" | Check dashboard code for direct API calls to state endpoints | Dashboard adds `fetch('/api/pipeline/status')` polling loop |

Not all assertions are automatically testable — some require human judgment. But the structured format makes it possible for the audit tool to check the ones that *are* testable (primarily import-graph and file-presence checks).

### Concept Lifecycle

```
proposed → active → [deprecated | superseded]
                         ↓
                    superseded_by: <new concept>
```

- **Proposed:** Someone (human or AI) thinks this should be a concept. Not yet enforced.
- **Active:** Validated and enforced. Concept violations against active concepts generate audit findings.
- **Deprecated:** No longer relevant. Kept for history but not enforced.
- **Superseded:** Replaced by a newer concept. The `superseded_by` link maintains the evolution chain.

### Concept Conflict Resolution

When two active concepts contradict each other:
- **For code enforcement:** Oldest concept wins. The older concept's assertion is used for violation detection.
- **In the dashboard:** Both conflicting concepts get **red outlines** until a human resolves the conflict.
- **In audit:** Surfaced as an audit finding: "Conflicting concepts detected" listing both, with a prompt to resolve.

CoDRAG doesn't pick a winner beyond the "oldest wins for code" default. Human resolution is required.

### Integration with Phase 83 Audit

The audit structural mode queries concepts as follows:

1. For each file in scope, find all concepts anchored to that file, its module, or matching glob patterns
2. For concepts with category=`constraint` or `architecture`, attempt automated violation check (import graph analysis, file presence, pattern matching)
3. For concepts that can't be auto-checked, include them as "architectural context" in the enrichment output (not a violation, but relevant background)

**Violation severity is derived from concept category:**
- `constraint` violation → high severity (hard rule broken)
- `architecture` violation → medium severity (structural intent diverged)
- `pattern` / `convention` violation → low severity (consistency issue)
- `domain` → not a violation source (informational only)

### Migration from Current Concepts

Current concepts are free-text blobs. Migration strategy:

1. Export all existing concepts
2. For each, attempt to extract: assertion, rationale, category, anchors
3. Where extraction fails, mark as `proposed` status and flag for human review
4. New concepts created via the API must conform to v2 schema (assertion required)
5. Old-format concepts still queryable but won't power violation detection until migrated

---

## Implementation Plan

### Stage 1: Schema & Storage Update

**Files to modify:**
- `src/codrag/core/concepts.py` (or equivalent) — Update data model to v2 schema
- Storage layer — Add new fields, handle migration of existing concepts
- `src/codrag/mcp_tools.py` — Update `codrag_concepts` parameter schema

**What to build:**
1. v2 Concept dataclass with all new fields
2. Storage migration (add columns/fields, preserve existing data)
3. Backward-compatible read (old concepts work but lack new fields)
4. Validation: `save` action requires `assertion` field for new concepts

### Stage 2: Anchor System

**What to build:**
1. Anchor data model and storage
2. Anchor resolution: given a file path, find all concepts anchored to it (direct file match, module match, glob match, symbol match)
3. Reverse lookup: given a concept, find all files it applies to
4. Anchor validation: check that anchor targets actually exist in the codebase

### Stage 3: Violation Detection Engine

**New file:** `src/codrag/core/concept_checker.py`

**What to build:**
1. Import-graph violation checker: does file X import something concept Y says it shouldn't?
2. File-presence checker: does a file/symbol exist that concept Y says shouldn't exist?
3. Pattern matcher: does code in scope follow the pattern concept Y describes?
4. Violation report generator: for a given scope, list all active concept violations with severity
5. Integration point: audit structural mode calls concept checker as part of its finding generation

### Stage 4: Concept Population & Tooling

**What to build:**
1. Concept extraction from observations: scan observation history for statements that should be concepts (e.g., "we decided to..." → proposed concept)
2. Concept suggestion during `codrag_observe`: when saving an observation that looks like a durable decision, suggest promoting it to a concept
3. Concept review command: surface proposed/unanchored concepts for human review
4. Bulk concept import: accept a structured file of concepts (for seeding from docs)

### Stage 5: Testing & Validation

- Create 10-15 seed concepts for the CoDRAG codebase itself (dogfooding)
- Validate that violation detection correctly identifies intentional violations
- Validate that no false positives occur for compliant code
- Test concept lifecycle: create → activate → violate → detect → resolve → deprecate

---

## Success Criteria

1. **Every concept has a testable assertion** — no more free-text blobs for new concepts
2. **Anchor resolution works** — given a file, all relevant concepts are found in <100ms
3. **Violation detection has <10% false positive rate** — measured against CoDRAG's own concepts
4. **Audit structural mode uses concepts** — concept violations appear as findings in `codrag_audit()`
5. **Observe → concept promotion** works — temporal observations can be promoted to durable concepts
6. **Backward compatible** — existing concepts still queryable even if not fully migrated

---

## Resolved Questions

1. **Auto-extraction quality** — Start with human review. Observation → concept promotion flow: suggest → human confirms/edits assertion → save. Measure auto-extraction success rate over time. If 60%+ are usable with light editing, consider more automation.
2. **Concept conflict resolution** — Oldest concept wins for code enforcement. Both get red outlines in dashboard UI. Also surfaced as an audit finding. Human resolution required.
3. **Anchor granularity** — File/module/directory/glob for MVP. Symbol-level deferred — no concrete use case demands it yet.
4. **LLM-assisted concept creation** — Behind global experimental toggle. High priority but not MVP. When enabled, LLM helps structure assertions from free-text input.
