# Phase 34 — Context-First Architecture

> **Status**: In progress. Phase 34a complete (A2 scope boost, B1 trace-always-on, D1+D3 tool description). Phase 34b complete (C1-C4 ambient context assembly). Supersedes the original "query optimization" framing after fundamental rethink of how users interact with CoDRAG via MCP.

---

## 1. The Fundamental Reframe

### What we were thinking (wrong)

The original Phase 34 framed CoDRAG as a **search tool** that needed better query handling. The focus was: "the AI model sends a bad query → embedding gets diffuse → results are unfocused → let's preprocess the query."

This treats the `query` parameter as the primary input and optimizes around it.

### What users actually do

Users tag `@codrag` and expect it to **give them focused context**. They don't think of CoDRAG as a search engine. They think of it as a context layer that:

1. **Knows what they're working on** — via file tree selections (included paths)
2. **Understands code structure** — via the trace graph (imports, calls, inheritance)
3. **Has macro-level orientation** — via atlas segments and module synthesis
4. **Respects their priorities** — via path weights

The query is a **refinement signal**, not the primary input. The user's pre-configured project state (file selections, trace graph, atlas, weights) is where the real value lives.

### The actual contract

```
User expectation:
  "I tagged @codrag. It should already know my project structure,
   what files I care about, and how my code connects. Give me the
   context I need — focused and structural, not just keyword matches."

What CoDRAG does today:
  "Give me a search query and I'll run it against the vector index.
   Everything else (trace, atlas, file selections) is opt-in or
   build-time only."
```

**The gap is not query quality. The gap is that CoDRAG ignores most of what it knows at query time.**

---

## 2. Signal Audit — What CoDRAG Knows vs. What It Uses

### Signals available at query time

| Signal | Where it lives | Used at query time? | How it's used |
|:-------|:---------------|:--------------------|:--------------|
| **Query embedding** | From AI model via MCP | ✅ Yes | Primary retrieval signal — cosine similarity against chunk embeddings |
| **Atlas routing** | `atlas_routing.json` + `atlas_routing_embeddings.npy` | ✅ Yes | Pre-search segment selection, +0.12 score boost for files in selected segments |
| **Knowledge routing** | `knowledge_documents.json` | ✅ Yes | Boosts files whose enriched descriptions match query |
| **Path weights** | `repo_policy.json` / manifest config | ✅ Yes | Score multiplier per directory (e.g., `src/core/=1.5`) |
| **Role weights** | `repo_policy.json` | ✅ Yes | Score multiplier per file role (code/docs/test/config) |
| **Intent classification** | Computed from query tokens | ✅ Yes | Adjusts role multipliers based on detected intent |
| **Keyword/FTS boosts** | Computed at search time | ✅ Yes | Exact-match bonuses |
| **Adaptive-K** | Computed post-search | ✅ Yes | Trims low-quality tail results |
| **MMR reranking** | Computed post-search | ✅ Yes | Diversity filter |
| **Included paths** (file tree selections) | `project.config["included_paths"]` in SQLite | ❌ **Build-time only** | Scopes what gets indexed, but **invisible at query time** |
| **Trace graph** | `trace_nodes.jsonl`, `trace_edges.jsonl` | ⚠️ Opt-in only | `trace_expand=false` by default. AI model must explicitly request it. |
| **Pinned files** | localStorage / dashboard state | ❌ **Not accessible** | Dashboard-only concept, not exposed to MCP |
| **Module synthesis** | `trace_modules.jsonl` | ❌ **Not used at query time** | Feeds into atlas and enrichment, but not directly into retrieval |
| **Epistemic scores** | `trace_enrichments.jsonl` | ❌ **Not used at query time** | Available but not factored into search ranking |
| **Augmentation summaries** | `trace_augmented.jsonl` | ❌ **Indirect only** | Fed into KnowledgeIndex at build time; not queried directly |

### The critical gaps

1. **Included paths are build-time only.** A user who carefully selects `src/auth/` and `src/middleware/` in the file tree gets zero benefit at query time. Those selections only scope what gets indexed — they don't bias retrieval toward those areas. If the index also contains `src/database/`, `src/utils/`, `tests/`, etc., the query has to compete against all of them.

2. **Trace expansion is off by default.** The trace graph is CoDRAG's most differentiating feature — it knows that `auth_middleware.py` imports `token_validator.py` which calls `jwt_decode()`. But `trace_expand=false` by default, and the AI model tool description doesn't even mention it prominently. Most calls will never use it.

3. **No ambient context mode.** There's no way to call `codrag` and say "give me context for what I'm working on." The `query` parameter is **required**. But the user's file selections, recent trace activity, and project structure already define their working context — CoDRAG should be able to assemble context from those signals alone.

4. **Pinned files are invisible to MCP.** The dashboard has a "pin file" feature that represents "I'm actively working on this." The MCP layer has no access to this signal.

---

## 3. Proposed Architecture: Context-First Defaults

### Design principle

**CoDRAG should provide the best possible context with zero configuration at query time.** Every signal CoDRAG has (file selections, trace graph, atlas, path weights) should be leveraged **automatically** when `codrag` is called. The query refines what comes back; it doesn't define it.

### New default behavior for `codrag` tool

```
When codrag is called:

1. ALWAYS load included_paths from project config
   → Use as a scope bias: boost files under selected paths
   → If no query is provided, use included_paths as the primary context source

2. ALWAYS enable trace expansion (when trace exists)
   → Follow structural edges from top results
   → This is what makes CoDRAG different from grep+embeddings

3. ALWAYS run atlas routing (when routing data exists)
   → Already happening — no change needed

4. ALWAYS run knowledge routing (when knowledge index exists)
   → Already happening — no change needed

5. Query becomes OPTIONAL refinement
   → With query: semantic search + all the above signals
   → Without query: assemble context from included_paths + trace hubs + atlas
```

### The three context modes

#### Mode 1: Focus Context (query provided)
This is the current behavior, enhanced with automatic signal integration:

```
Input:  query="How does token refresh work?"
Signals used:
  - Query embedding (primary retrieval)
  - included_paths → scope boost (NEW — files in selected areas get +boost)
  - trace_expand=true (NEW DEFAULT — follow imports/calls from top results)
  - Atlas routing (existing)
  - Knowledge routing (existing)
  - Path weights, role weights, intent (existing)
Output: Focused chunks about token refresh, with structural neighbors
```

#### Mode 2: Ambient Context (no query)
New capability — assemble context purely from project state:

```
Input:  (no query)
Signals used:
  - included_paths → identify focus areas
  - Trace graph → find hub files in those areas (highest in-degree)
  - Module synthesis → identify which modules the selected paths belong to
  - Atlas segments → provide macro-level orientation
  - Path weights → prioritize high-weight areas
Output: Structural overview of the user's working context
        "Here's what's in your focus area and how it connects"
```

#### Mode 3: Macro Context (architectural overview)
Already partially exists via `codrag_atlas` and `hi_codrag`, but should be available as a mode of `codrag`:

```
Input:  query="project overview" or explicit macro=true flag
Signals used:
  - Atlas narrative
  - Module synthesis
  - Trace graph topology (hub files, cross-module edges)
  - LOD compression at high levels (signatures + names only)
Output: Architectural orientation — module map, key entry points,
        cross-cutting concerns
```

---

## 4. Research Tracks

### Track A — Scope Boost (included_paths at query time)

**Cost: Low. Highest immediate impact.**

The user's file tree selections already exist in `project.config["included_paths"]`. They need to become a query-time signal.

**Options:**

- [ ] **A1 — Path-based score boost**: At search time, load `included_paths` from project config. For each result, check if its `source_path` falls under any included path. If so, apply a score boost (similar to `segment_boost` from atlas routing). This is the simplest approach — 10-20 lines in `context_project()`.

- [x] **A2 — Included-paths as segment_file_paths**: Reuse the existing `segment_file_paths` mechanism. Convert `included_paths` to a set of file paths, union with atlas routing results, and pass to `search()`. Files in the set get the existing +0.12 boost. *(Implemented: scope boost block in `context_project()` loads `included_paths`, resolves directory prefixes against indexed docs, unions into `_segment_file_paths`)*

- [ ] **A3 — Dual-pool retrieval**: Run search twice — once scoped to `included_paths` files only, once against the full index. Interleave results. This guarantees representation from the user's focus area while still finding globally relevant chunks.

- [ ] **A4 — Included-paths as hard scope**: When `included_paths` is non-empty, ONLY return results from those paths (no global fallback). This is aggressive but matches the user's intent — "I selected these files because they're what I care about."

**Recommendation:** Start with A2 (reuse existing mechanism). Measure. If results from outside selected paths are rarely useful, move to A4.

### Track B — Trace-Always-On

**Cost: Low. Changes a default.**

- [x] **B1 — Default `trace_expand=true`**: Change the default in `ContextRequest` and in the MCP tool schema. When trace exists and is loaded, always follow structural edges. When trace doesn't exist, gracefully fall back. *(Implemented: `ContextRequest.trace_expand=True`, `mcp_tools.py` schema default=True, `mcp_server.py` default=True, feature gate catch for free tier graceful degradation)*

- [ ] **B2 — Increase trace budget**: Current `trace_max_chars=2000` is conservative. With LOD compression working, we can afford `trace_max_chars=4000-6000` because trace-expanded chunks can be served at LOD 2 (signatures + docstrings) or LOD 4 (names + types).

- [ ] **B3 — Trace-aware result ordering**: Instead of appending trace neighbors after search results, interleave them based on structural importance (in-degree, module hub status). A trace neighbor that's a hub file should rank higher than a marginal search hit.

### Track C — Ambient Context Assembly

**Cost: Medium. New capability.**

Build the "no query" context mode:

- [x] **C1 — Hub-file extraction**: Given `included_paths`, walk the trace graph to find hub files (highest in-degree within the selected scope). These are the "most important files in the user's focus area." *(Implemented: `TraceIndex.get_hub_files()` reads edge files directly, scopes by path prefix, returns top-k by in-degree)*

- [x] **C2 — Module-aware context**: Map `included_paths` to modules (from `trace_modules.jsonl`). For each module in scope, include: module description, key files, boundary edges to other modules. This gives macro-level context automatically. *(Implemented: `_assemble_ambient_context()` loads modules, matches member_files against scope, produces markdown header)*

- [x] **C3 — LOD-stratified assembly**: Use LOD compression to pack more files into the context budget: *(Implemented: hubs=LOD 0 at 70% budget, neighbors=LOD 2 via `LODExtractor.extract()` at 30% budget, truncated fallback)*
  - Hub files → LOD 0 (full source)
  - Direct neighbors → LOD 2 (signatures + docstrings)
  - Transitive neighbors → LOD 4 (names + types)
  - Out-of-scope but connected → LOD 5 (file path + summary)

- [x] **C4 — Make `query` optional in tool schema**: Remove `query` from `required` in the `codrag` tool definition. When no query is provided, assemble ambient context from project state. Update tool description to communicate this capability. *(Implemented: `ContextRequest.query=""`, `required: []` in schema, `context_project()` routes to `_assemble_ambient_context()` on empty query)*

### Track D — Tool Description Rewrite

**Cost: Zero code changes. Reframes how AI models use CoDRAG.**

The current tool description says:
```
"Get assembled context for LLM prompt injection. Returns formatted chunks
optimized for token efficiency."
```

This tells the AI model "I'm a search endpoint." It should say:

- [x] **D1 — Context-first description**: Rewrite to communicate that CoDRAG is a context provider, not a search tool:
  ```
  "Get codebase context powered by structural analysis. CoDRAG uses
  your project's code graph, selected focus areas, and semantic search
  to assemble the most relevant context. Provide a query to focus on
  a specific topic, or call without a query to get context for the
  user's current working area. Trace expansion and structural routing
  are enabled automatically."
  ```

- [ ] **D2 — Deprecate search-oriented params from default use**: Move `k`, `min_score`, `mmr_lambda` etc. to a secondary "advanced" section of the schema or give them smart defaults that rarely need override.

- [x] **D3 — Guide multi-call behavior**: Added to description: `"For complex requests spanning multiple topics, call this tool once per topic for best results."` *(Included in D1 rewrite)*

### Track E — Compression for Volume

**Cost: Builds on existing LOD infrastructure.**

As compression improves, CoDRAG can provide MORE context without blowing token budgets:

- [ ] **E1 — Auto-LOD in default context**: Instead of serving everything at LOD 0 (full source), automatically assign LOD levels based on relevance score. Top hits get full source; lower-ranked hits get signatures only. This is already built (`assign_lod()`) but not wired into the default (non-`lod` compression) path.

- [ ] **E2 — Increase `max_chars` default**: Current default is 6000 chars (~1500 tokens). With LOD compression, we could serve 15000-20000 chars of LOD-compressed content for the same effective token cost. The information density per token goes up dramatically.

- [ ] **E3 — Budget-aware assembly**: Instead of a fixed `max_chars`, let CoDRAG decide the budget based on what it knows: lots of relevant files → more chars with aggressive LOD; few relevant files → full source at lower char count.

### Track F — Query Preprocessing (Retained)

**Cost: Moderate. Still valuable as a refinement layer.**

The original query optimization research remains valid as a secondary improvement. Even with context-first defaults, a better query embedding helps:

- [ ] **F1 — Truncation**: Cap query at 300 chars to prevent diffuse embeddings.
- [ ] **F2 — Stop-word removal**: Strip conversational filler before embedding.
- [ ] **F3 — Entity extraction**: Pull out code identifiers (camelCase, snake_case, file paths) for keyword boost.
- [ ] **F4 — Query decomposition**: Split multi-intent queries into sub-queries.

**These are all lower priority than Tracks A-E.** The best query preprocessing is irrelevant if CoDRAG isn't leveraging its structural signals.

---

## 5. Current vs. Proposed Context Flow

### Today

```
AI model calls codrag(query="token refresh auth")
  │
  ├─ embed query → cosine search → top-K chunks
  ├─ atlas routing (if available) → score boost
  ├─ knowledge routing (if available) → score boost
  ├─ path weights → score multiplier
  ├─ role weights + intent → score multiplier
  ├─ keyword/FTS boost
  ├─ adaptive-K trim
  ├─ MMR diversity
  │
  └─ Return: 5 chunks, ~6000 chars

  NOT USED: included_paths, trace graph (unless explicitly requested),
            pinned files, module data, epistemic scores
```

### Proposed

```
AI model calls codrag(query="token refresh auth")   ← query is optional
  │
  │  ── Pre-retrieval (NEW) ──────────────────────
  ├─ Load included_paths → scope boost set
  ├─ Atlas routing → segment boost set
  ├─ Knowledge routing → file boost set
  ├─ Union all boost sets
  │
  │  ── Retrieval ────────────────────────────────
  ├─ If query: embed → cosine search (boosted by all signals)
  ├─ If no query: hub files from included_paths + trace topology
  │
  │  ── Post-retrieval (ENHANCED) ────────────────
  ├─ Trace expansion (ALWAYS ON when trace exists)
  │    └─ Follow imports/calls from top results
  │    └─ LOD compress neighbors (sigs+docs, not full source)
  ├─ Path weights → score multiplier
  ├─ Role weights + intent → score multiplier
  ├─ Keyword/FTS boost
  ├─ Adaptive-K trim
  ├─ MMR diversity
  │
  │  ── Assembly (ENHANCED) ──────────────────────
  ├─ Auto-LOD: top results=LOD 0, neighbors=LOD 2, periphery=LOD 4
  ├─ Higher max_chars budget (compressed content packs more info)
  │
  └─ Return: 8-15 chunks, ~12000 chars (LOD-compressed ≈ 3000 tokens)

  USED: included_paths ✅, trace graph ✅, pinned files (future),
        module data (via knowledge routing) ✅, atlas ✅
```

---

## 6. Impact Assessment

### Why this matters more than query optimization

1. **Query optimization is a band-aid.** Even a perfect query can only retrieve what cosine similarity finds. Structural signals (trace, file selections, modules) find code that's *architecturally relevant* even when the embedding doesn't surface it.

2. **Users already told us what they care about.** When a user selects files in the tree, sets path weights, and pins files — that's explicit signal. Ignoring it at query time and relying solely on a query string from an AI model is throwing away high-quality human input.

3. **Trace expansion is CoDRAG's moat.** Every RAG tool does vector search. CoDRAG knows that `middleware.py` calls `validator.py` which imports `crypto.py`. Turning this on by default is the single highest-leverage change.

4. **Compression unlocks volume.** With LOD compression, we can serve 3-5x more content at the same token cost. But this only matters if we're selecting the RIGHT content. Context-first signals ensure we're packing the budget with architecturally relevant code, not just the top-5 cosine hits.

5. **Zero-query mode is a differentiator.** No other MCP tool can give you "context for what you're working on" without a search query. This is possible because CoDRAG has the trace graph and file selections — structural data that other tools don't have.

---

## 7. Proposed Implementation Order

```
Phase 34a — Scope boost (1 day)
  A2: Wire included_paths into search as segment_file_paths boost
  B1: Default trace_expand=true
  Measure: Same ground-truth queries, compare R@1/MRR with and without scope boost

Phase 34b — Tool description rewrite (0.5 days)
  D1: Context-first tool description
  D3: Multi-call guidance
  Test with Opus, Sonnet, GPT-4o: does the new description change behavior?

Phase 34c — Ambient context (2-3 days)
  C4: Make query optional in tool schema
  C1: Hub-file extraction from included_paths + trace
  C2: Module-aware context assembly
  C3: LOD-stratified assembly for ambient mode

Phase 34d — Compression integration (1-2 days)
  E1: Auto-LOD in default context path
  E2: Increase max_chars default for LOD-compressed output
  B2: Increase trace budget with LOD compression

Phase 34e — Query preprocessing (1-2 days, lower priority)
  F1-F4: Truncation, stop-words, entity extraction, decomposition
  Only if Phase 34a measurement shows query quality still matters
  after structural signals are integrated

Phase 34f — Validate (1 day)
  Benchmark: full pipeline with all signals vs. current query-only pipeline
  Real-world: capture MCP calls, replay, compare context quality
```

**Total estimate**: 6-10 days. But Phase 34a alone (1 day) delivers the majority of the value.

---

## 8. Dependencies

| Dependency | Phase | Status | Impact |
|:-----------|:------|:-------|:-------|
| LOD Extractor | Phase 31 | ✅ Complete | Required for auto-LOD assembly and trace compression |
| Atlas routing | Phase 29B | ✅ Complete | Already integrated, no changes needed |
| Knowledge routing | Phase 29C | ✅ Complete | Already integrated, no changes needed |
| Trace graph | Phase 22 | ✅ Complete | Required for trace-always-on and hub extraction |
| Included paths API | Phase 24 | ✅ Complete | Endpoints exist, just need query-time wiring |
| v2-moe context fix | Phase 33, P1 | 🔴 Open | Needed for embedding benchmarks but NOT blocking the architectural changes |

---

## 9. Files Likely Modified

| File | Expected Changes |
|:-----|:-----------------|
| `src/codrag/api/routers/projects.py` | Load `included_paths` in `context_project()`, convert to boost set, default `trace_expand=true` |
| `src/codrag/mcp_tools.py` | Rewrite `codrag` tool description, make `query` optional, default `trace_expand=true` |
| `src/codrag/mcp_server.py` | Handle missing query (ambient mode), always-on trace expansion |
| `src/codrag/core/index.py` | Accept `scope_paths` boost set in `search()` alongside `segment_file_paths` |
| `src/codrag/core/index.py` | Auto-LOD assignment in `get_context()` / `get_context_structured()` |
| `src/codrag/mcp_direct.py` | Mirror changes for direct mode |
| `scripts/eval_real_repos.py` | Add scope-boost and ambient-context test cases |

---

## 10. Open Questions

1. **How aggressive should scope boost be?** If a user selects `src/auth/`, should files in that directory get +0.12 (same as atlas), +0.25 (stronger), or should scope be a hard filter (only return from selected paths)? Needs empirical testing.

2. **Should ambient context include the atlas narrative?** When no query is provided, should the response start with the atlas overview ("This project has 4 modules: ...") or just jump to structural code context? The atlas narrative costs tokens but provides orientation.

3. **How do we handle empty included_paths?** If the user hasn't selected any files in the tree, ambient mode has no scope signal. Options: (a) fall back to full-index hub files, (b) return the atlas overview, (c) return an error asking them to select files. Probably (a) — graceful degradation.

4. **Should trace expansion follow all edge types?** Current trace expansion follows `imports` edges. Should it also follow `calls`, `inherits`, `references`? Following more edge types gives richer structural context but may also bring in noise.

5. **Token budget negotiation.** With LOD compression, we can serve much more content. But different AI models have different context windows and different sensitivity to context volume. Should CoDRAG try to detect the caller and adjust? Or should we provide a generous default and let the AI model set `max_chars` if it wants less?

6. **What does "focused context" mean without a query?** We need to define what makes ambient context *good*. Candidate metrics: (a) covers all included paths, (b) includes structural connections between them, (c) prioritizes hub files over leaf files, (d) fits in a reasonable token budget. But we need real-world feedback to tune.
