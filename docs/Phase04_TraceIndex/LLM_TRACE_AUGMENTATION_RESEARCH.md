# LLM Trace Augmentation — Research & Planning

> **Status:** Research Phase  
> **Created:** 2025-02-11  
> **Depends on:** Phase 04 (Trace Index), LLM_MODEL_CONFIGURATION.md, TRACEABILITY_AUTOMATION_STRATEGY.md  
> **Related:** ARCHITECTURE.md, CURATED_TRACEABILITY_FRAMEWORK.md

---

## 1. Problem Statement

Prep's trace index currently performs **static analysis only** — AST parsing of Python files to extract symbols, imports, and containment edges. This completes in ~4 seconds for a 670-file project but produces a structurally accurate yet semantically shallow graph.

**What's missing:**

| Gap | Impact |
|:----|:-------|
| No semantic summaries on nodes | MCP/RAG can't explain *what* a symbol does, only that it exists |
| No cross-file relationship semantics | Edges say "A imports B" but not *why* or how they collaborate |
| No confidence scoring | All edges are treated equally; no way to prioritize review |
| No trace embeddings | Trace nodes can't be found via semantic search |
| No codebase ontology | No high-level map of architectural patterns, domains, or intent |
| No `agent.md` generation | IDE agents get no pre-built orientation documents |

The trace graph is the **most fundamental knowledge layer** for the RAG — it is the structural skeleton that gives meaning to the embedding search. Without LLM augmentation, it's a graph of names and arrows with no understanding.

---

## 2. Architecture Overview: Two-Phase Pipeline

### Phase 1: Build-Time Augmentation (3 steps)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 1: STATIC TRACE                                          ~4 sec  │
│  ├── AST parsing (Python, TS/JS, Go, Rust — per language analyzer)     │
│  ├── Symbol extraction (functions, classes, methods)                    │
│  ├── Edge extraction (imports, contains, calls)                        │
│  ├── File hashing for staleness detection                              │
│  └── Output: trace_nodes.jsonl, trace_edges.jsonl, trace_manifest.json │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 2: LLM AUGMENTATION (Small/Fast Instruct Model)    ~30-90 min*  │
│  ├── Per-symbol summaries (1-2 sentence purpose description)           │
│  ├── Per-file role classification (entry point, utility, model, etc.)  │
│  ├── Edge semantic annotation ("imports for config loading")           │
│  ├── Confidence scoring (0.0-1.0) on each augmented attribute          │
│  ├── Module-level summaries (group symbols → module purpose)           │
│  ├── agent.md generation (per-directory orientation documents)         │
│  └── Output: trace_augmented.jsonl (overlay on trace_nodes/edges)      │
│                                                                         │
│  * Initial run on full codebase; incremental runs ~seconds per file    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 3: TRACE EMBEDDINGS                                    ~5 min*   │
│  ├── Embed augmented node summaries (symbol + context text)            │
│  ├── Embed agent.md documents                                          │
│  ├── Embed module-level summaries                                      │
│  ├── Store as trace_embeddings.npy + trace_documents.json              │
│  └── Register in Knowledge Base chunk counts ("Trace Chunks")          │
│                                                                         │
│  * Uses same embedding model as main index (nomic-embed-text)          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Phase 2: Deep Validation & Ontology (2 steps)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 4: REASONING VALIDATION (Large/Reasoning Model)       ~hours*    │
│  ├── Review lowest-confidence augmentations from Step 2                │
│  ├── Cross-reference with Prep's own retrieval (self-bootstrapping)  │
│  ├── Detect and flag outliers (legacy code, abandoned experiments)      │
│  ├── Verify architectural pattern claims                               │
│  ├── Resolve conflicting or ambiguous symbol purposes                  │
│  ├── Output: updated confidence scores, correction patches             │
│                                                                         │
│  * Runs on-demand or scheduled; GPU-intensive or BYOK                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 5: ONTOLOGY SYNTHESIS (Large Model + Prep tooling) ~hours*     │
│  ├── Build domain vocabulary (what concepts does this codebase use?)   │
│  ├── Map architectural layers and boundaries                           │
│  ├── Identify design patterns and their implementations                │
│  ├── Generate codebase-level orientation document                      │
│  ├── Produce taxonomy of modules by responsibility                     │
│  ├── Unify naming inconsistencies and identify conceptual drift        │
│  └── Output: trace_ontology.json, CODEBASE_OVERVIEW.md                │
│                                                                         │
│  * Epistemological layer — "what does this codebase know about itself?"│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Step 2 Deep Dive: Fast LLM Augmentation

### 3.1 Model Requirements

| Requirement | Rationale |
|:------------|:----------|
| **Instruct-tuned** | Must follow structured output instructions |
| **Fast inference** | Processing 500+ symbols; latency matters |
| **Small context sufficient** | Each prompt is self-contained (~2-4k tokens) |
| **Structured output** | JSON mode preferred for reliable parsing |
| **Local-first** | Ollama-served, no cloud dependency for core pipeline |

**Recommended models:** `ministral-3:3b`, `qwen2.5:3b`, `phi3:mini`  
**Fallback:** Any Ollama-compatible instruct model in the "Small Model" slot.

### 3.2 Prompt Design

Each augmentation task should be a **small, focused prompt** — never the whole repo.

#### Per-Symbol Summary

```
Input context (provided to model):
- Symbol name, kind, file_path, span
- Symbol source code (truncated to ~2000 chars)
- File-level context (imports, neighboring symbols)
- Containing module's existing summary (if available from prior pass)

Prompt:
  You are analyzing a symbol from a codebase. Provide:
  1. A 1-2 sentence summary of what this symbol does
  2. Its primary role: [entry_point | handler | utility | model | config | test | internal]
  3. Confidence (0.0-1.0) in your summary accuracy

  Respond in JSON: {"summary": "...", "role": "...", "confidence": 0.85}

Expected tokens per call: ~150-300 output
```

#### Per-File Role Classification

```
Input context:
- File path, imports list, symbol names and kinds
- First 50 lines of file (module docstring, top-level code)

Prompt:
  Classify this file's role in the codebase:
  1. Primary responsibility (1 sentence)
  2. Category: [api | core | model | utility | config | test | script | docs | ui]
  3. Key exports (top 3 most important symbols)
  4. Confidence (0.0-1.0)

Expected tokens per call: ~100-200 output
```

#### Module-Level Summary (directory aggregation)

```
Input context:
- Directory path
- List of files with their summaries (from prior pass)
- Import relationships between files in this directory

Prompt:
  Summarize the purpose of this module/directory:
  1. Module purpose (2-3 sentences)
  2. Key responsibilities
  3. Primary consumers (who imports from here?)
  4. Confidence (0.0-1.0)

Expected tokens per call: ~200-400 output
```

#### agent.md Generation

```
Input context:
- Module summary (from above)
- File list with roles
- Key symbol summaries
- Dependency graph (imports in/out)

Prompt:
  Generate a concise orientation document for an AI agent working in this
  directory. Include:
  1. What this module does (2-3 sentences)
  2. Key files and their purposes (bullet list)
  3. Important patterns or conventions
  4. Common modification points
  5. Dependencies and dependents

Expected tokens per call: ~500-1000 output
```

### 3.3 Processing Order

The augmentation must respect dependency order:

```
Pass 1: Per-symbol summaries (embarrassingly parallel per file)
Pass 2: Per-file role classification (uses symbol summaries)
Pass 3: Module-level summaries (uses file summaries, can be bottom-up)
Pass 4: agent.md generation (uses module + file summaries)
Pass 5: Edge semantic annotation (uses source + target summaries)
```

### 3.4 Confidence Scoring

Every LLM-generated attribute carries a confidence score:

| Score Range | Meaning | Phase 2 Priority |
|:------------|:--------|:-----------------|
| **0.9-1.0** | High confidence — clear purpose, well-documented | Skip (unless contradicted) |
| **0.7-0.89** | Medium — likely correct but ambiguous | Low priority |
| **0.5-0.69** | Low — uncertain, needs review | Medium priority |
| **0.0-0.49** | Very low — model is guessing | **High priority** for Phase 2 |

**Confidence factors the fast model should consider:**
- Does the symbol have a docstring? (+confidence)
- Is the name descriptive? (+confidence)
- Is the code short and focused? (+confidence)
- Is there dead code / commented-out code? (-confidence)
- Are there multiple unrelated responsibilities? (-confidence)
- Is this in a test/fixture directory? (flag as test code)

### 3.5 Incremental Strategy

After initial full-codebase run:

1. **Changed files only:** Re-augment symbols in files where `file_hash` differs from last run
2. **Cascade updates:** If a file's summary changes significantly, re-augment its module summary
3. **agent.md refresh:** Only regenerate if >30% of constituent file summaries changed
4. **Edge re-annotation:** Only for edges touching changed nodes

**Expected incremental cost:** 1-5 LLM calls per changed file (~2-10 seconds).

### 3.6 Storage Format

Augmentation data is stored as an overlay on the existing trace index:

```
{index_dir}/
├── trace_nodes.jsonl          # Static trace (unchanged)
├── trace_edges.jsonl          # Static trace (unchanged)
├── trace_manifest.json        # Static trace (unchanged)
├── trace_augmented.jsonl      # NEW: augmentation overlay
├── trace_agent_md/            # NEW: generated agent.md files
│   ├── src/prep/core/agent.md
│   ├── src/prep/dashboard/agent.md
│   └── ...
├── trace_embeddings.npy       # NEW: embedded trace chunks
├── trace_documents.json       # NEW: trace chunk documents
└── trace_augment_manifest.json # NEW: augmentation metadata
```

`trace_augmented.jsonl` format:
```json
{
  "node_id": "node-abc123",
  "summary": "Handles HTTP POST requests for project index builds...",
  "role": "handler",
  "confidence": 0.92,
  "augmented_at": "2025-02-11T12:00:00Z",
  "model": "ministral-3:3b",
  "version": 1
}
```

---

## 4. Step 3 Deep Dive: Trace Embeddings

### 4.1 What Gets Embedded

| Source | Embedding Text | Priority |
|:-------|:---------------|:---------|
| Symbol summary + source snippet | `"[function:build_project] Triggers project index build. Located in src/prep/server.py:497-520"` | High |
| File summary | `"[file:server.py] FastAPI server: project management, search, build orchestration"` | High |
| Module summary | `"[module:src/prep/core] Core engine: indexing, embedding, trace building, chunking"` | High |
| agent.md content | Full agent.md text, chunked | High |
| Edge annotations | `"server.py imports index.py for CodeIndex build orchestration"` | Medium |

### 4.2 Integration with Main Index

Trace embeddings should be searchable alongside code/instruction chunks:

- **Same embedding model** (nomic-embed-text) for consistent vector space
- **Stored separately** (trace_embeddings.npy) but merged at search time
- **Chunk metadata** includes `source_type: "trace"` for filtering
- **Knowledge Base Status** shows count as "Trace Chunks"

### 4.3 Search Fusion

At query time, Prep can blend results from three sources:

```
Query: "how does the build process work?"
    │
    ├── Code chunks (embeddings.npy)     → code implementation details
    ├── Instruction chunks (embeddings.npy, docs) → design docs, plans
    └── Trace chunks (trace_embeddings.npy) → structural summaries, agent.md
```

Ranking fusion strategy: reciprocal rank fusion (RRF) or score-weighted interleaving.

---

## 5. Step 4 Deep Dive: Reasoning Validation (Phase 2)

### 5.1 Why a Second Pass?

The fast model (Step 2) optimizes for throughput — it processes hundreds of symbols quickly but makes mistakes:

- **Superficial summaries:** "This function processes data" (unhelpful)
- **Misidentified roles:** Confusing a utility with an entry point
- **Missed relationships:** Not recognizing that two modules implement the same pattern
- **Overconfident on boilerplate:** High confidence on generated/template code
- **Blind to codebase conventions:** Can't see patterns across the whole graph

### 5.2 Model Requirements

| Requirement | Rationale |
|:------------|:----------|
| **Reasoning capability** | Must evaluate claims, not just generate text |
| **Larger context window** | Needs to see multiple related symbols together |
| **Self-consistency checking** | Should detect contradictions in the graph |
| **Optional: reasoning traces** | `<think>` mode helpful for complex analysis |

**Recommended models:** `qwen3:30b`, `deepseek-coder-v2`, `mistral-nemo`, or BYOK (Claude, GPT-4)  
**Uses the "Large Model" slot** from LLM_MODEL_CONFIGURATION.md.

### 5.3 Processing Strategy

Phase 2 does NOT re-process every node. It targets:

1. **Lowest confidence items first** (confidence < 0.5)
2. **High-importance nodes** (many inbound edges, entry points, exports)
3. **Contradiction detection** (conflicting summaries on related nodes)
4. **Outlier detection** (nodes that don't fit any module pattern)

#### Outlier Handling

The reasoning model must be prepared to recognize:

| Outlier Type | Signal | Appropriate Action |
|:-------------|:-------|:-------------------|
| **Legacy code** | No recent modifications, few importers, deprecated patterns | Flag as legacy, low priority |
| **Abandoned experiments** | Isolated module, no tests, incomplete implementation | Flag as abandoned, suggest removal |
| **Generated code** | Repetitive patterns, auto-gen comments | Flag as generated, skip deep analysis |
| **Vendored dependencies** | In vendor/ or third_party/ | Flag as vendored, skip |
| **Dead code** | No importers, unreachable | Flag as dead code |

These flags prevent wasting expensive reasoning model tokens on code that doesn't matter.

### 5.4 The Hallucination Bootstrap Problem

**Critical risk:** If Phase 2 uses Prep retrieval that includes Phase 1 LLM-augmented
data, it creates a circular dependency that launders hallucinations into "evidence":

```
Phase 1 (fast model) generates summary: "handles JWT authentication"  ← WRONG
    ↓
Phase 2 queries Prep: "what handles authentication?"
    ↓
Prep returns the Phase 1 summary as a search hit  ← CONFIRMING ITS OWN HALLUCINATION
    ↓
Phase 2 reasoning model: "confirmed — this handles JWT auth" ← LAUNDERED HALLUCINATION
```

This is not hypothetical — it is the default behavior if we naively use Prep search
during validation. The reasoning model would treat LLM-generated text as ground truth
because it appears in the retrieval results indistinguishably from real source code.

### 5.5 Evidence Tiers (Solution)

The fix is to define **restricted retrieval scopes** that Phase 2 queries against:

| Tier | Contents | Contamination Risk | Use Case |
|:-----|:---------|:-------------------|:---------|
| **Tier 0: Ground Truth** | Raw source code chunks + raw .md docs ONLY. Zero LLM-generated content. | **None** — purely deterministic data | Phase 2 validation (primary evidence) |
| **Tier 1: Verified** | Ground truth + augmentations with confidence ≥ 0.9 that Phase 2 has already reviewed and confirmed | **Minimal** — only high-confidence, validated items | Phase 2 cross-referencing (supplementary, clearly labeled as "model claim") |
| **Tier 2: Full** | Everything including low-confidence augmentations, agent.md, ontology | **Present** — contains unverified LLM output | Normal user search (default experience) |

**Phase 2 MUST use Tier 0 as its primary evidence source.** It may optionally consult
Tier 1 but ONLY when:
- The item is explicitly labeled as "another model's claim" in the prompt
- The reasoning model is asked to evaluate the claim, not treat it as fact
- The Tier 1 item has already been validated in a prior Phase 2 pass

**Implementation:**

```
Phase 2 Validation Prompt (corrected):

  You are validating an AI-generated summary of a code symbol.
  
  CLAIMED (unverified, from fast model):
    "Handles user authentication via JWT tokens"
  
  GROUND TRUTH EVIDENCE (source code + docs only, no AI summaries):
    [Prep Tier 0 search results for "authentication JWT"]
    [Actual source code of the symbol being validated]
    [Static trace: import edges, callers, file path]
  
  PRIOR MODEL CLAIMS (treat as hypotheses, not facts):
    [Tier 1 neighbor summaries, if any, clearly labeled]
  
  Based ONLY on the ground truth evidence:
  1. Is the claimed summary supported by the actual source code? (yes/partially/no)
  2. If not, what does the source code actually do?
  3. Confidence in your assessment (0.0-1.0)
  4. Should any related claims be flagged for re-review?
```

**Key architectural constraint:** The embedding index (`embeddings.npy` + `documents.json`)
is already LLM-free — it contains only chunked source code and raw documentation. This IS
Tier 0. The trace embeddings (`trace_embeddings.npy`) contain LLM-augmented content and
must be excluded from Tier 0 queries.

The implementation is straightforward because the storage is already separated:

```python
# Tier 0: search only the main index (already LLM-free)
results = index.search(query, k=10)  # embeddings.npy only

# Tier 1: search main index + high-confidence trace embeddings
results = index.search(query, k=10, include_trace=True, min_trace_confidence=0.9)

# Tier 2: search everything (default user experience)
results = index.search(query, k=10, include_trace=True, min_trace_confidence=0.0)
```

**Estimated implementation effort:** ~1-2 days.
- Add `evidence_tier` or `include_trace` + `min_trace_confidence` params to search API (~50 LOC)
- Phase 2 orchestrator always queries with Tier 0 by default (~5 LOC)
- Prompt templates clearly separate ground truth from model claims (~20 LOC)

### 5.6 Scheduling & Budget Controls

Phase 2 is expensive and should run under explicit user control:

**Trigger modes:**
- **On-demand:** User clicks "Deep Analyze" in dashboard
- **Scheduled:** Cron-style schedule (e.g., nightly, weekly) configured in Global Settings
- **Threshold-triggered:** After >N% of files changed since last run (configurable)
- **Never automatically** on every file save

**Budget controls (all configurable in Global Settings → Deep Analysis):**
- **Max tokens per session:** Default 50,000 (prevents runaway costs)
- **Max wall-clock time:** Default 30 minutes (prevents overnight GPU lock)
- **Max items per session:** Default 100 nodes (prevents processing entire codebase)
- **Priority ordering:** Lowest confidence first (default), or highest-connectivity first
- **Cost estimate preview:** Before starting, show estimated tokens/time based on queue size

**Schedule configuration (Global Settings UI):**

```
┌─ Deep Analysis Schedule ─────────────────────────────────────┐
│                                                               │
│  ○ Manual only (run from dashboard)                          │
│  ○ After major changes (>20% files changed)                  │
│  ● Scheduled                                                  │
│    └─ Frequency: [Weekly     ▼]                              │
│       Day:       [Sunday     ▼]                              │
│       Time:      [02:00 AM   ▼]                              │
│                                                               │
│  Budget per session:                                          │
│  ├─ Max tokens:    [50,000    ]                              │
│  ├─ Max time:      [30 min    ]                              │
│  └─ Max items:     [100       ]                              │
│                                                               │
│  Model: [Uses Large Model slot from AI Models settings]      │
│  Last run: 2025-02-09 02:14 AM — 47 items validated          │
│  Next run: 2025-02-16 02:00 AM (estimated)                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Step 5 Deep Dive: Ontology Synthesis

### 6.1 What is the Ontology?

The ontology is a **high-level semantic map** of the codebase:

```json
{
  "domains": [
    {
      "name": "Index Engine",
      "description": "Core indexing pipeline: file scanning, chunking, embedding, and persistence",
      "modules": ["src/prep/core/index.py", "src/prep/core/chunking.py", "src/prep/core/embedder.py"],
      "key_concepts": ["chunks", "embeddings", "manifest", "incremental build"],
      "entry_points": ["CodeIndex.build()"]
    },
    {
      "name": "Trace System",
      "description": "Structural code graph: symbol extraction, edge resolution, coverage analysis",
      "modules": ["src/prep/core/trace.py"],
      "key_concepts": ["nodes", "edges", "symbols", "imports", "coverage"],
      "entry_points": ["TraceBuilder.build()", "compute_trace_coverage()"]
    }
  ],
  "patterns": [
    {
      "name": "Atomic Build",
      "description": "Write to temp directory, validate, then swap into place",
      "instances": ["CodeIndex.build()", "TraceBuilder._write_atomic()"]
    }
  ],
  "vocabulary": {
    "chunk": "A segment of source code or documentation, typically 50-500 lines, used as the unit of embedding and retrieval",
    "trace": "The structural graph of symbols and their relationships (imports, contains, calls)",
    "manifest": "JSON metadata file describing a build's configuration, counts, and file hashes"
  }
}
```

### 6.2 Epistemological Layer

Beyond "what exists" (ontology), this step answers "what does the codebase know about itself?":

- **Self-documentation quality:** Which modules have good docs vs. none?
- **Naming consistency:** Are the same concepts named differently in different modules?
- **Architectural coherence:** Do module boundaries match domain boundaries?
- **Knowledge gaps:** What parts of the codebase has no one explained?

### 6.3 Output Artifacts

| Artifact | Purpose | Consumer |
|:---------|:--------|:---------|
| `trace_ontology.json` | Machine-readable domain map | Prep search ranking, MCP tools |
| `CODEBASE_OVERVIEW.md` | Human-readable orientation | Developers, AI agents |
| `agent.md` files | Per-directory AI orientation | IDE agents (Windsurf, Cursor) |
| Vocabulary index | Concept definitions | Search query expansion |

---

## 7. Data Flow Integration

### 7.1 Build Pipeline (Full)

```
prep build --project <id>
    │
    ├── [Parallel] Code Index Build (existing)
    │   ├── Scan → Chunk → Embed → Write
    │   └── Output: documents.json, embeddings.npy, manifest.json
    │
    └── [Parallel] Trace Pipeline
        ├── Step 1: Static Trace (~4s)
        │   └── Output: trace_nodes.jsonl, trace_edges.jsonl
        │
        ├── Step 2: LLM Augmentation (if small model configured)
        │   ├── Reads: trace_nodes, trace_edges, source files
        │   ├── Incremental: only changed files + cascading updates
        │   └── Output: trace_augmented.jsonl, trace_agent_md/
        │
        └── Step 3: Trace Embeddings (if Step 2 complete)
            ├── Reads: trace_augmented, agent.md files
            └── Output: trace_embeddings.npy, trace_documents.json

prep deep-analyze --project <id>  (separate command, on-demand)
    │
    ├── Step 4: Reasoning Validation
    │   ├── Reads: trace_augmented (low confidence items)
    │   ├── Uses: Prep search API (self-bootstrapping)
    │   └── Output: updated trace_augmented.jsonl
    │
    └── Step 5: Ontology Synthesis
        ├── Reads: all trace data, module summaries
        └── Output: trace_ontology.json, CODEBASE_OVERVIEW.md
```

### 7.2 Dashboard Progress Reporting

The dashboard should show distinct progress bars for each active step:

```
┌─ Cross-Reference Build ──────────────────────────────────┐
│  ✓ Static Trace         100% (670/670)              4.2s │
│  ● LLM Augmentation      34% (228/670 symbols)    12:45 │
│  ○ Trace Embeddings       — (waiting)                    │
└──────────────────────────────────────────────────────────┘
```

For Phase 2 (when running):
```
┌─ Deep Analysis ──────────────────────────────────────────┐
│  ● Validation            12% (15/124 low-confidence)     │
│  ○ Ontology Synthesis     — (waiting)                    │
│  Budget: 12,450 / 50,000 tokens used                     │
└──────────────────────────────────────────────────────────┘
```

### 7.3 API Extensions

New endpoints for augmentation:

```
POST /projects/{id}/trace/augment          Start augmentation (Step 2)
POST /projects/{id}/trace/embed            Start trace embedding (Step 3)
POST /projects/{id}/trace/deep-analyze     Start Phase 2 (Steps 4+5)
GET  /projects/{id}/trace/augment/status   Augmentation progress + stats

GET  /projects/{id}/trace/ontology         Get ontology data
GET  /projects/{id}/trace/agent-md/{path}  Get agent.md for a directory
```

---

## 8. Cost & Performance Estimates

### Phase 1 Costs (per 670-file project)

| Step | Calls | Tokens/Call | Total Tokens | Time (local 3B) | Time (local 7B) |
|:-----|:------|:------------|:-------------|:-----------------|:-----------------|
| Symbol summaries | ~2000 | ~300 | ~600k | ~15 min | ~30 min |
| File roles | ~670 | ~200 | ~134k | ~5 min | ~10 min |
| Module summaries | ~50 | ~400 | ~20k | ~1 min | ~2 min |
| agent.md | ~50 | ~800 | ~40k | ~2 min | ~4 min |
| Edge annotations | ~1000 | ~150 | ~150k | ~7 min | ~15 min |
| **Total** | **~3770** | | **~944k** | **~30 min** | **~61 min** |

### Phase 1 Incremental (10 changed files)

| Step | Calls | Time |
|:-----|:------|:-----|
| Re-augment changed symbols | ~30 | ~5 sec |
| Re-classify changed files | ~10 | ~2 sec |
| Re-summarize affected modules | ~3 | ~1 sec |
| **Total** | **~43** | **~8 sec** |

### Phase 2 Costs (targeted review)

| Step | Calls | Tokens/Call | Budget |
|:-----|:------|:------------|:-------|
| Low-confidence validation | ~124 | ~1000 | ~124k tokens |
| Ontology synthesis | ~20 | ~2000 | ~40k tokens |
| **Total** | **~144** | | **~164k tokens** |

---

## 9. Risk Analysis

| Risk | Severity | Mitigation |
|:-----|:---------|:-----------|
| **Hallucination bootstrap** | **Critical** | Evidence Tier architecture (§5.4-5.5): Phase 2 queries Tier 0 (ground truth only); LLM-augmented content never appears as evidence during validation |
| **LLM hallucination in summaries** | High | Confidence scoring in Phase 1; Phase 2 validation against source code; never trust augmentations without ground truth evidence |
| **Performance regression on large repos** | High | Strict incremental strategy; budget caps; async processing |
| **Model quality variance** | Medium | Test suite with fixture repos; minimum quality thresholds |
| **Abandoned code wasting tokens** | Medium | Outlier detection in Phase 2; configurable skip patterns |
| **Tier 1 contamination creep** | Medium | Tier 1 only includes items Phase 2 has explicitly validated; always labeled as "model claim" in prompts; re-validation on schedule |
| **Storage bloat** | Low | Overlay format; augmentation is ~10% of source size |
| **API key costs (BYOK)** | Low | Token budgets; user controls; local-first default |

---

## 10. Implementation Roadmap

### Milestone 1: Augmentation Infrastructure (1-2 weeks)
- [ ] `TraceAugmenter` class with prompt templates
- [ ] LLM client integration (use existing Small Model slot)
- [ ] `trace_augmented.jsonl` storage format
- [ ] Incremental augmentation (hash-based skip)
- [ ] Progress reporting via SSE

### Milestone 2: Per-Symbol + Per-File Augmentation (1 week)
- [ ] Symbol summary prompt + parser
- [ ] File role classification prompt + parser
- [ ] Confidence scoring integration
- [ ] Dashboard: augmentation progress in Cross-Reference panel

### Milestone 3: Module Summaries + agent.md (1 week)
- [ ] Directory aggregation logic
- [ ] Module summary prompt + parser
- [ ] agent.md generation prompt + writer
- [ ] Dashboard: browse agent.md files

### Milestone 4: Trace Embeddings + Evidence Tiers (1-2 weeks)
- [ ] Trace document preparation (summaries → embedding text)
- [ ] Embedding with shared embedder
- [ ] `trace_embeddings.npy` + `trace_documents.json` storage
- [ ] Search fusion (blend trace + code + instruction results)
- [ ] Knowledge Base Status: "Trace Chunks" counter (live)
- [ ] **Evidence Tier system:** `evidence_tier` / `include_trace` + `min_trace_confidence` params on search/context API
- [ ] Tier 0 = main index only (default for Phase 2); Tier 1 = + validated augmentations; Tier 2 = everything (default for users)

### Milestone 5: Phase 2 — Reasoning Validation (2 weeks)
- [ ] **Evidence-safe retrieval:** Phase 2 orchestrator always queries Tier 0; Tier 1 items labeled as "model claim" in prompts
- [ ] Validation prompt design with ground-truth / model-claim separation
- [ ] Priority queue (lowest confidence first)
- [ ] Outlier detection (legacy, abandoned, generated code)
- [ ] Token budget management
- [ ] Dashboard: deep analysis panel + progress

### Milestone 6: Global Settings — Deep Analysis UI (1 week)
- [ ] `DeepAnalysisSettings` component in Global Settings tab
- [ ] Schedule configuration (manual / threshold / cron)
- [ ] Budget controls (max tokens, max time, max items)
- [ ] Last run / next run status display
- [ ] Per-project override toggle (in Project Settings)

### Milestone 7: Phase 2 — Ontology Synthesis (2 weeks)
- [ ] Domain extraction from module summaries
- [ ] Pattern detection across codebase
- [ ] Vocabulary index generation
- [ ] `CODEBASE_OVERVIEW.md` generation
- [ ] `trace_ontology.json` schema + writer
- [ ] MCP tool: `get_codebase_overview`

---

## 11. Open Questions

### Resolved

1. **Should augmentation block the trace build or run as a follow-up job?**
   - **Resolved:** Follow-up async job. Static trace is always fast; augmentation is optional.

2. **Should Phase 2 use Prep retrieval? Won't it compound hallucinations?**
   - **Resolved:** Yes it should, but ONLY via Evidence Tiers (§5.4-5.5). Phase 2 queries Tier 0 (ground truth: raw source code + docs, zero LLM content). LLM-augmented content is never presented as evidence — only as "model claims" to evaluate. See §5.5 for full architecture.

3. **Should agent.md files be committed to the repo?**
   - **Resolved:** Option A by default (generated into index_dir, not in repo). Option B as user toggle.

### Open

4. **How do we handle multi-language augmentation?**
   - Start with Python-only (existing analyzer). TS/JS next via tree-sitter. Augmentation prompts are language-agnostic once symbols are extracted.

5. **How to handle very large codebases (>5000 files)?**
   - Batch processing with resume capability
   - Priority: augment most-connected files first
   - Skip files below a complexity threshold

6. **Should the ontology inform search ranking?**
   - Yes — if a query mentions a domain concept, boost chunks from that domain's modules.
   - This is a natural extension of the existing `role_weights` system.

7. **Rate limiting for BYOK providers?**
   - Implement configurable rate limits per endpoint
   - Default: 10 req/sec for local Ollama, 3 req/sec for cloud APIs

8. **Should Tier 1 items ever be demoted back to unverified?**
   - If the source code changes significantly (hash mismatch), the validation should be invalidated.
   - Recommendation: auto-demote to unverified on file hash change; re-validate in next Phase 2 run.

---

## 12. Research References

- **GraphRAG (Microsoft):** Multi-stage summarization of graph communities → global answers  
  https://arxiv.org/abs/2404.16130

- **CodeGraph:** Graph-based code understanding with LLM augmentation  
  https://arxiv.org/abs/2308.09687

- **RepoAgent:** Automated documentation generation via multi-agent LLM  
  https://arxiv.org/abs/2402.16667

- **TraceBERT:** Pre-trained BERT for traceability link recovery  
  https://arxiv.org/abs/2102.04411

- **Existing Prep docs:**
  - `TRACEABILITY_AUTOMATION_STRATEGY.md` — Options 0-4 spectrum (this doc extends Option 3+4)
  - `LLM_MODEL_CONFIGURATION.md` — Model slots and tiered processing strategy
  - `CURATED_TRACEABILITY_FRAMEWORK.md` — Manual traceability layer (complementary)
  - `ARCHITECTURE.md` — System component diagram and data flow
