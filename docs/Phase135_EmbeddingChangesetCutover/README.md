# Phase 135 — Embedding Changeset Cutover

> **Status:** Spec approved 2026-05-12. Next step: implementation plan.
>
> **Architectural lineage:** Phase 133 unified the *trace* walker/hasher onto
> Rust (single source of truth for file content hashing). Phase 134 made
> stage 1 emit a `Changeset` consumed by stages 6–9 (single source of truth
> for "what changed in this run"). Phase 135 closes the loop by extending
> the same contract to stages 5 (KNOWLEDGE) and 10 (DEEP_KNOWLEDGE), which
> are the last two pipeline stages still doing their own walking and hashing.

## Why this exists

Phase 134's review filed S3-1 as a follow-up: `src/prep/core/index.py` (the
embedding pipeline that powers stages 5 and 10) still has independent
staleness machinery — its own file walk, its own per-file hash, and its
own manifest `file_hashes` dict. This is the exact architectural duplicate
Phase 134 deleted from the augmenter, deepening, epistemic enrichment,
epistemic scoring, and audit staleness analyzer.

The Phase 134 insight — "why is any stage besides stage 1 concerned about
staleness?" — applies identically to stages 5 and 10. Stage 1 has already
walked the repo, hashed every file, and emitted a `Changeset` that
authoritatively says what changed. Stages 5 and 10 re-walking and re-hashing
is redundant work *and* an architectural duplicate.

## Goal

Make `CodeIndex.build()` (called by the knowledge worker at stage 5 and
the deep_knowledge worker at stage 10) consume the `Changeset` emitted by
stage 1. Delete all in-stage hashing, all per-file staleness comparison,
and the manifest's `file_hashes` dict. Walker converges onto the same
`prep_engine.walk_repo` primitive Phase 133/134 standardized on.

## Non-goals

- **`LayeredCodeIndex` cutover.** Used by `build_manager` for layered
  (remote + delta) builds and is not called by stages 5/10 pipeline
  workers. Out of scope. May get its own follow-up.
- **One-off `CodeIndex` callers.** `mcp_direct.py:118`, `agents/shared/prep_data.py:168`,
  and similar non-pipeline call sites pass `changeset=None` and keep
  current "treat everything as added" behavior. We do not extend the
  changeset contract to them in this phase.
- **Embedder model change handling.** The existing `prev_model != cur_model`
  branch (index.py:298-300) is orthogonal to file staleness. Stays as-is.

## Architecture

Single source of truth: stage 1's `Changeset`.

```
Stage 1 (TraceBuilder)
   ├─ walks repo via prep_engine.walk_repo (Phase 133)
   ├─ hashes via prep_engine.hash_content (Phase 133)
   └─ emits changeset.jsonl  ←─────────┐
                                       │
                       read_changeset(idx_dir)
                                       │
   ┌───────────────────────────────────┘
   │
Stage 5 (knowledge worker)        Stage 10 (deep_knowledge worker)
   │                                       │
   └─ CodeIndex.build(changeset=...)       └─ CodeIndex.build(changeset=...)
         ├─ changeset.added|modified → embed
         ├─ changeset.unchanged       → reuse cached embedding
         └─ changeset.deleted         → drop doc(s) for path
```

`CodeIndex.build()` does no hashing and reads no manifest hashes. It still
walks the filesystem to apply the embedding stage's user-scope filters
(`included_paths` for explicit user-selected paths, `roots` for the
scope-limited build mode, `.gitignore` loading), but the walker output
is *only* the scoped candidate set — the staleness decision comes from
the changeset.

## Deletion sites in `src/prep/core/index.py`

| # | Lines | What dies | Replacement |
|---|---|---|---|
| 1 | 302-320 | "Cold-start incremental" branch — loads previous index when manifest has `file_hashes` dict | Load previous embeddings/docs from disk when `changeset.unchanged` is non-empty |
| 2 | 322-334 | `prev_by_source` + `prev_hash_by_source` maps (the second is the redundant one) | Keep `prev_by_source` (source_path → row indices); delete `prev_hash_by_source` entirely |
| 3 | 438, 512-513 | `current_file_hashes` dict + inline `stable_file_hash(raw)` | Deleted. No hashing in this stage. |
| 4 | 515-535 | `if prev_hash == file_hash: reuse` per-file staleness compare | `if rel_path in changeset.unchanged: reuse` |
| 5 | 524, 556, 597, 617 | `"file_hash": file_hash` field on doc entries (4 sites) | Field removed from doc schema |
| 6 | 775 | `file_hashes=current_file_hashes` on manifest write | Field removed from KnowledgeManifest schema |

Additionally: the file walk loop at lines 362-378 (`repo_root.glob(pat)`)
converges onto `prep_engine.walk_repo` — the 5th and final remaining
non-Rust walker (Phase 134 swept 4 of 5; index.py was the holdout).

## Injection mechanics

Same closure-based pattern Phase 134 established:

1. `WorkerFactory._knowledge_worker` (`workers/__init__.py:584`) reads the
   changeset once via `read_changeset(idx_dir)` before invoking `idx.build()`.
2. `CodeIndex.build()` gains a `changeset: Optional[Changeset] = None` kwarg.
3. When called from the pipeline, `changeset` is non-None and drives reuse
   decisions.
4. When called from non-pipeline callers, `changeset` is None → fall back
   to current behavior (treat every file as added → full rebuild). This
   preserves backward compatibility with `mcp_direct.py`, agent code,
   tests, and CLI tools that build a CodeIndex outside the pipeline.

The worker has access to `project_index_dir(project)` already (it reads
`deep_knowledge_manifest.json` for the baseline-clamp logic). The
changeset path follows the same convention: `<idx_dir>/changeset.jsonl`.

## Migration

Three cases:

**1. Never built** — no `manifest.json`, no `embeddings.npy`. Changeset says
every file is `added`. Embed everything. Same outcome as today.

**2. Phase 135+ embedding manifest** — manifest is changeset-driven, no
`file_hashes` field. Load previous embeddings/docs from disk, key by
`source_path` only, use changeset for reuse decisions. The happy path.

**3. Pre-Phase-135 embedding manifest** — manifest still carries a
`file_hashes` dict (left over from before this cutover). On first run after
upgrade: the loader ignores the `file_hashes` dict completely, reads the
changeset as canonical. The dict gets dropped on the next manifest write.

There is no Phase-133-style cascade risk here. Stage 1's changeset is
*already* canonical (post-Phase-134). The pre-135 embedding manifest is
internally consistent with itself; we just stop reading its hash dict and
start reading the changeset. Files marked `unchanged` by stage 1 keep
their cached embeddings (correct — the file genuinely didn't change).
Files marked `modified` re-embed (correct — they changed). Files marked
`deleted` get dropped (correct).

## Walker convergence

The 5th and final non-Rust walker. `CodeIndex.build` currently:

```python
for pat in include_globs:
    files.extend(repo_root.glob(pat))   # index.py:374-378
```

Becomes:

```python
files = prep_engine.walk_repo(
    repo_root=str(repo_root),
    include_globs=include_globs,
    exclude_globs=exclude_globs,
    use_gitignore=use_gitignore,
)
```

(Exact signature to match what stage 1 uses — verified during
implementation.) The downstream filters (`included_paths`, `roots`,
`hard_limit_bytes`) apply on top, same as today.

This closes the walker cutover that Phase 133 opened and Phase 134's task
13/15 advanced to 4-of-5.

## Net diff target

**−75 to −100 net production lines.** Smaller than Phase 134's −300 — this
phase touches one stage's worth of surface, not six.

Rough budget breakdown:

| File | Lines deleted | Lines added | Net |
|---|---|---|---|
| `src/prep/core/index.py` — staleness sites | ~60 | ~20 (changeset-driven branches) | −40 |
| `src/prep/services/pipeline/workers/__init__.py` — changeset read + inject for stages 5 and 10 | 0 | ~20 | +20 |
| KnowledgeManifest schema field deletion (resolved during implementation: likely a dataclass / TypedDict in `core/index.py` or `core/manifest.py`) | ~5 | 0 | −5 |
| Walker convergence (`repo_root.glob` loop → `prep_engine.walk_repo`) | ~10 | ~3 | −7 |
| **Estimated total** | | | **−32** |

The −75 to −100 target is a stretch goal: hitting it depends on whether
ancillary code (the `current_file_hashes` accumulator, log lines, the
`prev_hash_by_source` map population, cold-start manifest fields) lets us
go further than the conservative table above. Floor is the table; ceiling
is the stretch target.

## Testing strategy

Mirrors Phase 134's test suite layout:

| Test file | Coverage |
|---|---|
| `tests/test_phase135_embedding_changeset.py` | `CodeIndex.build()` with explicit changesets — added, modified, unchanged, deleted partitions exercise correctly |
| `tests/test_phase135_migration_cases.py` | All three migration cases (never-built, Phase 135+ manifest, pre-Phase-135 manifest) |
| `tests/test_phase135_no_inline_hashing.py` | Static assertion: no `stable_file_hash` / `hashlib` references remain in `index.py` build path |
| `tests/test_phase135_walker_convergence.py` | `CodeIndex.build` calls `prep_engine.walk_repo`, not `repo_root.glob` |
| `tests/test_phase135_worker_injection.py` | `_knowledge_worker` reads changeset and passes it to `idx.build()` (both stage 5 and stage 10 paths) |
| `tests/test_phase135_e2e_no_llm.py` | Build → modify one file → rebuild — only the modified file's chunks change; cached embeddings preserved |

Same TDD-per-task workflow as Phase 134.

## Risks

| Risk | Mitigation |
|---|---|
| `included_paths` / `roots` filters silently drop files that the changeset marked changed — user expects them re-embedded | Apply the filter to the candidate set BEFORE intersecting with the changeset; files outside scope simply stay untouched (unchanged) regardless of changeset status |
| Embedder model change interacts with changeset — if model changed, all `unchanged` files still need re-embedding | The existing `prev_model != cur_model` branch short-circuits BEFORE the changeset is consulted. If model changed, treat every file as added |
| Migration case 3 leaves orphan `file_hashes` dict on manifest for one cycle | Acceptable. Field is harmless; gets dropped on next manifest write. No need for explicit cleanup pass |
| Non-pipeline callers (mcp_direct, agents) regress because `changeset=None` triggers full rebuild every time | This is exactly the pre-Phase-135 behavior for those callers — they never had pipeline-driven incrementalism. No regression |

## Out-of-scope follow-ups

- **`LayeredCodeIndex` Phase 136 candidate** — `core/layered_index.py` composes
  a remote + delta `CodeIndex`. Each underlying index has the same staleness
  machinery. Cutting this over needs its own design (where does the
  changeset come from for the remote layer?).
- **`build_manager` walker convergence** — the embedding stage's walker is
  the last one in the pipeline. `build_manager` itself has supporting
  walkers (e.g. for project discovery) that are not in the trace/embed hot
  path. Audit separately.
- **`file_hash` field on doc entries — full deletion in consumers** — Phase 135
  deletes the *writes* of `file_hash`. If any non-pipeline reader still
  expects the field (search code, dashboards), they may need a compat read.
  Verified during implementation; if a real consumer exists, it gets a
  follow-up rather than blocking this cutover.

## References

- Phase 133 — Rust walker/hasher cutover (`docs/Phase133_RustWalkerCutover/`)
- Phase 134 — Changeset-driven pipeline (`docs/Phase134_ChangesetDrivenPipeline/`)
- S3-1 follow-up filed at the end of Phase 134 review
- `src/prep/services/pipeline/changeset.py` — Changeset dataclass + read/write helpers (Phase 134)
- `src/prep/services/pipeline/workers/__init__.py:584` — knowledge worker (the injection site)
