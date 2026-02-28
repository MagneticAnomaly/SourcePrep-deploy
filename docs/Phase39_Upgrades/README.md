# Phase 39: Invisible Upgrades — Better Context, Zero New Complexity

## Design Philosophy

Every upgrade in this phase must satisfy one rule: **the user does nothing new**. No new settings, no new CLI flags, no new concepts to learn. The pipeline gets smarter, the context gets better, the dashboard shows richer data — all automatically.

The upgrades are organized into four workstreams that map directly to existing pipeline stages and surfaces:

| Workstream | Existing Touchpoint | User-Visible Change |
|---|---|---|
| **W1: Trace Graph Enrichment** | Stage 1 (structural) + Stage 2 (inferred_edges) | More edges → better trace expansion → more relevant context |
| **W2: Smarter Context Assembly** | `get_context_with_trace_expansion()` + `/context` endpoint | Higher quality assembled context per query |
| **W3: Session Continuity** | MCP tools + pipeline journal | Agent remembers what it learned; stale knowledge flagged |
| **W4: Impact Awareness** | MCP `codrag_trace_neighbors` tool | Agent can answer "what breaks if I change X?" |

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────────┐
│                    USER DOES NOTHING                      │
│                                                           │
│  Existing Pipeline (unchanged flow):                      │
│                                                           │
│  Stage 1: structural ──► Stage 2: inferred_edges          │
│       │                       │                           │
│       │  W1a: LSP edge        │  W1b: git co-change       │
│       │  ingestion hook       │  edges (DONE in Phase38)  │
│       │  (new edges auto-     │                           │
│       │   merged into graph)  │                           │
│       ▼                       ▼                           │
│  Stage 3-5: catalogue → validate → knowledge              │
│       │                                                   │
│       ▼                                                   │
│  Stage 6-10: enrichment → cluster → atlas → deepen → know │
│       │                                                   │
│       ▼                                                   │
│  CodeIndex build (auto)                                   │
│       │                                                   │
│       ├──► W2: Smarter context assembly (query time)      │
│       ├──► W3: Session memory (MCP tool, auto-capture)    │
│       └──► W4: Impact graph (MCP tool, on-demand)         │
│                                                           │
│  Dashboard: shows new data automatically via existing     │
│  SSE events and status endpoints                          │
└───────────────────────────────────────────────────────────┘
```

--- 

## W1: Trace Graph Enrichment (More Edges, Automatically)

**Goal:** The trace graph becomes denser and more accurate without the user configuring anything. More edges = better trace expansion at query time = better context.

### W1a: LSP Edge Ingestion Hook

**What:** Accept type-resolved call-graph edges from the user's IDE Language Server and merge them into the trace graph alongside our tree-sitter static edges.

**Why invisible:** The VS Code extension (or any future IDE plugin) captures LSP data in the background and POSTs it to the daemon. No user action required. If no IDE extension is installed, nothing changes — the pipeline works exactly as before.

**Integration point:** New REST endpoint `POST /api/projects/{id}/trace/lsp-edges` that writes to `trace_lsp_edges.jsonl`. The existing `TraceIndex.load()` already loads `trace_inferred_edges.jsonl` — we add a second load for `trace_lsp_edges.jsonl` using the same edge schema.

**Files to modify:**
- `src/codrag/api/routers/trace.py` — new endpoint
- `src/codrag/core/trace.py` — `TraceIndex.load()` picks up `trace_lsp_edges.jsonl`
- `packages/vscode/` — extension sends LSP edges on save/build (future)

**Checkboxes:**
- [x] Define `trace_lsp_edges.jsonl` schema (same as `trace_edges.jsonl`: source, target, kind, metadata)
- [x] Add `POST /api/projects/{id}/trace/lsp-edges` endpoint in `trace.py` router
- [x] Validate incoming edges (source/target must be known files, dedup against existing edges)
- [x] Write accepted edges to `trace_lsp_edges.jsonl` in the project index dir
- [x] Update `TraceIndex.load()` to also load `trace_lsp_edges.jsonl` (additive merge)
- [x] Add edge provenance field (`origin: "static" | "inferred" | "lsp" | "co_change"`) to trace edge schema
- [x] Dashboard: trace coverage panel auto-shows LSP edge count (`edge_counts.lsp` in `/trace/coverage` summary)
- [x] Test: submit mock LSP edges via API, accepted + persisted + deduped
- [x] Test: LSP edges with unknown nodes rejected

### W1b: Deferred Phase 38 Items (Finish the Graph)

These were deferred from Phase 38 Sprint 5 but directly improve context quality:

- [x] **SR-3: Weighted trace expansion** — When expanding context via trace edges, weight edge kinds differently (e.g., `calls` > `imports` > `co_change` > `proximity`). Currently all edges are treated equally in `get_context_with_trace_expansion()`.
  - File: `src/codrag/core/index.py` lines 1355-1373 (neighbor collection loop)
  - Implementation: Add `EDGE_WEIGHT` dict, multiply neighbor score by edge weight before ranking

- [x] **SR-9: Graph-augmented retrieval boost** — When a search hit has high in-degree in the trace graph, boost its ranking. Currently implemented only for trace-expanded nodes (Phase 34d B3) but NOT for base search hits.
  - File: `src/codrag/core/index.py` in `get_context_structured()`
  - Implementation: After embedding search, look up in-degree for each hit and add a small boost (0.05-0.10 × normalized_degree)

- [ ] **TG-6: Barrel file resolution** — TypeScript/JavaScript `index.ts` re-export files should forward edges to their actual targets. Currently barrel files are dead-ends in the trace graph.
  - File: `engine/crates/codrag-parser/src/typescript.rs`
  - Implementation: Detect `export * from` / `export { X } from` patterns and emit forwarding edges

---

## W2: Smarter Context Assembly (Better Output Per Query)

**Goal:** The `/context` endpoint and `codrag` MCP tool return higher-quality, more precisely targeted context for each query. All improvements happen at query time inside `get_context_with_trace_expansion()` — no new pipeline stages, no new user config.

### W2a: Intent-Aware Search Mode

**What:** Detect the intent of the query (e.g., "fix bug" vs "add feature" vs "refactor") and adjust the search/expansion strategy automatically.

**Why invisible:** The intent is detected from the query string itself. No new parameters.

**Integration point:** A lightweight classifier function called at the top of `get_context_with_trace_expansion()` that sets internal parameters (trace direction, edge kind weights, expansion depth).

**Files to modify:**
- `src/codrag/core/index.py` — new `_detect_intent(query)` function + parameter adjustment

**Checkboxes:**
- [x] Define intent categories: `debug`, `refactor`, `add_feature`, `understand`, `general`
- [x] Implement `_detect_intent(query: str) -> str` using keyword matching (no LLM needed)
  - `debug` keywords: fix, bug, error, crash, failing, broken, exception, traceback
  - `refactor` keywords: refactor, rename, extract, move, clean up, simplify
  - `add_feature` keywords: add, create, implement, new, feature, build
  - `understand` keywords: how, what, why, explain, where, which
- [x] Adjust search parameters per intent:
  - `debug`: trace_direction="in" (follow callers), prefer `calls` edges, expand 2 hops
  - `refactor`: trace_direction="both", include all edge kinds, expand 2 hops
  - `add_feature`: trace_direction="out" (follow dependencies), expand 1 hop
  - `understand`: trace_direction="both", expand 1 hop, prefer module summaries
- [x] Test: verify "fix the auth bug" returns callers of auth functions
- [x] Test: verify "refactor UserService" returns both callers and dependencies

### W2b: Module Summary Injection

**What:** When the query is broad (e.g., "how does authentication work?"), inject the relevant module summary from the cluster stage into the context *before* the file chunks.

**Why invisible:** The module summaries already exist (from Stage 7: clustering). We just need to include them in the assembled context when appropriate.

**Integration point:** Inside `get_context_with_trace_expansion()`, after base search, check if the top hits cluster into 1-2 modules. If so, prepend the module summary.

**Files to modify:**
- `src/codrag/core/index.py` — in context assembly
- `src/codrag/api/routers/projects.py` — load modules data alongside trace data

**Checkboxes:**
- [x] Load `modules.json` at query time (already loaded by atlas — reuse cache)
- [x] After base search, map top-K hit file paths → module membership
- [x] If ≥60% of hits belong to the same module, prepend that module's `summary` as a `[module-context]` header block
- [x] Cap module summary injection at 500 chars (LOD-compressed if needed)
- [x] Test: broad query about a known module returns module summary + file chunks
- [x] Test: narrow query about a single function does NOT inject module summary

### W2c: Skeleton Context for Adjacent Nodes

**What:** When trace expansion adds neighboring files, instead of including their best chunk (which may be a random function), include a structural skeleton: function signatures, class definitions, exports — no implementation bodies.

**Why invisible:** This changes the *format* of trace-expanded content, not the user's workflow.

**Integration point:** In `get_context_with_trace_expansion()` where additional_chunks are built (lines 1439-1461), replace raw chunk content with a skeleton for trace-expanded nodes.

**Files to modify:**
- `src/codrag/core/index.py` — skeleton formatter for trace-expanded chunks
- `src/codrag/core/trace.py` — expose `get_node_skeleton(file_path)` using existing trace node metadata (the catalogue stage already extracts signatures)

**Checkboxes:**
- [x] Add `TraceIndex.get_file_skeleton(file_path) -> str` that returns signatures/exports from trace node metadata
- [x] In `get_context_with_trace_expansion()`, for trace-expanded chunks, use skeleton instead of raw chunk content
- [x] Skeleton format: `// @path/to/file.ts\nexport function foo(a: string): boolean\nexport class Bar { ... }\n`
- [x] Estimate 70-80% token reduction for adjacent nodes (full source → signatures only) — **measured 83.1% reduction (5.9:1 ratio)**
- [x] Test: trace-expanded neighbor shows signatures, not full implementation
- [x] Test: primary search hits still show full content (not skeletonized)

---

## W3: Session Continuity (Agent Remembers Across Sessions)

**Goal:** The AI agent's observations and decisions are automatically persisted and surfaced in future sessions. When code changes, linked observations are flagged stale. The user does nothing — the MCP tools handle everything.

### W3a: Observation Store

**What:** A new MCP tool `codrag_save_observation` that lets the agent write a note linked to a specific file or symbol in the trace graph. A companion tool `codrag_get_observations` retrieves relevant observations for a query.

**Why invisible:** The *agent* calls these tools automatically as part of its workflow. The user sees better continuity between sessions. The Dashboard shows observation count in the existing project health panel.

**Integration point:** New SQLite table in `codrag_settings.db` (we already use SQLite for the pipeline journal). MCP tools call the daemon API which reads/writes this table.

**Storage design:**
```sql
CREATE TABLE observations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    file_path TEXT,           -- linked file (optional)
    symbol_fqn TEXT,          -- linked symbol (optional, e.g. "UserService.validate")
    trace_node_id TEXT,       -- linked trace node (optional)
    content TEXT NOT NULL,    -- the observation text
    category TEXT DEFAULT 'note',  -- note | decision | bug | pattern | assumption
    created_at REAL NOT NULL,
    updated_at REAL,
    stale BOOLEAN DEFAULT 0,  -- set to 1 when linked code changes
    stale_reason TEXT          -- e.g. "file modified at 2026-02-23T10:00:00"
);
CREATE INDEX idx_obs_project ON observations(project_id);
CREATE INDEX idx_obs_file ON observations(project_id, file_path);
CREATE INDEX idx_obs_stale ON observations(project_id, stale);
```

**Files to modify:**
- `src/codrag/services/observation_store.py` — new file, SQLite CRUD
- `src/codrag/api/routers/observations.py` — new REST endpoints
- `src/codrag/mcp_tools.py` — add `codrag_save_observation` and `codrag_get_observations` tool definitions
- `src/codrag/mcp_server.py` — wire tool handlers to daemon API

**Checkboxes:**
- [x] Create `src/codrag/services/observation_store.py` with SQLite-backed ObservationStore class
  - [x] `save(project_id, content, file_path?, symbol_fqn?, category?) -> observation_id`
  - [x] `get_for_file(project_id, file_path) -> List[Observation]`
  - [x] `get_for_query(project_id, query, limit=5) -> List[Observation]` (FTS5 search over content)
  - [x] `mark_stale(project_id, file_path, reason)`
  - [x] `get_stats(project_id) -> {total, stale, by_category}`
- [x] Create `src/codrag/api/routers/observations.py` REST endpoints
  - [x] `POST /api/projects/{id}/observations` — save
  - [x] `GET /api/projects/{id}/observations` — list/search
  - [x] `GET /api/projects/{id}/observations/stats` — counts
- [x] Add MCP tool `codrag_save_observation` to `mcp_tools.py`
  - [x] Parameters: `content` (required), `file_path` (optional), `symbol` (optional), `category` (optional)
  - [x] Returns: observation ID + confirmation
- [x] Add MCP tool `codrag_get_observations` to `mcp_tools.py`
  - [x] Parameters: `query` (optional — FTS search), `file_path` (optional — filter by file)
  - [x] Returns: list of observations with stale flags
- [x] Wire both tools in `mcp_server.py` to daemon API calls
- [x] Test: save observation via MCP, retrieve via MCP
- [x] Test: observation appears when querying context for the linked file

### W3b: Automatic Staleness Detection

**What:** When the scope orchestrator detects file changes (it already does this for rebuild triggers), also mark any observations linked to those files as stale.

**Why invisible:** Happens automatically inside the existing `ScopeOrchestrator._build_worker()` flow. No new triggers, no new config.

**Integration point:** After a successful scope rebuild, call `observation_store.mark_stale(project_id, changed_files)`.

**Files to modify:**
- `src/codrag/services/scope_orchestrator.py` — in `_build_worker()`, after success
- `src/codrag/services/observation_store.py` — `mark_stale_batch(project_id, file_paths, reason)`

**Checkboxes:**
- [x] In `ScopeOrchestrator._build_worker()`, after successful build, collect `changed` paths
- [x] Call `observation_store.mark_stale_batch(project_id, changed_paths, reason="file modified")`
- [x] When `codrag_get_observations` returns stale observations, prepend `[STALE — file modified since this was recorded]` to the content
- [x] Test: save observation for file A, modify file A, trigger rebuild, verify observation is stale
- [x] Dashboard: project health endpoint includes observation stats (total / stale count)

### W3c: Auto-Inject Observations into Context

**What:** When the `/context` endpoint assembles context for a query, automatically append relevant non-stale observations as a `[session-memory]` section at the end.

**Why invisible:** Happens inside `get_context_with_trace_expansion()`. No new parameters.

**Files to modify:**
- `src/codrag/api/routers/projects.py` — in the `/context` handler, after context assembly
- `src/codrag/core/index.py` — optional: add observation injection as a post-processing step

**Checkboxes:**
- [x] After context assembly, query `observation_store.get_for_query(project_id, query, limit=3)`
- [x] If observations found, append a `\n\n---\n\n[session-memory]\n` section with observation text
- [x] Stale observations included but marked `[STALE]` so the agent knows to re-evaluate
- [x] Cap session-memory section at 500 chars
- [x] Test: save observation about auth, query about auth, verify observation appears in context
- [x] Test: observation does NOT appear for unrelated queries

---

## W4: Impact Awareness (What Breaks If I Change X?)

**Goal:** The agent can answer "what depends on this function?" and "what's the blast radius of changing this file?" using the existing trace graph. No new indexing, no new pipeline stages.

### W4a: Impact Graph MCP Tool

**What:** Enhance the existing `codrag_trace_neighbors` MCP tool (or add a dedicated `codrag_impact` tool) that traverses reverse dependencies (callers, importers) and returns a LOD-compressed summary of everything that depends on a target.

**Why invisible:** The agent calls this tool when it detects the user is asking about change impact. The trace graph already has the edges — we're just exposing a better traversal.

**Integration point:** New method on `TraceIndex` that does multi-hop reverse traversal with LOD compression. New MCP tool that calls this method via the daemon API.

**Files to modify:**
- `src/codrag/core/trace.py` — `TraceIndex.get_impact_graph(node_id, max_hops=2) -> ImpactResult`
- `src/codrag/api/routers/trace.py` — `GET /api/projects/{id}/trace/impact/{node_id}`
- `src/codrag/mcp_tools.py` — add `codrag_impact` tool definition
- `src/codrag/mcp_server.py` — wire tool handler

**Checkboxes:**
- [x] Add `TraceIndex.get_impact_graph(node_id, max_hops=2, max_nodes=30)` method
  - [x] BFS reverse traversal (follow `in_nodes` only — callers, importers)
  - [x] Return: `{target: node_info, dependents: [{path, kind, distance, signature}], total_dependents: int}`
  - [x] LOD compression: distance=1 nodes get full signature, distance=2 get file path + name only
- [x] Add `GET /api/projects/{id}/trace/impact/{node_id}` endpoint
- [x] Add MCP tool `codrag_impact` to `mcp_tools.py`
  - [x] Parameters: `file_path` or `symbol` (required), `max_hops` (optional, default 2)
  - [x] Returns: formatted impact summary with LOD-compressed dependents
- [x] Wire in `mcp_server.py`
- [x] Test: function with known callers returns correct impact graph
- [x] Test: max_hops=1 returns only direct dependents
- [x] Test: file with no dependents returns empty impact graph

---

## Implementation Priority & Sprint Plan

### Sprint 1: Foundation (Highest Impact, Lowest Risk) ✅
*Focus: Better context from existing data. Zero new infrastructure.*

- [x] **W2a: Intent-aware search** — keyword classifier + parameter adjustment
- [x] **W1b/SR-3: Weighted trace expansion** — edge kind weights
- [x] **W1b/SR-9: Graph-augmented retrieval boost** — in-degree boost for base hits
- [x] **W2b: Module summary injection** — prepend module context for broad queries
- [x] Verified context quality: W2b module injection, W2c skeleton (83% reduction), intent detection, edge weighting all connected
- [x] All tests pass ✅

### Sprint 2: Skeleton + Impact (Big Token Savings) ✅
*Focus: Dramatically reduce tokens for adjacent context. Add blast-radius tool.*

- [x] **W2c: Skeleton context for adjacent nodes** — signatures only for trace-expanded chunks
- [x] **W4a: Impact graph MCP tool** — reverse-dependency traversal
- [x] Benchmark: skeleton compression measured at 83.1% reduction (6,356→1,071 chars across 3 test files)
- [x] All tests pass ✅

### Sprint 3: Session Memory (Cross-Session Continuity) ✅
*Focus: Observations, staleness, auto-injection.*

- [x] **W3a: Observation store** — SQLite table, REST endpoints, MCP tools
- [x] **W3b: Staleness detection** — auto-mark observations when files change
- [x] **W3c: Auto-inject into context** — append relevant observations to `/context` response
- [x] Test full cycle: save → modify file → stale flag → re-query
- [x] All tests pass ✅

### Sprint 4: LSP Integration + Polish (in progress)
*Focus: External edge sources, barrel files, edge provenance.*

- [x] **W1a: LSP edge ingestion** — REST endpoint, TraceIndex merge, validation + dedup
- [ ] **W1b/TG-6: Barrel file resolution** — TS/JS `index.ts` forwarding edges (Rust parser change)
- [x] **Edge provenance** — `origin: "lsp"` field added to LSP edges
- [x] All tests pass ✅

---

## What We Are NOT Doing (Complexity Budget)

These would add user-facing complexity and are explicitly deferred:

| Rejected Idea | Why |
|---|---|
| New "observation" panel in dashboard | Adds UI surface. Observations are shown in existing project health stats instead. |
| User-configurable intent detection | Over-engineering. Keyword matching is sufficient. If we need LLM-based intent, it can replace keywords transparently later. |
| Git-native epistemic checkpoints (`git notes`) | Cool idea but adds git workflow complexity. Revisit for enterprise/team tier only. |
| Dedicated Graph DB backend | Over-engineering for local-first. SQLite + in-memory graph handles our scale. Revisit for enterprise container only. |
| Cross-encoder re-ranking | Requires a separate model. Revisit when we have benchmarks showing RRF fusion is insufficient. |
| Structure-aware chunking (SR-7) | Major refactor of the chunking pipeline. The skeleton approach (W2c) achieves similar token savings with much less risk. |

---

## Success Metrics

| Metric | Current | Target |
|---|---|---|
| Tokens per context query (TEST3 repo) | ~18,000 | ~6,000 (skeleton + module injection) |
| Trace-expanded context relevance | Unweighted edges | Weighted by kind + in-degree |
| Session 2 re-exploration overhead | 100% re-read | <30% (observations surface prior context) |
| "What breaks if I change X?" | Not possible | Available via `codrag_impact` MCP tool |
| User-facing config changes | — | **Zero** |

---

*Created: 2026-02-23*
*Phase 38 completion required before starting Sprint 1.*
