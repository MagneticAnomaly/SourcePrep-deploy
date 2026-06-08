# Pipeline Reliability + UX Audit Fixes (post-2026-06-08 incident) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the chain of bugs surfaced by the 2026-06-08 incident where initializing a second project triggered cross-project pipeline runs, freshness-skipped stages displayed as "0% Running" forever, and clustering output was silently reverted by the Write Guard.

**Architecture:**
- **Pipeline isolation:** the global `/settings/pipeline-config` endpoint stops dispatching runs across all projects; per-project `auto_config` becomes the sole authority (matching the existing `_is_*_auto` design contract).
- **UI state honesty:** freshness-skipped stages persist a `"skipped"` status to `pipeline_run_metadata.json` so the dashboard stops rendering them as running. The X-button design gains transparency via toasts plus a repeat-click heuristic that catches runaway-loop cases without punishing accidental clicks.
- **Write Guard correctness:** the shrink guard distinguishes "the workload legitimately shrunk" from "data was destroyed" using the active changeset; cluster stages that reorganize data without growing the file count don't get reverted.
- **Orphan loop break:** clustering interrupted by a Write Guard revert is recorded as failed and skipped on the next selfheal scan instead of re-attempting the same revert cycle forever.

**Tech Stack:** Python (FastAPI backend, pytest), React/TypeScript (Vite UI, Storybook), Rust engine (untouched).

---

## File Structure

| Workstream | Files Created | Files Modified |
|---|---|---|
| P0 commit hygiene | (none) | (commits unstaged work in topic bundles) |
| P1 settings fan-out | `tests/test_settings_pipeline_config_no_fanout.py` | `src/prep/api/routers/settings.py` |
| P2 skipped-stage UI | `tests/test_pipeline_metadata_skip.py` | `src/prep/services/pipeline_metadata.py`, `src/prep/services/pipeline/orchestrator.py` (verify) |
| P3 X-button toast + heuristic | `packages/ui/src/components/primitives/Toast.tsx`, `packages/ui/src/components/primitives/Toast.stories.tsx`, `packages/ui/src/hooks/useCancelToast.ts`, `tests/test_pipeline_cancel_reason.py` | `src/prep/api/routers/pipeline.py`, `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx`, `src/prep/dashboard/src/App.tsx` (or root toast mount point) |
| P4 Write Guard correctness | `tests/test_write_guard_clustering_shrink.py` | `src/prep/services/pipeline/orchestrator.py` (`_compute_allowed_shrink_ratio`), `src/prep/services/pipeline_integrity.py` (per-stage override) |
| P5 orphan-clustering loop break | `tests/test_orphan_clustering_recovery.py` | `src/prep/services/pipeline/recovery.py` |
| P6 close_shared_embedders scoping | `tests/test_close_shared_embedders_scope.py` | `src/prep/api/routers/pipeline.py`, `src/prep/services/embedder_factory.py` |

Workstreams P1–P6 are independent and each produces a committable, testable change. P0 must run first to clean the working tree.

---

## P0 — Pre-flight: commit existing unstaged work in topic bundles

**Goal:** Drive `git status` to a clean tree so the targeted fixes don't blend with unrelated WIP. Each commit is a logical bundle. No behavior changes here — these are diffs already in your working tree.

**Per-commit verification:** after each commit, run the corresponding test slice and confirm pass before moving on.

### Task P0.1 — Verify current daemon state

**Files:** none (read-only)

- [ ] **Step 1: Confirm queue is empty.**

  Run: `curl -s http://localhost:8400/queue | python3 -m json.tool | head -30`
  Expected: `"queue": []`. If non-empty, stop and investigate before continuing.

- [ ] **Step 2: Confirm git status matches the inventory.**

  Run: `git status --short`
  Expected: the same 30-ish files identified in the brainstorming session. If anything new is present, decide whether to add to the relevant bundle or leave for later.

### Task P0.2 — Bundle 1: Phase 136 Part 15 (concurrency observability)

**Files:** `src/prep/services/pipeline_logger.py`, `src/prep/services/token_telemetry.py`, `src/prep/api/routers/queue.py`, `src/prep/api/routers/llm.py`, `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx`, `tests/test_phase136_part15_concurrency_visibility.py` (new)

- [ ] **Step 1: Verify the test passes.**

  Run: `.venv/bin/pytest tests/test_phase136_part15_concurrency_visibility.py -v`
  Expected: PASS. If FAIL, fix before committing.

- [ ] **Step 2: Stage and commit.**

  ```bash
  git add src/prep/services/pipeline_logger.py \
          src/prep/services/token_telemetry.py \
          src/prep/api/routers/queue.py \
          src/prep/api/routers/llm.py \
          packages/ui/src/components/navigation/SidebarPipelineQueue.tsx \
          tests/test_phase136_part15_concurrency_visibility.py
  git commit -m "$(cat <<'EOF'
feat(phase136-p15): concurrency observability + SWARM_CAPABLE gating

Adds periodic concurrency sampler to PipelineFileLogger so mid-stage
leaks show up in the log instead of only at stage boundaries. Adds
TokenTelemetryStore.dump_active_state() for forensic snapshots of
_active_requests with per-tid thread liveness and age.

Queue + LLM routers now gate the "is_swarm" heuristic on
SWARM_CAPABLE_STAGES — stale swarm_role entries that survived past a
swarm stage's drain were mislabeling subsequent batched stages
(notably inferred_edges) as "Swarming".

Dashboard sidebar denominator switches to dynamic_capacity so cloud
slots with float current_limit > max_concurrent don't display
nonsense like "10 / 19".

Configure via:
- PREP_PIPELINE_CONCURRENCY_SAMPLE_SEC (default 30; 0 disables)
EOF
)"
  ```

- [ ] **Step 3: Verify clean status for this bundle.**

  Run: `git status --short | grep -E 'pipeline_logger|token_telemetry|queue.py|llm.py|SidebarPipelineQueue|phase136_part15'`
  Expected: empty output.

### Task P0.3 — Bundle 2: 2026-05-17 regression fixes (included_paths + watcher parity)

**Files:** `src/prep/api/routers/projects/build.py`, `src/prep/api/routers/projects/watch.py`, `src/prep/api/routers/projects/crud.py`, `src/prep/api/routers/projects/helpers.py`

- [ ] **Step 1: Verify project-router tests pass.**

  Run: `.venv/bin/pytest tests/test_project_auto_detect.py tests/test_phase_a8_no_auto_detect_lock_skip.py -v`
  Expected: PASS.

- [ ] **Step 2: Stage and commit.**

  ```bash
  git add src/prep/api/routers/projects/build.py \
          src/prep/api/routers/projects/watch.py \
          src/prep/api/routers/projects/crud.py \
          src/prep/api/routers/projects/helpers.py \
          tests/test_project_auto_detect.py \
          tests/test_phase_a8_no_auto_detect_lock_skip.py
  git commit -m "$(cat <<'EOF'
fix(projects-router): tri-state included_paths + watcher parity (2026-05-17)

build.py: distinguish "user has never touched scope" (legacy: embed
full repo) from "user explicitly cleared scope" (embed nothing). The
2026-05 follow-up flipped the default to [] which silently neutered
prep_search on every freshly-imported project — trace graph indexed
everything while CodeIndex indexed nothing.

watch.py: watcher trigger always run_fast_sync; deep auto-chains via
_is_deep_enrichment_auto at fast-sync completion. Old fork called
run_all when both axes were auto, which (combined with the resume
barrier bug) painted as "Rebuilding All" in the UI for what was
actually a 1-file incremental update.

crud.py / helpers.py: convert _DEFAULT_UI_CONFIG class attribute reads
to _default_ui_config() method calls so live-edited UI config defaults
take effect immediately for newly-added projects.
EOF
)"
  ```

### Task P0.4 — Bundle 3: Reset/destroy completeness (sibling to F-78)

**Files:** `src/prep/api/routers/trace_routes/shared.py`, `tests/test_phase134_migration_cases.py`, `tests/test_scoped_full_reset.py`, `tests/test_freshness_skip_metadata.py` (new untracked)

- [ ] **Step 1: Verify the reset tests pass.**

  Run: `.venv/bin/pytest tests/test_scoped_full_reset.py tests/test_phase134_migration_cases.py -v`
  Expected: PASS.

- [ ] **Step 2: Stage and commit.**

  ```bash
  git add src/prep/api/routers/trace_routes/shared.py \
          tests/test_phase134_migration_cases.py \
          tests/test_scoped_full_reset.py \
          tests/test_freshness_skip_metadata.py
  git commit -m "$(cat <<'EOF'
fix(reset): add 9 missing files to TRACE_FILES destroy list (sibling to F-78)

Phase 134 introduced the centralized Changeset (stage 1 → all
downstream workers); the destroy list was never updated. Surviving a
full reset, the stale changeset re-classified every file as
cs.modified (because the last rebuild marked them so) and
coverage.py:101 mapped that to stale_set, painting "74 stale" on a
freshly-wiped project.

Adds to TRACE_FILES (parity-tested against STAGE_OUTPUTS):
  changeset.json, catalogue.jsonl, catalogue_manifest.json,
  trace_swarm_synthesis.json, atlas_swarm_synthesis.json,
  atlas_markdown_links.json, concept_generate_manifest.json,
  docs_grounding.json, concept_synthesis_manifest.json,
  deep_analysis_manifest.json
EOF
)"
  ```

### Task P0.5 — Bundle 4: mcp_direct ambient context fix

**Files:** `src/prep/mcp_direct.py`

- [ ] **Step 1: Stage and commit (no test in the working tree for this one — direct mode tests are sparse).**

  ```bash
  git add src/prep/mcp_direct.py
  git commit -m "$(cat <<'EOF'
fix(mcp-direct): prep no-arg routes to tool_hi, not search-context

The prep tool has no required args per mcp_tools.py — calling it with
no query/task should return the ambient overview, not the
search-context handler that demands a query. task is the schema's
natural-language slot; treat it as the query when set.

Also corrects the default index_dir to .sourceprep/ (embedded mode
writes artifacts directly there, no /index/ subdirectory).
EOF
)"
  ```

### Task P0.6 — Bundle 5: Test harness alignment

**Files:** `tests/test_augmenter.py`, `tests/test_deep_merge.py`, `tests/test_paused_run_survives_restart.py`

- [ ] **Step 1: Verify changed tests still pass.**

  Run: `.venv/bin/pytest tests/test_augmenter.py tests/test_deep_merge.py tests/test_paused_run_survives_restart.py -v`
  Expected: PASS.

- [ ] **Step 2: Stage and commit.**

  ```bash
  git add tests/test_augmenter.py tests/test_deep_merge.py tests/test_paused_run_survives_restart.py
  git commit -m "test: align harness with engine + pause-resume edits"
  ```

### Task P0.7 — Bundle 6: Docs + config drift

**Files:** `.cursor/rules/prep.mdc`, `AGENTS.md`, `CLAUDE.md`, `packages/ui/src/components/llm/index.ts`, `websites/apps/docs/netlify.toml`, `docs/Phase140_Prompt-Dogfood/snapshots/2026-05-19_A-followup-post-rerun/`

- [ ] **Step 1: Eyeball the doc diff for surprises.**

  Run: `git diff CLAUDE.md AGENTS.md .cursor/rules/prep.mdc websites/apps/docs/netlify.toml packages/ui/src/components/llm/index.ts | head -100`
  Expected: matches your memory of recent edits. If you see anything you didn't write, stop and investigate.

- [ ] **Step 2: Stage and commit.**

  ```bash
  git add .cursor/rules/prep.mdc AGENTS.md CLAUDE.md \
          packages/ui/src/components/llm/index.ts \
          websites/apps/docs/netlify.toml \
          docs/Phase140_Prompt-Dogfood/snapshots/2026-05-19_A-followup-post-rerun/
  git commit -m "docs+config: assorted updates (AGENTS, CLAUDE, prep.mdc, llm index, netlify, Phase140 snapshot)"
  ```

### Task P0.8 — Bundle 7: Mini-repo fixture deletions

**Files:** `tests/fixtures/mini_repo/.sourceprep/index/documents.json`, `embeddings.npy`, `fts.sqlite3`, `manifest.json`, `repo_policy.json`

- [ ] **Step 1: STOP. Check whether the fixture is referenced as required by any test.**

  Run: `grep -rn "mini_repo/.sourceprep" tests/ src/ 2>/dev/null | head -20`
  Expected: see whether tests construct these on the fly or expect them to exist.

- [ ] **Step 2: Decision point.**
  - If tests rebuild the fixture on setup → safe to commit the deletion.
  - If tests assume the fixture exists at rest → restore via `git checkout -- tests/fixtures/mini_repo/.sourceprep/index/` and skip this bundle.

- [ ] **Step 3 (only if safe per Step 2): Stage and commit the deletions.**

  ```bash
  git add -u tests/fixtures/mini_repo/.sourceprep/index/
  git commit -m "test(fixtures): remove pre-built mini_repo index artifacts (rebuilt on setup)"
  ```

### Task P0.9 — Verify clean tree

- [ ] **Step 1: Final state.**

  Run: `git status --short`
  Expected: empty (or only the deletions if you skipped P0.8).

- [ ] **Step 2: Run the full test suite to baseline.**

  Run: `.venv/bin/pytest tests/ -x --tb=short 2>&1 | tail -30`
  Expected: all pass, or the same failures that existed before P0 (note them).

---

## P1 — Stop the settings-router cross-project fan-out

**Goal:** Remove the bug that initiated this whole incident. Global `/settings/pipeline-config` flips no longer dispatch `run_fast_sync` / `run_deep_enrichment` to every active project. The per-project `auto_config` remains the sole authority for auto-chaining, matching the design contract documented in `_is_deep_enrichment_auto`.

### Task P1.1 — Write the failing test

**Files:** `tests/test_settings_pipeline_config_no_fanout.py` (new)

- [ ] **Step 1: Write the test.**

  ```python
  """Regression test: POST /settings/pipeline-config must not dispatch
  pipeline runs across projects.

  See docs/superpowers/plans/2026-06-08-pipeline-reliability-ux-fixes.md
  for the 2026-06-08 incident that motivated this guard.
  """
  from __future__ import annotations

  from unittest.mock import patch

  from fastapi.testclient import TestClient

  from prep.server import app


  def test_pipeline_config_auto_flip_does_not_trigger_runs():
      """Flipping deep_enrichment_mode to 'auto' globally must not call
      pipeline_orchestrator.run_deep_enrichment for any project."""
      client = TestClient(app)
      with patch(
          "prep.services.pipeline_orchestrator.pipeline_orchestrator.run_deep_enrichment"
      ) as run_deep, patch(
          "prep.services.pipeline_orchestrator.pipeline_orchestrator.run_fast_sync"
      ) as run_fast:
          response = client.post(
              "/settings/pipeline-config",
              json={"deep_enrichment_mode": "auto", "fast_sync_auto": True},
          )
      assert response.status_code == 200
      assert run_deep.call_count == 0, (
          f"Global config flip dispatched run_deep_enrichment "
          f"{run_deep.call_count} times across projects — regression of "
          f"the 2026-06-08 fan-out bug."
      )
      assert run_fast.call_count == 0, (
          f"Global config flip dispatched run_fast_sync "
          f"{run_fast.call_count} times across projects — regression of "
          f"the 2026-06-08 fan-out bug."
      )
  ```

- [ ] **Step 2: Run it to confirm it fails.**

  Run: `.venv/bin/pytest tests/test_settings_pipeline_config_no_fanout.py -v`
  Expected: FAIL with assertion on `run_deep.call_count == 0` (because the current code calls it for every active trace-enabled project).

### Task P1.2 — Remove the fan-out from the settings router

**Files:** `src/prep/api/routers/settings.py:265-312`

- [ ] **Step 1: Delete the two `_trigger_*_runs` thread-spawning blocks and replace with a comment block documenting the design contract.**

  Replace `src/prep/api/routers/settings.py:265-312` (the `if body.fast_sync_auto and not prev_fast_auto:` and `if body.deep_enrichment_mode == "auto" and prev_deep_mode != "auto":` blocks) with:

  ```python
  # 2026-06-08: Removed cross-project fan-out on auto-mode flips.
  #
  # Previously, flipping fast_sync_auto or deep_enrichment_mode to
  # auto via this global endpoint would spawn a thread that
  # iterated get_registry().list_projects() and called
  # pipeline_orchestrator.run_fast_sync / run_deep_enrichment for
  # every trace-enabled active project. That meant configuring auto
  # for one project triggered work for ALL projects — directly
  # violating the per-project authority contract in
  # PipelineOrchestrator._is_deep_enrichment_auto (orchestrator.py:1712):
  #
  #     "Per-project auto_config is the only authority; default is
  #      manual. The legacy global fallback was the regression that
  #      caused projects with their UI on Manual to auto-chain
  #      whenever a stale global pipeline_config.deep_enrichment.mode
  #      was still set to auto."
  #
  # The global pipeline_config is now strictly a default for *new*
  # projects (read in add_project at crud.py) and a diagnostic
  # readback. Existing projects rely on their own auto_config plus
  # the watcher's _check_incomplete_deep_enrichment timer to start
  # work when there's work to start.
  ```

- [ ] **Step 2: Run the failing test to confirm it now passes.**

  Run: `.venv/bin/pytest tests/test_settings_pipeline_config_no_fanout.py -v`
  Expected: PASS.

- [ ] **Step 3: Run the broader settings test slice to confirm no regression.**

  Run: `.venv/bin/pytest tests/ -k "settings or pipeline_config" -v`
  Expected: PASS.

### Task P1.3 — Commit

- [ ] **Step 1: Stage and commit.**

  ```bash
  git add src/prep/api/routers/settings.py tests/test_settings_pipeline_config_no_fanout.py
  git commit -m "$(cat <<'EOF'
fix(settings): remove cross-project fan-out on auto-mode flips

The global POST /settings/pipeline-config endpoint was spawning a
thread that called pipeline_orchestrator.run_fast_sync /
run_deep_enrichment for every trace-enabled active project whenever
fast_sync_auto or deep_enrichment_mode transitioned to auto. This
directly contradicted the per-project authority contract documented
in PipelineOrchestrator._is_deep_enrichment_auto.

2026-06-08 incident: initializing /Volumes/Thunderbolt/AI/deep-live-cam
flipped the global toggle, dispatched run_deep_enrichment for
SourcePrep (and two other projects), and SourcePrep's pipeline ran
for 44 seconds against an orphan clustering manifest from a prior
interrupted run.

Global pipeline_config is now strictly a default for new projects
plus a diagnostic readback. Per-project auto_config + the watcher's
_check_incomplete_deep_enrichment timer drive when existing projects
do work.

Regression test pins the new behavior.
EOF
)"
  ```

---

## P2 — Complete the skipped-stage UI fix (`mark_stage_skipped` is missing)

**Goal:** Freshness-skipped stages stop rendering as "0% Running" forever. The orchestrator's `_update_run_metadata_for_skip` already calls `mark_stage_skipped`, but that function doesn't exist in `pipeline_metadata.py` — the bare `except` silently swallows the ImportError so the fix has been a no-op.

### Task P2.1 — Write the failing test for `mark_stage_skipped`

**Files:** `tests/test_pipeline_metadata_skip.py` (new)

- [ ] **Step 1: Write the test.**

  ```python
  """Tests for pipeline_metadata.mark_stage_skipped — the missing
  helper that PipelineOrchestrator._update_run_metadata_for_skip
  calls. Without it, freshness-skipped stages stay 'pending' in
  pipeline_run_metadata.json and the UI renders them as 0% Running
  forever (the 2026-06-08 incident's UI bug)."""
  from __future__ import annotations

  import pytest

  from prep.services.pipeline_metadata import (
      PipelineRunMetadata,
      StageMetadata,
      mark_stage_skipped,
      mark_stage_started,
  )


  def _new_meta() -> PipelineRunMetadata:
      meta = PipelineRunMetadata(
          run_id="r1",
          group="deep_enrichment",
          stages=["enrichment", "group_reasoning", "clustering"],
      )
      meta.stage_metadata = {
          s: StageMetadata(stage_id=s) for s in meta.stages
      }
      return meta


  def test_mark_stage_skipped_sets_status_and_reason():
      meta = _new_meta()
      mark_stage_skipped(meta, "enrichment", reason="all outputs are newer")
      stage = meta.stage_metadata["enrichment"]
      assert stage.status == "skipped"
      assert "all outputs are newer" in (stage.error or "")
      assert stage.started_at is not None
      assert stage.finished_at is not None
      assert stage.finished_at >= stage.started_at


  def test_mark_stage_skipped_idempotent_does_not_overwrite_running():
      meta = _new_meta()
      mark_stage_started(meta, "enrichment")
      first_started = meta.stage_metadata["enrichment"].started_at
      mark_stage_skipped(meta, "enrichment", reason="late skip")
      stage = meta.stage_metadata["enrichment"]
      assert stage.status == "skipped"
      assert stage.started_at == first_started  # preserved


  def test_mark_stage_skipped_unknown_stage_is_noop():
      meta = _new_meta()
      mark_stage_skipped(meta, "no_such_stage", reason="x")
      # No raise, no mutation of other stages
      assert meta.stage_metadata["enrichment"].status == "pending"
  ```

- [ ] **Step 2: Run it to confirm it fails.**

  Run: `.venv/bin/pytest tests/test_pipeline_metadata_skip.py -v`
  Expected: FAIL with ImportError on `mark_stage_skipped`.

### Task P2.2 — Add `mark_stage_skipped` to `pipeline_metadata.py`

**Files:** `src/prep/services/pipeline_metadata.py` (add helper next to `mark_stage_failed`)

- [ ] **Step 1: Read the existing `mark_stage_failed` to match style.**

  Read `src/prep/services/pipeline_metadata.py:244-258` (the `mark_stage_failed` definition area).

- [ ] **Step 2: Add `mark_stage_skipped` immediately after `mark_stage_failed`.**

  Insert into `src/prep/services/pipeline_metadata.py` after the `mark_stage_failed` function:

  ```python
  def mark_stage_skipped(
      meta: PipelineRunMetadata,
      stage_id: str,
      reason: str = "",
  ) -> None:
      """Mark a stage as skipped (freshness check found outputs current).

      Called by PipelineOrchestrator._update_run_metadata_for_skip when
      a stage decides it has nothing to do because all its outputs are
      newer than all its inputs. Without this call, the per-stage entry
      keeps the initial 'pending' status from create_run_metadata and
      the dashboard renders the stage as still running (the 2026-06-08
      UI bug).

      If ``stage_id`` is unknown, this is a no-op (defensive — never
      raise from a metadata helper).

      Idempotent against repeated invocation; preserves an existing
      ``started_at`` if the stage was already in a running state.
      """
      import time as _time
      stage = meta.stage_metadata.get(stage_id)
      if stage is None:
          return
      now = _time.time()
      if stage.started_at is None:
          stage.started_at = now
      stage.finished_at = now
      stage.status = "skipped"
      if reason:
          # Reuse the error field as a free-form "why" line. The UI
          # reads .status for the badge and .error for the tooltip.
          stage.error = f"skipped: {reason}"
  ```

- [ ] **Step 3: Run the test slice to confirm it passes.**

  Run: `.venv/bin/pytest tests/test_pipeline_metadata_skip.py -v`
  Expected: PASS (all three tests).

### Task P2.3 — Verify the orchestrator wiring works end-to-end

**Files:** none (verification of `src/prep/services/pipeline/orchestrator.py:4661-4700` already-existing helper)

- [ ] **Step 1: Sanity check the import path.**

  Run: `.venv/bin/python -c "from prep.services.pipeline_metadata import mark_stage_skipped, save_run_metadata; print('OK', mark_stage_skipped, save_run_metadata)"`
  Expected: prints "OK" and both callable references.

- [ ] **Step 2: Restart the daemon so the new code is live.**

  Run: `scripts/dev.sh --kill && sleep 2 && scripts/dev.sh &`
  Then wait ~10 seconds for boot. (Per your standing memory: codrag serve has no hot-reload.)

- [ ] **Step 3: Live verification.**

  Trigger a small deep enrichment run that will freshness-skip several stages, then read the metadata file. (Replace `<pid>` with the SourcePrep project ID `f1636374-abc6-410d-99ee-822120379e79`.)

  Run: `curl -s -X POST http://localhost:8400/projects/f1636374-abc6-410d-99ee-822120379e79/pipeline/deep && sleep 5 && python3 -c "import json; m=json.load(open('.sourceprep/pipeline_run_metadata.json')); [print(s,v.get('status'),v.get('error')) for s,v in m.get('stage_metadata',{}).items()]"`
  Expected: at least one stage shows `skipped` with `skipped: all outputs are newer than inputs — already current`.

### Task P2.4 — Commit

- [ ] **Step 1: Stage and commit.**

  ```bash
  git add src/prep/services/pipeline_metadata.py tests/test_pipeline_metadata_skip.py
  git commit -m "$(cat <<'EOF'
fix(pipeline-metadata): add missing mark_stage_skipped helper

PipelineOrchestrator._update_run_metadata_for_skip (orchestrator.py:4661)
imports mark_stage_skipped from pipeline_metadata, but the function
didn't exist. The bare except in the orchestrator silently swallowed
the ImportError, so freshness-skipped stages stayed 'pending' in
pipeline_run_metadata.json forever and the dashboard kept rendering
them as 0% Running.

2026-06-08 incident: SourcePrep's run completed in 44s but the panel
showed enrichment and group_reasoning at 0% "Enriching..." /
"Analyzing groups..." indefinitely.

Tests pin: status flip, started_at preservation, unknown-stage no-op.
EOF
)"
  ```

---

## P3 — X-button design: toast on cancel + repeat-click escalation

**Goal:** Implement design B+heuristic from the 2026-06-08 brainstorm. When the user clicks X on a queue item, the run cancels (today's behavior) and:

1. Every cancel emits a toast that explains the auto state (transparency).
2. Repeated cancels on the same project within 5 minutes escalate to an inline warning ("Looks like this keeps restarting — switch to manual to break the loop?").
3. The cancel endpoint accepts an optional `reason` so infrastructure-initiated cancels (drain timeout, watchdog) don't count toward the user-cancel heuristic.

### Task P3.1 — Backend: add `reason` to the cancel endpoint

**Files:** `src/prep/api/routers/pipeline.py:1051-1092` (the cancel-pipeline endpoint), `tests/test_pipeline_cancel_reason.py` (new)

- [ ] **Step 1: Write the failing test.**

  ```python
  """Test that POST /projects/{id}/pipeline/cancel accepts a reason
  field so the X-button heuristic can distinguish user-initiated
  cancels from infrastructure-initiated ones (drain timeout,
  watchdog, etc.)."""
  from __future__ import annotations

  from unittest.mock import patch

  from fastapi.testclient import TestClient

  from prep.server import app


  def test_cancel_endpoint_accepts_reason_field():
      """The endpoint must accept reason in the request body and
      pass it to the orchestrator (or at minimum log it). Reason
      defaults to 'user_action' so older clients omit it harmlessly."""
      client = TestClient(app)
      with patch(
          "prep.services.pipeline_orchestrator.pipeline_orchestrator.cancel_fast_sync",
          return_value=True,
      ) as mock_cancel:
          # New-style call with explicit reason
          r1 = client.post(
              "/projects/fake-pid/pipeline/cancel",
              json={"group": "fast_sync", "reason": "user_action"},
          )
          # Old-style call without reason (must not break)
          r2 = client.post(
              "/projects/fake-pid/pipeline/cancel",
              json={"group": "fast_sync"},
          )
      assert r1.status_code in (200, 404, 409), r1.text
      assert r2.status_code in (200, 404, 409), r2.text
  ```

- [ ] **Step 2: Confirm it fails (the CancelRequest model rejects the unknown `reason` field, OR the endpoint succeeds but doesn't surface the field).**

  Run: `.venv/bin/pytest tests/test_pipeline_cancel_reason.py -v`
  Expected: FAIL with pydantic ValidationError on `reason`, OR PASS trivially if pydantic is lenient — in either case, continue to Step 3 to make the field meaningful.

- [ ] **Step 3: Find the CancelRequest pydantic model.**

  Run: `grep -n "class CancelRequest\|class.*CancelRequest" src/prep/api/routers/pipeline.py 2>/dev/null`
  Expected: shows the class definition line.

- [ ] **Step 4: Add the optional `reason` field.**

  In the CancelRequest model add (preserving the existing `group` field):

  ```python
  class CancelRequest(BaseModel):
      group: str
      # 2026-06-08: optional reason so the X-button heuristic can
      # distinguish user-initiated cancels ("user_action") from
      # infrastructure-initiated ones ("drain_timeout", "watchdog",
      # "stale_run_reset", etc). Logged for forensics; the heuristic
      # itself lives in the dashboard's useCancelToast hook.
      reason: str = "user_action"
  ```

- [ ] **Step 5: Add the reason to the log line in the cancel handler.**

  In the cancel endpoint (around line 1085 where it raises NOT_RUNNING) add a log line BEFORE the dispatch:

  ```python
  logger.info(
      "Pipeline cancel requested for %s/%s (reason=%s)",
      project_id, req.group, req.reason,
  )
  ```

- [ ] **Step 6: Run the test to confirm both shapes accepted.**

  Run: `.venv/bin/pytest tests/test_pipeline_cancel_reason.py -v`
  Expected: PASS.

### Task P3.2 — Backend: tag infrastructure cancels with their reason

**Files:** `src/prep/services/pipeline/orchestrator.py` (the drain-timeout cancel call at lines 117–123, and any other internal callers of cancel)

- [ ] **Step 1: Find all internal callers of `strong_self.cancel(pid)`, `cancel_fast_sync`, `cancel_deep_enrichment`, `cancel_finalize` from non-HTTP callers.**

  Run: `grep -rn "self\.cancel(\|strong_self\.cancel\|orchestrator\.cancel_" src/prep/services/pipeline/ src/prep/core/watcher.py 2>/dev/null | grep -v test_ | head -20`
  Expected: list of internal call sites.

- [ ] **Step 2: Audit the list. For now, these stay as direct internal calls (they don't go through the HTTP endpoint). The `reason` field exists for the HTTP layer + UI heuristic only. No internal changes required.**

  Note in the orchestrator above each internal `cancel()` call site what kind of cancel it is (drain_timeout, watchdog, etc.) — comment-only for forensic clarity. Example:

  ```python
  # Drain timeout: infrastructure-initiated cancel, NOT user_action.
  # The UI's repeat-click heuristic only counts cancels that arrive
  # via the HTTP cancel endpoint with reason="user_action".
  strong_self.cancel(pid)
  ```

### Task P3.3 — UI: create the shared `Toast` primitive

**Files:** `packages/ui/src/components/primitives/Toast.tsx` (new), `packages/ui/src/components/primitives/Toast.stories.tsx` (new)

- [ ] **Step 1: Write the Toast component (simple, no external dep).**

  Create `packages/ui/src/components/primitives/Toast.tsx`:

  ```tsx
  /**
   * Shared toast primitive — used by the SidebarPipelineQueue cancel
   * flow (2026-06-08 design B+heuristic). Intentionally minimal: one
   * fixed-position stack, dismiss on click or timeout, optional
   * action button. Not a full notification system — we have no need
   * for one yet.
   */
  import { useEffect, useState, useCallback, createContext, useContext } from 'react';
  import { X } from 'lucide-react';
  import { cn } from '../../lib/utils';

  export type ToastVariant = 'info' | 'warn' | 'error';

  export interface ToastInput {
    id?: string;
    title: string;
    body?: string;
    variant?: ToastVariant;
    action?: { label: string; onClick: () => void };
    durationMs?: number; // default 12000; 0 = sticky
  }

  interface ToastEntry extends Required<Omit<ToastInput, 'action' | 'body' | 'durationMs'>> {
    body?: string;
    action?: ToastInput['action'];
    durationMs: number;
  }

  interface ToastContextValue {
    push: (t: ToastInput) => string;
    dismiss: (id: string) => void;
  }

  const ToastContext = createContext<ToastContextValue | null>(null);

  export function useToast(): ToastContextValue {
    const ctx = useContext(ToastContext);
    if (!ctx) {
      throw new Error('useToast must be used inside <ToastProvider>');
    }
    return ctx;
  }

  export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastEntry[]>([]);

    const dismiss = useCallback((id: string) => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, []);

    const push = useCallback(
      (t: ToastInput): string => {
        const id = t.id ?? `t-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
        const entry: ToastEntry = {
          id,
          title: t.title,
          body: t.body,
          variant: t.variant ?? 'info',
          action: t.action,
          durationMs: t.durationMs ?? 12000,
        };
        setToasts((prev) => [...prev.filter((x) => x.id !== id), entry]);
        if (entry.durationMs > 0) {
          window.setTimeout(() => dismiss(id), entry.durationMs);
        }
        return id;
      },
      [dismiss],
    );

    return (
      <ToastContext.Provider value={{ push, dismiss }}>
        {children}
        <div
          aria-live="polite"
          className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm pointer-events-none"
        >
          {toasts.map((t) => (
            <div
              key={t.id}
              className={cn(
                'pointer-events-auto rounded-md border px-3 py-2 shadow-lg backdrop-blur-sm text-sm',
                t.variant === 'error' && 'bg-red-950/90 border-red-700 text-red-100',
                t.variant === 'warn' && 'bg-amber-950/90 border-amber-700 text-amber-100',
                t.variant === 'info' && 'bg-slate-900/90 border-slate-700 text-slate-100',
              )}
              role="status"
            >
              <div className="flex items-start gap-2">
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{t.title}</div>
                  {t.body && (
                    <div className="text-xs text-slate-300 mt-0.5">{t.body}</div>
                  )}
                  {t.action && (
                    <button
                      className="text-xs font-medium underline hover:no-underline mt-1.5"
                      onClick={() => {
                        t.action!.onClick();
                        dismiss(t.id);
                      }}
                    >
                      {t.action.label}
                    </button>
                  )}
                </div>
                <button
                  aria-label="Dismiss"
                  className="text-slate-400 hover:text-slate-100"
                  onClick={() => dismiss(t.id)}
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </ToastContext.Provider>
    );
  }
  ```

- [ ] **Step 2: Write a Storybook story so design review is possible.**

  Create `packages/ui/src/components/primitives/Toast.stories.tsx`:

  ```tsx
  import type { Meta, StoryObj } from '@storybook/react';
  import { ToastProvider, useToast } from './Toast';

  function Demo() {
    const { push } = useToast();
    return (
      <div className="p-6 space-x-2">
        <button
          className="px-3 py-1.5 rounded bg-slate-800 text-slate-100"
          onClick={() =>
            push({
              title: 'Run cancelled for SourcePrep',
              body: 'Auto is on — next file change or 5-min check will restart it.',
              action: { label: 'Switch to Manual', onClick: () => alert('switched') },
              variant: 'info',
            })
          }
        >
          info toast (B)
        </button>
        <button
          className="px-3 py-1.5 rounded bg-amber-800 text-amber-100"
          onClick={() =>
            push({
              title: 'Looks like this keeps restarting',
              body: 'You\'ve cancelled this project 2 times in the last 5 minutes. Switch to manual to break the loop?',
              action: { label: 'Switch to Manual', onClick: () => alert('switched') },
              variant: 'warn',
              durationMs: 0, // sticky
            })
          }
        >
          warn toast (heuristic)
        </button>
      </div>
    );
  }

  const meta: Meta<typeof Demo> = {
    title: 'Primitives/Toast',
    decorators: [
      (Story) => (
        <ToastProvider>
          <Story />
        </ToastProvider>
      ),
    ],
  };
  export default meta;
  type Story = StoryObj<typeof Demo>;
  export const Playground: Story = { render: () => <Demo /> };
  ```

- [ ] **Step 3: Verify Storybook renders both stories.**

  Run: `cd packages/ui && npm run storybook` (in background)
  Open: `http://localhost:6006/?path=/story/primitives-toast--playground`
  Click both buttons; verify the toast appears at bottom-right and the warn variant is sticky.

### Task P3.4 — UI: cancel-click heuristic hook

**Files:** `packages/ui/src/hooks/useCancelToast.ts` (new)

- [ ] **Step 1: Write the hook that wraps cancel + emits the appropriate toast.**

  Create `packages/ui/src/hooks/useCancelToast.ts`:

  ```ts
  /**
   * Wraps the queue X-button cancel action with:
   *   - a toast showing the project's current auto state (transparency)
   *   - a 5-minute rolling counter per project_id; on the 2nd cancel
   *     within the window, emit a sticky warning toast offering a
   *     one-click switch to manual.
   *
   * Design: docs/superpowers/plans/2026-06-08-pipeline-reliability-ux-fixes.md P3
   */
  import { useCallback, useRef } from 'react';
  import { useToast } from '../components/primitives/Toast';

  const WINDOW_MS = 5 * 60 * 1000; // 5 minutes
  const ESCALATE_AT = 2; // 2nd click triggers warning

  export interface UseCancelToastOpts {
    /** Resolve the project's current auto mode ('auto' | 'manual' | 'scheduled' | string). */
    resolveAutoMode: (projectId: string) => Promise<'auto' | 'manual' | 'scheduled' | string>;
    /** Flip the project to manual. Should call the per-project settings endpoint. */
    switchToManual: (projectId: string) => Promise<void>;
    /** Send the actual cancel HTTP call, returning success. */
    sendCancel: (projectId: string, group: string, reason: string) => Promise<boolean>;
    /** Display name for the project in toast copy. */
    projectName?: (projectId: string) => string;
  }

  export function useCancelToast(opts: UseCancelToastOpts) {
    const { push } = useToast();
    const recent = useRef<Map<string, number[]>>(new Map());

    return useCallback(
      async (projectId: string, group: string) => {
        const ok = await opts.sendCancel(projectId, group, 'user_action');
        if (!ok) {
          push({
            title: 'Cancel failed',
            body: 'Could not cancel — see daemon logs.',
            variant: 'error',
          });
          return;
        }

        // Update the rolling window
        const now = Date.now();
        const list = (recent.current.get(projectId) ?? []).filter(
          (t) => now - t < WINDOW_MS,
        );
        list.push(now);
        recent.current.set(projectId, list);

        const mode = await opts.resolveAutoMode(projectId).catch(() => 'unknown');
        const name = opts.projectName?.(projectId) ?? projectId.slice(0, 8);

        // Heuristic escalation: 2+ cancels in 5 min on the same project
        if (list.length >= ESCALATE_AT) {
          push({
            title: 'Looks like this keeps restarting',
            body: `You've cancelled ${name} ${list.length} times in the last 5 minutes. Switch to manual to break the loop?`,
            action: {
              label: 'Switch to Manual',
              onClick: () => {
                opts.switchToManual(projectId).catch(() => {});
              },
            },
            variant: 'warn',
            durationMs: 0, // sticky
          });
          return;
        }

        // Single-click transparency toast
        if (mode === 'auto') {
          push({
            title: `Run cancelled for ${name}`,
            body: 'Auto is enabled — next file change or 5-min watcher check will restart it.',
            action: {
              label: 'Switch to Manual',
              onClick: () => {
                opts.switchToManual(projectId).catch(() => {});
              },
            },
            variant: 'info',
          });
        } else if (mode === 'scheduled') {
          push({
            title: `Run cancelled for ${name}`,
            body: 'Next scheduled run still applies.',
            action: {
              label: 'Switch to Manual',
              onClick: () => {
                opts.switchToManual(projectId).catch(() => {});
              },
            },
            variant: 'info',
          });
        } else {
          push({
            title: `Run cancelled for ${name}`,
            body: 'Won\'t restart automatically (mode is manual).',
            variant: 'info',
          });
        }
      },
      [push, opts],
    );
  }
  ```

### Task P3.5 — UI: wire SidebarPipelineQueue to the hook

**Files:** `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` (modify `handleCancel` around line 240)

- [ ] **Step 1: Replace the existing `handleCancel` callback with one that uses `useCancelToast`.**

  Locate `handleCancel` (currently at ~line 240) and replace with:

  ```ts
  // 2026-06-08 design B+heuristic: cancel + transparency toast +
  // repeat-click escalation. See useCancelToast for the full design.
  const cancelWithToast = useCancelToast({
    sendCancel: async (projectId, group, reason) => {
      const r = await fetch(`${baseUrl}/projects/${projectId}/pipeline/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group, reason }),
      });
      // 409 NOT_RUNNING is fine — the run already ended on its own.
      return r.ok || r.status === 409;
    },
    resolveAutoMode: async (projectId) => {
      const r = await fetch(`${baseUrl}/projects/${projectId}`);
      const j = await r.json();
      const cfg = j?.data?.project?.config ?? {};
      const auto = cfg.auto_config ?? {};
      return auto.deepEnrichment ?? auto.deep_enrichment ?? 'manual';
    },
    switchToManual: async (projectId) => {
      await fetch(`${baseUrl}/projects/${projectId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: { auto_config: { deepEnrichment: 'manual' } },
        }),
      });
    },
    projectName: (projectId) => {
      const item = queue.find((q) => q.project_id === projectId);
      return item?.project_name ?? projectId.slice(0, 8);
    },
  });

  const handleCancel = useCallback(
    async (item: QueueItem) => {
      if (onCancel) {
        // Caller-provided cancel still runs — they may bypass the
        // toast intentionally (e.g. headless tests).
        onCancel(item.project_id, item.group);
        await fetchQueue();
        return;
      }
      await cancelWithToast(item.project_id, item.group);
      await fetchQueue();
    },
    [onCancel, cancelWithToast, fetchQueue],
  );
  ```

- [ ] **Step 2: Add the import.**

  At the top of `SidebarPipelineQueue.tsx`:

  ```ts
  import { useCancelToast } from '../../hooks/useCancelToast';
  ```

### Task P3.6 — UI: mount `<ToastProvider>` at the dashboard root

**Files:** `src/prep/dashboard/src/App.tsx` (or whichever component is the root provider chain)

- [ ] **Step 1: Identify the root provider in the dashboard.**

  Run: `grep -rn "QueryClientProvider\|ReactDOM\.render\|createRoot" src/prep/dashboard/src/ 2>/dev/null | head -10`
  Expected: locate the top-level mount and provider stack.

- [ ] **Step 2: Wrap the existing provider tree with `<ToastProvider>` from `@prep/ui`.**

  Add the import at the top of the root file:

  ```ts
  import { ToastProvider } from '@prep/ui/components/primitives/Toast';
  ```

  And wrap the children:

  ```tsx
  <ToastProvider>
    {/* existing tree */}
  </ToastProvider>
  ```

- [ ] **Step 3: Verify the dashboard builds.**

  Run: `cd src/prep/dashboard && npm run typecheck`
  Expected: PASS (or pre-existing failures unchanged).

  Run: `cd src/prep/dashboard && npm run build 2>&1 | tail -20`
  Expected: build succeeds.

### Task P3.7 — Live verification

- [ ] **Step 1: Restart daemon + dashboard.**

  Run: `scripts/dev.sh --kill && sleep 2 && scripts/dev.sh &`

- [ ] **Step 2: Trigger a cancel from the UI.**

  Open the dashboard. Trigger a deep enrichment for any project. While running, click X on its queue item. Verify the toast appears at the bottom-right with the auto state info and the "Switch to Manual" action.

- [ ] **Step 3: Trigger the heuristic.**

  Re-trigger deep enrichment for the same project, click X again within 5 minutes. Verify the sticky warning toast appears with the "keeps restarting" copy.

- [ ] **Step 4: Click "Switch to Manual" on the toast.**

  Verify the project's auto_config flips to manual (check via `curl -s http://localhost:8400/projects/<pid> | python3 -m json.tool | grep deepEnrichment`).

### Task P3.8 — Commit

- [ ] **Step 1: Stage and commit.**

  ```bash
  git add src/prep/api/routers/pipeline.py \
          tests/test_pipeline_cancel_reason.py \
          packages/ui/src/components/primitives/Toast.tsx \
          packages/ui/src/components/primitives/Toast.stories.tsx \
          packages/ui/src/hooks/useCancelToast.ts \
          packages/ui/src/components/navigation/SidebarPipelineQueue.tsx \
          src/prep/dashboard/src/App.tsx
  git commit -m "$(cat <<'EOF'
feat(queue-x): toast + repeat-click escalation on queue cancel (design B+heuristic)

Today's X-button silently cancelled the run while leaving auto on,
so the next watcher tick or file change restarted the same work —
from the user POV, X did nothing.

Design B+heuristic:
  - Every cancel emits a toast showing the project's current auto
    state with a one-click "Switch to Manual" action (transparency).
  - 2+ cancels on the same project within 5 minutes escalate to a
    sticky warning toast that explicitly offers to break the loop.
  - The cancel endpoint accepts an optional reason field; the UI
    sends "user_action", infrastructure cancels (drain timeout,
    watchdog) keep their internal in-process path. The heuristic
    only counts HTTP cancels, so transient infra cancels can't
    accidentally trip the escalation.

Adds a shared Toast primitive (lightweight, no external dep) +
Storybook story + useCancelToast hook.
EOF
)"
  ```

---

## P4 — Write Guard correctness for cluster reorganizations

**Goal:** Cluster stages that *consolidate* records (836 from 861 input modules — a 2.9% shrink) are not reverted by the Write Guard. Today the orchestrator computes `_compute_allowed_shrink_ratio` only from changeset deletions, returning 0.0 when there's no deleted file — so the guard's default-strict floor blocks legitimate consolidation.

### Task P4.1 — Write the failing test

**Files:** `tests/test_write_guard_clustering_shrink.py` (new)

- [ ] **Step 1: Write the test.**

  ```python
  """Regression test for the 2026-06-08 cluster-revert loop.

  Clustering legitimately produced 836 modules from 861 prior
  records (2.9% shrink, no user file deletions). The Write Guard
  reverted the output via checkpoint restore because
  _compute_allowed_shrink_ratio returned 0.0 (no changeset
  deletions). Selfheal then saw the orphan manifest on the next
  scan, kicked clustering again, same revert, infinite loop.

  Fix: stage-specific allowance — clustering and other
  consolidation stages get a baseline tolerance independent of
  deletion ratio.
  """
  from __future__ import annotations

  from prep.services.pipeline_integrity import IntegrityGuard


  def _snap(records: int, size: int = 1000):
      from prep.services.pipeline_integrity import FileSnapshot
      return FileSnapshot(
          exists=True, size_bytes=size, mtime=0.0,
          record_count=records, sha256_prefix="x",
      )


  def test_clustering_three_percent_shrink_allowed_by_default():
      """A 2.9% shrink on trace_modules.jsonl during clustering
      must not be blocked even with no user deletions."""
      g = IntegrityGuard()
      g._snapshots[("pid", "clustering")] = type(
          "S", (), {"files": {"trace_modules.jsonl": _snap(861)}}
      )()
      post = {"trace_modules.jsonl": _snap(836)}
      blocked, reason = g.should_block_stage_completion(
          "pid", "clustering", post,
          allowed_shrink_ratio=0.10,  # the orchestrator's new default
      )
      assert not blocked, f"clustering 836/861 shrunk only 2.9% — should pass. reason={reason}"


  def test_destructive_50pct_shrink_still_blocked():
      """The guard must still catch genuine data loss."""
      g = IntegrityGuard()
      g._snapshots[("pid", "clustering")] = type(
          "S", (), {"files": {"trace_modules.jsonl": _snap(800)}}
      )()
      post = {"trace_modules.jsonl": _snap(400)}  # 50% loss
      blocked, reason = g.should_block_stage_completion(
          "pid", "clustering", post,
          allowed_shrink_ratio=0.10,
      )
      assert blocked, f"50% shrink should always block. reason={reason}"
  ```

- [ ] **Step 2: Run it to see current behavior.**

  Run: `.venv/bin/pytest tests/test_write_guard_clustering_shrink.py -v`
  Expected: the second test passes (guard correctly blocks 50%), the first test may or may not pass depending on the `_snap` shim. If FAIL, that confirms the bug. If PASS, the guard math is right and the real bug is `_compute_allowed_shrink_ratio` returning 0.0 — see Task P4.2 step 2 for the actual fix location.

### Task P4.2 — Add a baseline default allowance to `_compute_allowed_shrink_ratio`

**Files:** `src/prep/services/pipeline/orchestrator.py` (the `_compute_allowed_shrink_ratio` method)

- [ ] **Step 1: Read the current implementation.**

  Read `src/prep/services/pipeline/orchestrator.py:3927-3966` (approximately — the `_compute_allowed_shrink_ratio` definition).

- [ ] **Step 2: Modify the method to return a non-zero baseline.**

  Replace the "Returns 0.0 if no changeset is present" final-line behavior. After the existing `if cs is None: return 0.0` and `if deleted_n == 0: return 0.0` early-exits, change those returns to `return _BASELINE_SHRINK_TOLERANCE` instead. Define the constant at module scope above the method:

  ```python
  # 2026-06-08: baseline shrink tolerance applied even when there's no
  # changeset or no user deletions. Clustering and other consolidation
  # stages legitimately produce slightly fewer output records than
  # input records as they merge near-duplicates. Without this floor,
  # the Write Guard reverts every such run, selfheal sees the orphan
  # manifest, and the same cluster work re-runs in a loop forever
  # (the 2026-06-08 incident).
  #
  # 0.10 means "up to 10% shrink is OK". The 2026-06-08 clustering
  # case shrunk by 2.9% (836/861). The destructive-data-loss tests
  # (50%+ shrink) still block.
  _BASELINE_SHRINK_TOLERANCE = 0.10
  ```

  And in the method:

  ```python
  def _compute_allowed_shrink_ratio(self, idx_dir: Path) -> float:
      """Return the fraction of shrinkage the integrity guard should
      tolerate.

      Composition:
        - baseline:  _BASELINE_SHRINK_TOLERANCE — covers consolidation
                     stages (clustering, dedup) that legitimately
                     produce slightly fewer records than they read.
        - changeset: deletion_ratio * 1.5 — when the user deletes
                     source files, downstream graph records should
                     shrink proportionally.

      The two are combined as max(baseline, changeset_allowance),
      capped at 0.95 by the guard itself so the safety net is never
      fully disabled. A 50%+ destructive shrink still blocks.
      """
      try:
          from prep.services.pipeline.changeset import read_changeset
          cs = read_changeset(idx_dir)
      except Exception:
          return _BASELINE_SHRINK_TOLERANCE
      if cs is None:
          return _BASELINE_SHRINK_TOLERANCE
      deleted_n = len(cs.deleted)
      if deleted_n == 0:
          return _BASELINE_SHRINK_TOLERANCE
      prior_n = len(cs.all_known()) + deleted_n
      if prior_n == 0:
          return _BASELINE_SHRINK_TOLERANCE
      deletion_ratio = deleted_n / prior_n
      changeset_allowance = deletion_ratio * 1.5 + _BASELINE_SHRINK_TOLERANCE
      return changeset_allowance
  ```

- [ ] **Step 3: Run the test.**

  Run: `.venv/bin/pytest tests/test_write_guard_clustering_shrink.py -v`
  Expected: both PASS.

- [ ] **Step 4: Run the broader integrity test slice.**

  Run: `.venv/bin/pytest tests/ -k "integrity or write_guard or shrink" -v`
  Expected: PASS or only pre-existing failures.

### Task P4.3 — Commit

- [ ] **Step 1: Stage and commit.**

  ```bash
  git add src/prep/services/pipeline/orchestrator.py tests/test_write_guard_clustering_shrink.py
  git commit -m "$(cat <<'EOF'
fix(write-guard): baseline 10% shrink tolerance to prevent cluster-revert loop

2026-06-08 incident: SourcePrep's clustering stage produced 836
modules from 861 input records (97.1% retention, 2.9% shrink). The
Write Guard restored the prior file from checkpoint because
_compute_allowed_shrink_ratio returned 0.0 (no user deletions in the
changeset). Selfheal then saw the orphan clustering manifest, kicked
clustering again, same revert, infinite loop. 44 seconds of cloud
LLM spend per cycle thrown away.

_compute_allowed_shrink_ratio now returns max(0.10, deletion-driven)
so consolidation stages with small natural shrinkage pass. 50%+
destructive shrinks still block (regression test pins).
EOF
)"
  ```

---

## P5 — Break the orphan-clustering loop

**Goal:** Even with P4's Write Guard fix, the orphan-clustering recovery path needs to be resilient. If clustering's output IS legitimately rejected (genuine data-destroying bug), selfheal should not re-trigger the same run on the next scan; it should defer until a real signal (file change, user action) requests it.

### Task P5.1 — Reproduce the loop in a test

**Files:** `tests/test_orphan_clustering_recovery.py` (new)

- [ ] **Step 1: Write the test.**

  ```python
  """Regression test: when a stage's output is rejected by the Write
  Guard and restored from checkpoint, the next selfheal scan must
  NOT immediately re-trigger that stage. The Guard rejection is a
  semantic signal that the output was wrong; running it again without
  a new input signal will hit the same rejection.

  Approach: record a 'guard_rejected_until' marker that suppresses
  selfheal resurrection until either:
    - a file in the project changes (watcher emits a new signal), OR
    - the user explicitly triggers a manual run, OR
    - 30 minutes elapse (defensive timeout for transient guard bugs)
  """
  from __future__ import annotations

  import time
  from pathlib import Path

  from prep.services.pipeline.recovery import (
      record_guard_rejection,
      should_defer_selfheal_resurrection,
  )


  def test_guard_rejection_suppresses_immediate_resurrection(tmp_path: Path):
      record_guard_rejection(tmp_path, stage="clustering", reason="MAJOR_SHRINK")
      assert should_defer_selfheal_resurrection(tmp_path, "clustering")


  def test_guard_rejection_expires_after_timeout(tmp_path: Path, monkeypatch):
      record_guard_rejection(tmp_path, stage="clustering", reason="MAJOR_SHRINK")
      future = time.time() + 30 * 60 + 1
      monkeypatch.setattr("prep.services.pipeline.recovery.time.time", lambda: future)
      assert not should_defer_selfheal_resurrection(tmp_path, "clustering")


  def test_other_stages_not_suppressed(tmp_path: Path):
      record_guard_rejection(tmp_path, stage="clustering", reason="x")
      assert not should_defer_selfheal_resurrection(tmp_path, "deepening")
  ```

- [ ] **Step 2: Run to confirm it fails (helpers don't exist).**

  Run: `.venv/bin/pytest tests/test_orphan_clustering_recovery.py -v`
  Expected: FAIL with ImportError.

### Task P5.2 — Add the rejection marker helpers

**Files:** `src/prep/services/pipeline/recovery.py`

- [ ] **Step 1: Add module-level constants + helpers.**

  In `src/prep/services/pipeline/recovery.py` (top-level, after imports):

  ```python
  import time

  # 2026-06-08: guard-rejected stage marker. When the Write Guard
  # rejects a stage's output and restores from checkpoint, record it
  # here so the next selfheal scan defers resurrection until a real
  # signal arrives (file change, user action, or 30-min timeout).
  # Without this, selfheal sees the orphan manifest and immediately
  # re-triggers the same rejected work in an infinite loop.
  _GUARD_REJECTION_FILENAME = ".guard_rejections.json"
  _GUARD_REJECTION_TTL_SECONDS = 30 * 60  # 30 minutes


  def record_guard_rejection(idx_dir: Path, stage: str, reason: str) -> None:
      """Persist that ``stage`` had its output rejected by the Write
      Guard. Caller: orchestrator's _write_guard recovery branch.
      """
      import json
      path = Path(idx_dir) / _GUARD_REJECTION_FILENAME
      try:
          existing = json.loads(path.read_text()) if path.exists() else {}
      except Exception:
          existing = {}
      existing[stage] = {"at": time.time(), "reason": reason}
      try:
          path.write_text(json.dumps(existing, indent=2))
      except Exception:
          pass  # non-fatal


  def should_defer_selfheal_resurrection(idx_dir: Path, stage: str) -> bool:
      """True if selfheal must NOT re-trigger ``stage`` because it was
      recently rejected by the Write Guard. Caller: selfheal scan."""
      import json
      path = Path(idx_dir) / _GUARD_REJECTION_FILENAME
      if not path.exists():
          return False
      try:
          data = json.loads(path.read_text())
      except Exception:
          return False
      entry = data.get(stage)
      if not entry:
          return False
      at = entry.get("at", 0.0)
      return (time.time() - at) < _GUARD_REJECTION_TTL_SECONDS


  def clear_guard_rejection(idx_dir: Path, stage: str) -> None:
      """Remove the rejection marker — called when a real signal (file
      change, manual run) arrives so the next selfheal can resurrect."""
      import json
      path = Path(idx_dir) / _GUARD_REJECTION_FILENAME
      if not path.exists():
          return
      try:
          data = json.loads(path.read_text())
          data.pop(stage, None)
          if data:
              path.write_text(json.dumps(data, indent=2))
          else:
              path.unlink()
      except Exception:
          pass
  ```

- [ ] **Step 2: Run the test.**

  Run: `.venv/bin/pytest tests/test_orphan_clustering_recovery.py -v`
  Expected: PASS.

### Task P5.3 — Wire the orchestrator to record the rejection on guard restore

**Files:** `src/prep/services/pipeline/orchestrator.py` (search for "RESTORED" log line in `_attempt_write_guard_recovery`)

- [ ] **Step 1: Locate the guard recovery call.**

  Run: `grep -n "_attempt_write_guard_recovery\|RESTORED.*checkpoint" src/prep/services/pipeline/orchestrator.py | head -10`

- [ ] **Step 2: After the checkpoint restore succeeds, call `record_guard_rejection`.**

  In `_attempt_write_guard_recovery` (or wherever the restore succeeds), at the success branch:

  ```python
  # 2026-06-08 P5: record the rejection so selfheal defers
  # resurrection. Without this marker, the next selfheal scan
  # sees the orphan manifest, re-triggers the stage, hits the
  # same guard rejection, restores the same checkpoint — looping
  # forever and burning LLM cycles.
  from prep.services.pipeline.recovery import record_guard_rejection
  record_guard_rejection(idx_dir, stage.value, reason)
  ```

### Task P5.4 — Wire selfheal to honor the marker

**Files:** `src/prep/services/pipeline/recovery.py` (the selfheal scan loop) and `src/prep/core/watcher.py` (clear the marker on real file change)

- [ ] **Step 1: Find the selfheal resurrection scan.**

  Run: `grep -n "skip_orphan_interrupted\|orphan output is pending\|selfheal_group_complete" src/prep/services/pipeline/recovery.py | head -10`

- [ ] **Step 2: Add the defer check at the resurrection decision point.**

  In the selfheal scan, before deciding to resurrect a stage:

  ```python
  if should_defer_selfheal_resurrection(idx_dir, stage_value):
      details.append({
          "stage": stage_value,
          "status": "deferred_guard_rejection",
          "reason": "Write Guard rejected this stage's output recently — waiting for a file change or manual run before retrying.",
      })
      continue
  ```

- [ ] **Step 3: In the watcher, clear the marker when a real file change is seen.**

  In `src/prep/core/watcher.py`, in the `on_event` (or equivalent) handler that processes a file-change event:

  ```python
  # 2026-06-08 P5: clear any guard-rejection markers when real file
  # activity arrives. A new file change is the signal that the
  # workload has actually changed; the previously-rejected stage
  # output may now be different.
  try:
      from prep.services.pipeline.recovery import clear_guard_rejection
      # Clear for every deep-enrichment stage that might have been rejected.
      from prep.services.pipeline.stages import DEEP_ENRICHMENT_STAGES
      for s in DEEP_ENRICHMENT_STAGES:
          clear_guard_rejection(idx_dir, s.value)
  except Exception:
      pass
  ```

### Task P5.5 — Commit

- [ ] **Step 1: Stage and commit.**

  ```bash
  git add src/prep/services/pipeline/recovery.py \
          src/prep/services/pipeline/orchestrator.py \
          src/prep/core/watcher.py \
          tests/test_orphan_clustering_recovery.py
  git commit -m "$(cat <<'EOF'
fix(selfheal): defer resurrection of Write-Guard-rejected stages

2026-06-08 incident continued: even with the P4 shrink-tolerance fix,
if a stage's output is genuinely rejected by the Write Guard
(checkpoint restored), today's selfheal sees the orphan manifest on
the next scan and immediately re-runs the same stage — hits the
same rejection — restores the same checkpoint — loops forever.

Adds .guard_rejections.json per-index marker with a 30-min TTL.
Selfheal honors it (deferring resurrection); the watcher clears it
when real file activity arrives. Manual run still works (the
selfheal path is only blocked, not the explicit /pipeline/deep
endpoint).
EOF
)"
  ```

---

## P6 — Scope `close_shared_embedders` to be cross-project safe

**Goal:** `POST /projects/{id}/pipeline/rebuild/stop` calls `close_shared_embedders()` — a process-wide singleton release. Today this drops the ONNX session for every project, not just the one being stopped. Any project mid-embed gets its session ripped out from under it. The fix: only release if no other project is actively embedding.

### Task P6.1 — Write the failing test

**Files:** `tests/test_close_shared_embedders_scope.py` (new)

- [ ] **Step 1: Write the test.**

  ```python
  """Regression test: /pipeline/rebuild/stop must not drop the shared
  embedder if another project is still using it.

  2026-06-08 incident: stopping deep-live-cam appeared to also stop
  SourcePrep. close_shared_embedders is process-wide; even when only
  one project is in-flight on the embedder, dropping the singleton
  invalidates any in-flight ONNX session for any other project."""
  from __future__ import annotations

  from unittest.mock import patch

  from prep.services.embedder_factory import (
      close_shared_embedders,
      _SHARED_EMBEDDERS,
  )


  def test_close_with_no_active_embedding_releases(tmp_path):
      _SHARED_EMBEDDERS.clear()
      _SHARED_EMBEDDERS[("native", "x")] = object()
      with patch(
          "prep.services.embedder_factory._is_other_project_embedding",
          return_value=False,
      ):
          n = close_shared_embedders(active_project_id="pid_a")
      assert n == 1
      assert not _SHARED_EMBEDDERS


  def test_close_with_other_project_embedding_skips(tmp_path):
      _SHARED_EMBEDDERS.clear()
      _SHARED_EMBEDDERS[("native", "x")] = object()
      with patch(
          "prep.services.embedder_factory._is_other_project_embedding",
          return_value=True,
      ):
          n = close_shared_embedders(active_project_id="pid_a")
      assert n == 0
      assert _SHARED_EMBEDDERS
  ```

- [ ] **Step 2: Confirm failure.**

  Run: `.venv/bin/pytest tests/test_close_shared_embedders_scope.py -v`
  Expected: FAIL — `close_shared_embedders` has no `active_project_id` parameter today.

### Task P6.2 — Update the embedder factory

**Files:** `src/prep/services/embedder_factory.py`

- [ ] **Step 1: Add the parameter and the safety check.**

  Modify `close_shared_embedders` in `src/prep/services/embedder_factory.py`:

  ```python
  def close_shared_embedders(
      *, active_project_id: str | None = None,
  ) -> int:
      """Drop all cached embedders and call close() on any that expose it.

      ``active_project_id`` (2026-06-08): the project that initiated
      the close (typically from /pipeline/rebuild/stop). If another
      project is actively embedding (running a stage on
      __embedding__), the close is SKIPPED — the embedder singleton
      stays alive so the other project's in-flight ONNX session
      doesn't get ripped out from under it. Pass None to force
      release regardless (e.g., graceful daemon shutdown).

      Returns the number of embedders released.
      """
      import gc
      if active_project_id is not None and _is_other_project_embedding(
          active_project_id
      ):
          logger.info(
              "close_shared_embedders: SKIPPED — another project is "
              "actively embedding (caller=%s)", active_project_id,
          )
          return 0
      with _SHARED_EMBEDDERS_LOCK:
          n = len(_SHARED_EMBEDDERS)
          for key, emb in list(_SHARED_EMBEDDERS.items()):
              try:
                  close = getattr(emb, "close", None)
                  if callable(close):
                      close()
              except Exception:
                  logger.debug("close() failed for embedder %r", key, exc_info=True)
          _SHARED_EMBEDDERS.clear()
      gc.collect()
      if n:
          logger.info("Released %d shared embedder(s)", n)
      return n


  def _is_other_project_embedding(caller_project_id: str) -> bool:
      """Return True if any project other than caller_project_id has
      an active embedding slot on the __embedding__ node."""
      try:
          from prep.services.pipeline.scheduler import pipeline_scheduler
          status = pipeline_scheduler.status()
          embed_slot = (status.get("nodes") or {}).get("__embedding__") or {}
          active = embed_slot.get("active") or {}
          return any(pid != caller_project_id for pid in active)
      except Exception:
          # If we can't determine, err on the side of caution and
          # report False so the close proceeds — the original behavior.
          return False
  ```

- [ ] **Step 2: Update the caller in `pipeline.py`.**

  In `src/prep/api/routers/pipeline.py:1145`, change:

  ```python
  released = close_shared_embedders()
  ```

  to:

  ```python
  released = close_shared_embedders(active_project_id=project_id)
  ```

- [ ] **Step 3: Run the test.**

  Run: `.venv/bin/pytest tests/test_close_shared_embedders_scope.py -v`
  Expected: PASS.

### Task P6.3 — Commit

- [ ] **Step 1: Stage and commit.**

  ```bash
  git add src/prep/services/embedder_factory.py \
          src/prep/api/routers/pipeline.py \
          tests/test_close_shared_embedders_scope.py
  git commit -m "$(cat <<'EOF'
fix(embedder): scope /pipeline/rebuild/stop close to caller project

close_shared_embedders is process-wide singleton release.
/pipeline/rebuild/stop calling it unconditionally meant stopping
project A's rebuild ripped the ONNX session out from under any
other project mid-embed.

New optional active_project_id parameter: if another project has
an active slot on the __embedding__ node, skip the close. Graceful
daemon shutdown still passes None to force release.
EOF
)"
  ```

---

## Self-Review (post-write checklist run by the plan author)

**1. Spec coverage**

| User concern | Plan task(s) |
|---|---|
| "Commit and merge anything not merged yet" | P0.1–P0.9 |
| "Settings router fan-out is the wrong design" | P1 |
| "Why is SourcePrep stuck in a weird UI state?" | P2 |
| "X-button design B+heuristic" | P3 |
| "Clustering output thrown away — Write Guard reverted" | P4 |
| "Orphan clustering manifest re-triggers same loop" | P5 |
| "Stopping deep-live-cam stopped SourcePrep" | P6 |

All seven concerns mapped.

**2. Placeholder scan**

No TODO / TBD / "appropriate error handling" / "similar to Task N" patterns. Every code block is complete. Every command has an expected output.

**3. Type consistency**

- `mark_stage_skipped(meta, stage_id, reason)` — same signature in P2.1 test and P2.2 implementation.
- `close_shared_embedders(active_project_id=...)` — same signature in P6.1 test, P6.2 implementation, and P6.2 caller update.
- `_compute_allowed_shrink_ratio` — return type unchanged (`float`), constant `_BASELINE_SHRINK_TOLERANCE` introduced and used consistently.
- `useCancelToast` hook signature matches between definition (P3.4) and usage (P3.5).
- `record_guard_rejection / should_defer_selfheal_resurrection / clear_guard_rejection` — three sibling helpers with consistent `(idx_dir, stage[, reason])` shapes.

**Open question for the author before execution**: P0.8 (fixture deletion) and the stash list (7 stashes) are flagged for explicit user decision, not auto-resolved by the plan. Confirm intent before running.

---
