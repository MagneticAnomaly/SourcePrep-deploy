# Phase 134 — Changeset-Driven Pipeline

> **Scope:** Delete every per-stage staleness check across the
> enrichment pipeline (augmenter, deepening, epistemic enrichment,
> epistemic scoring, audit StalenessAnalyzer). Replace the entire
> "each stage independently re-derives staleness from hashes"
> pattern with a single explicit `Changeset` object emitted by stage 1
> (structural) and consumed by stages 2-15. Converge the four
> remaining `os.walk` callers in pipeline-relevant code onto
> `prep_engine.walk_repo`. Net result: one source of truth for
> "what changed in this run," ~600 lines of net deletion, an entire
> bug class (cache-invalidation cascade) eliminated by construction.
>
> **Prior art:** Phase 133 (Rust Walker/Hasher Cutover) — unified
> ONE walker (`compute_trace_coverage`) and propagated a hash format
> change through it. Phase 133 was supposed to deliver "single
> source of truth for staleness," but it shipped only the walker
> half of that goal and left six staleness-check sites intact —
> propagating a hash format change through six independent
> consumers simultaneously. The result was the cache-invalidation
> cascade documented as Important #3 in the post-implementation
> review and observed live on 2026-05-10 when clicking
> deep_enrichment Auto re-ran the entire LLM chain on unchanged
> content. The Phase 133 hot-fix (`is_hash_stale` grace helper at
> commit `889c042b`) is the bandage; this phase is the actual
> surgery.
>
> **Status:** Spec approved 2026-05-11. Implementation pending.
>
> **Framing:** Deletion-driven. The headline number is "~600 lines
> removed" not "~600 lines added." Most of the work is `git rm`
> shaped, with a small `Changeset` infrastructure addition that
> makes the deletions safe.
>
> **Trigger incident:** 2026-05-10 — user clicked deep_enrichment
> Auto on the SourcePrep project after Phase 133 landed. The
> orchestrator chained into the deep enrichment group, the
> augmenter found that every stored `entry.file_hash`
> (SHA-256-64, 16 hex chars) mismatched the manifest's
> `file_hashes` (BLAKE3-128, 32 hex chars), every node was flagged
> stale, and the entire enrichment chain re-ran for content that
> hadn't changed. User correctly identified this as the
> architectural failure of Phase 133: *"why is any stage besides
> stage 1 concerned about staleness?"* The watcher already detects
> staleness; stage 1 already reconciles it. Once stage 1 has spoken,
> downstream stages should simply process what they're told to
> process — no more independent staleness derivation.

---

## What Phase 133 missed and why this phase exists

Phase 133's stated goal was *"unify the walker, single source of
truth, eliminate filter divergence."* The phase delivered ONE walker
unification (`compute_trace_coverage` → `prep_engine.walk_repo`) and
ONE hash format migration (SHA-256-64 → BLAKE3-128). It did NOT
delete the per-stage staleness checks. Result:

1. **Six staleness-check sites remained**, each independently comparing
   per-entry stored hashes against the manifest's hashes. Phase 133's
   hash format change invalidated all six caches simultaneously.
2. **Four remaining `os.walk` callers** outside coverage (in
   `repo_profile.py`, `builder.py:557`, `atlas/markdown_links.py`,
   `orchestrator.py:2772`) still walked independently with divergent
   filter implementations. Phase 133's "single walker" claim is only
   true for the coverage path.
3. **The hot-fix at commit `889c042b`** added an `is_hash_stale`
   helper that graces hash format mismatches. It works, but it's a
   bandage — it doesn't address the architectural problem (per-stage
   staleness derivation). The next time anyone touches hash semantics,
   the cascade re-emerges.

The user's framing of the actual fix:

> *"If there are new/stale files [the watcher and stage 1 detect them
> and] begin an incremental PIPELINE at stage 1, everything after
> that is simply a pipeline. The whole point of the watcher is to
> handle staleness and initiate the pipeline. After [stage 1] we
> know which files are new/stale and this should be a very easy and
> predictable thing for the pipeline to simply pass from stage to
> stage."*

This phase implements that architecture.

---

## Goals (what success looks like)

| Goal | Measurable outcome |
|---|---|
| **One source of truth for "what changed in this run"** | A single `Changeset` object, written exactly once per pipeline run by stage 1, read by every downstream stage. Zero per-stage hash comparisons remain in the codebase (verified by grep). |
| **Hash format changes are non-events for stages 2-15** | A future hash format migration would not require touching any stage past stage 1. Verified by removing the `file_hash` field from `AugmentationEntry`, `EmbeddingDoc`, etc. — if those fields are gone, no downstream stage CAN compare hashes. |
| **One walker primitive in pipeline-relevant code** | After this phase, `grep -rn "os.walk" src/prep/services/pipeline/ src/prep/core/{augmenter,deepening,epistemic_enrichment,audit/analyzers,trace}/*.py src/prep/core/repo_profile.py src/prep/core/atlas/markdown_links.py` returns zero results. (Tests, eval fixtures, and unrelated scripts are out of scope.) |
| **Net deletion of ~600 lines** | The changeset infrastructure adds ~150 lines. The deletions across augmenter, deepening, enrichment, scoring, audit, coverage self-heal, F-67 backup pattern, and `refresh_manifest_hashes` total ~750 lines. Net negative. |
| **The cache-invalidation cascade is eliminated by construction** | Re-running a Phase-133-style migration test (write SHA-256 manifest, deploy, observe behavior) produces zero LLM re-augmentation calls. Today (with hot-fix only) it produces zero only because of the `is_hash_stale` grace; after this phase it produces zero because there's no comparison to fail. |

---

## What this phase completes

The user's stated complaint was that Phase 133 *added complexity to
something that was supposed to be a simplification*. This phase
inverts that — every change is in service of removing code, not
adding it. The `Changeset` object exists ONLY to make the deletions
safe.

### What's already in place (don't rebuild)

| Primitive | Location | State |
|---|---|---|
| Rust walker `prep_engine.walk_repo` | `engine/crates/prep-walker/src/lib.rs:180` + PyO3 binding | ✅ Used by `compute_trace_coverage` and `_compute_file_hashes` |
| BLAKE3 hash via `prep_engine.hash_content` | Same crate | ✅ Used by builder + coverage |
| `_changed_paths` infra in orchestrator | `orchestrator.py:96, 2452` | ✅ Already passes paths to STRUCTURAL worker; this phase generalizes it to pass a richer `Changeset` to ALL workers |
| Pipeline journal (authoritative completion record) | `prep_pipeline_journal.db` via `pipeline_journal.py` | ✅ Used by Phase 128's journal-authority gate (`recovery.py:1515-1527`); changeset persistence will reuse it for `run_id` correlation |
| Manifest schema (`trace_manifest.json`) | `core/trace/builder.py::_build_manifest` | ✅ Stays as-is. Per the design decision below, the manifest remains the persistent hash store stage 1 needs to compute the *next* run's diff. The changeset is purely an inter-stage artifact. |

### What this phase changes

| Layer | Change |
|---|---|
| **(a)** New `Changeset` dataclass and persistence | Add `src/prep/services/pipeline/changeset.py` with `Changeset(added, modified, deleted, unchanged, run_id, base_run_id)` plus `read_changeset(idx_dir)` / `write_changeset(idx_dir, cs)`. Persisted to `.sourceprep/changeset.json`, single file overwritten by stage 1 each run. |
| **(b)** Stage 1 emits the Changeset | After `_build_python` / `_build_rust` write the manifest, also compute the diff against the prior manifest's `file_hashes` and write the resulting `Changeset` to disk. |
| **(c)** Worker contract gains `changeset` injection | `WorkerFactory` reads the latest `Changeset` from disk before constructing each worker, sets `worker.changeset = changeset`. Worker base offers `should_process(file_path) -> bool` returning `True` iff the path is in `added` or `modified`. |
| **(d)** Delete per-stage staleness checks | Augmenter, deepening, epistemic enrichment, epistemic scoring, audit StalenessAnalyzer all stop reading per-entry `file_hash`, stop reading `manifest.file_hashes`, stop comparing. Each switches to `self.changeset.should_process(path)`. |
| **(e)** Delete the `file_hash` field from stored entries | `AugmentationEntry.file_hash`, embedding doc `file_hash` keys, etc. — removed from in-memory dataclasses and from new on-disk writes. Existing on-disk entries with the field continue to load (extra field ignored). |
| **(f)** Converge remaining walkers onto `prep_engine.walk_repo` | `repo_profile.py:241, 327` (compute_index_metrics, _collect_files), `builder.py:557` (`_enumerate_files`), `atlas/markdown_links.py:152`, `orchestrator.py:2772` (post-structural sanity). Each switches to `prep_engine.walk_repo`. |
| **(g)** Simplify `compute_trace_coverage` to changeset-reader + walker-diff | Delete the per-file hash compare branch (becomes "set diff between changeset and current disk file list"). Delete the `hash_algo_mismatch` self-heal branch (Phase 133's Path A becomes unnecessary — there's no per-stage cache to invalidate). Delete the backfill carve-out (changeset is the truth). |
| **(h)** Delete `ResumeStrategy.refresh_manifest_hashes` entirely | This 220-line method exists to "refresh hashes between rebuilds." With the changeset as the staleness signal, it has no purpose. Remove its three orchestrator call sites too. |
| **(i)** Simplify F-67 manifest invalidation | The Phase 133 follow-up at `orchestrator.py:2453-2495` (rename to `.f67_pending` + restore on next start) was added to protect against Rust panics wiping the manifest. With the changeset persisted independently, the manifest's role is downgraded — the changeset is the inter-stage truth. F-67 backup pattern can simplify. (Conservative call: keep the rename pattern, delete only the inline restore logic since the manifest is now non-load-bearing for downstream stages.) |
| **(j)** Delete the Phase 133 `is_hash_stale` helper | After per-stage staleness checks are gone, `prep.core.ids.is_hash_stale` and its 5 call sites are dead code. Removed. |

### What this phase does NOT do (deferred or out of scope)

| Deferred item | Why |
|---|---|
| **`recovery.py:1310-1493` user-pause-marker simplification** | The user-pause-marker recovery has a related-but-distinct mtime concern ("manifest finished_at is unreliable when previous run wrote a stale manifest"). Phase 128 already landed the journal-authority gate that runs first; the marker tangle below it is residual complexity that should be a Phase 135. Folding it into 134 risks repeating the Phase 133 mistake of "tried to do too many things in one phase." |
| **The Rust crate panic fix** (`prep_engine.build_trace` em-dash crash) | Phase 133 follow-up commit `d8e89580` added an em-dash workaround in one file plus the F-67 backup pattern. The actual Rust crate bug (unsafe string slicing in the trace builder) needs a fix in `engine/crates/prep-*` and is a Rust workstream, not Phase 134. |
| **Migrating the watcher's pathspec filter to the Rust walker** | Watcher uses pathspec correctly today (F-40 fix). It's not a divergence source. Out of scope. |
| **Adding `hash_files` parallel batch binding** | Per-file `hash_content` calls are not the bottleneck. YAGNI. |
| **Removing the `file_hashes` field from `trace_manifest.json`** | Per design decision #1 (Approach B), the manifest remains the persistent hash store that stage 1 needs to compute the next run's diff. The field stays. Naming the manifest as "the hash store" instead of "the staleness truth" is the conceptual fix. |
| **Removing the `hash_algo` field from `trace_manifest.json`** | Stays for forensics. No consumer cares about it post-Phase-134, but it's a 5-byte field that helps future debugging. |
| **Frontend warning surface for max_files cap** (Important #2 from Phase 133 review) | Still deferred. Backend emits the warning; frontend should display it. Tracked as a Phase 134.5 follow-up. |

---

## Architecture

### Today (post-Phase-133, with hot-fix in place)

```
Watcher: OS event → trigger pipeline

Stage 1 (structural): walks (Rust), hashes (BLAKE3), writes manifest
                      with file_hashes + hash_algo. Done.

Stage 2-15: each stage independently:
  • re-reads manifest.file_hashes
  • re-reads its own per-entry file_hash from prior run's output
  • compares (with is_hash_stale grace from Phase 133 hot-fix)
  • if "stale" → re-process with LLM
  • else → use cached entry

Audit StalenessAnalyzer: re-walks disk, re-hashes, re-compares.

compute_trace_coverage (UI): re-walks disk, re-hashes, re-compares,
  + Path A self-heal branch for hash_algo mismatch,
  + backfill carve-out for files in trace_nodes but not manifest.
```

Six independent staleness-derivation sites. Hash format change
invalidates all six simultaneously. Hot-fix `is_hash_stale` graces
ONE specific failure mode (length-mismatch); any other future
divergence (different algo same length, etc.) bypasses the grace.

### After Phase 134

```
Watcher: OS event → trigger pipeline. (Unchanged.)

Stage 1 (structural): walks (Rust), hashes (BLAKE3), writes
                      manifest with file_hashes (the persistent
                      hash store), AND writes Changeset to
                      .sourceprep/changeset.json:
                        added:     {files new since prior manifest}
                        modified:  {files whose hash changed}
                        deleted:   {files in prior manifest, gone now}
                        unchanged: {everything else}
                        run_id:    "run-960393c2fecb"
                        base_run_id: "run-7b2a1e..." (or null)

Stage 2-15: each worker receives `self.changeset` injected by
  WorkerFactory. Worker uses `self.changeset.should_process(path)`
  to decide what to process. Zero hash logic. Zero manifest reads
  for staleness. Worker simply trusts: stage 1 said this path is
  in `added | modified` → process it; otherwise skip.

Audit StalenessAnalyzer (post-134):
  • orphan check: files in changeset.deleted that still have augmentations
  • coverage check: files in changeset.added | modified that the augmenter
    didn't process by run end
  Two narrow checks, no hashes.

compute_trace_coverage (post-134):
  • read changeset.json (the categorized result of the last run)
  • walker-only diff (no hashing) for "what's been added on disk
    since the last run" — surfaces unindexed files in the Graph
    Scope panel
  No hash compare. No Path A self-heal branch. No backfill carve-out.
```

One staleness-derivation site (stage 1). Hash format change is
invisible to stages 2-15 by construction (they have no `file_hash`
field to compare against, no manifest read at all).

### Diagram of the Changeset's place in the data flow

```
                             ┌─────────────────────┐
       OS event              │   Watcher (Phase 96)│
       (file modified) ────► │   debounce, trigger │
                             └──────────┬──────────┘
                                        │ run_fast_sync(project_id)
                                        ▼
                             ┌──────────────────────┐
                             │ Pipeline Orchestrator│
                             └──────────┬───────────┘
                                        │
                ┌───────────────────────┴───────────────────────┐
                │                                               │
                ▼                                               ▼
   ┌───────────────────────┐                       ┌──────────────────────┐
   │ STAGE 1 (structural)  │                       │ WorkerFactory        │
   │ • walk_repo (Rust)    │                       │ • read changeset.json│
   │ • hash_content (BLAKE3│                       │ • inject into worker │
   │ • diff vs prior       │  writes               │                      │
   │ • write trace_manifest│  changeset.json       │                      │
   │ • write CHANGESET ────┼─────────►             │                      │
   └───────────────────────┘                       └──────────┬───────────┘
                                                              │ worker.changeset = cs
                                                              ▼
                                            ┌──────────────────────────────┐
                                            │ Stage N worker               │
                                            │   for path in pending:       │
                                            │     if self.changeset        │
                                            │           .should_process(p):│
                                            │       process(p) [LLM, etc.] │
                                            └──────────────────────────────┘
```

The `Changeset` is the *only* inter-stage artifact for staleness.
The manifest's `file_hashes` is the persistent state that stage 1
diffs against on the *next* run; no other stage reads it.

---

## The Changeset object

### Schema

```python
# src/prep/services/pipeline/changeset.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import FrozenSet, Optional


@dataclass(frozen=True)
class Changeset:
    """The single source of truth for 'what changed in this pipeline run.'

    Emitted by stage 1 (structural) after it walks the filesystem,
    hashes file contents, and diffs against the prior manifest's
    file_hashes. Read by every downstream stage (2-15) to decide
    what to process. Persisted to .sourceprep/changeset.json so it
    survives daemon restarts mid-run.

    Phase 134 architecture: this is the ONLY mechanism by which any
    stage past stage 1 derives 'should I process this file.' No
    per-stage hash comparison exists post-Phase-134. A future hash
    format change is a non-event for any stage past stage 1.
    """
    added:       FrozenSet[str]   # files new since base_run_id
    modified:    FrozenSet[str]   # files whose content changed
    deleted:     FrozenSet[str]   # files in base_run, no longer present
    unchanged:   FrozenSet[str]   # everything else (carry forward augmentations as-is)
    run_id:      str              # this pipeline run's ID (matches journal)
    base_run_id: Optional[str]    # prior run we diffed against; None on first build

    def should_process(self, file_path: str) -> bool:
        """Return True iff a stage worker should run on this file in
        this run. Files in `unchanged` skip processing (carry-forward
        augmentation entries as-is); files in `deleted` are handled
        by the post-stage cleanup pass; everything in `added` or
        `modified` is fair game.
        """
        return file_path in self.added or file_path in self.modified

    def all_known(self) -> FrozenSet[str]:
        """Union of all four sets — every file the pipeline knows
        about for this run. Used by the audit orphan check."""
        return self.added | self.modified | self.unchanged
        # NB: deleted intentionally excluded — these files are no
        # longer present, so they are not "known" for downstream
        # consumers' purposes.
```

### Serialization

JSON, sorted keys, persisted at `.sourceprep/changeset.json`:

```json
{
  "version": 1,
  "run_id": "run-960393c2fecb",
  "base_run_id": "run-7b2a1e83cd45",
  "added":     ["src/prep/api/routers/projects/scope.py", ...],
  "modified":  ["src/prep/core/augmenter.py", ...],
  "deleted":   ["src/legacy/old.py"],
  "unchanged": ["src/prep/__init__.py", ...]
}
```

`unchanged` is the largest set (~1900 entries on a fresh-ish
SourcePrep run). Could be omitted from disk if file size becomes
a concern; for now keep it explicit so consumers don't need to
re-derive it.

### Persistence helpers

```python
def read_changeset(idx_dir: Path) -> Optional[Changeset]:
    """Load the changeset from disk. Returns None if absent or
    malformed (caller decides fallback behavior)."""

def write_changeset(idx_dir: Path, cs: Changeset) -> None:
    """Atomic write via tempfile + rename. The orchestrator calls
    this once per run, after stage 1's manifest write succeeds."""
```

---

## Migration

The migration boundary is "first pipeline run on a project after
Phase 134 deploys." The project's `trace_manifest.json` may be in
one of three states:

### Case 1: Project has never been built

- No prior `trace_manifest.json` on disk.
- Stage 1 walks, hashes, writes manifest, emits Changeset:
  ```
  added = {every file walker found}
  modified = {}
  deleted = {}
  unchanged = {}
  ```
- Every downstream stage processes everything. Equivalent to today's
  fresh-build behavior.

### Case 2: Project has a Phase-133+ manifest (BLAKE3-128 hashes, hash_algo set)

- Stage 1 reads prior manifest's `file_hashes` (BLAKE3-128).
- Stage 1 walks, hashes (BLAKE3-128), real diff.
- Emits Changeset with the actual `added / modified / deleted / unchanged`
  partition. Downstream stages process only the deltas.
- Equivalent to today's incremental behavior, but expressed as an
  explicit Changeset instead of derived per-stage.

### Case 3: Project has a pre-Phase-133 manifest (SHA-256-64 hashes, no hash_algo)

This is the migration boundary. The user's existing augmentation /
enrichment / module data (1900+ entries each, hours of LLM work)
must NOT be invalidated.

- Stage 1 reads prior manifest. Detects `hash_algo` is absent or
  `"sha256-64"`. Cannot meaningfully diff the SHA-256 hashes
  against fresh BLAKE3-128 hashes (different algorithms).
- Stage 1 emits a **migration changeset**:
  ```
  added = {files on disk NOT in prior manifest's file_hashes}
  modified = {}
  deleted = {files in prior manifest, no longer on disk}
  unchanged = {everything else from prior manifest still on disk}
  ```
- This **trusts the prior augmentation work** unconditionally. The
  augmenter / enricher / deepening / scoring / audit see
  `should_process` return False for the existing entries → skip
  re-processing → preserve the user's hours of LLM work.
- Stage 1 ALSO writes a fresh BLAKE3 manifest. The next run's diff
  is then a real Case-2 diff.

This is the same behavior as the Phase 133 hot-fix's `is_hash_stale`
helper — but applied at the changeset boundary (stage 1, once)
instead of at every downstream comparison site (5 places, every run).

After the migration boundary is crossed, the project is in Case 2
forever; the migration logic never re-runs.

---

## Worker contract

### Today

Workers are constructed by `WorkerFactory.create_worker(project_id, stage)`.
The orchestrator passes per-run state via class-attribute assignment
on `WorkerFactory` itself (e.g., `WorkerFactory._changed_paths[project_id] = ...`).
Workers read the assignment when they need it.

### Post-Phase-134

Workers gain a `self.changeset` attribute, populated by `WorkerFactory`
at construction time:

```python
class Worker:
    changeset: Optional[Changeset] = None  # set by WorkerFactory

    def should_process(self, file_path: str) -> bool:
        """Convenience for the common case. Returns True iff the
        path is in this run's changeset added/modified set."""
        if self.changeset is None:
            return True  # no changeset → process everything (defensive)
        return self.changeset.should_process(file_path)
```

`WorkerFactory.create_worker` reads the changeset once per stage
start, sets it on the constructed worker, returns. Each worker uses
`self.should_process(path)` instead of any hash comparison.

The defensive `changeset is None → process everything` fallback
exists to protect against the orchestrator forgetting to set it
during a refactor. Tests will verify the orchestrator always sets it.

---

## Recovery semantics

### Daemon restarts mid-stage-7 with a written Changeset on disk

1. Orchestrator's existing recovery code reads the journal, finds
   stage 7 was active.
2. Recovery flow loads the Changeset from `.sourceprep/changeset.json`.
3. WorkerFactory injects it into the resumed stage-7 worker.
4. Worker resumes processing the changeset's `added | modified` set
   from where it left off (existing per-stage resume logic, unchanged).

### Daemon restarts mid-stage-1 with a partial manifest write

1. F-67 backup pattern (Phase 133 hardening) restores the prior
   manifest from `.f67_pending` if no fresh manifest exists.
2. The prior changeset (from the previous successful run) is still
   on disk. It is ignored — stage 1 will rewrite it.
3. Stage 1 retries from scratch, computing a fresh Changeset.

### Daemon restarts mid-stage-1 BEFORE the changeset has been written

1. Same as above. The changeset is written atomically AFTER the
   manifest write succeeds, so a pre-changeset crash leaves the
   prior changeset intact (and stale-but-internally-consistent).
2. Stage 1's retry overwrites both manifest and changeset.

---

## Detailed change manifest

| Task | File(s) | Summary |
|------|---------|---------|
| 1 | `src/prep/services/pipeline/changeset.py` (new) | Add `Changeset` dataclass, `read_changeset`, `write_changeset`. ~80 lines. |
| 2 | `src/prep/core/trace/builder.py` (`_build_python` and `_build_rust`) | After manifest write, compute the changeset by diffing prior manifest vs new file_hashes, write to disk via `write_changeset`. Handle the three migration cases above. |
| 3 | `src/prep/services/pipeline/workers/__init__.py` (or appropriate base) | Add `Worker.changeset: Optional[Changeset] = None`. Add `Worker.should_process(file_path)` convenience method. |
| 4 | `src/prep/services/pipeline/workers/factory.py` (`WorkerFactory.create_worker`) | Load changeset once per stage start. Inject into constructed worker via `worker.changeset = cs`. |
| 5 | `src/prep/core/augmenter.py` | DELETE: `AugmentationEntry.file_hash` field, `_load_manifest_hashes`, the entire hash compare block (~20 lines around line 524). REPLACE: with `if not self.changeset.should_process(file_path): continue`. |
| 6 | `src/prep/core/deepening.py` | DELETE: `_load_manifest_hashes` (line 649), the stale-set hash compare loop (line 158-175). REPLACE: stale_set computed from `self.changeset` directly. |
| 7 | `src/prep/core/epistemic_enrichment.py` | DELETE: per-stage manifest hash reads (lines 449, 1365), per-entry compare (line 475). REPLACE: `should_process` check. |
| 8 | `src/prep/core/epistemic_score.py` | DELETE: c6 staleness check (lines 211-220) entirely. The c6 component existed to discount scores for files whose enrichment was stale (hash mismatch). With Phase 134 those entries don't exist — the augmenter / enricher only ever produces entries for files in the current changeset's added/modified set, and those entries are by definition fresh. Redistribute the c6 weight (`SCORE_WEIGHTS["staleness"]`) across the other components proportionally (or drop the weight entirely and renormalize). Verify by running the existing scoring tests; no score should change for entries that pre-Phase-134 had c6 = 1.0. |
| 9 | `src/prep/core/audit/analyzers/staleness.py` | REWRITE: from "compare hashes for every file" to two narrow checks: (a) orphan check (files in changeset.deleted with surviving augmentations), (b) coverage check (files in changeset.added | modified that the augmenter didn't process by run end). ~60 lines down from ~80. |
| 10 | `src/prep/core/trace/coverage.py` | DELETE: per-file hash compare branch (~80 lines around line 320-460), Path A `hash_algo_mismatch` self-heal branch (~30 lines), backfill carve-out (~50 lines around line 110-220). REPLACE: read changeset for "what the pipeline knows about" + walker-only diff (no hashing) for "what's been added on disk since the last run." |
| 11 | `src/prep/services/pipeline/resume.py` (`refresh_manifest_hashes`) | DELETE entire method (lines ~816-1043, ~220 lines). DELETE three call sites in `orchestrator.py:572, 684, 2231`. The changeset is the staleness signal; refreshing manifest hashes between runs is unnecessary and error-prone (Critical #1 from Phase 133 review). |
| 12 | `src/prep/core/ids.py` | DELETE: `is_hash_stale` helper (added in Phase 133 hot-fix, commit 889c042b). DELETE: 5 call sites (augmenter, deepening, epistemic_enrichment, epistemic_score, audit/analyzers/staleness). All gone after tasks 5-9. |
| 13 | `src/prep/core/repo_profile.py` | Migrate `os.walk` callers at lines 241, 327 to `prep_engine.walk_repo`. |
| 14 | `src/prep/core/trace/builder.py` (`_enumerate_files`) | Migrate `os.walk` at line 557 to `prep_engine.walk_repo`. (May allow deletion of `_enumerate_files` entirely if no remaining caller.) |
| 15 | `src/prep/core/atlas/markdown_links.py` | Migrate `os.walk` at line 152 to `prep_engine.walk_repo`. |
| 16 | `src/prep/services/pipeline/orchestrator.py` (post-structural sanity) | Migrate `os.walk` at line 2772 to `prep_engine.walk_repo`. |
| 17 | `src/prep/services/pipeline/orchestrator.py` (F-67 backup) | Simplify the rename-to-`.f67_pending` pattern from Phase 133 commit `d8e89580`. The manifest is no longer load-bearing for downstream stages (the changeset is), so the restoration logic at line 2466-2475 can simplify to a normal atomic write. Conservative call: keep the rename, drop the inline restore — just delete the backup if the stage succeeds. |
| 18 | Tests: 6 new files | See Testing strategy below. |
| 19 | `docs/Phase134_ChangesetDrivenPipeline/IMPLEMENTATION_PLAN.md` | Created by `superpowers:writing-plans` after spec approval. |
| 20 | `docs/MASTER_TODO.md` | Append Phase 134 entry. |
| 21 | `docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md` (new) | New dogfooding follow-up doc capturing the Phase 134 lessons + the prep MCP gaps observed during the spec phase (intent classifier collapsing to MASTER_ROADMAP.md, prep_impact over-filtering for hub files, atlas role projection ignoring task-named files). |

**Net diff estimate:** +~250 lines (changeset infra + worker contract + builder integration + tests). −~850 lines (per-stage staleness checks, refresh_manifest_hashes, coverage's self-heal + backfill, is_hash_stale helper). **Net −600 lines.**

---

## Testing strategy

Per the `superpowers:test-driven-development` skill and the
`feedback_test_full_import_chain.md` memory ("for cross-module
features, at least one test must not mock the seam under test").

### TDD discipline

Each task lands a failing test first, then the implementation, then
the verification. Per Phase 133's rhythm, each task ends with a
commit (`feat(phase134): ...`) — bisectable, revertable.

### Test layers

1. **Changeset object unit tests** — `tests/test_phase134_changeset.py`. Schema, serialization, `should_process`, `all_known`, the three migration cases.
2. **Worker contract tests** — `tests/test_phase134_worker_changeset_injection.py`. WorkerFactory injects the changeset; workers see it; the defensive None fallback works.
3. **Migration tests** — `tests/test_phase134_migration_cases.py`. Cover Case 1 (no manifest), Case 2 (BLAKE3 manifest), Case 3 (SHA-256 manifest, the trust-prior-work scenario). The Case 3 test is the one that proves the cache invalidation cascade is dead.
4. **Per-stage cutover tests** — `tests/test_phase134_<stage>_uses_changeset.py` for each of augmenter, deepening, epistemic_enrichment, epistemic_score, audit-staleness. Each test mocks the worker's changeset, verifies the stage processes the right files and skips the rest. Integration test (no mock at the seam) for at least one stage.
5. **Walker convergence tests** — `tests/test_phase134_walker_convergence.py`. Greps the codebase for `os.walk` outside the explicit out-of-scope list (eval, scripts, tests). Asserts zero hits in pipeline-relevant code. Guards against future `os.walk` reintroduction.
6. **End-to-end migration smoke** — `tests/test_phase134_e2e_no_llm_recall.py`. Builds a fixture project with stub augmentations carrying SHA-256 hashes, runs stage 1 + augmenter, asserts zero augmenter LLM call sites were invoked. The headline regression test for the Important #3 cascade.

### Integration test discipline

Per the memory: at least one test per cross-module feature MUST exercise the actual Python ↔ disk ↔ stage-worker seam without mocks. The end-to-end migration smoke (test 6) is that test.

### Pre-existing test fixes

Phase 134 will likely surface tests that mocked the per-stage hash comparison. Those tests need to either delete their mock setup or be deleted entirely. List captured during implementation; cataloged in the implementation plan.

---

## Migration validation

After Phase 134 deploys and the daemon restarts:

```bash
# 1. Check that every project's manifest is BLAKE3-128 (Phase 133's work persists)
for dir in ~/.local/share/sourceprep/projects/*/; do
  echo "$dir: $(jq -r '.hash_algo // "absent"' "$dir/trace_manifest.json")"
done

# 2. Trigger one coverage call per project (e.g. dashboard load)
curl -s "http://localhost:8400/projects/<pid>/trace/coverage" | jq '.data.summary'

# 3. Verify changeset.json was written by stage 1
for dir in ~/.local/share/sourceprep/projects/*/; do
  ls -la "$dir/.sourceprep/changeset.json" 2>/dev/null || echo "$dir: no changeset"
done

# 4. Verify the migration didn't trigger a full re-augmentation
# (count LLM calls in daemon log over a window after restart)
grep -c "augmenter.*llm_request" /tmp/prep_daemon_logs/daemon_*.log
# Expected: low single digits (only for genuinely new files), not thousands.

# 5. Verify the cascade is dead
# (click deep_enrichment Auto, watch the augmenter immediately report cache hits)
curl -X PUT http://localhost:8400/projects/<pid> \
  -d '{"config":{"auto_config":{"deepEnrichment":"auto"}}}'
# Then watch logs for "augmenter cache hit" messages dominating "llm_request" messages.
```

If the LLM-call count after step 5 is non-trivial (more than the
count of files actually modified since last run), Phase 134 didn't
land its promise — investigate before declaring done.

---

## Rollback story

If Phase 134 causes user-visible problems and we need to back out:

1. **Code rollback:** revert the Phase 134 commits. The pre-Phase-134
   per-stage hash compare logic comes back.
2. **Data rollback:** `.sourceprep/changeset.json` is now an unread
   file (older code doesn't open it). Stays on disk harmlessly.
3. **Manifest:** unchanged by Phase 134 (still BLAKE3-128 from
   Phase 133). Older code reads it normally.
4. **Per-entry `file_hash`:** the post-Phase-134 augmenter / enricher
   stopped writing it. New entries lack the field. Rolled-back code
   reads the missing field as `None`, treats as "no comparison data"
   → up-to-date (graceful).
5. **No data loss.** The user's augmentation / enrichment / module
   data is unaffected.

The bidirectional safety is a property of the design: the changeset
is purely additive, the deletion of `file_hash` from entries
gracefully degrades on rollback (treated as missing, not as
mismatched).

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **The Case 3 migration trusts the prior augmentation work unconditionally.** If the prior augmentation was incomplete or corrupt, Phase 134 freezes that bad state. | The augmenter still has its own "did this entry have an error?" check; entries with errors are processed regardless of changeset. The migration only protects entries that were *successfully* augmented in prior runs. |
| **A worker forgets to consult `self.changeset` and processes everything.** | The defensive `changeset is None → process everything` fallback covers the case where the orchestrator forgets to inject. But a worker bug that ignores the injection silently is harder to catch. Mitigation: per-stage cutover tests assert that workers process exactly the changeset's `added | modified` files, no more, no fewer. |
| **The Case 3 migration emits `unchanged = {everything in prior manifest}` even for files that are physically gone from disk.** | Fixed by the `unchanged = {prior manifest entries that still exist on disk}` clause in the Case 3 logic. Verified by test_phase134_migration_cases.py. |
| **Stage 1's diff is wrong (files marked unchanged that actually changed).** | This is just "stage 1 has a bug" — the same risk that exists today. The user-visible effect is "edits not picked up until next change" — same as today. The hash-diff logic is well-tested by Phase 133's coverage tests. |
| **Existing tests break because they assumed the per-stage hash comparison.** | Each broken test gets either deleted (if it was testing the deleted logic) or rewritten (if it was testing functionality that survived). Tracked in the implementation plan task-by-task. |
| **The `.sourceprep/changeset.json` file size on a 100k-file repo is ~5 MB (mostly the `unchanged` set).** | Acceptable on disk. If profiling shows it's a hot-path slowdown, omit `unchanged` and have consumers compute it as `all_disk_paths - added - modified - deleted`. YAGNI for now. |

---

## Out-of-scope items flagged for future phases

| Item | Why deferred |
|---|---|
| `recovery.py:1310-1493` user-pause-marker simplification | Different problem class. Phase 135 candidate. |
| Rust crate panic fix (`prep_engine.build_trace` em-dash) | Rust workstream, not Python. |
| Watcher pathspec → Rust walker | Watcher already correct (F-40). YAGNI. |
| `hash_files` parallel batch binding | YAGNI; profile first. |
| `trace_manifest.json::hash_algo` field deletion | Stays for forensics. |
| Frontend warning surface for max_files cap (Important #2 from Phase 133 review) | Tracked as Phase 134.5 follow-up. |

---

## Success criteria

The phase is done when:

1. ✅ `src/prep/services/pipeline/changeset.py` exists with `Changeset` dataclass, `read_changeset`, `write_changeset`. Tested.
2. ✅ Stage 1 (`TraceBuilder._build_python` and `_build_rust`) writes `changeset.json` after every successful build. The three migration cases (no manifest / BLAKE3 manifest / SHA-256 manifest) all produce correct changesets per the spec.
3. ✅ `WorkerFactory` injects the loaded changeset into every worker before construction returns. Verified by integration test.
4. ✅ Augmenter, deepening, epistemic_enrichment, epistemic_score, audit StalenessAnalyzer all use `self.changeset.should_process(path)` and have NO hash comparison logic remaining. Verified by grep + per-stage tests.
5. ✅ `AugmentationEntry.file_hash`, embedding doc `file_hash` keys, and analogous fields are removed from in-memory dataclasses and from new on-disk writes. Existing on-disk entries with the field continue to load (extra field ignored).
6. ✅ `compute_trace_coverage` no longer hashes anything. Reads the changeset for the categorized prior-run state, plus a walker-only diff for "what's new on disk." All `hash_algo_mismatch` self-heal logic and backfill carve-outs are gone.
7. ✅ `ResumeStrategy.refresh_manifest_hashes` and its three call sites are deleted.
8. ✅ `prep.core.ids.is_hash_stale` and its 5 call sites are deleted.
9. ✅ All four remaining `os.walk` callers in pipeline-relevant code (repo_profile, builder._enumerate_files, atlas/markdown_links, orchestrator post-structural) use `prep_engine.walk_repo`. Verified by grep.
10. ✅ The end-to-end migration smoke test (`test_phase134_e2e_no_llm_recall.py`) passes — proves the Important #3 cascade is dead by construction.
11. ✅ Phase 133's hot-fix (`is_hash_stale`) and the cascade's bandage are gone. The hot-fix existed only to keep the patient alive until Phase 134 — it's removed in this phase, not preserved.
12. ✅ `docs/Phase82_MCP-Dogfooding/19_Followup_2026-05-11.md` documents the Phase 133 → 134 lesson plus the three prep MCP gaps observed during spec authoring.
13. ✅ Net line delta is negative (≥ −400 lines). Phase 134 ships less code than what was in the codebase at the end of Phase 133.

---

## Open questions (none — all resolved during brainstorming)

All design decisions were resolved in the 2026-05-11 brainstorming
session. If new questions arise during implementation, they go in
the `IMPLEMENTATION_PLAN.md` under "Decisions to make during
execution" and not back into this spec.
