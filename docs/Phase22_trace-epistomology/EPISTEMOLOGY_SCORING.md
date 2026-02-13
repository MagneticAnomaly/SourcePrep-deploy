# Epistemology Scoring System — Deep Dive

**Parent**: `Phase22_trace-epistomology/README.md`  
**Status**: Design

---

## Why a Separate Score?

The current augmentation has a `confidence` field (0.0–1.0), but this is the **3b model's self-reported certainty about its own output**. It answers: "How sure am I that this summary is correct?"

The **epistemic score** answers a fundamentally different question: "How well does the trace understand this node **in the context of the entire codebase**?"

A node can have confidence=0.99 (the summary is factually correct) but epistemic_score=0.40 (we don't know how it connects to anything, what subsystem it's part of, or whether the docs about it are current).

---

## Score Components — Detailed Breakdown

### 1. Summary Confidence (weight: 0.20)

**Source**: `trace_augmented.jsonl` → `confidence` field  
**Range**: 0.0–1.0 (direct from 3b model)

This is the baseline. If the 3b model itself isn't confident, the epistemic score starts low.

**Normalization**: Used directly. No transformation needed.

### 2. Validation Status (weight: 0.15)

**Source**: `trace_augmented.jsonl` → `validated` field  
**Values**:
- `validated=true, validated_by=14b`: score component = 1.0
- `validated=true, validated_by=3b` (self-validation): score component = 0.6
- `validated=false`: score component = 0.0

**Rationale**: A 14b-validated summary is significantly more trustworthy. Self-validation by the same model is weak evidence. Unvalidated means we're relying entirely on the 3b's self-confidence.

### 3. Neighbor Coverage (weight: 0.20)

**Source**: Computed from `trace_edges.jsonl` + `trace_epistemic.jsonl`  
**Formula**:

```
neighbor_ids = all nodes connected to this node via trace edges
enriched_neighbors = count of neighbor_ids that have entries in trace_epistemic.jsonl
total_neighbors = len(neighbor_ids)

if total_neighbors == 0:
    score_component = 0.5  # isolated node, neutral
else:
    score_component = enriched_neighbors / total_neighbors
```

**Rationale**: A node whose neighbors are all enriched is better understood contextually. If we know what `InterstitialAdManager` imports and what imports it, and all those files have enriched summaries, we can be confident about this node's role in the system.

**Edge case**: Nodes with 0 neighbors (orphan files) get 0.5 — not penalized, but not boosted either.

### 4. Cross-Reference Density (weight: 0.15)

**Source**: Computed from `trace_epistemic.jsonl` → `relationships.documented_by` + `doc_meta.references_code`  
**Formula**:

```
doc_refs = count of documentation nodes that reference this code node
code_refs = count of code nodes referenced by this doc node (if this is a doc)
cross_ref_count = doc_refs + code_refs

# Sigmoid normalization: rapidly diminishing returns after 3-4 references
score_component = min(1.0, cross_ref_count / 4.0)
```

**Rationale**: A code file referenced by 3 docs is well-documented and understood. A doc that references 5 code files is well-grounded. After 4+ references, additional references add marginal value.

**For code nodes**: How many docs reference this code?
**For doc nodes**: How many code files does this doc reference (and were those files found in the trace)?

### 5. Enrichment Depth (weight: 0.15)

**Source**: `trace_epistemic.jsonl` → `pass` field  
**Values**:

| Passes completed | Score component |
|---|---|
| Pass 1 only (no epistemic entry) | 0.0 |
| Pass 2 (initial enrichment) | 0.5 |
| Pass 3 (part of a synthesized module) | 0.75 |
| Pass 4+ (at least one re-enrichment) | 1.0 |

**Rationale**: More passes = more refinement. A node that has been through the full loop and re-examined at least once is well-understood.

### 6. Staleness Check (weight: 0.15)

**Source**: Compare `trace_augmented.jsonl` → `file_hash` against current `trace_manifest.json` → `file_hashes`  
**Formula**:

```
if file_hash matches current:
    score_component = 1.0  # content hasn't changed since augmentation
elif file_hash exists but doesn't match:
    score_component = 0.0  # content changed, augmentation is stale
elif no file_hash recorded:
    score_component = 0.3  # unknown, slightly penalized
```

**Rationale**: If the file has changed since augmentation, everything we "know" about it might be wrong. This is the strongest negative signal.

---

## Composite Score Calculation

```python
def compute_epistemic_score(
    node_id: str,
    augmentation: AugmentationEntry,
    epistemic: Optional[EpistemicEntry],
    edges: List[TraceEdge],
    all_epistemic: Dict[str, EpistemicEntry],
    current_file_hashes: Dict[str, str],
) -> float:
    """Compute the composite epistemic score for a node."""
    
    weights = {
        "summary_confidence": 0.20,
        "validation_status": 0.15,
        "neighbor_coverage": 0.20,
        "cross_reference_density": 0.15,
        "enrichment_depth": 0.15,
        "staleness_check": 0.15,
    }
    
    # 1. Summary confidence
    c1 = augmentation.confidence
    
    # 2. Validation status
    if augmentation.validated and augmentation.validated_by and "14b" in augmentation.validated_by:
        c2 = 1.0
    elif augmentation.validated:
        c2 = 0.6
    else:
        c2 = 0.0
    
    # 3. Neighbor coverage
    neighbor_ids = get_neighbor_ids(node_id, edges)
    if not neighbor_ids:
        c3 = 0.5
    else:
        enriched = sum(1 for n in neighbor_ids if n in all_epistemic)
        c3 = enriched / len(neighbor_ids)
    
    # 4. Cross-reference density
    cross_refs = count_cross_references(node_id, all_epistemic)
    c4 = min(1.0, cross_refs / 4.0)
    
    # 5. Enrichment depth
    if epistemic is None:
        c5 = 0.0
    elif epistemic.pass_number >= 4:
        c5 = 1.0
    elif epistemic.pass_number >= 3:
        c5 = 0.75
    else:
        c5 = 0.5
    
    # 6. Staleness check
    file_path = augmentation.node_id.replace("file:", "", 1)
    current_hash = current_file_hashes.get(file_path)
    if augmentation.file_hash and current_hash:
        c6 = 1.0 if augmentation.file_hash == current_hash else 0.0
    elif augmentation.file_hash:
        c6 = 0.3  # hash exists but can't verify
    else:
        c6 = 0.3  # no hash recorded
    
    # Weighted sum
    score = (
        weights["summary_confidence"] * c1 +
        weights["validation_status"] * c2 +
        weights["neighbor_coverage"] * c3 +
        weights["cross_reference_density"] * c4 +
        weights["enrichment_depth"] * c5 +
        weights["staleness_check"] * c6
    )
    
    return round(score, 3)
```

---

## Score Decay Mechanics

### When does a score decay?

Epistemic scores aren't static. They decay when the world changes around a node.

| Event | Decay formula | Rationale |
|---|---|---|
| **Source file changed** | `score = 0.0` | Everything might be wrong |
| **Neighbor re-enriched** | `score *= 0.95` | Context shifted slightly |
| **Referenced doc updated** | `score *= 0.90` | Documentation changed, claims may be invalid |
| **Trace rebuilt** (structural) | `score *= 0.80` | Edges changed, relationships may be different |
| **Module re-synthesized** | `score *= 0.97` | Module understanding refined |
| **Time decay** (>30 days stale) | `score *= 0.98/day` | Gentle aging for very old enrichments |

### Decay propagation

When a node's score decays, it may trigger cascading decay in neighbors:

```
File A changes → A.score = 0.0
  → B imports A → B.score *= 0.95
    → C imports B → C.score *= 0.95 (second-order, mild)
      → D imports C → no further propagation (3-hop limit)
```

**Propagation limit**: 3 hops max. Beyond that, the indirect effect is negligible.

### Re-enrichment queue

After decay, nodes with `epistemic_score < 0.95` enter the re-enrichment queue:

```python
class EnrichmentQueue:
    """Priority queue for nodes needing re-enrichment."""
    
    def __init__(self):
        self.queue: List[Tuple[float, str]] = []  # (score, node_id)
    
    def add(self, node_id: str, score: float):
        """Add node to queue. Lower scores = higher priority."""
        heapq.heappush(self.queue, (score, node_id))
    
    def next_batch(self, budget_tokens: int, est_tokens_per_node: int = 500) -> List[str]:
        """Pop the highest-priority nodes that fit within budget."""
        batch = []
        budget = budget_tokens
        while self.queue and budget >= est_tokens_per_node:
            score, node_id = heapq.heappop(self.queue)
            batch.append(node_id)
            budget -= est_tokens_per_node
        return batch
```

---

## Epistemic Score in the UI

### Dashboard: Trace Status Card

Current card shows: nodes, edges, files parsed, augmented nodes, avg confidence.

Add:
- **Epistemic Coverage**: `412/571 nodes fully understood (72%)`
- **Epistemic Score**: `avg 0.84 | min 0.12 | fully settled: 312`
- **Enrichment status**: `Pass 2: 400/571 | Pass 3: 18/20 modules | Pass 4: converged`
- **Pending re-enrichment**: `23 nodes in queue`

### File Explorer: Per-File Indicator

Each file in the explorer could show a small epistemic indicator:
- 🟢 Green dot: score >= 0.95 (fully understood)
- 🟡 Yellow dot: score 0.60–0.94 (partially understood)
- 🔴 Red dot: score < 0.60 (needs enrichment)
- ⚪ Gray dot: not yet augmented

### File Detail Panel

When clicking a file, show:
- Summary (from Pass 1)
- Extended summary (from Pass 2, if available)
- Domain tags and subsystem
- Related docs
- Epistemic score breakdown (expandable)
- Tech debt signals

---

## Worked Example: Score Lifecycle

### Initial state (after Pass 1 only)

`InterstitialAdManager.swift`:
- summary_confidence: 0.99 → weighted: 0.198
- validation_status: validated by 14b → weighted: 0.150
- neighbor_coverage: 0/6 neighbors enriched → weighted: 0.000
- cross_reference_density: 0 refs → weighted: 0.000
- enrichment_depth: Pass 1 only → weighted: 0.000
- staleness_check: hash matches → weighted: 0.150
- **Total: 0.498** — "Poorly understood" despite accurate summary

### After Pass 2

- neighbor_coverage: 4/6 neighbors now enriched → weighted: 0.133
- cross_reference_density: 2 docs reference this → weighted: 0.075
- enrichment_depth: Pass 2 done → weighted: 0.075
- **Total: 0.781** — "Partially understood"

### After Pass 3 (module synthesis)

- neighbor_coverage: 6/6 → weighted: 0.200
- cross_reference_density: 3 docs → weighted: 0.113
- enrichment_depth: Pass 3 → weighted: 0.113
- **Total: 0.924** — "Well understood"

### After Pass 4 (one re-enrichment)

- enrichment_depth: Pass 4+ → weighted: 0.150
- **Total: 0.961** — "Fully understood, stable" ✅

### Then source file changes

- staleness_check: hash mismatch → weighted: 0.000
- **Total: 0.000** — immediately back to Pass 1 queue

---

## Open Design Questions

1. **Should epistemic scores be stored in a separate file or embedded in `trace_epistemic.jsonl`?**
   - Recommendation: Embed in `trace_epistemic.jsonl` as a computed field. Recompute on load (scores depend on neighbor state which may have changed).

2. **Should isolated files (no edges) be penalized?**
   - Current design: neutral (0.5 on neighbor_coverage). Could argue they should be penalized since we can't contextualize them, or boosted since they're self-contained.

3. **How aggressively should time decay work?**
   - Current proposal: 0.98/day after 30 days. This means after 60 days of no changes, a fully-settled node drops from 0.96 to ~0.54. Is this too aggressive? Maybe 0.995/day (drops to 0.82 after 60 days).

4. **Should module synthesis (Pass 3) produce its own epistemic score?**
   - Yes — module-level score = average of member scores × coverage factor. This allows "module X is well-understood but module Y needs work."

5. **How do we handle nodes that the LLM consistently fails on?**
   - After 3 failed augmentation attempts, mark as `augmentation_blocked` with reason. Don't keep retrying. Surface to user as "needs manual review."
