# Phase 22: Trace Epistemology — Multi-Pass Knowledge Crystallization

**Status**: Design  
**Depends on**: Phase 1 (Trace Graph), Phase 5 (Augmentation), Phase 16 (Context Intelligence)  
**Owner**: —

---

## The Core Thesis

Current trace augmentation treats each file as an **isolated classification task**: the 3b model sees one file, produces a summary and role, done. The 14b model validates the summary, done. This is flat. It produces accurate *descriptions* but not *understanding*.

**Epistemological augmentation** is the idea that the trace should build a **self-model** — a layered, cross-referenced understanding of what the codebase *is*, what it *intends*, what's *active* vs *shelved*, and how concepts link across code and documentation. This cannot happen in a single pass. It requires **iterative reasoning passes** where each pass deepens understanding by leveraging what previous passes discovered.

The key insight: **if the reasoning passes use CoDRAG itself as context, they are never truly "done" — every augmented node becomes context for every other node.** The trace becomes a living knowledge base that refines itself.

---

## Why This Matters

Modern AI-assisted codebases have a distinctive pattern: **large quantities of `.md` files** containing design docs, research findings, architecture decisions, planning docs, shelved ideas, and sometimes outright junk. These docs are epistemic gold — they explain *why* code exists, *what was considered and rejected*, and *where the project is heading*. But they're also noisy, contradictory, and stale.

Current augmentation treats `FREEMIUM_IMPLEMENTATION_PLAN.md` the same as `PriceFormatter.swift` — both get a one-line summary and a role tag. This misses:

- **Cross-references**: The plan doc references `AdConfiguration.swift` and `FeatureFlags.swift` — these links aren't captured
- **Temporal status**: Is this plan active? Completed? Shelved? The doc might say "Status: Complete" but the code might not reflect it
- **Decision chains**: Research doc → findings doc → architecture decision → implementation — this chain exists in file naming conventions but isn't explicit in the trace
- **Contradictions**: Two docs might describe conflicting approaches — the trace should flag this
- **Staleness**: A doc referencing `InterstitialAdController.swift` when the file is now `InterstitialAdManager.swift` — evidence of drift

---

## Architecture: The Multi-Pass Pipeline

### Pass 0: Structural Trace + Document Extraction (Rust Engine — enhanced)
**What it does**: Parses code into nodes (files, symbols) and edges (imports, contains, calls).  
**Output**: `trace_nodes.jsonl`, `trace_edges.jsonl`  
**No LLM involved.** This is the factual skeleton.

**Current gap (identified in `RUST_ENRICHMENT_ANALYSIS.md`)**: The Rust engine currently does **nothing** for `.md` files — `detect_language()` returns `None`, no content is read, no structure is extracted. Docs are bare file nodes floating disconnected in the graph. This is the single biggest underutilization in the pipeline.

**Enhancement**: Add a `markdown.rs` analyzer to the Rust parser that extracts:
- **Section headers** → `section` nodes with `contains` edges from the file
- **Backtick file references** → `references` edges to code file nodes
- **Markdown links** → `links_to` edges to other doc nodes
- **Status markers** (✅, ⏳, ❌) → metadata on the file node
- **Document metrics** (line count, section count, reference density)

This costs ~25ms for 200 docs (negligible vs the 72ms code parse) and gives docs **structural graph connections** for the first time. The entire enrichment pipeline downstream benefits.

### Pass 1: Fast Catalogue (3b model — existing, minor enhancements)
**What it does**: One LLM call per node. Produces summary + role + confidence.  
**Output**: `trace_augmented.jsonl` (overlay)  
**Design philosophy**: Keep this fast, cheap, and shallow. The 3b model's job is **triage**, not understanding. It's answering: "What does this file appear to do?" This is already good and we don't want to stress the 3b model further.

**What we should NOT change about Pass 1**:
- Don't feed it neighbors (too slow, 3b can't reason about relationships anyway)
- Don't raise the 500-char summary cap (the 3b truncates poorly with longer output)

**What we CAN tune**:
- Better role hints from file path heuristics (e.g., `Docs/` → `documentation`, not `utility`)
- Separate prompt templates for `.md` files vs code files (the 3b already does OK here but could be nudged)
- Read 100 lines instead of 30 for `.md` files (one-line change, docs front-load value in headers)
- Add a lightweight `related_files` field to the output — the 3b already sees file paths and imports, asking "what other files might this relate to?" is a cheap addition that feeds Pass 0.5

### Pass 0.5: LLM-Guided Rust Re-Trace (NEW — the hypothesis-and-test loop)
**What it does**: Takes the 3b's `related_files` hypotheses from Pass 1 and feeds them back to Rust for **validation and graph enrichment**. See `RUST_ENRICHMENT_ANALYSIS.md` for full analysis.

The pattern: **LLM hypothesizes, Rust validates.**
- LLM says "InterstitialAdManager.swift relates to AdConfiguration.swift" → Rust checks both nodes exist → adds `inferred` edge
- LLM says "ADS_FRAMEWORK_STATUS.md documents AdManager.swift" → Rust confirms the backtick reference from Pass 0 → mutual confirmation, confidence → 1.0
- LLM says "FileA relates to NonExistentFile.swift" → Rust discards (node doesn't exist)

**Cost**: Nearly zero. Rust validates pre-computed hypotheses against the in-memory graph. ~5ms for 500 hypotheses.

**Output**: Enriched graph with `inferred` edges (stored in `trace_inferred_edges.jsonl`, separate from structural edges). By the time Pass 2 runs, every node has a rich neighborhood of both factual and semantic connections.

**Safeguards against hallucination**:
- Inferred edges use `kind: "inferred"`, never override structural edges
- Confidence gating: only edges with LLM confidence >= 0.7 are added
- Decay/pruning: unconfirmed inferences are removed after 2 enrichment passes
- Additive only: LLM can never delete or override parser-derived edges

### Pass 2: Epistemic Enrichment (14b model — NEW, replaces simple validation)
**What it does**: The 14b model receives:
1. The target node's source content
2. The 3b's initial summary from Pass 1
3. **Summaries of neighbor nodes** (from trace edges — imports, callers, callees, AND inferred edges from Pass 0.5)
4. **The trace graph structure** around this node (structural + inferred edges)
5. **Doc references** extracted by Rust in Pass 0 (backtick refs, markdown links)

**What it produces** (expanded `AugmentationEntry`):

```json
{
  "node_id": "file:HomeColabApp/Components/Ads/Interstitial/InterstitialAdManager.swift",
  
  "summary": "...(3b summary, potentially corrected/expanded)...",
  "one_liner": "Full-screen ad manager: 1/session, 5min cooldown, 10-view gate",
  "role": "core",
  
  "epistemic": {
    "domain_tags": ["monetization", "ads", "interstitial"],
    "architecture_layer": "infrastructure",
    "design_pattern": "singleton-coordinator",
    "subsystem": "ad-framework",
    
    "depends_on": ["AdConfiguration", "AdPlacementCoordinator"],
    "depended_by": ["PropertyWorkspaceView (via .interstitialTrigger modifier)"],
    
    "doc_references": [
      "Docs/ADS_FRAMEWORK_STATUS.md",
      "Docs/ADS_QUICK_REFERENCE.md"
    ],
    
    "status": "active-stubbed",
    "tech_debt": ["SDK integration stubbed with TODO comments", "No real GADInterstitialAd loading"],
    "staleness_risk": "low",
    
    "epistemic_confidence": 0.92,
    "reasoning_depth": 2
  }
}
```

**Key difference from current validation**: The 14b doesn't just say "yes/no, summary is correct." It **enriches** with cross-references, architectural context, and epistemic metadata that the 3b couldn't produce.

### Pass 3+: Continuous Deepening (14b model — NEW, iterative)
This is where it gets interesting. After Pass 2 enriches individual nodes, **Pass 3 runs cluster-level reasoning**:

1. **Group nodes by domain tags** (from Pass 2): all `monetization` files together, all `authentication` files together
2. **Feed the 14b a cluster of summaries** (not full source — just the enriched summaries from Pass 2)
3. **Produce module-level synthesis**:
   - Module purpose and boundaries
   - Entry points and data flow
   - Internal dependencies
   - Cross-module interfaces
   - Status (complete? in-progress? shelved?)

**Pass 4+ (continuous)**: Re-examine nodes whose neighbors have been enriched since they were last processed. This creates a **convergence loop**:
- Node A gets enriched in Pass 2
- Node B (which depends on A) gets enriched in Pass 3, now understanding A's role
- Node A gets re-examined in Pass 4 because B's enrichment added context about how A is *used*
- Eventually, confidence and epistemic scores converge and the loop self-terminates

**Convergence criterion**: A node is "settled" when:
- `epistemic_confidence >= 0.95` AND
- `confidence >= 0.95` AND
- No neighbor's enrichment has changed since this node was last processed
- We call this a node's **epistemic stability score**

---

## The Documentation Problem (Epistemic Mining)

### The Challenge
AI-assisted projects generate massive `Docs/` folders. In the HomeColab project we just examined, there are hundreds of `.md` files across:
- `Docs/2.0/BusinessAPP/Phase01-06/` — phased research and strategy
- `Docs/Architectural-Audit/` — risk assessments and migration plans
- `Docs/Design/` — UI specs, style guides, voting behavior
- `Docs/Developer/` — conventions, Firebase audit, compatibility notes
- `Docs/ADS_*.md` — ad framework documentation

These docs contain **epistemic gold**:
- **Decisions**: "We chose CSV import over API integration because..."
- **Research findings**: "Competitor analysis shows X is the gap"
- **Shelved ideas**: "De-prioritized: MLS API integration (too expensive)"
- **Status markers**: "Status: Research Complete", "✅ Complete", "⏳ Pending"
- **Cross-references**: "See `1_Link_unfurrling_findings.md`", "Related: `MONETIZATION_STRATEGY.md`"

### The Strategy: Document-Aware Enrichment

**Step 1: Document Classification (Pass 1 improvement)**

Add a separate prompt template for `.md` files in the 3b pass:

```
Instead of: "Classify this file's role in the codebase"
Use:        "Classify this document's purpose and current status"
```

Produce:
- `doc_type`: one of `research`, `design_spec`, `architecture_decision`, `plan`, `guide`, `reference`, `changelog`, `meeting_notes`, `stub`
- `doc_status`: one of `active`, `completed`, `shelved`, `superseded`, `draft`, `unknown`
- `references_files`: list of code files mentioned in the doc

**Step 2: Cross-Reference Extraction (Pass 2)**

The 14b model reads each doc and extracts:
- **Explicit references**: file paths, class names, function names mentioned in the doc
- **Implicit references**: "the ad framework" → maps to `Components/Ads/*`
- **Decision outcomes**: "Verdict: X" or "Decision: Y" → becomes a `decision` edge in the trace
- **Status assertions**: "Status: Complete" → cross-check against actual code state

These become new **trace edges** of type `documents`, `decides`, `supersedes`:
```
doc:Phase01/01_TASKS.md --[documents]--> file:Managers/FirestoreManager.swift
doc:Phase03/07_ARCHITECTURE_DECISION.md --[decides]--> subsystem:shared-components
doc:LISTING_CARD_MIGRATION_COMPLETE.md --[supersedes]--> doc:LISTING_CARD_REFACTOR_GUIDE.md
```

**Step 3: Staleness Detection (Pass 3+)**

Cross-reference doc assertions against code reality:
- Doc says "InterstitialAdController" but file is now `InterstitialAdManager` → **drift detected**
- Doc says "Status: ⏳ Pending" for SDK integration → check if SDK imports exist → **still pending, doc is current**
- Doc references `BannerAdView.swift` → file exists, hash matches → **doc is current**
- Doc describes architecture that doesn't match trace edges → **potential staleness**

**Step 4: Outlier and Stub Detection**

Identify:
- **Orphan docs**: `.md` files with no code references and no references from other docs
- **Idea stubs**: Docs with `draft` or `stub` status, or very short docs with questions/TODOs
- **Contradictions**: Two docs making conflicting claims about the same subsystem
- **Dead references**: Docs referencing files that no longer exist

---

## Epistemology Scoring System

Every node (code or doc) gets an **epistemic score** (0.0–1.0) that represents how well the trace *understands* this node in context. This is distinct from the augmentation `confidence` (which measures the 3b's self-reported certainty about its own summary).

### Score Components

| Component | Weight | What it measures |
|---|---|---|
| `summary_confidence` | 0.20 | 3b model's self-reported confidence |
| `validation_status` | 0.15 | Has the 14b confirmed the summary? |
| `neighbor_coverage` | 0.20 | What fraction of this node's neighbors are also enriched? |
| `cross_reference_density` | 0.15 | How many doc↔code links involve this node? |
| `enrichment_depth` | 0.15 | How many passes have refined this node? |
| `staleness_check` | 0.15 | Has this node been checked against current file hash? |

### Score Interpretation

| Range | Meaning | Action |
|---|---|---|
| **0.95–1.00** | Fully understood, stable | Skip in future passes unless neighbors change |
| **0.80–0.94** | Well understood, minor gaps | Low-priority re-enrichment |
| **0.60–0.79** | Partially understood | Medium-priority enrichment target |
| **0.40–0.59** | Poorly understood | High-priority enrichment target |
| **0.00–0.39** | Unknown / failed augmentation | Critical — schedule for next pass |

### The "Never Done" Principle

Nodes with `epistemic_score >= 0.95` are effectively "settled" — but they're never permanently done. If:
- A neighbor gets re-augmented (code changed, or deeper enrichment discovered something new)
- A doc referencing this node is updated
- The node's own source file hash changes

...then its epistemic score **decays** and it re-enters the enrichment queue. This is the "always context for everything else" property — every enriched node is potential context for enriching its neighbors.

### Decay Rules

```
On neighbor re-enrichment:  score *= 0.95  (gentle nudge)
On referenced doc update:   score *= 0.90  (moderate)
On source file change:      score  = 0.00  (full re-augment from Pass 1)
On trace rebuild:           score *= 0.80  (structural change, re-validate)
```

---

## The Continuous Enrichment Loop

```
┌─────────────────────────────────────────────────────┐
│         PASS 0: STRUCTURAL TRACE (Rust)              │
│  Code: tree-sitter → symbols + import edges          │
│  Docs: regex → sections + backtick refs + links      │
│  Cost: ~100ms for 650 files                          │
│  Output: trace_nodes.jsonl, trace_edges.jsonl        │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│         PASS 1: FAST CATALOGUE (3b LLM)              │
│  Per-node: summary + role + confidence               │
│  NEW: + related_files hypotheses                     │
│  ~1 second per node, ~10 minutes for 600 files       │
│  Output: trace_augmented.jsonl                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│   PASS 0.5: LLM-GUIDED RE-TRACE (Rust validation)   │
│  Validates 3b's relationship hypotheses              │
│  Adds inferred edges where both endpoints exist      │
│  Confirms/boosts Rust-extracted doc↔code refs        │
│  Cost: ~5ms (pure graph operations)                  │
│  Output: trace_inferred_edges.jsonl                  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│        PASS 2: EPISTEMIC ENRICHMENT (14b)            │
│  Per-node: source + 3b summary + neighbor summaries  │
│  Now with: structural + inferred + doc-ref edges     │
│  Produces: domain_tags, architecture, cross-refs     │
│  Output: trace_epistemic.jsonl (new overlay)         │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│          PASS 3: CLUSTER SYNTHESIS (14b)             │
│  Per-domain: all enriched summaries in cluster       │
│  Produces: module summaries, data flow, status       │
│  Output: trace_modules.jsonl (new overlay)           │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│       PASS 4+: CONTINUOUS DEEPENING (14b loop)       │
│  Re-examine nodes where neighbors changed            │
│  Convergence: stop when all scores >= 0.95           │
│  Uses CoDRAG context endpoint for self-reference     │
│  ◄──── loops back to re-enrich as needed ────►       │
└─────────────────────────────────────────────────────┘
```

### Budget and Scheduling

Each pass is more expensive than the last:
- **Pass 1**: ~1 token/node (3b, fast) — run on every trace build
- **Pass 2**: ~5 tokens/node (14b, medium) — run after Pass 1, or on demand
- **Pass 3**: ~20 tokens/cluster (14b, heavy) — run nightly or on demand
- **Pass 4+**: proportional to change — run continuously in background

The system should respect the user's configured LLM budget (`codrag_data/ui_config.json`). If no 14b model is configured, Passes 2+ simply don't run — Pass 1 alone is still valuable.

### Self-Referential Context (The Recursive Insight)

In Pass 4+, when the 14b enriches a node, it can query **CoDRAG's own context endpoint** to gather relevant context. This means:
- The enrichment prompt includes `GET /context?query="ad framework architecture"` results
- Which returns chunks from already-enriched nodes
- Which means the trace is literally using its own understanding to deepen its understanding
- This is the "never done, always context for everything else" property

This creates a positive feedback loop: better enrichment → better context → better enrichment. The convergence criterion (epistemic score >= 0.95 for all reachable neighbors) prevents infinite loops.

---

## Implementation Phases

### Phase 22A: Foundation
- Expand `AugmentationEntry` with epistemic fields
- Add `trace_epistemic.jsonl` as a separate overlay (don't modify v1 format)
- Add `epistemic_score` computation function
- Add `doc_type` and `doc_status` to the 3b prompt for `.md` files

### Phase 22B: Pass 2 — Neighbor-Aware Enrichment
- Implement neighbor summary gathering from trace edges
- New 14b prompt template with neighbor context
- New `EpistemicEnricher` class (separate from `TraceAugmenter`)
- Write `trace_epistemic.jsonl` overlay

### Phase 22C: Pass 3 — Cluster Synthesis
- Domain-based clustering from Pass 2 tags
- Module summary generation
- `trace_modules.jsonl` output

### Phase 22D: Pass 4+ — Continuous Loop
- Epistemic score decay on neighbor changes
- Background enrichment scheduler
- CoDRAG self-referential context integration
- Convergence detection and reporting

### Phase 22E: Documentation Mining
- Cross-reference extraction from `.md` files
- New trace edge types (`documents`, `decides`, `supersedes`)
- Staleness detection
- Outlier and stub identification

---

## Open Questions

1. **How much context can we fit in a single 14b prompt?** With 8k context, we can fit ~20 neighbor summaries. With 32k, we can fit source + all neighbors. This affects Pass 2 quality significantly.

2. **Should Pass 2 be incremental?** (Only re-enrich nodes whose neighbors changed.) Yes — but we need to track "last enrichment timestamp" per node and compare against neighbor enrichment timestamps.

3. **Should module synthesis produce new trace nodes?** (e.g., a virtual `module:ad-framework` node.) Probably yes — this gives the trace a hierarchical structure that's useful for navigation and context selection.

4. **How do we handle contradictory docs?** Flag them for user review? Auto-resolve by recency? This is an important UX question.

5. **Should the continuous loop run during the user's work session or only as a background job?** Both — gentle enrichment during idle time, deep passes on explicit trigger or nightly schedule.

6. **Can we use embedding similarity to discover implicit cross-references?** (e.g., a doc mentioning "frequency caps" links to `InterstitialAdManager` even without naming it.) Yes — this is where Phase 16 (Context Intelligence) and Phase 22 intersect.

---

## Related Documents

- `docs/Phase01_Foundation/` — Trace graph fundamentals
- `docs/Phase05_Augmentation/` — Current augmentation pipeline (Pass 1)
- `docs/Phase16_ContextIntelligence/` — Native embeddings, path weights, CLaRa compression
- `MULTI_PASS_PIPELINE.md` — Detailed pass-by-pass implementation spec (this folder)
- `EPISTEMOLOGY_SCORING.md` — Scoring system deep dive (this folder)
- `RUST_ENRICHMENT_ANALYSIS.md` — Analysis of Rust pass underutilization + LLM-guided re-trace theory (this folder)
- `DOC_MINING_STRATEGY.md` — Documentation-specific enrichment (this folder)
- `PATH_FORWARD.md` — Consolidated implementation plan with research validation (this folder)
- `OVERVIEW.md` — Visual quick-read summary of the full pipeline (this folder)
