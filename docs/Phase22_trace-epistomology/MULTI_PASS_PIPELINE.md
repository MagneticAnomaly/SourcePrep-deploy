# Multi-Pass Augmentation Pipeline — Detailed Design

**Parent**: `Phase22_trace-epistomology/README.md`  
**Status**: Design

---

## Current State (v1 Pipeline)

The existing `TraceAugmenter` in `src/prep/core/augmenter.py` implements a **two-step single-pass** pipeline:

1. **Symbol augmentation**: For each `kind=symbol` node, sends source snippet + imports to 3b → gets `{summary, role, confidence}`
2. **File augmentation**: For each `kind=file` node, sends first 30 lines + symbol names + imports to 3b → gets `{summary, role, confidence, key_exports}`

Then optionally, a **validation pass** where the 14b model checks the 3b's summary and marks `validated=true/false`.

### What works well
- Fast: ~1s per node, entire 650-file repo in ~10 minutes
- Accurate: 100% of spot-checked samples were factually correct
- Incremental: only re-augments nodes whose file hash changed
- Atomic writes: temp file + rename pattern

### What's missing
- No cross-file awareness (each node augmented in isolation)
- No document-specific handling (`.md` files get code-oriented prompts)
- Flat role taxonomy (12 roles, no domain/architectural classification)
- Validation is binary (pass/fail), doesn't enrich
- No epistemic metadata (how well-understood is this node in context?)
- 500-char summary cap truncates complex descriptions

---

## Proposed v2 Pipeline

### Data Model Changes

#### New file: `trace_epistemic.jsonl`

Separate overlay from `trace_augmented.jsonl` (backward compatible). Each line:

```json
{
  "node_id": "file:Components/Ads/Interstitial/InterstitialAdManager.swift",
  "pass": 2,
  "enriched_at": "2026-02-13T04:00:00Z",
  "enriched_by": "ministral-3:14b",
  
  "one_liner": "Full-screen ad manager: 1/session, 5min cooldown, 10-view gate",
  "extended_summary": "...(no char cap, 14b produces as much as needed)...",
  
  "domain_tags": ["monetization", "ads", "interstitial"],
  "architecture_layer": "infrastructure",
  "design_pattern": "singleton-coordinator",
  "subsystem": "ad-framework",
  
  "relationships": {
    "depends_on": [
      {"node_id": "file:Components/Ads/AdConfiguration.swift", "relationship": "reads global ad config"},
      {"node_id": "file:Components/Ads/AdPlacementCoordinator.swift", "relationship": "coordinates with for visibility"}
    ],
    "depended_by": [
      {"node_id": "file:Views/PropertyDetail/PropertyWorkspaceView.swift", "relationship": "triggers via .interstitialTrigger() modifier"}
    ],
    "documented_by": [
      {"node_id": "file:Docs/ADS_FRAMEWORK_STATUS.md", "section": "InterstitialAdController"},
      {"node_id": "file:Docs/ADS_QUICK_REFERENCE.md", "section": "Interstitial Ads"}
    ]
  },
  
  "signals": {
    "status": "active-stubbed",
    "tech_debt": ["SDK integration stubbed with TODO comments"],
    "staleness_risk": "low",
    "test_coverage": "none-detected",
    "complexity": "low"
  },
  
  "doc_meta": null,
  
  "epistemic_score": 0.82,
  "epistemic_version": 1,
  "neighbor_hash": "abc123"
}
```

For documentation nodes, `doc_meta` is populated instead:

```json
{
  "node_id": "file:Docs/ADS_FRAMEWORK_STATUS.md",
  "doc_meta": {
    "doc_type": "reference",
    "doc_status": "active",
    "references_code": [
      "Managers/AdManager.swift",
      "Components/BannerAdView.swift",
      "Managers/InterstitialAdController.swift"
    ],
    "references_docs": [
      "Docs/ADS_INTEGRATION_GUIDE.md"
    ],
    "decisions": [],
    "status_assertions": [
      {"target": "AdManager", "asserted_status": "complete"},
      {"target": "SDK Integration", "asserted_status": "pending"}
    ],
    "drift_detected": [
      {"reference": "InterstitialAdController.swift", "actual": "InterstitialAdManager.swift", "type": "renamed"}
    ]
  }
}
```

#### New file: `trace_modules.jsonl`

Module-level synthesis from Pass 3:

```json
{
  "module_id": "mod:ad-framework",
  "name": "Ad Framework",
  "domain": "monetization",
  "status": "active-stubbed",
  "synthesized_at": "2026-02-13T04:30:00Z",
  
  "purpose": "Conservative ad monetization system with strict frequency caps, supporting banner, interstitial, and native ad formats. Currently framework-complete but SDK-stubbed.",
  
  "members": [
    "file:Components/Ads/AdConfiguration.swift",
    "file:Components/Ads/AdPlacementCoordinator.swift",
    "file:Components/Ads/Interstitial/InterstitialAdManager.swift",
    "file:Components/Ads/Banners/AdaptiveBannerView.swift",
    "..."
  ],
  
  "entry_points": ["AdPlacementCoordinator.shared", "InterstitialAdManager.shared"],
  "external_interfaces": [".interstitialTrigger() ViewModifier", "MapBannerAdContainer View"],
  
  "documentation": [
    "file:Docs/ADS_FRAMEWORK_STATUS.md",
    "file:Docs/ADS_QUICK_REFERENCE.md",
    "file:Docs/ADS_INTEGRATION_GUIDE.md"
  ],
  
  "data_flow": "AdConfiguration → AdPlacementCoordinator → {BannerViews, InterstitialAdManager, NativeAdLoader} → UI",
  
  "risks": ["No SDK integration yet", "InterstitialAdController renamed to InterstitialAdManager but docs not updated"],
  
  "epistemic_score": 0.88
}
```

---

## Pass-by-Pass Implementation

### Pass 1: Fast Catalogue (3b) — Existing, Minor Tweaks

**Changes needed**:

1. **Separate `.md` prompt template**:

```python
DOC_CLASSIFICATION_PROMPT = """Classify this document's purpose and status.

File: {file_path}

First 50 lines:
```
{head}
```

Respond with JSON:
{{"summary": "1-2 sentence purpose", "role": "utility", "confidence": 0.85, "doc_type": "research", "doc_status": "active"}}

Where:
- role: one of api, core, model, utility, config, test, script, ui, documentation
- doc_type: one of research, design_spec, architecture_decision, plan, guide, reference, changelog, stub
- doc_status: one of active, completed, shelved, superseded, draft, unknown

JSON response:"""
```

2. **Add `documentation` to `VALID_ROLES`** — currently, all docs get `utility` or `config` which is lossy.

3. **Increase head lines for docs**: Currently reads first 30 lines. For `.md` files, read first 50 — docs front-load their status and purpose in headers.

4. **Store `doc_type` and `doc_status`** in augmentation entry (new optional fields).

**Implementation effort**: Small. ~30 lines of changes to `augmenter.py`.

---

### Pass 2: Epistemic Enrichment (14b) — New

**Architecture**: New class `EpistemicEnricher` alongside existing `TraceAugmenter`.

```python
class EpistemicEnricher:
    """
    Pass 2: Neighbor-aware epistemic enrichment using a larger model.
    
    Reads:
      - trace_nodes.jsonl (structural graph)
      - trace_edges.jsonl (relationships)
      - trace_augmented.jsonl (Pass 1 summaries)
    
    Writes:
      - trace_epistemic.jsonl (enriched overlay)
    """
```

**Prompt strategy for code files**:

```
You are analyzing a code file in the context of its codebase relationships.

## Target File
Path: {file_path}
Initial summary (from fast model): {pass1_summary}
Role: {pass1_role}

## Source (first 100 lines)
```
{source_head}
```

## This file's relationships
Imports: {imports_list}
Imported by: {imported_by_list}
Contains symbols: {symbol_list}

## Neighbor summaries (files this imports)
{for each imported file: "- {path}: {pass1_summary}"}

## Neighbor summaries (files that import this)
{for each importing file: "- {path}: {pass1_summary}"}

## Task
Produce a JSON enrichment with these fields:
- one_liner: Single line (<100 chars) capturing the essence
- extended_summary: Detailed summary (no length limit), correcting/expanding the initial summary
- domain_tags: Array of 1-5 domain tags (e.g., "monetization", "auth", "navigation")
- architecture_layer: one of "presentation", "business_logic", "data_access", "infrastructure", "configuration", "documentation", "test"
- design_pattern: recognized pattern if any (e.g., "singleton", "observer", "coordinator", "repository")
- subsystem: short name grouping related files (e.g., "ad-framework", "auth-flow", "listing-management")
- tech_debt: array of issues found (TODO/FIXME/HACK/stubbed code)
- status: one of "active", "active-stubbed", "deprecated", "experimental", "stable"
```

**Prompt strategy for `.md` files** — different focus:

```
You are analyzing a documentation file in a software project.

## Target Document
Path: {file_path}
Initial summary: {pass1_summary}
Doc type: {pass1_doc_type}
Doc status: {pass1_doc_status}

## Full content (first 200 lines)
```
{content}
```

## Known code files in this project (from trace)
{list of all file paths, so the model can identify cross-references}

## Task
Produce a JSON enrichment with:
- extended_summary: Detailed summary of the document's content and conclusions
- doc_type: refined classification
- doc_status: refined status assessment based on content markers
- references_code: array of code file paths mentioned or implied by this document
- references_docs: array of other doc file paths mentioned
- decisions: array of key decisions made in this document (if any)
- status_assertions: array of {target, asserted_status} for any status claims about code/features
- is_stale: boolean, true if content appears outdated based on internal evidence
- staleness_evidence: explanation if is_stale is true
```

**Scheduling**: 
- Run after Pass 1 completes
- Process nodes in priority order: lowest epistemic score first
- Respect LLM budget (configurable max tokens per session)
- Skip nodes with `epistemic_score >= 0.95` unless neighbors changed

**Neighbor hash**: To detect when re-enrichment is needed, compute a hash of all neighbors' enrichment timestamps. Store as `neighbor_hash`. On next run, if the hash differs, the node needs re-enrichment.

---

### Pass 3: Cluster Synthesis (14b) — New

**Prerequisites**: Pass 2 must have enriched a sufficient portion of nodes (>50% of a cluster).

**Clustering algorithm**:
1. Group nodes by `subsystem` tag from Pass 2
2. For clusters with no subsystem tag, fall back to directory-based grouping
3. Minimum cluster size: 3 nodes. Maximum: 30 nodes (split larger ones by subdirectory).

**Prompt**:

```
You are synthesizing a module-level understanding of a code subsystem.

## Module: {subsystem_name}
Files in this module:
{for each member:
  "- {path} ({role}): {one_liner}"
}

## Key relationships between members:
{extracted from trace_edges: internal imports/calls within the cluster}

## Documentation about this module:
{any docs whose doc_meta.references_code overlaps with this cluster's members}

## Task
Produce a JSON module synthesis:
- name: Human-readable module name
- purpose: 2-3 sentence explanation of what this module does and why it exists
- entry_points: array of primary entry points (classes, functions, views)
- external_interfaces: how other code interacts with this module
- data_flow: brief description of data flow through the module
- status: overall module status
- risks: array of identified risks or issues
- missing: anything that seems like it should exist but doesn't (e.g., no tests, no error handling)
```

**Output**: `trace_modules.jsonl`

---

### Pass 4+: Continuous Deepening — New

**Trigger conditions** (any of these schedules re-enrichment):
1. **File change**: Source hash changed → score drops to 0.0, enters Pass 1 queue
2. **Neighbor enrichment**: A neighbor's epistemic entry was updated → score *= 0.95
3. **Doc update**: A doc referencing this node was re-enriched → score *= 0.90
4. **Trace rebuild**: Structural changes (new edges/nodes) → score *= 0.80
5. **Manual trigger**: User requests "deep analysis" → all nodes enter queue regardless of score

**Self-referential context**:
In Pass 4+, the enrichment prompt can include a **Prep context query**:

```python
# Inside EpistemicEnricher.enrich_node_deep():
context = prep_context_api.get_context(
    query=f"What is the purpose and architecture of {node.subsystem}?",
    k=10, max_chars=4000
)
# Feed `context` into the enrichment prompt as additional background
```

This means the trace uses its own enriched knowledge to further enrich nodes. The convergence criterion prevents infinite loops: if the context doesn't change (because all neighbors are stable), the enrichment produces the same result, and the score stays >= 0.95.

**Budget control**:
```python
class EnrichmentScheduler:
    def __init__(self, max_tokens_per_session: int = 100_000):
        self.budget_remaining = max_tokens_per_session
    
    def next_batch(self, all_nodes: List[EpistemicEntry]) -> List[str]:
        """Return node_ids to enrich, prioritized by lowest epistemic score."""
        candidates = [n for n in all_nodes if n.epistemic_score < 0.95]
        candidates.sort(key=lambda n: n.epistemic_score)
        # Estimate ~500 tokens per enrichment
        batch_size = min(len(candidates), self.budget_remaining // 500)
        return [n.node_id for n in candidates[:batch_size]]
```

---

## Migration Path

### v1 → v2 Compatibility

- `trace_augmented.jsonl` (Pass 1 output) format is **unchanged**
- New optional fields (`doc_type`, `doc_status`) are added but old entries without them are fine
- `trace_epistemic.jsonl` is a **new file**, never modifies the v1 overlay
- `trace_modules.jsonl` is a **new file**
- All API endpoints continue to work with v1 data
- v2 data is additive — the dashboard can show epistemic metadata when available, fall back gracefully

### Rollout order

1. Ship Pass 1 improvements (doc prompt, `documentation` role) — no new files needed
2. Ship Pass 2 with `trace_epistemic.jsonl` — new enrichment, backward compatible
3. Ship Pass 3 with `trace_modules.jsonl` — builds on Pass 2
4. Ship Pass 4+ continuous loop — builds on all previous

---

## Performance Estimates

For a 650-file repo like HomeColab (989 nodes):

| Pass | Model | Tokens/node | Total tokens | Time (local Ollama) | Time (API) |
|---|---|---|---|---|---|
| Pass 1 | 3b | ~200 | ~200K | ~10 min | ~2 min |
| Pass 2 | 14b | ~800 | ~800K | ~60 min | ~8 min |
| Pass 3 | 14b | ~2000/cluster | ~40K (20 clusters) | ~5 min | ~1 min |
| Pass 4 (delta) | 14b | ~800 | varies | varies | varies |

Pass 2 is the expensive one. For local Ollama on CPU, it's an hour. On GPU or API, it's very manageable. The key optimization: **Pass 2 is incremental** — after the first run, only changed nodes and their neighbors get re-enriched.

---

## Testing Strategy

1. **Unit tests**: Mock LLM client, verify prompt construction and JSON parsing for each pass
2. **Integration test**: Run Pass 1+2 on `tests/fixtures/mini_repo/`, verify `trace_epistemic.jsonl` output
3. **Snapshot tests**: Save a "golden" enrichment for a known file, assert future runs produce similar results
4. **Convergence test**: Run Pass 4 loop on a stable repo, verify it terminates (all scores >= 0.95) within N iterations
5. **Staleness test**: Modify a file, verify epistemic scores decay correctly for that file and its neighbors
