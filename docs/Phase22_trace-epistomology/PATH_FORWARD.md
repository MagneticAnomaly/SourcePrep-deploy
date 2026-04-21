# Phase 22: Path Forward — Epistemic Trace Enrichment

**Parent**: `Phase22_trace-epistomology/README.md`  
**Status**: Implementation Plan  
**Created**: 2025-02-13  

---

## Executive Summary

Prep's trace currently produces a structural graph (nodes + edges via tree-sitter) and a flat LLM overlay (summary + role via 3b model). This plan defines the path to a **self-refining epistemic knowledge graph** — a system that iteratively deepens its understanding of a codebase through coordinated Rust and LLM passes, with special attention to documentation mining, cross-referencing, and convergence.

The strategy is grounded in recent CS research on knowledge graph construction, GraphRAG, and iterative LLM-augmented systems. This document consolidates all Phase 22 sub-documents into a single actionable roadmap.

---

## Research Validation

Our multi-pass epistemic architecture aligns with — and extends — several active research areas. This section maps each of our key design decisions to published work.

### 1. GraphRAG: Hierarchical Knowledge Graphs for LLM Grounding

**Our approach**: Build a trace graph, extract community clusters, generate hierarchical summaries (Pass 2 → Pass 3).

**Research backing**: Microsoft's **GraphRAG** (2024) demonstrates that LLM-derived knowledge graphs with community detection (Leiden algorithm) and hierarchical summarization dramatically outperform baseline RAG for holistic reasoning. Their pipeline:
1. Extract entities + relationships from text → knowledge graph
2. Hierarchical community clustering
3. Bottom-up community summaries
4. Query-time: fan out from entities through neighbors + community context

**How Prep extends this**: GraphRAG operates on unstructured text. Prep starts with a *structurally parsed* graph (tree-sitter AST → nodes + edges), then enriches with LLM-derived semantic edges. This gives us a **hybrid factual-semantic graph** — stronger than either pure static analysis or pure LLM extraction alone.

**Reference**: Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization," Microsoft Research, 2024. https://microsoft.github.io/graphrag/

### 2. LLM-Powered Knowledge Graph Enrichment with Multi-Agent Validation

**Our approach**: Pass 0.5 — LLM hypothesizes relationships, Rust validates them, conflict resolution prunes hallucinations.

**Research backing**: The **KARMA** framework (Lu & Wang, 2025) uses 9 specialized LLM agents for KG enrichment: entity extraction, relationship extraction, schema alignment, conflict resolution, and evaluation. Key findings:
- Multi-layer validation reduces conflict edges by 18.6%
- Schema alignment agents catch entity type mismatches
- Confidence scoring (composite of multiple verification signals) is critical for quality

**How Prep adapts this**: We replace KARMA's multi-agent approach with a **two-tier architecture**: a cheap 3b model as the "hypothesis generator" and Rust as the "validator." This is more efficient for our use case — we don't need 9 agents because our domain (code + docs) has strong structural priors. Rust can validate file existence, node type compatibility, and edge uniqueness deterministically, which KARMA does with additional LLM calls.

**Reference**: Lu & Wang, "KARMA: Leveraging Multi-Agent LLMs for Automated Knowledge Graph Enrichment," arXiv:2502.06472, 2025.

### 3. Repository-Level Code Knowledge Graphs

**Our approach**: AST parsing → nodes (files, symbols) + edges (imports, contains) → LLM enrichment with descriptions.

**Research backing**: **Knowledge Graph Based Repository-Level Code Generation** (2025) builds code KGs from AST analysis with node types {File, Class, Method, Function, Attribute, LLM-Generated Description} and hybrid retrieval (full-text + vector indexes). Their key insight: storing LLM-generated descriptions as *additional nodes* in the KG (not just metadata) enables both structural and semantic search.

**How Prep compares**: Our current trace is structurally equivalent to their KG (tree-sitter AST → nodes + edges). Our planned enhancement adds LLM-generated semantic edges and doc-derived cross-references, which they don't address (their work is code-only). We go further by making the enrichment *iterative* rather than one-shot.

**Reference**: Knowledge Graph Based Repository-Level Code Generation, arXiv:2505.14394, 2025.

### 4. Topological-Order Documentation Generation

**Our approach**: Bottom-up enrichment — enrich leaf nodes first (files with no dependents), then work up the dependency graph so parent nodes have child context.

**Research backing**: **RepoAgent** (Luo et al., EMNLP 2024) generates repository-level documentation using a topological ordering strategy: build a DAG from code reference relationships, then generate docs bottom-to-top so each node's children and callees have docs before it does. This ensures *contextual completeness* — the LLM always has downstream context when generating upstream documentation.

**How Prep adapts this**: Our Pass 2 enrichment should process nodes in reverse-topological order of the trace graph. Leaf files (utilities, configs) get enriched first. Then files that import them get enriched with the benefit of already-enriched neighbor summaries. This is a direct application of RepoAgent's key insight to our epistemic pipeline.

**Reference**: Luo et al., "RepoAgent: An LLM-Powered Open-Source Framework for Repository-level Code Documentation Generation," EMNLP 2024. arXiv:2402.16667.

### 5. Iterative Convergence via Message Passing

**Our approach**: Pass 4+ continuous deepening loop — re-enrich nodes whose neighbors changed, converge when all epistemic scores ≥ 0.95.

**Research backing**: This is directly analogous to **Belief Propagation** (Pearl, 1988; Yedidia et al., 2003), an iterative message-passing algorithm on graphical models. In BP:
- Each node sends "messages" (beliefs) to its neighbors
- Each node updates its belief based on received messages
- The process iterates until beliefs converge to a fixed point
- Convergence is guaranteed on trees; on loopy graphs, "Loopy BP" often converges in practice

Our enrichment loop is structurally identical: each node's "belief" is its epistemic state (summary, domain tags, cross-refs). When a neighbor is re-enriched (its message changes), downstream nodes re-evaluate. Convergence occurs when no node's enrichment changes between iterations.

**Key insight from BP research**: Scheduling matters. Random scheduling can oscillate. **Residual Belief Propagation** (Elidan et al., 2006) prioritizes nodes with the largest "residuals" (difference between current and incoming messages). Our equivalent: prioritize re-enrichment of nodes whose neighbors' epistemic scores changed the most.

**Reference**: Yedidia, Freeman, & Weiss, "Understanding Belief Propagation and its Generalizations," IJCAI 2003; Elidan et al., "Residual Belief Propagation," UAI 2006.

### 6. Code-Documentation Drift Detection

**Our approach**: Compare doc references to actual code state; flag stale cross-references and contradictory docs.

**Research backing**: **"A Review on Detecting and Managing Documentation Drift in Software"** (IEEE, 2025) surveys techniques for detecting when documentation diverges from code. Key methods include:
- Reference link validation (do mentioned files/functions still exist?)
- Semantic similarity between doc descriptions and actual code behavior
- Temporal analysis (when was the doc last updated vs. when was the code last changed?)

**How Prep implements this**: Our Rust markdown parser extracts backtick references and markdown links. The LLM enrichment pass compares these references against the current trace graph. If a doc references `InterstitialAdController.swift` but the graph only contains `InterstitialAdManager.swift`, that's detectable drift — both by Rust (fuzzy file match) and by the LLM (semantic understanding of the rename).

**Reference**: IEEE, "A Review on Detecting and Managing Documentation Drift in Software," IEEE Xplore, 2025.

### 7. Aider's Tree-Sitter Repository Map

**Our approach**: Use tree-sitter AST to extract structural context for LLM consumption.

**Research backing**: **Aider** (2023) uses tree-sitter to build a "repository map" — a compact representation of the codebase showing class/function signatures, optimized by graph-ranking to select the most-referenced identifiers. This map provides LLMs with structural context without sending full file contents.

**How Prep differs**: Aider builds a *transient* map per-query (optimized for the current edit task). Prep builds a *persistent* enriched graph (optimized for holistic codebase understanding). Aider's map is read-only context; Prep's graph is iteratively enriched. But the core insight is shared: tree-sitter AST → graph → ranked context selection.

**Reference**: Aider, "Building a better repository map with tree sitter," aider.chat, 2023.

### 8. Dynamic Knowledge Memory for Agentic Systems

**Our approach**: The trace graph as persistent, evolving memory that agents query for context.

**Research backing**: The survey "LLM-empowered Knowledge Graph Construction" (2025) identifies **Dynamic Knowledge Memory** as a key future direction: KGs as *living memory substrates* that evolve with agent interactions, rather than static stores. Frameworks like A-MEM (Xu et al., 2025) model memory as interconnected notes with contextual metadata, enabling continuous reorganization. Zep (Rasmussen et al., 2025) uses temporal knowledge graphs for fact validity tracking.

**How Prep aligns**: Our epistemic scoring system with decay mechanics is exactly this — a temporal knowledge graph where each node's "belief" has a timestamp, confidence, and staleness risk. The continuous enrichment loop is the "reorganization" mechanism. Prep's trace is a dynamic knowledge memory for coding agents.

**Reference**: Survey: "LLM-empowered Knowledge Graph Construction," arXiv:2510.20345, 2025.

---

## Consolidated Architecture

Based on the research validation above, here is the refined pipeline:

```
┌────────────────────────────────────────────────────────────────┐
│  PASS 0: Structural Trace + Document Extraction (Rust)         │
│                                                                │
│  Code files:  tree-sitter AST → symbols + import edges         │
│  Doc files:   regex/markdown → sections + refs + links         │
│  All files:   content hash for staleness detection             │
│                                                                │
│  Output: trace_nodes.jsonl, trace_edges.jsonl                  │
│  Cost: ~100ms                                                  │
│  Research: [Aider repomap, KG-based code gen]                  │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  PASS 1: Fast Catalogue (3b LLM)                               │
│                                                                │
│  Per-node: summary + role + confidence + related_files         │
│  Strategic snippets: head + Rust-ranked hot sections            │
│  Long files (>500 lines): chunked pre-summarization            │
│                                                                │
│  Output: trace_augmented.jsonl                                 │
│  Cost: ~10 min for 600 files (+50s for long-file chunks)       │
│  Research: [RepoAgent topological ordering]                    │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  PASS 0.5: LLM-Guided Re-Trace (Rust validation)              │
│                                                                │
│  Validates 3b's relationship hypotheses against graph          │
│  Adds typed "inferred" edges where both endpoints exist        │
│  Cross-validates with Rust-extracted doc references             │
│  Confidence gating: only edges with conf >= 0.7                │
│                                                                │
│  Output: trace_inferred_edges.jsonl                            │
│  Cost: ~5ms                                                    │
│  Research: [KARMA multi-agent validation]                      │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  PASS 2: Epistemic Enrichment (14b LLM)                        │
│                                                                │
│  Per-node (reverse-topological order):                         │
│    source content + 3b summary + neighbor summaries            │
│    + structural edges + inferred edges + doc refs              │
│  Produces: domain_tags, architecture_layer, design_pattern,    │
│    subsystem, cross-refs, tech_debt, staleness_risk            │
│                                                                │
│  Output: trace_epistemic.jsonl                                 │
│  Cost: ~60 min for 600 files                                   │
│  Research: [GraphRAG community summaries, RepoAgent ordering]  │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  PASS 3: Cluster Synthesis (14b LLM)                           │
│                                                                │
│  Group nodes by domain_tags → subsystem clusters               │
│  Per-cluster: all enriched summaries → module synthesis        │
│  Produces: module summary, data flow, component status         │
│  Creates virtual module:* nodes in the graph                   │
│                                                                │
│  Output: trace_modules.jsonl                                   │
│  Cost: ~15 min (one call per cluster)                          │
│  Research: [GraphRAG Leiden clustering + community summaries]  │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│  PASS 4+: Continuous Deepening (14b LLM, iterative)            │
│                                                                │
│  Re-examine nodes whose neighbors changed since last pass      │
│  Priority scheduling: largest residual first (from BP theory)  │
│  Convergence: stop when all epistemic scores >= 0.95           │
│  Drift detection: flag stale doc↔code references               │
│                                                                │
│  Output: updates to trace_epistemic.jsonl                      │
│  Cost: decreasing per iteration (fewer nodes to process)       │
│  Research: [Belief Propagation convergence, doc drift survey]  │
└────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Sprint 1: Rust Markdown Extraction (Pass 0 Enhancement)

**Goal**: Give documentation files structural graph connections for the first time.

**Deliverables**:
1. **`engine/crates/prep-parser/src/markdown.rs`** — new module
   - Parse `#`/`##`/`###` headers → `section` nodes with `contains` edges
   - **Each section records `start_line`, `end_line`, `ref_count`, `depth`** for importance ranking
   - Extract backtick file references (`` `path/to/file.ext` ``) → `references` edges
   - Extract markdown links (`[text](path)`) → `links_to` edges
   - Detect status markers (✅, ⏳, ❌, `**Status**:`) → file node metadata
   - Compute doc metrics (line count, section count, ref density)
   - **Produce a ranked section digest** stored in file node metadata — sections sorted by importance (ref_count × depth heuristic). This digest powers strategic snippet selection in Pass 1.
   - **No tree-sitter** — pure regex line scanner (simpler, sufficient, no new dependency)

   For **code files**, the existing tree-sitter parse already provides symbol spans + edge degree. The augmenter can rank symbols by inbound `calls`/`imports` edge count to identify the "hottest" code regions — same principle as for docs.

2. **`engine/crates/prep-graph/src/lib.rs`** — modify `build_trace()`
   - Add `.md`/`.markdown` branch that reads content + calls `analyze_markdown()`
   - Wire section nodes + reference edges into the graph

3. **`engine/crates/prep-parser/src/lib.rs`** — extend `parse_file()` or add parallel entry point
   - Export `analyze_markdown` alongside language-specific analyzers

4. **Tests**:
   - Unit tests for markdown regex extraction (headers, refs, links, status)
   - Integration test: build trace on a fixture repo with `.md` files, verify section nodes + edges
   - Regression: existing Rust tests still pass (41 tests)

**Estimated effort**: 3-4 days  
**Performance impact**: +25ms on 200 docs (negligible)

### Sprint 2: Strategic Snippet Selection + Augmenter Enhancements (Pass 1 Tuning)

**Goal**: Replace blind first-N-line reads with Rust-guided strategic excerpts. Improve augmentation quality for docs.

**Key insight**: The Rust pass (Sprint 1) produces a ranked section digest for every file. Instead of reading the first 100 lines and hoping the important content is there, the augmenter reads **the head + the highest-ranked sections** — targeting the "juiciest" parts of the file.

**Deliverables**:
1. **`src/prep/core/augmenter.py`** — new `_get_strategic_excerpt()` replacing `_get_file_head()`
   ```python
   def _get_strategic_excerpt(self, file_path, digest, 
                               head_lines=100, section_lines=30,
                               max_total=300):
       lines = self._read_file_lines(file_path)
       parts = [("head", lines[:head_lines])]
       budget = max_total - head_lines
       
       # Rank sections by importance (ref_count, depth)
       sections = sorted(digest.get("sections", []),
                         key=lambda s: s.get("ref_count", 0), reverse=True)
       for sec in sections:
           if budget <= 0: break
           start = sec["start_line"] - 1
           if start < head_lines: continue  # already in head
           end = min(start + section_lines, sec["end_line"])
           parts.append((sec["name"], lines[start:end]))
           budget -= (end - start)
       
       # Format with markers so LLM knows these are excerpts
       output = []
       for name, chunk in parts:
           output.append(f"--- [{name}] ---")
           output.extend(chunk)
       return "\n".join(output)
   ```

   **For `.md` files**: sections ranked by `ref_count` (backtick references to code). A section referencing 6 code files is more important than a section with 0.

   **For code files**: symbols ranked by inbound edge degree from the trace graph. A function called by 12 other files is more important than a private helper.

   **Budget**: ~300 lines total per file (head 100 + up to 6 sections × 30 lines). This gives the LLM a representative view of an 800-line file while staying within token budget.

2. **`src/prep/core/augmenter.py`** — separate prompt template for `.md` files
   - Ask for `doc_type` (research, design_spec, plan, guide, reference, changelog, stub)
   - Ask for `doc_status` (active, completed, shelved, superseded, draft)
   - Ask for `references_files` (code files mentioned in the doc)

3. **`src/prep/core/augmenter.py`** — add `related_files` field to output schema
   - Both code and doc prompts ask: "List up to 5 files this file likely relates to"
   - This feeds Pass 0.5

4. **Chunked summarization for very long files (Pass 1.5)**
   - Files exceeding 500 lines: split into 200-line chunks, 3b summarizes each chunk independently
   - Chunk summaries concatenated and stored in the augmentation overlay
   - This summary feeds Pass 2 as additional context (~4 extra 3b calls per long file)
   - Only ~50 files in a typical project exceed 500 lines → ~50 sec extra cost

5. **Tests**:
   - Unit test: `_get_strategic_excerpt` produces correct section selections
   - Integration: verify augmenter uses digest when available, falls back to head-only when not
   - Spot-check augmentation quality on real long docs vs. current 30-line approach

**Estimated effort**: 3-4 days  
**LLM cost impact**: Moderate for long files (chunked summarization adds ~50 sec). Strategic excerpts are same token count as 100-line reads but much higher quality.

### Sprint 3: Pass 0.5 — LLM-Guided Rust Re-Trace

**Goal**: Validate LLM relationship hypotheses and enrich the graph with semantic edges.

**Deliverables**:
1. **`engine/crates/prep-graph/src/lib.rs`** — new `incorporate_inferred_edges()` function
   - Accept a list of `(source_id, target_path, relationship, confidence)`
   - Validate both endpoints exist in graph
   - Confidence gate (>= 0.7)
   - Add edges with `kind: "inferred"`
   - Cross-validate against Rust-extracted doc references (boost confidence on mutual confirmation)

2. **`engine/crates/prep-engine/src/lib.rs`** — expose via PyO3
   - New Python-callable function: `incorporate_inferred_edges(handle, edges_json)`

3. **`src/prep/core/augmenter.py`** — parse `related_files` from Pass 1 output
   - After Pass 1 completes, extract all `related_files` entries
   - Format as input for `incorporate_inferred_edges`
   - Call Rust validation
   - Write `trace_inferred_edges.jsonl`

4. **`src/prep/core/trace.py`** — load inferred edges in `TraceIndex`
   - `TraceIndex.load()` also loads `trace_inferred_edges.jsonl`
   - `get_neighbors()` includes inferred edges (with type filtering)

5. **Tests**:
   - Unit test: inferred edge validation (accept valid, reject missing endpoint, reject low confidence)
   - Integration: end-to-end Pass 1 → Pass 0.5 on fixture repo

**Estimated effort**: 4-5 days  
**Performance impact**: ~5ms (pure in-memory graph operations)

### Sprint 4: Pass 2 — Epistemic Enrichment (14b)

**Goal**: Deep per-node enrichment using the 14b model with full graph context.

**Deliverables**:
1. **`src/prep/core/augmenter.py`** — new `EpistemicAugmenter` class (or extend existing)
   - Topological ordering of nodes for processing (reverse dependency order)
   - For each node: gather source + 3b summary + neighbor summaries (structural + inferred)
   - 14b prompt producing expanded `AugmentationEntry` with epistemic fields
   - Write to `trace_epistemic.jsonl` (separate overlay from `trace_augmented.jsonl`)

2. **Prompt engineering**:
   - Code file prompt: domain tags, architecture layer, design pattern, subsystem, depends_on, depended_by, doc_references, tech_debt, staleness_risk
   - Doc file prompt: doc_type, doc_status, decision_chains, cross_references, contradictions, currency assessment
   - Both: epistemic_confidence score (0.0-1.0) with required reasoning

3. **`src/prep/core/epistemic_score.py`** — new module
   - `EpistemicScore` dataclass with components: structural_completeness, semantic_richness, cross_reference_density, temporal_currency, neighbor_consistency
   - Composite score calculation
   - Decay mechanics (neighbor change → 0.95×, doc update → 0.90×, source change → reset, rebuild → 0.80×)

4. **API integration**:
   - New endpoint: `POST /projects/{id}/trace/enrich` — trigger Pass 2
   - New endpoint: `GET /projects/{id}/trace/epistemic/{node_id}` — get epistemic data
   - Dashboard: display epistemic score + domain tags in file detail panel

5. **Tests**:
   - Prompt template tests (output schema validation)
   - Epistemic score calculation tests
   - API endpoint tests

**Estimated effort**: 8-10 days  
**LLM cost**: ~60 min for 600 files (14b model, local inference)

### Sprint 5: Pass 3 — Cluster Synthesis

**Goal**: Group enriched nodes into subsystem clusters and generate module-level understanding.

**Deliverables**:
1. **`src/prep/core/cluster.py`** — new module
   - Group nodes by `domain_tags` from Pass 2
   - Connected-component analysis on inferred edges within each domain
   - Output: clusters with member lists, inter-cluster edges

2. **`src/prep/core/augmenter.py`** — cluster synthesis prompt
   - Input: all enriched summaries in a cluster (not full source)
   - Output: module summary, data flow description, component status, architecture role
   - Create virtual `module:*` nodes in the graph

3. **`trace_modules.jsonl`** — new overlay file
   - Module-level summaries and metadata
   - Loadable by `TraceIndex` for context selection

4. **Dashboard integration**:
   - Module overview panel showing subsystem clusters
   - Click-through to member files

**Estimated effort**: 5-6 days

### Sprint 6: Pass 4+ — Continuous Deepening Loop

**Goal**: Iterative refinement until convergence.

**Deliverables**:
1. **Enrichment scheduler**:
   - Track `last_enriched_at` per node
   - Detect nodes whose neighbors changed since last enrichment
   - Priority queue: largest epistemic score residual first (BP-inspired)
   - Budget control: max N nodes per iteration, max M iterations total

2. **Convergence detection**:
   - All nodes `epistemic_score >= 0.95` → converged
   - No node's enrichment changed in last iteration → converged
   - Report: "Converged after K iterations, N nodes settled"

3. **Drift detection**:
   - Compare doc-referenced files against current trace graph
   - Flag: "Doc X references file Y, but Y doesn't exist (renamed? deleted?)"
   - Flag: "Doc X and Doc Y describe conflicting approaches to Z"

4. **Background execution**:
   - Gentle enrichment during idle time (1 node per minute)
   - Deep pass on explicit trigger or scheduled (nightly)
   - Progress reporting in dashboard

**Estimated effort**: 6-8 days

---

## Risk Assessment

### Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **LLM hallucination in Pass 0.5 edges** | Medium | Confidence gating, Rust validation, edge typing, decay/pruning |
| **14b model too slow for 600+ files** | Medium | Process in topological order; cache results; incremental re-enrichment |
| **Convergence loop doesn't converge** | Low | Budget control (max iterations); convergence ≈ no-change rather than score threshold |
| **Markdown regex misparses complex docs** | Low | Start with simple regex; upgrade to tree-sitter-markdown if needed |
| **Graph bloat from inferred edges** | Low | Separate file (`trace_inferred_edges.jsonl`); pruning of unconfirmed edges |
| **Breaking existing augmentation** | Medium | All new overlays are separate files; existing `trace_augmented.jsonl` untouched until Sprint 2 |

### What We're NOT Doing (Scope Boundaries)

- **Not replacing the 3b Pass 1** — it works well enough as triage. Enhancement only.
- **Not building a full ontology** — we're building a code-specific KG, not a general-purpose ontology.
- **Not using external APIs** — all LLM inference is local (Ollama). No cloud dependency.
- **Not changing the trace graph schema** — new node/edge kinds are additive. Existing consumers unaffected.
- **Not doing multi-repo** — single-project scope. Cross-project enrichment is future work.

---

## Success Metrics

### Quantitative
- **Doc connectivity**: % of `.md` files with ≥1 graph edge (current: 0%, target: 80%+)
- **Cross-reference coverage**: % of backtick file references that resolve to actual nodes (target: 90%+)
- **Enrichment depth**: average epistemic score across all nodes (target: 0.85+)
- **Convergence speed**: iterations until 95% of nodes settle (target: ≤ 3 iterations)
- **Build time regression**: Pass 0 stays under 200ms (current: 72ms)

### Qualitative
- **Context quality**: When Prep is used as context for coding tasks, does the enriched trace provide more relevant and accurate context than the current flat augmentation?
- **Self-model accuracy**: Can the system correctly describe its own architecture, identify subsystems, and flag stale documentation?
- **Developer trust**: Do epistemic scores correlate with developer assessment of augmentation quality?

---

## Open Research Questions

These are areas where our approach is novel or under-explored in the literature:

1. **Optimal scheduling for code-graph belief propagation**: BP research focuses on probabilistic graphical models. Our "messages" are rich text (summaries, domain tags). What's the right convergence criterion for text-valued beliefs? Semantic similarity between iterations?

2. **Epistemic score calibration**: How do we validate that a score of 0.92 actually means "well understood"? Need human evaluation studies comparing scores to developer assessment.

3. **Cross-modal graph enrichment**: Our graph has two "modalities" — code nodes (AST-derived) and doc nodes (regex-derived). Are there better fusion techniques from multimodal KG research (see Liu et al., 2025 VaLiK)?

4. **Diminishing returns of iterative enrichment**: At what point does re-enriching a node produce negligible new information? Can we predict this from graph topology (e.g., nodes with high degree converge faster)?

5. **Adversarial robustness**: If a doc contains intentionally misleading information (e.g., outdated README that was never updated), does the enrichment loop eventually identify and flag it, or does it propagate the misinformation?

---

## Timeline Summary

| Sprint | Focus | Duration | Dependencies |
|---|---|---|---|
| **Sprint 1** | Rust markdown extraction (Pass 0) | 3-4 days | None |
| **Sprint 2** | Augmenter quick wins (Pass 1) | 2 days | None (parallel with Sprint 1) |
| **Sprint 3** | LLM-guided re-trace (Pass 0.5) | 4-5 days | Sprints 1 + 2 |
| **Sprint 4** | Epistemic enrichment (Pass 2) | 8-10 days | Sprint 3 |
| **Sprint 5** | Cluster synthesis (Pass 3) | 5-6 days | Sprint 4 |
| **Sprint 6** | Continuous deepening (Pass 4+) | 6-8 days | Sprint 5 |

**Total estimated**: 28-35 days  
**Critical path**: Sprint 1 → Sprint 3 → Sprint 4 → Sprint 5 → Sprint 6  
**Quick wins** (Sprint 1 + 2) can ship independently in ~1 week.

---

## Related Documents

- `README.md` — Master strategy and thesis
- `MULTI_PASS_PIPELINE.md` — Detailed pass-by-pass prompt design
- `EPISTEMOLOGY_SCORING.md` — Scoring system deep dive
- `DOC_MINING_STRATEGY.md` — Documentation-specific enrichment patterns
- `RUST_ENRICHMENT_ANALYSIS.md` — Analysis of Rust pass underutilization + re-trace theory

---

## Academic References

1. Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization," Microsoft Research, 2024.
2. Lu & Wang, "KARMA: Leveraging Multi-Agent LLMs for Automated Knowledge Graph Enrichment," arXiv:2502.06472, 2025.
3. "Knowledge Graph Based Repository-Level Code Generation," arXiv:2505.14394, 2025.
4. Luo et al., "RepoAgent: An LLM-Powered Open-Source Framework for Repository-level Code Documentation Generation," EMNLP 2024, arXiv:2402.16667.
5. "LLM-empowered Knowledge Graph Construction: A Survey," arXiv:2510.20345, 2025.
6. Yedidia, Freeman, & Weiss, "Understanding Belief Propagation and its Generalizations," IJCAI 2003.
7. Elidan et al., "Residual Belief Propagation: Informed Scheduling for Asynchronous Message Passing," UAI 2006.
8. "A Review on Detecting and Managing Documentation Drift in Software," IEEE, 2025.
9. Aider, "Building a better repository map with tree sitter," aider.chat, 2023.
10. Pearl, "Probabilistic Reasoning in Intelligent Systems: Networks of Plausible Inference," Morgan Kaufmann, 1988.
