# Part 11 — Atlas reports "Stale" immediately after rebuild

> **Status:** Stub / awaiting implementation plan
> **Trigger:** 2026-05-17 dashboard screenshot — atlas + all 10 sub-atlases
> badged "Stale" 90 seconds after a successful rebuild completed
> **Work order:** TBD — slot between Part 10 and Part 01 (correctness, simple fix)

## The bug

`CodebaseAtlas.is_stale()` at `src/prep/core/atlas/generator.py:1511-1521`:

```python
def is_stale(self) -> bool:
    """Phase 135.5: stale iff stage 1's Changeset has churn OR atlas
    doesn't exist yet."""
    if not self.exists():
        return True
    cs = self._resolve_changeset()
    if cs is None:
        return True
    return bool(cs.added) or bool(cs.modified) or bool(cs.deleted)
```

This treats *any* churn in `changeset.json` as a staleness signal, but
never checks whether that changeset has already been consumed by the
current atlas. Both artifacts carry a `run_id`:

```
.sourceprep/changeset.json       → run_id: run-50071c9e0869
.sourceprep/atlas_manifest.json  → run_id: run-50071c9e0869
```

After a successful rebuild the atlas IS up to date with the changeset
it just consumed, but `is_stale()` still returns True because the
changeset contains the 1971 added files from that very rebuild.
Result: dashboard permanently displays "Stale" after every non-empty
rebuild until someone manually clicks Regenerate (which loops back to
the same state).

## Evidence (2026-05-17 rebuild `run-50071c9e0869`)

```
changeset.json: added=1971, modified=0, deleted=0
atlas_manifest.json: run_id=run-50071c9e0869, started_at 20:12:43,
                     finished_at 20:13:25, elapsed 41.73s
pipeline_telemetry: atlas stage completed successfully
Dashboard 21:46 PM (~90 minutes later): all 10 sub-atlases "Stale"
```

The atlas successfully built using exactly the changeset it now
points at as evidence of being stale.

## The fix

`is_stale()` should compare `changeset.run_id` vs the atlas's own
stored `run_id` (from `atlas_manifest.json`). If they match, the atlas
already consumed this changeset → not stale. Otherwise apply the
existing churn check.

Sketch:

```python
def is_stale(self) -> bool:
    if not self.exists():
        return True
    cs = self._resolve_changeset()
    if cs is None:
        return True
    # Phase 136 P11: changeset already consumed?  Compare run_ids.
    atlas_run_id = self._load_atlas_run_id()  # reads atlas_manifest.json
    if atlas_run_id and cs.run_id == atlas_run_id:
        return False
    return bool(cs.added) or bool(cs.modified) or bool(cs.deleted)
```

The helper `_load_atlas_run_id` reads `<index_dir>/atlas_manifest.json`
and returns its `run_id`, or None if the manifest is missing/unreadable
(in which case fall back to the old churn check — safe degradation).

## Files likely touched

- `src/prep/core/atlas/generator.py` — `is_stale` + new
  `_load_atlas_run_id` helper (~15 LOC)
- Possibly `src/prep/api/routers/atlas.py` — confirm the staleness
  signal surfaced to the dashboard flows through `is_stale()` (not a
  duplicate check elsewhere)

## Audit: are other Phase 135.5 stage stalness checks similarly broken?

Phase 135.5 unified staleness around the changeset. Other stages
(deep_knowledge, group_reasoning, deepening, augmenter,
epistemic_enrichment, clustering, inferred_edges) all "consult
Changeset" per the commit log. They likely have similar
`is_stale`-shaped logic. **This Part's investigation should grep for
all `bool(cs.added) or bool(cs.modified) or bool(cs.deleted)`
patterns** and verify each one compares `run_id`s. If multiple stages
share the bug, fold them into Part 11 — same fix shape across all.

```
grep -rn "cs.added.*cs.modified.*cs.deleted" src/prep/
```

## Test plan

### Layer 1 — pytest

- `tests/test_atlas_stale_after_consume.py` (new)
  - Build atlas against a fixture project.
  - Verify `is_stale()` returns True before build (atlas doesn't exist).
  - Run atlas build.
  - Verify `is_stale()` returns False after build (run_ids match).
  - Touch a file → new changeset with a new run_id.
  - Verify `is_stale()` returns True again.

### Layer 2 — live dashboard probe

```
Before fix:
  Trigger a clean rebuild → atlas completes → dashboard shows "Stale"
  immediately. Click Regenerate → same state.

After fix:
  Same trigger → dashboard shows "Fresh" (or no badge) immediately
  after the build completes.
```

### Layer 3 — telemetry assertion

Once fixed, the `atlas_stale` UI signal (if recorded in telemetry)
should not fire within 60 seconds of an `atlas_stage_completed` event.

## Acceptance

Part 11 is shipped when:

1. `is_stale()` returns False directly after a successful rebuild
   against an unchanged repo.
2. `is_stale()` still returns True when the changeset shows real
   incremental churn against the last atlas run_id.
3. The dashboard "Stale" badge clears automatically after rebuild.
4. Sister stages (if found to share the bug) are fixed in the same
   commit.

## Risks

- **`atlas_manifest.json` missing the `run_id` field.** Check older
  builds — if pre-Phase-135.5 atlases don't carry run_id, the helper
  must fall back gracefully (return None → churn check applies).
- **Cross-machine atlas serving** (S3-hosted index pattern). The
  run_id is generated per-build per-machine; if Machine A built and
  Machine B reads, run_ids will differ. For Phase 136 scope, the dev
  workflow is single-machine; flag as out-of-scope but document.

## Cross-refs

- `00_Status_2026-05-17.md` — telemetry evidence
- Phase 135.5 commit thread:
  - `b7909647` feat(phase135.5): stage 11 atlas consults Changeset
  - `0c49c359` fix(phase135.5b): lazy-load Changeset for non-worker callers
- User screenshot 2026-05-17 17:54 PT — dashboard showing all 10
  sub-atlases as "Stale"
