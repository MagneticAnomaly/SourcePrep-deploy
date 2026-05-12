# Phase 135 — Delete remaining mid-pipeline staleness checks (stages 7, 8, 10)

> **The rule:** nothing becomes stale mid-pipeline. Stage 1 already told
> every downstream stage what changed via the Changeset. Any stage that
> re-checks "is this still fresh?" is the duplicate Phase 134 deleted —
> just incomplete coverage.

Phase 134 deleted the staleness checks from stages 3 (catalogue), 6
(enrichment), 9 (deepening), and 14 (audit). Phase 135 finishes the
deep enrichment group by deleting them from the three stages Phase 134
missed: **7 (group_reasoning), 8 (clustering), 10 (deep_knowledge).**

## The three deletions

### Stage 7 — `src/prep/core/group_reasoning.py`

Today: each group has a "fingerprint" computed from a hash of its member
files' epistemic entries. The engine compares each group's current
fingerprint to a stored manifest of prior fingerprints. Same-fingerprint
groups are reused without re-analysis.

Phase 135: delete the fingerprint mechanism. A group needs re-analysis iff
any of its member files is in `changeset.modified | deleted`. Worker
inherits from `Worker` (Phase 134 base class), reads `self.changeset`,
applies `should_process(file_path)` to each member to decide.

Sites: lines 12 (comment), 61 (fingerprint field), 745-798 (staleness
check loop), plus the manifest-write that persists fingerprints.

### Stage 8 — `src/prep/core/cluster.py`

Today: each cluster has its own fingerprint (member-set + member epistemic
hashes). "Cluster reuse: X total, Y reused (fingerprint match)" — same
pattern at a different granularity.

Phase 135: delete cluster fingerprint reuse. A cluster needs re-synthesis
iff any of its member files is in `changeset.modified | deleted`. Same
`Worker.should_process` pattern.

Sites: lines 1696, 1932-1981 (reuse loop and reporting), plus the
manifest-write that persists fingerprints.

### Stage 10 — `src/prep/core/knowledge.py`

Today: `prev_hash == content_hash` per-doc compare on the synthesized
embedding text (line 454). If the augmenter/enricher upstream skipped a
file (changeset said `unchanged`), its doc's synthesized text doesn't
change, so the hash matches, embedding is reused. The hash compare is
*redundant* with the changeset — the changeset already told us the file
didn't change.

Phase 135: delete the per-doc content_hash check from the deep_knowledge
path. Stage 10 consumes the changeset: docs whose underlying file is in
`changeset.unchanged` keep their cached embedding; docs whose file is in
`changeset.modified | added` re-embed; docs whose file is in
`changeset.deleted` get dropped.

Stage 5 (initial knowledge embedding, same code path with `is_deep=False`)
is **out of scope** — stage 10 overwrites stage 5's output anyway, so
stage 5 can keep its simple full-embed-each-run behavior. The cutover
applies only to the `is_deep=True` path.

Sites: line 454 (the compare itself), plus the `_load_previous_for_reuse`
helper at lines 263-271 if it's exclusive to the deep path.

## Out of scope (do not touch)

- **`src/prep/core/index.py` (`CodeIndex`)** — separate concurrent task,
  not a pipeline stage. Untouched.
- **Stage 5 knowledge** — full re-embed each run is fine; stage 10
  overwrites it. The `is_deep=False` code path stays as-is.
- **Stages 11-15 finalize** — out of scope for this phase.
- **`LayeredCodeIndex`, `build_manager` walkers** — out of scope.

## Injection mechanics (already in place)

Phase 134 installed the closure-based injection at
`workers/__init__.py:191-204`. `wrapped_worker.changeset = read_changeset(idx_dir)`
sets a `changeset` attribute on the closure before invocation. Inside the
worker, the engine instance gets `engine.changeset = wrapped_worker.changeset`
before its `.run()` call (mirrors how Phase 134 wires `drift_detector` for
stage 9).

For Phase 135:
- `_group_reasoning_worker` (line 754) — inject changeset into
  `GroupReasoningEngine` before `engine.run(...)`.
- `_cluster_worker` (line 798) — inject changeset into `ClusterSynthesizer`
  before `synthesizer.run(...)`.
- `_knowledge_worker` (line 584, `is_deep=True` branch) — inject changeset
  into `KnowledgeIndex` before `idx.build(...)`.

All three engines inherit from the Phase 134 `Worker` base class
(`src/prep/services/pipeline/workers/base.py`) so `should_process` works
identically.

## Migration

No migration cases beyond Phase 134's. On first run after this phase:
- Stage 7 ignores any prior fingerprint manifest and processes the
  changeset's modified/deleted groups. Fingerprint manifest field gets
  dropped on next write.
- Stage 8 same.
- Stage 10 same — prior `prev_hash` field on cached docs is harmless;
  gets dropped on next manifest write.

The changeset is already canonical (Phase 134). Nothing else changes.

## Net diff target

**Around −150 net production lines** — three fingerprint/hash machineries
collapse onto the same Worker.should_process pattern.

| File | Rough net |
|---|---|
| `src/prep/core/group_reasoning.py` | −60 |
| `src/prep/core/cluster.py` | −60 |
| `src/prep/core/knowledge.py` | −20 (deep path only) |
| `src/prep/services/pipeline/workers/__init__.py` | +10 (three inject points) |
| **Estimated total** | **−130** |

## Testing strategy

Mirrors Phase 134:

| Test file | Coverage |
|---|---|
| `tests/test_phase135_group_reasoning_changeset.py` | GroupReasoningEngine with explicit changesets — groups with all-unchanged members skip; groups with any modified/deleted member re-analyze |
| `tests/test_phase135_cluster_changeset.py` | Same for ClusterSynthesizer |
| `tests/test_phase135_deep_knowledge_changeset.py` | KnowledgeIndex deep path: unchanged-file docs keep cached embeddings, modified-file docs re-embed |
| `tests/test_phase135_no_fingerprints.py` | Static: no fingerprint computation remains in `group_reasoning.py` or `cluster.py` build paths |
| `tests/test_phase135_stage5_unaffected.py` | Stage 5 (`is_deep=False`) keeps its current behavior — no changeset coupling |
| `tests/test_phase135_e2e_no_llm.py` | Full pipeline rebuild on no-change → stages 7/8/10 do zero work |

## References

- Phase 133 — Rust walker/hasher cutover
- Phase 134 — Changeset-driven pipeline (the precedent; stages 3/6/9/14
  already done)
- Phase 134 `Worker` base class — `src/prep/services/pipeline/workers/base.py`
- Phase 134 `Changeset` — `src/prep/services/pipeline/changeset.py`
- `WorkerFactory` closure-based injection — `src/prep/services/pipeline/workers/__init__.py:191-204`
