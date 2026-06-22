# Phase 145 Finding — Stage 15 (Immune System / Antibodies) never appears complete in the UI

**Status:** Open. Symptom reported from dogfooding. Root cause not yet confirmed against live evidence — multiple plausible causes pinned in the code.
**Found:** 2026-06-17, reported by Eric.
**Severity:** Medium. The Finalize group's last stage (stage 15) appears stuck in `Not run` indefinitely. User cannot tell whether the worker ran-and-produced-zero, ran-and-failed, or was never reached.
**Linked symptom in README:** §2n (to be added).

---

## 1. Symptom (as reported)

> "It is either never running stage 15 or it's never showing stage 15 is complete in the UI."

The Finalize group's fifth and final stage is `antibodies` (UI label: "Immune System"). Even after a finalize run, the stage row continues to render `Not run` in `GraphEnrichmentPipeline.tsx`, with no progress bar, no completion checkmark, and no derived-antibody count.

The user does not yet know whether the worker is:
1. Never being dispatched (orchestrator stops at stage 14, audit), OR
2. Being dispatched but failing silently, OR
3. Being dispatched and succeeding but with `0` derived antibodies (which the UI treats indistinguishably from "never ran").

This finding pins the code-level reasons all three appear identical from the dashboard, and lists diagnostic checks to distinguish them on the next run.

## 2. The "stage 15 is complete" decision — code trace

### 2.1 Frontend gate (`GraphEnrichmentPipeline.tsx:1550-1557`)

```tsx
{
  id: 'antibodies', label: 'Immune System', icon: Shield, modelTag: 'CPU',
  state: promoteForRebuild(finStageState('antibodies', !!(effectiveAntibodiesStatus?.count))),
  stats: effectiveAntibodiesStatus?.count
    ? `${effectiveAntibodiesStatus.count} antibodies`
    : finStageState('antibodies', false) === 'running' ? 'Deriving...' : 'Not run',
  ...
}
```

The completion gate is `!!(effectiveAntibodiesStatus?.count)`. If `count <= 0`, `finStageState` returns `'not_built'` and the row renders `Not run`. There is **no intermediate state for "stage ran but produced no derivables"** — zero count is treated identically to never-ran.

Compare with sibling finalize stages, which gate on existence/booleans, not counts:
- Atlas → `!!effectiveAtlas?.exists && (module_count ?? 0) > 0`
- Rules → `!!effectiveRulesStatus?.generated && (module_count ?? 0) > 0`
- Concepts → `!!effectiveConceptsStatus?.seeded`
- Audit → `!!effectiveAuditPipelineStatus?.exists`

Antibodies is the only stage gated purely on a count of derived items.

### 2.2 Backend status route (`src/prep/api/routers/pipeline.py:789-803`)

```python
antibodies_status: dict[str, Any] = {"count": 0}
try:
    from prep.services.antibody_store import antibody_store
    ab_list = antibody_store.list_antibodies(project_id)
    antibodies_manifest_path = idx_dir / "antibodies_manifest.json"
    antibodies_status = {
        "count": len(ab_list) if antibodies_manifest_path.exists() else 0,
    }
except Exception:
    pass
```

`count` is non-zero only when **both**:
- `antibodies_manifest.json` exists at the index dir, AND
- `antibody_store.list_antibodies(project_id)` returns at least one row.

The comment above this block calls out the gate explicitly: "the antibody_store may carry rows derived in a prior session. Without the manifest gate, count > 0 would flip the Immune System stage to complete on a fresh post-reset project." So the dual gate is intentional — but it means a missing manifest OR a missing DB row independently zeroes the count.

### 2.3 Worker (`src/prep/services/pipeline/workers/__init__.py:1631-1693`)

```python
def worker(slot, progress_cb):
    ...
    log_cb("Loading concepts", 0, 2)
    concepts = concept_store.list_concepts(project_id)

    if not concepts:
        log_cb("No concepts — skipping", 1, 1)
        return {
            "stage": "antibodies",
            "skipped": True,
            "reason": "no_concepts",
            "_stage_timing": {...},
        }

    log_cb("Deriving antibodies", 1, 2)
    concept_dicts = [c.to_dict() if hasattr(c, "to_dict") else c for c in concepts]
    antibodies = derive_antibodies_for_project(concept_dicts)

    saved = 0
    try:
        saved = antibody_store.save_many(project_id, antibodies)
    except Exception as e:
        logger.warning(...)
        for ab in antibodies:
            try:
                antibody_store.save(project_id, ab)
                saved += 1
            except Exception as e2: ...

    log_cb(f"{saved} antibodies derived", 2, 2)
    return {"stage": "antibodies", "skipped": False, "derived": ..., "saved": saved, ...}
```

The worker **always returns a result** — either `skipped=True` (no concepts) or `skipped=False` with derived/saved counts. It does not raise.

### 2.4 Derivation filter (`src/prep/core/antibody_derivation.py:79-199`)

`suggest_antibody(concept)` returns `None` unless the concept satisfies **all** of:
- `kind == "concept"` (not `module_rationale` — the bulk Phase 125b layer is excluded)
- `category in ("constraint", "architecture")`
- `status` not in `(archived, superseded, deprecated)`
- has at least one `anchor`
- has `assertion` or `content` text

For projects whose concept seeding produces mostly `module_rationale` rows or whose `concept` rows are `category="technical"`, `derive_antibodies_for_project()` returns `[]` even though the input list is non-empty. The worker then calls `save_many(project_id, [])` which immediately returns `0` (early-out at `antibody_store.py:155`).

### 2.5 Manifest writer (`src/prep/services/pipeline/orchestrator.py:4535-4710`)

`_write_stage_manifest_and_update_run` runs unconditionally after the worker returns. It writes via `ManifestStore.write_provenance(stage, manifest.to_dict())`. Notably:
- `STAGE_OUTPUT_FILE[StageId.ANTIBODIES] == None` (stages.py:227) — there is no JSONL to read a count from.
- `STAGE_CONFIDENCE_FIELD[StageId.ANTIBODIES] == None` (stages.py:248).
- The manifest's `quality`/`throughput` blocks are skipped because the quality path requires an output file.

So the manifest **carries no count of its own**. The number of derived antibodies lives entirely in the shared SQLite store at `<data_dir>/prep_antibodies.db`, scoped by `project_id`.

### 2.6 The intersection

The UI shows "Not run" whenever:
- `antibodies_manifest.json` is missing, **OR**
- `antibody_store.list_antibodies(project_id)` returns `[]`.

Any of the following scenarios produces "Not run" — without a way to distinguish them from the dashboard:
- (a) Orchestrator never dispatched stage 15.
- (b) Worker dispatched but raised (no manifest written via `_write_stage_manifest_and_update_run`'s outer `try/except`).
- (c) Worker dispatched, returned `skipped=True` because `concept_store.list_concepts(project_id)` returned `[]`. Manifest IS written; DB has no rows for this project_id.
- (d) Worker dispatched, found concepts, but `derive_antibodies_for_project` returned `[]` because none matched the constraint/architecture filter. Manifest IS written; DB has no rows.
- (e) `save_many` failed in BOTH the batch and the per-item fallback path. Manifest IS written; DB has no rows.
- (f) `antibody_store` resolved a different `data_dir` than the read side (e.g., MCP-server / FastAPI-daemon split — there is an explicit lazy-init fallback at `antibody_store.py:108-115` that uses `prep.core.paths.data_dir()`; a divergence here would route writes to one DB and reads to another).

## 3. Hypotheses, ranked

| # | Hypothesis | Why I think it's likely | First place to check |
|---|---|---|---|
| **H1** | Scenarios (c) or (d): worker ran, returned an empty set, manifest written, count=0. **The stage genuinely completed but the UI's count-gate hides it.** | Most projects' concepts are dominated by `module_rationale` rows (Phase 125b bulk layer). The `kind=concept` + `category in {constraint, architecture}` filter is narrow — many projects legitimately produce 0 derivables. | Check `antibodies_manifest.json` mtime on disk (was it written during the last run?). Then check `pipeline_*.log` for `[Antibodies]` worker-progress lines emitted via `log_cb`. |
| **H2** | Scenario (a): orchestrator never dispatched stage 15. | `FINALIZE_WAVES` (`stages.py:269-273`) puts `ANTIBODIES` alone in the third wave. If wave 2 (rules / concepts / audit) is treated as the group's terminal wave by some path, antibodies never dispatches. | Inspect `pipeline_run_metadata.json` `stage_metadata` for `antibodies`. If absent, the orchestrator didn't reach it. |
| **H3** | Scenario (b) / (e): worker raised, or `save_many` and the per-item fallback both failed. | The per-item fallback exists *because* `save_many` has been observed to fail under writer-lock contention (F-37, `antibody_store.py:151-152`). If both paths fail, only a warning log is emitted. | Grep daemon logs for `save_many failed for antibodies` or `Failed to save antibody`. |
| **H4** | Scenario (f): write/read `data_dir` divergence between MCP process and daemon. | The lazy-init at `antibody_store.py:108-115` was added because the MCP server has its own process and singleton. If the daemon writes to one DB and the status route reads from another, the count is always 0. | Compare `data_dir()` resolution between the daemon and any other process that touches `antibody_store`. Inspect `prep_antibodies.db` rows: `sqlite3 <data_dir>/prep_antibodies.db "SELECT project_id, count(*) FROM antibodies GROUP BY project_id"`. |
| **H5** | UI rebuild-aware snapshot pins a stale `count=0`. | `effectiveAntibodiesStatus = rebuildAware(antibodiesStatus, rebuildSnapshotRef.current.antibodiesStatus, (v) => !!v?.count)` (`GraphEnrichmentPipeline.tsx:1144`). If the snapshot baseline captured `count=0` during a rebuild, the rebuild-aware projection might mask a subsequent non-zero value depending on `rebuildAware`'s contract. | Read `rebuildAware` and confirm it falls forward when the live value is truthy. Cross-check by hard-refreshing the dashboard after a finalize run. |

**Most likely:** H1. The narrow derivation filter combined with the count-only UI gate is a clean explanation for what the user is seeing without invoking any actual bug — it's a UX gap. But H2–H5 are real bugs if they fire, and the diagnostic to distinguish them is cheap.

## 4. Diagnostic checklist (run on the next finalize run)

For the affected project (`<project_id>`, index dir `<idx>`):

1. **Did the manifest get written?**
   ```bash
   ls -la <idx>/antibodies_manifest.json
   # mtime within the last finalize run window? → worker reached _write_stage_manifest_and_update_run
   # missing? → H2 (never dispatched) or H3 (worker raised before manifest write)
   ```
2. **Did the worker log anything?**
   ```bash
   grep -E '\[Antibodies\]|antibodies' <idx>/logs/pipeline_*.log | tail -20
   # "Loading concepts" → dispatched
   # "No concepts — skipping" → H1, scenario (c)
   # "N antibodies derived" with N=0 → H1, scenario (d)
   # "save_many failed" / "Failed to save antibody" → H3, scenario (e)
   ```
3. **Did rows actually persist?**
   ```bash
   sqlite3 <data_dir>/prep_antibodies.db \
     "SELECT count(*) FROM antibodies WHERE project_id = '<project_id>'"
   # > 0 → worker succeeded; UI is incorrectly hiding it (H5 or status route returning the wrong path)
   # 0   → either (c), (d), (e), or (f)
   ```
4. **Are there any constraint/architecture concepts to derive from?**
   ```bash
   # Via API:
   curl -s localhost:8400/projects/<project_id>/concepts | jq \
     '.data.concepts | map(select(.category as $c | ["constraint","architecture"] | index($c))) | length'
   # 0 → confirms H1 (d)
   # > 0 but the row count from step 3 is 0 → escalate to H3 / H4
   ```
5. **Compare to a known-good case (this repo).** SourcePrep has concepts. Run finalize, check that stage 15 lights up. If it does on SourcePrep but not on the user's other projects, H1 is confirmed.

## 5. Design questions raised (do NOT fix here)

These belong in a `PROPOSAL_` once the diagnostic above produces evidence:

- **Q1.** Should the antibodies stage have a "ran, derived 0" terminal state distinct from "not run"? The other finalize stages avoid this by gating on existence — `audit` shows complete with `0 findings`, for example. Mirroring that pattern (gate on `antibodies_manifest.json` exists + a separate `ran` bool, with `count` as a stat, not a gate) would eliminate the false `Not run` for scenarios (c) and (d).
- **Q2.** Should `STAGE_OUTPUT_FILE[ANTIBODIES]` produce an actual on-disk file (e.g., `antibodies_derived.json`) so the manifest carries a count instead of routing the count through the shared SQLite store? This would also remove the H4 cross-process risk.
- **Q3.** Is `derive_antibodies_for_project`'s filter (constraint + architecture + anchors + text) the intended Phase 125b boundary, or is it too narrow? `module_rationale` rows are the bulk of every project's concept output today.

## 6. Out of scope

- The UI gate fix itself.
- Any change to the worker's derivation logic.
- Cross-process `data_dir` rationalization.

This finding documents the symptom and pins the proximate code paths. Implementation comes after a `DIAGNOSTIC_` or `PROPOSAL_` per the Phase 145 working principles.

---

## 7. Recurrence 2026-06-19 19:14 — confirms "regular" pattern user described

Eric: "another bug I'm pretty sure stage 15 regularly claims to have never been run when it has."

Screenshot (small project, finalize group):

| Stage | UI state |
|---|---|
| Atlas Building | ✓ (372 segments · 920 files) |
| Rules Generation | ✓ (Generated) |
| Concept Seeding | ✓ (1 concepts) |
| Structural Audit | ✓ (732 findings) |
| Immune System | empty circle + "Not run" |

The other four finalize stages clearly ran (with valid metadata). Immune System is the only "Not run" row. **This is the same pattern documented in §1, now confirmed as a regular recurrence.** The user's word "regularly" — multiple sessions — means this is not edge-case noise; this is the dominant outcome on small projects.

**Strongest hypothesis given this screenshot's specifics:** scenario (d) from §3 — "Found concepts but derivation filter rejected all." With only **1 concept** in the project, the antibody derivation pipeline likely had nothing usable to derive from. Worker ran, emitted `count: 0`, manifest written cleanly, UI's `count > 0` gate rendered "Not run." Worker did its job correctly; the UI's count-based completion gate is the bug.

This is exactly the case [`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md) T1 closes — if `compute*State` (the finalize equivalent `finStageState`) consulted `stage_results["antibodies"]` from S1 instead of `effectiveAntibodiesStatus?.count`, this row would render `complete` because S1 fired `STAGE_COMPLETED` for the stage regardless of whether the worker produced any antibodies. **T1 + a "complete-but-empty" chip (Thread D-shape) is the clean fix.**

Recurrence count: at least 3 captured (the original §2n screenshots earlier, plus 2026-06-19 19:14). All on different project / stage-output combinations. The bug is structural, not data-dependent.

---

**Linked code:**
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1550-1557` — UI completion gate
- `src/prep/api/routers/pipeline.py:789-803` — status route dual-gate
- `src/prep/services/pipeline/workers/__init__.py:1631-1693` — worker
- `src/prep/core/antibody_derivation.py:79-209` — derivation filter
- `src/prep/services/antibody_store.py:148-185` — `save_many` + writer-lock note (F-37)
- `src/prep/services/pipeline/orchestrator.py:4535-4710` — generic manifest writer
- `src/prep/services/pipeline/stages.py:212-273` — `STAGE_OUTPUT_FILE`, `FINALIZE_WAVES`
