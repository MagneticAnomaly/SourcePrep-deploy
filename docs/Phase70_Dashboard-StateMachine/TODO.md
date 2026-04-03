# Phase 70: Dashboard State Machine — TODO

## Phase 70A: Hydration Controller (Complete)

- [x] Create `useHydrationController` hook (AbortController + 250ms debounce)
- [x] Wire controller into App.tsx
- [x] Thread AbortSignal into all 12+ hooks
- [x] Guard polling effects with `isHydrating` flag
- [x] Move App.tsx hydration effects behind controller
- [x] Fix `isHydrating` stuck true (review finding)
- [x] Restore cleanup functions in useEnrichment/useTraceSystem
- [x] Guard fetchFileTree with signal
- [x] Fix signal lifecycle (render-phase AbortController replacement)
- [x] API timeout (8s) + 3-attempt retry with backoff
- [x] Async status endpoints with `run_in_executor`
- [x] Staleness cache TTL 10s → 30s
- [x] Trace count fallback when manifest lacks counts
- [x] Mark abort errors with `aborted` flag for clean error handling
- [x] Increase debounce to 250ms to prevent daemon thread pool exhaustion

## Phase 70B: Pipeline Overwrite Protection (Complete)

- [x] `should_block_stage_completion()` — blocks if output has fewer records
- [x] Wire write guard into orchestrator completion handler
- [x] `check_stage_freshness()` — skips stage if outputs newer than inputs
- [x] `STAGE_INPUT_FILES` dependency map + `STAGE_IS_DETERMINISTIC` flag
- [x] Auto-recovery: deterministic stages allowed, LLM stages try checkpoint restore
- [x] Fix deadlock risk (remove nested Lock acquisition)
- [x] Move freshness check before heartbeat timer
- [x] Document write guard = detection + rollback (not prevention)

## Phase 70C: Atlas Segment Drift (Complete)

- [x] `segment_ids` persisted in AtlasDocument
- [x] 4th staleness trigger: segment drift detection
- [x] Mtime guard so `compute_segments()` only runs when graph changed

## Phase 70D: Two-Tone Progress Bars (TODO)

See `04_two-tone-progress-bars-plan.md` for full spec.

- [ ] Add `progress_baseline` to Group Reasoning status type
- [ ] Add `progress_baseline` to Module Synthesis status type
- [ ] Add `progress_baseline` to Atlas Building status type
- [ ] Add `progress_baseline` to Continuous Deepening status type
- [ ] Add two-tone support to Deep Knowledge Embedding (Stage 10)
- [ ] Update `computeStageRerun()` calls for all 5 stages
- [ ] Verify `slot_progress.baseline` is exposed in pipeline API for all active stages
- [ ] **Test:** Run incremental pipeline, verify all stages show per-stage two-tone (not generic fallback)

## Manual Testing Checklist

- [ ] Switch between projects rapidly — no freeze, no timeout cascade
- [ ] Switch to unbuilt project — shows "Initialize Trace Graph" correctly
- [ ] Switch back to built project — panels reload with data
- [ ] Run pipeline while switching — no data corruption
- [ ] Pipeline incremental run — write guard allows growth, blocks shrinkage
- [ ] Pipeline fresh outputs skip — stages with current outputs are skipped
- [ ] Add new directory to repo — atlas marks stale (segment drift)

## Known Issues

- [ ] Rapid project switching (5+ clicks fast) can still exhaust daemon thread pool
  - Root cause: aborted requests still process server-side
  - Mitigation: 250ms debounce reduces but doesn't eliminate
  - Full fix: server-side request cancellation (check client disconnect in `run_in_executor`)
