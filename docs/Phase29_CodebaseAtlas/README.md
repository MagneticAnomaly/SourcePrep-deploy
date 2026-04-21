# Phase 29: Codebase Atlas

> A hierarchical routing index over the trace graph. The Atlas tells CoDRAG *where* to search — not the AI *what* was found. Segmented atlases scope retrieval to the relevant subsystem, improving precision without adding token overhead to AI queries.

---

## Problem

For small repos (<150 files), CoDRAG's search works well: vector search covers the full index, trace expansion walks the full graph, results are precise. For any repo with identifiable subsystems — whether a monorepo or a large single-service app — a fundamental retrieval problem emerges:

**Every query searches the entire trace graph blindly.** A query about authentication walks edges into the payments module, the UI layer, the test suite. The retrieval system has no concept of "this query is about the auth subsystem" before it starts searching.

The result: lower precision, noisy trace expansion, and missed intra-subsystem connections. The trace graph contains the structural knowledge needed to route queries — but that knowledge isn't consulted at retrieval time.

The root problem is architectural: the trace graph IS the structural RAG, but without a routing layer above it, it's searched wholesale for every query.

## Solution: Three-Layer Retrieval Hierarchy

The Atlas creates a routing layer above the trace graph, making retrieval hierarchical:

```
Layer 1 — Atlas Segments     ← "Which subsystem is relevant to this query?"
          (routing index)       Segment descriptors pre-embedded at build time.
                                Query embedded at search time → top-K segments selected.

Layer 2 — Trace Graph        ← "Which files/symbols in that subsystem?"
          (structural RAG)      Walk trace edges scoped to selected segments.
                                Hub files within segments are preferred entry points.

Layer 3 — Vector Index       ← "Which specific chunks?"
          (semantic RAG)        Full search with score boosting for files
                                within the selected segments.
```

The Atlas is **input to the retrieval pipeline**, not output context for the AI. The AI receives better-targeted results — not atlas text.

### Query-Time Routing Flow

```
Query: "How does authentication connect to the session store?"

Step 1 — Segment routing (pre-retrieval)
  Embed query → cosine similarity against pre-embedded segment descriptors
  Selected: "auth-middleware" (0.87), "data-persistence" (0.71)

Step 2 — Scoped trace walk
  Enter trace graph from hub files within selected segments.
  Walk edges within + across selected segments preferentially.

Step 3 — Boosted vector search
  Full search, but +score boost for files in selected segments.

Step 4 — Results assembled (what the AI actually receives)
  [Result 1] auth/middleware.py  score=0.91  ← scoped by atlas, not stated
  [Result 2] session/store.py    score=0.88
  [Result 3] auth/decorators.py  score=0.82
  [Trace 1]  session/backend.py  score=0.74  ← neighbor in selected segment

  Optional: minimal label "Subsystems: auth-middleware, data-persistence"
            (~8 tokens, not 375)
```

The improvement is structural: the AI gets results that are more relevant because retrieval was routed. No orientation paragraph prepended.

---

## Staleness & Regeneration

The Atlas is expensive to generate (one reasoning LLM call) but should rarely change. Three triggers:

### 1. Module Fingerprint Change
When cluster synthesis (Pass 3) produces different modules — new clusters, merged clusters, or significantly changed summaries — the Atlas is stale.

**Implementation**: Hash the sorted list of `(module_id, member_file_count, summary_hash)` tuples. Compare against stored fingerprint.

### 2. Core Infrastructure Change
When "hub files" (highest fan-in in the trace graph) are modified, the Atlas may need updating even if modules haven't been resynthesized yet.

**Implementation**: Identify top-N files by `node_degree()` (in-degree). Store their content hashes in the Atlas metadata. If any change, mark stale.

### 3. Significant Growth/Shrinkage
When the file count changes by more than 20% since last Atlas generation.

**Implementation**: Store `file_count` in Atlas metadata. Compare against current manifest.

### Regeneration Strategy
- **Never block queries.** If the Atlas is stale, serve the old one. Regenerate in background.
- **Regeneration happens after pipeline completion** — the Atlas is the capstone of the enrichment pipeline.
- **Falls back gracefully**: If no Atlas exists yet (first index), queries just get the normal 5 results.

---

## Implementation Plan

### Phase A: Atlas Generator (`src/codrag/core/atlas.py`)

```python
class CodebaseAtlas:
    """Generates and caches a single-document codebase map."""
    
    def __init__(self, index_dir: Path, llm: LLMClient):
        self.index_dir = index_dir
        self.llm = llm
        self.atlas_path = index_dir / "atlas.json"
    
    def generate(self) -> AtlasDocument:
        """One reasoning LLM call to synthesize the Atlas."""
        modules = self._load_modules()      # trace_modules.jsonl
        epistemic = self._load_epistemic()   # trace_epistemic.jsonl  
        graph_stats = self._load_graph_stats()  # node/edge counts
        
        prompt = ATLAS_PROMPT.format(
            module_summaries=self._format_modules(modules),
            architecture_layers=self._summarize_layers(epistemic),
            graph_stats=self._format_stats(graph_stats),
            hub_files=self._identify_hubs(graph_stats),
        )
        
        text, tokens = self.llm.generate(prompt, system=ATLAS_SYSTEM, num_predict=4096)
        return self._parse_and_cache(text)
    
    def load(self) -> Optional[AtlasDocument]:
        """Load cached Atlas from disk."""
        ...
    
    def is_stale(self) -> bool:
        """Check if Atlas needs regeneration."""
        ...
    
    def fingerprint(self) -> str:
        """Current fingerprint for staleness comparison."""
        ...
```

### Phase B: Context Integration

Wire into `get_context_structured()` and `get_context_with_trace_expansion()`:

```python
# In index.py or server.py context assembly
def _prepend_atlas(self, context_result: dict, max_atlas_chars: int = 1500) -> dict:
    atlas = self._atlas.load()
    if atlas and atlas.content:
        atlas_block = f"[ATLAS | Codebase Map]\n{atlas.content[:max_atlas_chars]}"
        context_result["context"] = atlas_block + "\n\n---\n\n" + context_result["context"]
        context_result["total_chars"] += len(atlas_block)
        context_result["has_atlas"] = True
    return context_result
```

### Phase C: Pipeline Integration

Atlas generation becomes Pass 3.5 — runs after cluster synthesis, before knowledge embedding:

```
Pass 0:   Rust Structural Trace         (~100ms)
Pass 0.5: Rust Validates LLM Hypotheses (~5ms)
Pass 1:   3b Fast Catalogue             (~10min)
Pass 2:   14b Epistemic Enrichment      (~60min)
Pass 3:   14b Cluster Synthesis          (~15min)
Pass 3.5: Atlas Generation (NEW)         (~30s)  ← ONE reasoning call
Pass 4+:  Continuous Deepening           (converges)
```

### Phase D: MCP/API Exposure

- `codrag_context` tool gets `include_atlas` param (default: true)
- `GET /projects/{id}/atlas` endpoint for direct access
- `POST /projects/{id}/atlas/regenerate` for manual trigger

---

## The Prompt

The Atlas prompt is the key design element. It receives **pre-computed summaries**, not raw code. This means the input is already condensed — a 500-file project might produce 20 module summaries totaling ~5000 chars.

```
ATLAS_SYSTEM = """You are synthesizing a single-page architectural overview 
of a software project. You have access to pre-computed module summaries and 
file-level metadata. Your output will be injected into every AI coding 
assistant query as orientation context. Be dense, precise, and structural. 
No filler. Every sentence must convey architectural information."""

ATLAS_PROMPT = """Generate a concise codebase map (800-1500 words) for this project.

## Module Summaries (pre-computed)
{module_summaries}

## Architecture Layer Distribution
{architecture_layers}

## Graph Statistics  
{graph_stats}

## Hub Files (most-connected)
{hub_files}

Your output MUST include:
1. One-line project identity (what is this?)
2. Tech stack and languages
3. Architecture overview (how do the major pieces connect?)
4. Key subsystems with entry points
5. Data/control flow (what calls what?)
6. Cross-cutting concerns (shared deps, patterns)
7. Known risks or debt (if any modules flagged issues)

Format as dense prose with bullet points for subsystems. 
No headers, no markdown formatting — this will be injected as plain context.
Optimize for an AI coding assistant that needs orientation before answering 
a specific code question."""
```

---

## Effort & Impact

| Aspect | Estimate |
|--------|----------|
| `atlas.py` core class | ~200 LOC, 2-3 hours |
| Context integration | ~50 LOC, 1 hour |
| Pipeline wiring | ~30 LOC, 1 hour |
| API endpoints | ~40 LOC, 1 hour |
| MCP param | ~10 LOC, 30 min |
| Tests | ~150 LOC, 2 hours |
| **Total** | **~480 LOC, ~8 hours** |

**Impact**: HIGH. This is potentially the single highest-impact feature for context quality:
- Every query is routed to the relevant subsystem before retrieval begins
- Trace expansion follows edges within the relevant subsystem first — more coherent neighbors
- Vector search scores boosted for files in the selected segment — less cross-subsystem noise
- Zero additional AI context cost (routing is internal; AI sees results, not atlas text)
- Amortized cost: segment descriptors built once, routing lookup is sub-millisecond
- Leverages 100% of existing enrichment infrastructure
- No new models, no new dependencies

---

## Open Questions

1. **Routing boost magnitude**: How much score boost for files in selected segments? Too small = no routing effect. Too large = always returns segment files even when query barely matches. Needs empirical tuning.
2. **Segment threshold**: What score threshold distinguishes "select this segment" from "skip"? Absolute threshold vs top-K vs score gap heuristic (same adaptive-K logic as search).
3. **Cross-subsystem queries**: When a query legitimately spans multiple subsystems (e.g., "how does the API serialize trace results for the dashboard?"), we want all 3 segments selected. Should routing be top-K or threshold-based to handle this gracefully?
4. **Free tier**: Can Free users get routing? The segment descriptors can be generated from graph stats alone (no LLM) using the structural-only path — giving basic routing without requiring an LLM.
5. **codrag_atlas tool**: Should the AI-facing `codrag_atlas` tool return full LLM-generated narrative (for human understanding) or the routing descriptor (compact, machine-readable)? Likely two separate response modes.

---

## Relationship to Existing Features

| Feature | Role | Atlas Interaction |
|---------|------|-------------------|
| Adaptive K | Controls local result count | Routing improves result homogeneity → cleaner score gaps → better K |
| Trace Expansion | Adds graph neighbors | Routing scopes trace walk start nodes to relevant segment hubs |
| MMR Diversity | Deduplicates local results | Routing narrows the candidate set; MMR still deduplicates within it |
| Context Compression | Compresses context | Unaffected — atlas is not in AI context, compression applies to results only |
| Primer Chunks | Always-included chunks | Unaffected — primer chunks bypass routing (they're always included) |
| Path Weights | Per-folder scoring | Segment boundaries could be informed by path weights in future |
| Module Summaries | Per-cluster summaries | Atlas **consumes** module summaries to build `COVERS` vocabulary |

The Atlas is the natural capstone of the enrichment pipeline. Passes 0-3 compute per-node and per-cluster understanding. The Atlas distills all of it into one document.

---

## Deep Design Decisions

### 1. Why This Is the Highest-Impact Feature

The trace graph is CoDRAG's structural RAG — it knows which files call which, which modules depend on which, which symbols are defined where. But without a routing layer above it, every query searches the whole graph. For a 500-file repo with 8 subsystems, that means 7/8 of the trace walk is noise by construction.

The Atlas is the routing layer. Segment routing narrows the trace walk to the 1-2 subsystems most relevant to the query before a single edge is traversed. The precision improvement compounds:

- **Trace expansion**: edges within the relevant subsystem are followed first → more coherent neighbors
- **Vector search**: files from the relevant subsystem score higher → less noise from similar-sounding but unrelated files
- **Adaptive K**: with higher-precision results, the score gap is cleaner → better K selection

**Cost-benefit**: One reasoning LLM call per segment (~15-25s each, amortized across thousands of queries). Segment descriptors are pre-embedded once at build time. Query routing at search time is a lightweight cosine similarity lookup — sub-millisecond.

This is the cleanest architectural addition: it improves every other retrieval feature without touching any of them.

### 2. Atlas Content Strategy

Each atlas segment is a **routing descriptor**, not a documentation artifact. Its primary consumer is CoDRAG's own retrieval system, not the AI tool.

**What a segment descriptor must contain:**
- `SEGMENT`: directory path + name
- `COVERS`: the concepts/domains this segment handles (used for semantic routing)
- `KEY FILES`: hub files that are good trace walk entry points
- `BOUNDARIES`: what this segment hands off to (for cross-segment routing)

**What a segment descriptor does NOT need:**
- Prose descriptions of architecture
- Detailed data flow narratives
- Cross-cutting summaries (that's the root atlas)

**Embedding strategy**: Each segment descriptor is embedded at build time using the same embedder as the main index. At query time, query embedding is compared against segment descriptor embeddings — same model, same latent space, no special infrastructure.

**Optional AI-visible label**: A minimal `"Subsystems: auth, persistence"` tag (~5-10 tokens) can be prepended to results. This is separate from the segment descriptor and far smaller than a narrative atlas block.

### 3. Segmentation Threshold — When to Activate Routing

Not all repos need segmented routing. A 30-file project has a trace graph small enough that full-graph search is already precise. Routing adds overhead without benefit.

| Repo Complexity | Files | Segments | Rationale |
|---|---|---|---|
| Tiny | < 50 | 0 (no routing) | Full graph search is fine |
| Small | 50-150 | 0 (no routing) | Minimal subsystem separation |
| Medium | 150-500 | 3-6 | Clear subsystem boundaries emerging |
| Large | 500-2000 | 6-12 | Multiple distinct subsystems |
| Huge | 2000+ | 10-15 (capped) | Monorepo or deeply layered service |

**Activation trigger**: `file_count >= 150 AND detected_module_count >= 4`. Below this threshold, Phase 29 code is dormant and retrieval proceeds unchanged.

**Not monorepo-specific.** A 300-file Django app (models, views, serializers, tasks, signals, middleware) has as much routing benefit as a 5-package monorepo. The segmentation algorithm adapts: use domain tag clustering when directory structure is flat.

### 4. Structural-Only Segments (No-LLM Fallback)

LLM-generated `COVERS` vocabulary is highest quality, but structural segments can be built from graph statistics alone — no LLM required:

- **Segment boundaries**: directory grouping (always algorithmic, no LLM)
- **KEY FILES**: top-N files by in-degree within segment (from `trace_nodes.jsonl`)
- **COVERS**: concatenation of domain tags from all files in segment (available from existing clustering data)
- **BOUNDARIES**: inferred from cross-segment edges in trace graph

This gives routing coverage to Free tier users and users without an LLM configured. Structural segments route queries to the right directory cluster with reasonable accuracy. LLM-expanded `COVERS` vocabulary (synonyms, related concepts) improves routing for ambiguous queries but isn't required for the basic routing benefit.

**Implementation**: Generate structural segments from `trace_nodes.jsonl` + domain tag data + manifest metadata. No LLM call. Available to all tiers.

### 5. Atlas Versioning & History

The Atlas is regenerated, not appended. But we should keep the previous version:
- `atlas.json` — current Atlas
- `atlas_prev.json` — previous Atlas (for diff detection)

This enables a future feature: "What changed since last Atlas?" — useful for the deepening loop and for user notification.

### 6. MCP Integration — Routing, Not Injection

The Atlas is used **inside** the `codrag_context` tool handler before retrieval — not appended to the output. The AI never sees atlas text unless it explicitly calls a separate `codrag_atlas` tool.

```python
# In the codrag tool handler (pre-retrieval):
if segments_available:
    # Step 1: Route query to relevant segments
    selected_segments = route_query_to_segments(query, project_id)
    segment_paths = get_files_in_segments(selected_segments)
    
    # Step 2: Pass segment context to retrieval
    results = search(query, segment_bias=segment_paths, ...)
else:
    # No segments yet: full search (same as today)
    results = search(query, ...)

# AI receives: results only. No atlas block prepended.
```

**Separate `codrag_atlas` MCP tool** (optional, for AI tools that want to orient themselves):
```json
{"name": "codrag_atlas", "description": "Get the architectural map of the codebase. Call this when you need to understand project structure before querying for specific code. Not needed for most queries."}
```

This lets the AI tool decide when it needs orientation (e.g., at the start of a complex refactor), without burning context on every routine query.

**The `include_atlas` param** on `codrag_context` is deprecated in this model. Segment routing is always on when segments exist — it improves results, it doesn't consume AI context budget.

### 7. Compression Interaction

In the routing model, Context compression is unaffected by the Atlas. Since atlas text is not prepended to AI context, there's nothing to compress or protect.

When compression is enabled:
1. Segment routing runs (pre-retrieval, internal)
2. Search results assembled with scoped retrieval
3. Context compression applies to the search results
4. AI receives: compressed results + optional ~8-token subsystem label

If `codrag_atlas` is called as a separate MCP tool by the AI, that response is separate from the context assembly pipeline and context compression does not apply to it.

### 8. Multi-Project Considerations

Each CoDRAG project gets its own atlas and segment descriptors. The `codrag` MCP tool already targets a specific project, so the correct routing index is selected automatically.

For very large repos (>5000 files), the 15-segment cap may create overly coarse segments. In that case, consider two-level routing:
- Level 1: coarse segments (top-level workspace boundaries)
- Level 2: fine segments within the matched coarse segment

This is the same problem as hierarchical navigable small worlds (HNSW) in ANN search — the solution is the same: hierarchical index layers. **Deferred** — the 15-segment flat index handles everything up to large monorepos.

---

## Dashboard UX Strategy

> **Goal**: The Atlas should be visible as an internal routing artifact — developers want to understand why a query returned what it returned. The Atlas explains the routing decision.

### Primary: Routing Transparency in Context Assembler

When context is returned, show which segments were selected and how they influenced retrieval:

```
┌─────────────────────────────────────┐
│  Context Assembler                  │
├─────────────────────────────────────┤
│  Routed via: auth-middleware (0.87) │  ← routing decision shown
│              data-persistence (0.71)│
│  5 results (3 in-segment, 2 other)  │
│                                     │
│  --- auth/middleware.py ---          │
│  --- session/store.py ---            │
│  --- auth/decorators.py ---          │
└─────────────────────────────────────┘
```

### Secondary: Atlas Status in Knowledge Base Status Panel

The Atlas is a build artifact. Freshness matters for routing quality:

```
Knowledge Base Status
├── Index: 547 files, 1,823 chunks
├── Freshness: 2 min ago
├── Atlas: ✓ 15 segments, fresh (12m ago)  ← routing status
│         [Regenerate] [View Segments]
└── ...
```

### Optional: Segment Browser Panel

For power users: show the computed segments, their `COVERS` vocabulary, and per-segment freshness. Allows editing `COVERS` to tune routing without regenerating the full atlas.

### Dashboard TODOs (Deferred)

- [ ] Routing provenance in Context Assembler (which segments selected, scores)
- [ ] Atlas freshness + segment count in IndexStatusCard
- [ ] Segment browser panel (view/edit segment descriptors)
- [ ] Atlas regenerate button
- [ ] SSE event for atlas_regenerated (updates UI in real-time)

---

## Marketing Website Strategy

> **Goal**: Position the Atlas as the intelligence layer that makes CoDRAG's retrieval smarter — not a prompt engineering trick that adds text to every query. The value proposition: "CoDRAG gets your AI better code, not more text."

### Feature Card Integration

The Atlas should be the **6th visible card** — framed around retrieval precision, not orientation injection:

```typescript
{
  icon: <Waypoints className="w-8 h-8" />,
  title: 'Smarter Retrieval — The Atlas Routes Every Query',
  description: 'CoDRAG maps your codebase into subsystem segments at build time. 
    When your AI asks for context, the Atlas routes the query to the right 
    subsystem first — so the trace graph search is scoped before it starts. 
    Better results. No extra tokens.',
  badge: 'New',
  highlight: true,
}
```

**Placement**: Position it after "Graph Enrichment" (index 2) and before "Instant Context Assembly" (index 3). The narrative flow becomes:

1. **Semantic Search** — find relevant code
2. **Code Graph** — map structural relationships  
3. **Graph Enrichment** — deepen understanding over time
4. **Codebase Atlas** — route every query to the right subsystem ← NEW
5. **Context Assembly** — deliver the right context to your AI
6. **Path Weights** — you steer the signal

### Stat Role

```
"CoDRAG routes every query through a 15-segment atlas built from 
 547 files, 30 modules, and 656 structural edges — before retrieval 
 even starts. Smarter search. No prompt overhead."
```

### Marketing TODOs (Deferred)

- [ ] Add Atlas feature card to `codragFeatures` array (6th card)
- [ ] Update homepage feature count (5 → 6 cards visible)
- [ ] Add Atlas stat to hero section or trust strip
- [ ] Update `/download` page to mention Atlas in feature list
- [ ] Add Atlas section to docs guide (`/guides/atlas`)
- [ ] Consider Atlas as a demo/preview on marketing site (show example Atlas for a well-known OSS project)

---

## Edge Cases & Nuance

### 1. Empty/New Projects
No enrichment data yet → no Atlas. Graceful fallback: structural-only Atlas from manifest stats, or nothing.

### 2. Very Small Projects (< 150 files)
Below the activation threshold, no segments are generated and routing is dormant. Full-graph search is used as-is. No atlas generation, no overhead.

### 3. Rapid File Changes During Atlas Generation
Atlas generation takes ~30 seconds. Files may change during this time. The Atlas should be generated from a snapshot (the already-computed enrichment data), not from live filesystem state. Enrichment data is already a point-in-time snapshot, so this is naturally handled.

### 4. LLM Unavailable
If the LLM slot is unreachable when Atlas generation is triggered:
- Log warning
- Serve stale Atlas if one exists
- Queue regeneration for next LLM availability check
- Fall back to structural-only Atlas if no cached version exists

### 5. Routing Descriptor Drift
If the LLM generates incorrect `COVERS` vocabulary for a segment (e.g., wrong domain terms), queries that should route to that segment will miss it. Mitigation:
- `COVERS` is generated from domain tags (already validated) + LLM expansion
- Structural fallback uses domain tags directly (no LLM hallucination risk)
- Dashboard segment browser lets users inspect and correct `COVERS` vocabulary
- Bad routing shows up as retrieval degradation, which can be caught by the eval harness

### 6. User Wants to Override Routing
Power users may want to tune routing behavior (e.g., "queries about payments should always route to `src/billing/`"). This maps directly to editing segment `COVERS` vocabulary:
- Dashboard segment browser: edit `COVERS` terms for any segment
- `atlas_override.json` in project root: define custom segments with hand-written `COVERS`
- Higher priority than LLM-generated segments

### 7. Atlas Language
Should the Atlas be in English? Yes, for now. The LLM generates in English regardless of code language. Future: accept a `language` parameter for localized Atlas generation.

### 8. Routing Latency
Segment routing adds one embedding lookup (query → segment descriptors) before retrieval. With N≤15 segments, this is N cosine similarities between pre-computed vectors — sub-millisecond on CPU. The segment descriptor embeddings are loaded into memory on first query and cached. No meaningful latency impact.

---

# Phase 29B: Segmented Atlas (Hierarchical)

> Applies to any repo with identifiable subsystems — not just monorepos. The segmentation threshold is codebase complexity (file count, module count, trace graph diameter), not project structure. A root descriptor provides global routing context while segment descriptors enable fine-grained subsystem routing.

## Research Findings

### The 1-File Module Problem

Analysis across **all 7 indexed projects** (29 to 499 modules each) revealed a systemic issue: **every module contains exactly 1 file**. The clustering pipeline in `build_clusters()` produces 1:1 file-to-module mappings — no grouping is happening.

Root cause in `src/codrag/core/cluster.py`:
1. Groups by primary domain tag (first tag per file)
2. Domain tags are too specific — 68% are singletons (only 1 file per tag)
3. Connected-component analysis further splits multi-file groups
4. The merge step returns all clusters as-is when there are no "large" clusters (≥2 files)

**Implication**: We cannot use existing modules as segment boundaries. We need a separate grouping strategy.

### Segmentation Strategy Analysis

**Strategy A: Top-Level Directory Grouping**

Tested on spark-java (2,028 files, 195 modules):

| Directory | Modules |
|---|---|
| `src/main/java` | 99 |
| `src/test/java` | 84 |
| `src/test/resources` | 5 |
| misc (pom.xml, README, etc.) | 7 |

- **Verdict for single-service repos**: Too coarse — only 2 meaningful groups
- **Verdict for monorepos**: Excellent — workspace structure IS the architecture

**Strategy B: Domain Tag Super-Clustering**

Group by overlapping semantic themes:

| Theme | Modules | Key Tags |
|---|---|---|
| Web Core | 96 | web-framework, http-routing, http-handling |
| Middleware | 41 | middleware, security, content-negotiation |
| Server Runtime | 33 | embedded-servers, jetty-integration |
| Data | 31 | serialization, error-handling |
| Static Assets | 25 | static-assets, resource-management |
| Testing | 24 | testing, integration-testing |
| Unthemed | 31 | — |

- **Verdict for single-service repos**: Good thematic grouping, but overlap problem — modules appear in multiple themes
- **Verdict for monorepos**: Cuts across workspace boundaries in confusing ways

### Chosen Approach: Hybrid Directory + Domain

1. **Primary segmentation**: Top-level directory structure (depth 2-3). Always stable.
2. **Secondary grouping**: Within each directory segment, group by dominant domain tags for richer summaries.
3. **For monorepos**: Segments = workspace packages (detected via package.json, Cargo.toml, go.mod boundaries).
4. **For single-service repos**: Segments = top-level source directories + domain tag clusters within each.

### Model Comparison: Thinking vs Standard

| Model | Quantization | Output | Quality |
|---|---|---|---|
| Qwen3-NEXT-80b | q4_k_m | 687 chars | Raw stats, ignored section labels entirely | **not using this model moving forward**
| Mistral:14b | full | 3,998 chars | Perfect section structure, rich detail |
testinging with qwen3-vl:32b-instruct-bf16 nex

The thinking model (Qwen3) consumed most of `num_predict=4096` on internal `<think>` blocks, leaving insufficient budget for visible output. Thinking models need `num_predict=8192+` and `<think>` block stripping in post-processing.

---

## Segmented Atlas Design

### Architecture

```
atlas.json                      ← Root atlas (~1200 chars)
                                   Project identity, workspace map, cross-cutting patterns
atlas_segments/
  seg_src-main-java.json        ← Segment: main source (~800-1500 chars)
  seg_src-test-java.json        ← Segment: test suite
  seg_packages-ui.json          ← Segment: UI library (monorepo)
  seg_engine.json               ← Segment: Rust engine (monorepo)
  ...
```

### Query-Time Routing Flow

```
┌─────────────────────────────────────────────────────┐
│ 1. Query arrives at codrag_context handler          │
│    query = "How does auth connect to session store?" │
│                                                     │
│ 2. Route: embed query → cosine sim vs segments      │
│    root descriptor   → always included in routing   │
│    "auth-middleware" → score 0.87 ✓ selected         │
│    "data-persistence"→ score 0.71 ✓ selected         │
│    "dashboard-ui"    → score 0.22   skipped          │
│                                                     │
│ 3. Scoped retrieval (pre-AI)                        │
│    Trace walk: start from hubs in selected segments │
│    Vector search: +boost for files in segments      │
│                                                     │
│ 4. AI receives: targeted results only               │
│    auth/middleware.py  0.91   <- routed correctly   │
│    session/store.py    0.88                         │
│    auth/decorators.py  0.82                         │
│    [optional] "Subsystems: auth, persistence" label │
│    NO atlas text injected                           │
└─────────────────────────────────────────────────────┘
```

### Descriptor Sizing

Segment descriptors are sized for routing accuracy, not for human readability. Smaller is better if routing accuracy is maintained.

| Component | Target Chars | Purpose |
|---|---|---|
| Root descriptor | 500–800 | Project identity + segment manifest for routing |
| Per segment | 300–600 | COVERS + KEY FILES + BOUNDARIES |
| Embedding overhead | 0 | Embedded at build time, sub-ms lookup at query time |
| **AI context cost** | **~8 tokens** | Optional subsystem label only |

Compare to the Phase 29A approach: 1,500–4,200 chars prepended to every AI query. The routing model eliminates that cost entirely — the improvement shows up in result quality, not AI context.

### Root Descriptor Content

The root descriptor orients the routing system to the project identity and provides a segment manifest. It is also embedded and used as a fallback when no segment scores above threshold:

```
IDENTITY: CoDRAG — local-first code intelligence. Python/TypeScript/Rust monorepo.
STACK: Python 3.11, FastAPI, React 18, Rust (PyO3), SQLite.
SEGMENTS: src/codrag/ (backend core, 89 files), packages/ui/ (dashboard, 67 files),
  engine/ (Rust parser, 23 files), websites/ (marketing/docs, 45 files), tests/ (48 files).
CROSS-CUTTING HUB: src/codrag/core/index.py (47 edges) — all subsystems connect through here.
```

Note: root descriptor is shorter than before because it no longer needs to be a complete architectural narrative. The segment descriptors carry the subsystem detail needed for routing.

### Segment Descriptor Content

Each segment descriptor is optimized for routing precision. The embedding of `COVERS` drives which queries route here:

```
SEGMENT: src/codrag/core/ (Core Engine, 89 files)
COVERS: indexing, search, trace graph, embedding, enrichment pipeline, semantic search,
  code index, chunk retrieval, vector search, LLM client, epistemic enrichment.
KEY FILES: index.py, trace.py, embedder.py, atlas.py, cluster.py, augmenter.py.
BOUNDARIES: → src/codrag/api/ (exposed as REST endpoints)
             → engine/ (delegates parsing via PyO3)
             ← src/codrag/services/ (orchestration calls in)
```

`COVERS` is the critical field: it should include all the domain vocabulary that queries about this subsystem would use. This is what the embedding model uses to match queries to segments.

### Segmentation Algorithm

```python
def compute_segments(index_dir: Path) -> List[Segment]:
    """Compute segments from directory structure + module data.
    
    Strategy:
    1. Scan all indexed file paths from trace_nodes.jsonl
    2. Group by top-level directory (depth 2-3, adaptive)
    3. For monorepos: detect workspace boundaries (package.json, Cargo.toml, go.mod)
    4. Merge tiny groups (<5 files) into nearest sibling
    5. Cap at MAX_SEGMENTS (10-15) — merge smallest if over budget
    6. Annotate each segment with its modules' domain tags + summaries
    
    Returns list of Segment(id, name, file_paths, module_ids, domain_tags).
    """
```

**Directory depth heuristic**:
- If top-level has `src/`, `packages/`, `apps/`, `lib/` → use depth 2 (`src/codrag/`, `packages/ui/`)
- If top-level has `cmd/`, `internal/`, `pkg/` (Go convention) → use depth 2
- Otherwise → use depth 1

**Workspace boundary detection**:
- `package.json` with `"workspaces"` → each workspace is a segment
- `Cargo.toml` with `[workspace]` → each member is a segment
- `go.work` → each module is a segment
- `turbo.json` or `pnpm-workspace.yaml` → parse packages

**Merge threshold**: Segments with <5 files merge into their parent directory segment.

**Max segments**: 15. If more, merge smallest pairs until ≤15.

### Storage Format

Each segment atlas is an `AtlasDocument` (same schema as root):

```json
{
  "content": "SEGMENT: src/codrag/core/ (Core Engine, 89 files)\nROLE: ...",
  "generated_at": "2026-02-20T05:30:00Z",
  "mode": "llm",
  "model": "mistral:14b",
  "char_count": 1247,
  "fingerprint": "a1b2c3...",
  "segment_id": "src-codrag-core",
  "segment_name": "Core Engine",
  "file_count": 89,
  "file_paths": ["src/codrag/core/index.py", "..."]
}
```

Root atlas adds a `segments` manifest:

```json
{
  "content": "IDENTITY: CoDRAG is...",
  "segments": [
    {"id": "src-codrag-core", "name": "Core Engine", "file_count": 89},
    {"id": "packages-ui", "name": "Dashboard UI", "file_count": 67},
    ...
  ]
}
```

### Staleness & Regeneration

**Root atlas**: Regenerate when:
- Segment list changes (new workspace, renamed directory)
- File count changes >20% overall
- Triggered manually

**Segment atlases**: Regenerate when:
- Module fingerprints within segment change
- Hub files within segment change
- File count within segment changes >20%

Per-segment fingerprints mean only changed segments regenerate. Adding a new file to `packages/ui/` only regenerates the `packages-ui` segment, not the root or other segments.

### Generation Cost

| Component | LLM Calls | Time (14b) |
|---|---|---|
| Root atlas | 1 | ~30s |
| Per segment | 1 each | ~15-25s each |
| **Total (10 segments)** | **11** | **~4-5 min** |

Segments can be generated in parallel if multiple LLM slots are available.
Incremental: only changed segments regenerate. Typical rebuild touches 1-2 segments.

---

## Implementation Plan

### Prerequisites

#### P0: Fix Upstream Clustering (Foundational)

The 1-file-module problem must be addressed. Without multi-file modules, segment atlas content will be shallow — essentially file summaries, not subsystem overviews.

Changes to `src/codrag/core/cluster.py`:
- [ ] Increase `min_cluster_size` from 2 to 5
- [ ] Use tag similarity (Jaccard) for initial grouping, not just primary tag match
- [ ] Add embedding similarity as secondary grouping signal (files that are semantically similar should cluster)
- [ ] Better merge strategy: merge into semantically nearest, not just edge-nearest
- [ ] Target: 10-30 files per module for medium repos

**This is a separate effort from atlas segmentation**, but improves segment content quality dramatically.

### Phase 29B Implementation Steps

#### Step 1: Segment Discovery (`src/codrag/core/atlas.py`)

- [ ] Add `Segment` dataclass: `id, name, dir_path, file_paths, module_ids, domain_tags`
- [ ] Add `compute_segments(index_dir)` function:
  - Scan `trace_nodes.jsonl` for all file paths
  - Group by directory (adaptive depth heuristic)
  - Detect workspace boundaries (package.json, Cargo.toml, etc.)
  - Merge tiny groups, cap at MAX_SEGMENTS=15
- [ ] Add `_detect_workspace_boundaries(project_root)` helper
- [ ] Tests for segment discovery on various directory structures

#### Step 2: Root Atlas Generation

- [ ] Add `generate_root_atlas()` method to `CodebaseAtlas`
- [ ] New prompt template `ROOT_ATLAS_SYSTEM` / `ROOT_ATLAS_PROMPT`:
  - Shorter: ~1200 chars target
  - Focuses on: identity, stack, workspace map, cross-cutting patterns, pipeline overview
  - Receives segment manifest (name, file_count, top domain tags per segment)
  - Does NOT detail individual subsystems (that's what segments are for)
- [ ] Root atlas stores segment manifest in `atlas.json`
- [ ] Tests for root atlas generation

#### Step 3: Segment Atlas Generation

- [ ] Add `generate_segment(segment: Segment)` method to `CodebaseAtlas`
- [ ] New prompt template `SEGMENT_ATLAS_SYSTEM` / `SEGMENT_ATLAS_PROMPT`:
  - Per-segment: ~800-1500 chars target
  - Focuses on: role, key files, internal flow, dependencies on other segments, status
  - Receives: module summaries within segment, epistemic data within segment, edges within/across segment
- [ ] Storage: `atlas_segments/{segment_id}.json`
- [ ] Per-segment fingerprint for incremental regeneration
- [ ] Tests for segment atlas generation

#### Step 4: Query-Time Segment Selection

- [ ] Build file-to-segment index: `Dict[str, str]` mapping `source_path → segment_id`
  - Built from segment discovery data
  - Cached in memory on first load
- [ ] Modify `_prepend_atlas()` in `projects.py`:
  - Accept search result `source_path` list
  - Map paths to segment IDs
  - Rank segments by hit count (how many search results touch each)
  - Inject: root atlas + top 2-3 segment atlases
  - Respect total atlas budget (root + segments ≤ 4200 chars)
- [ ] Update `ContextRequest` model to pass source paths through
- [ ] Tests for segment selection logic

#### Step 5: Pipeline Integration

- [ ] Atlas generation (Pass 3.5) now generates root + all segments
- [ ] Incremental: only regenerate segments whose fingerprint changed
- [ ] Progress callback reports per-segment progress
- [ ] SSE events for segment generation progress

#### Step 6: API & MCP Updates

- [ ] `GET /projects/{id}/atlas` returns root + segment manifest
- [ ] `GET /projects/{id}/atlas/segments/{segment_id}` returns specific segment
- [ ] `POST /projects/{id}/atlas/regenerate` regenerates root + all stale segments
- [ ] MCP `codrag_context` tool: `include_atlas` now means root + relevant segments
- [ ] Dashboard: Atlas panel shows segment list with freshness indicators

### Bonus: Thinking Model Compatibility

- [ ] Detect thinking models (model name contains "thinking", "qwen3", or model outputs `<think>` blocks)
- [ ] Bump `num_predict` to 8192 for thinking models
- [ ] Post-process: strip `<think>...</think>` blocks before quality gate
- [ ] Add `thinking_model` flag to LLMClient or detect automatically

---

## Migration Path

The segmented atlas is **backward-compatible** with Phase 29A (single atlas):

1. **No segments**: Falls back to unscoped search (same as pre-Phase-29 behavior)
2. **Segments generated**: Routing activates automatically on next query
3. **Gradual rollout**: Generate segments on next pipeline run; routing activates once at least 2 segments exist
4. **Phase 29A atlas.json**: If a Phase 29A single atlas exists, it can optionally be exposed via the `codrag_atlas` MCP tool while Phase 29B segment routing is built

---

## Open Questions (Phase 29B)

1. **Segment count cap**: Is 15 right? More segments = more routing precision but more LLM calls at build time and more embedding comparisons at query time (though N=15 cosine comparisons is negligible).
2. **COVERS vocabulary construction**: Should `COVERS` be LLM-generated (best quality) or auto-generated from domain tags + file summaries (no extra LLM call)? Hybrid: auto-generate, LLM expands with synonyms.
3. **User-defined segments**: Should users be able to define custom segment boundaries and COVERS vocabulary? Power users know their codebase better than any algorithm.
4. **Segmentation for small single-service repos**: A 200-file Django app has identifiable subsystems (models, views, serializers, tasks, signals) that benefit from routing but don't follow directory conventions cleanly. Domain tag clustering may work better than directory grouping here.
5. **Routing accuracy measurement**: Need an eval harness for routing quality separate from retrieval quality. Ground truth: "query X should route to segment Y" — can be built from the existing real-repo eval queries.
