# Phase 64D — Rust Projection Engine

> **Status:** Planned  
> **Dependencies:** Phase 64A (Role Composition Engine), codrag-graph crate  
> **Trigger:** When live role projection latency becomes a concern on 50K+ file projects

---

## Motivation

Role projection (`project_atlas_for_role()`) currently runs in Python and has two paths:

| Path | Latency | Bottleneck |
|------|---------|-----------|
| **Cache hit** | ~0.1ms | File read (negligible) |
| **Cache miss (live)** | ~200ms | JSONL loading + scoring |

For projects under ~10K files, the cache system makes this invisible. But for very large codebases (50K-100K+ files), the live path becomes relevant:

- Cold start (no cache yet): every agent's first request triggers live projection
- Cache invalidation: any index rebuild invalidates all role caches
- Novel compound roles (e.g., "Senior Design Security Lead"): computed live, never cached

The `codrag-graph` Rust crate already holds the structural graph in memory. Moving scoring into Rust would eliminate the JSONL parsing bottleneck entirely.

---

## Architecture

### Current (Python)

```
Agent request → MCP server (Python)
  → load trace_epistemic.jsonl (I/O bound)
  → load trace_edges.jsonl (I/O bound)
  → score N files (CPU: ~1µs/file)
  → assemble string (CPU: ~0.1ms)
```

### Proposed (Rust via codrag-graph)

```
Agent request → MCP server (Python)
  → FFI call to codrag-graph (already loaded in memory)
    → score N files (CPU: ~10ns/file, vectorizable)
    → return scored file list
  → assemble string (Python, ~0.1ms)
```

### What moves to Rust

```rust
// codrag-graph/src/role_projection.rs

/// Role weight vector, mirrors Python RoleVector
pub struct RoleVector {
    pub layer_weights: HashMap<String, f32>,
    pub domain_affinity: Vec<String>,
    pub audience_tags: HashMap<String, Vec<String>>,  // TAG_TO_AUDIENCE
    pub centrality_weight: f32,
    pub detail_level: f32,
    pub max_chars: usize,
}

impl TraceGraph {
    /// Score all file nodes against a role vector.
    /// Returns (file_path, score) pairs sorted by relevance.
    pub fn score_files_for_role(
        &self,
        role: &RoleVector,
        epistemic: &EpistemicIndex,  // Loaded from trace_epistemic.jsonl
    ) -> Vec<(String, f32)> {
        // O(n) scoring with SIMD-friendly memory layout
        // Tag affinity uses FxHashSet for O(1) lookups
        // Audience bonus uses pre-indexed tag→role mapping
    }
}
```

### What stays in Python

- **Role resolver** (`resolve_role()`) — called once per request, 24µs, not worth moving
- **Assembly functions** (`_assemble_executive`, `_assemble_manager`, `_assemble_practitioner`) — string-heavy, Python is fine
- **Cache system** — file I/O, Python is fine

---

## Implementation Plan

### Step 1: Add epistemic data to TraceGraph

Currently `TraceGraph` only stores structural nodes/edges. Extend it to optionally hold epistemic annotations:

```rust
pub struct EpistemicAnnotation {
    pub architecture_layer: String,
    pub domain_tags: Vec<String>,
    pub epistemic_confidence: f32,
    pub extended_summary: String,
}

impl TraceGraph {
    pub fn load_epistemic(&mut self, index_dir: &Path) -> Result<(), GraphError> {
        // Load trace_epistemic.jsonl and attach to file nodes
    }
}
```

### Step 2: Implement scoring in Rust

Port `compute_role_relevance()` and `_compute_audience_bonus()` to Rust with:
- `FxHashMap` for O(1) tag lookups (vs Python dict)
- Pre-computed max_degree (avoid redundant iteration)
- SIMD-friendly scoring loop (f32 multiply-accumulate)

### Step 3: Expose via PyO3 FFI

```rust
#[pyfunction]
fn score_files_for_role(
    index_dir: &str,
    role_json: &str,  // Serialized RoleVector
) -> PyResult<Vec<(String, f32)>> {
    // Load graph + epistemic (or use cached)
    // Score all files
    // Return sorted results
}
```

### Step 4: Python adapter

```python
def project_atlas_for_role(role, index_dir, atlas_content=""):
    try:
        from codrag_engine import score_files_for_role
        scored = score_files_for_role(str(index_dir), role.to_json())
    except ImportError:
        scored = _score_files_python(role, index_dir)  # Fallback
    
    return _assemble(role, scored, atlas_content)
```

---

## Expected Performance

| Metric | Python (current) | Rust (projected) |
|--------|:-:|:-:|
| 1K files, live | ~200ms | ~5ms |
| 10K files, live | ~800ms | ~15ms |
| 50K files, live | ~4s | ~50ms |
| 100K files, live | ~8s | ~100ms |
| Cache hit (any size) | 0.1ms | 0.1ms (unchanged) |

The bottleneck shifts from JSONL parsing (~95% of current time) to the Python→Rust FFI boundary + string serialization.

---

## When to Build

**Trigger conditions** (any one):
- A user reports slow cold-start projection on a large project
- Cache miss latency exceeds 500ms in production telemetry
- CoDRAG targets codebases with 50K+ files as a market segment

**Not worth building if:**
- The cache system keeps hit rates above 95% (currently true)
- All customers are on projects under 10K files
- The role resolver LLM fallback (Phase 64B) adds more latency than projection

---

## Related

- [Phase 64A: Role Composition Engine](./02_Role_Composition_Engine.md) — Current Python implementation
- [codrag-graph crate](../../engine/crates/codrag-graph/) — Rust graph engine
- [role_projection.py](../../src/codrag/core/atlas/role_projection.py) — Python scoring (current)
