/**
 * Phase 145 I3 — pure helper tests for the rebuild freeze-green decision.
 *
 * Pins the contract that closes invariant I3 (intra-group stale-leak):
 * during a rebuild, downstream stages of the current rebuild stage must
 * NOT have their state pushed back to 'complete' even when they were
 * previously complete. See `freezeGreen.ts` for the helper docstring and
 * docs/Phase145_Pipeline-UI-Reliability/SCORECARD_uat_baseline_2026-06-22.md
 * for the live evidence.
 *
 * Test pattern follows RebuildingRow.test.tsx — no DOM render, pure
 * function calls, vitest only.
 */

import { describe, it, expect } from 'vitest';
import {
  FAST_STAGE_ORDER,
  DEEP_STAGE_ORDER,
  FINALIZE_STAGE_ORDER,
  groupForStage,
  i3SafeStageState,
  normalizeFastStage,
  shouldApplyFreezeGreen,
  stagePositionInGroup,
} from '../freezeGreen';
import type { StageState } from '../GraphEnrichmentPipeline';

const REGRESSED: ReadonlyArray<StageState> = [
  'not_built', 'disabled', 'queued', 'waiting', 'idle', 'stale', 'warning',
];

describe('freezeGreen helpers', () => {
  describe('stage taxonomy', () => {
    it('FAST_STAGE_ORDER mirrors the canonical 5 fast-sync stages', () => {
      expect(FAST_STAGE_ORDER).toEqual([
        'structural', 'inferred_edges', 'catalogue', 'validation', 'knowledge',
      ]);
    });

    it('DEEP_STAGE_ORDER mirrors the canonical 5 deep-enrichment stages', () => {
      expect(DEEP_STAGE_ORDER).toEqual([
        'enrichment', 'group_reasoning', 'clustering', 'deepening', 'deep_knowledge',
      ]);
    });

    it('FINALIZE_STAGE_ORDER mirrors the canonical 5 finalize stages', () => {
      expect(FINALIZE_STAGE_ORDER).toEqual([
        'atlas', 'rules', 'concepts', 'audit', 'antibodies',
      ]);
    });

    it('groupForStage resolves a stage to its group', () => {
      expect(groupForStage('structural')).toBe('fast');
      expect(groupForStage('inferred_edges')).toBe('fast');
      expect(groupForStage('enrichment')).toBe('deep');
      expect(groupForStage('clustering')).toBe('deep');
      expect(groupForStage('atlas')).toBe('finalize');
      expect(groupForStage('antibodies')).toBe('finalize');
    });

    it('groupForStage returns null for unknown stage ids', () => {
      expect(groupForStage('not-a-stage')).toBeNull();
      expect(groupForStage('')).toBeNull();
    });

    it('stagePositionInGroup returns 0-based position', () => {
      expect(stagePositionInGroup('structural')).toBe(0);
      expect(stagePositionInGroup('knowledge')).toBe(4);
      expect(stagePositionInGroup('enrichment')).toBe(0);
      expect(stagePositionInGroup('atlas')).toBe(0);
      expect(stagePositionInGroup('antibodies')).toBe(4);
    });

    it('stagePositionInGroup returns -1 for unknown stage ids', () => {
      expect(stagePositionInGroup('not-a-stage')).toBe(-1);
    });

    it('normalizeFastStage maps augment alias to catalogue', () => {
      expect(normalizeFastStage('augment')).toBe('catalogue');
      expect(normalizeFastStage('catalogue')).toBe('catalogue');
      expect(normalizeFastStage('inferred_edges')).toBe('inferred_edges');
      expect(normalizeFastStage(undefined)).toBeUndefined();
    });
  });

  describe('shouldApplyFreezeGreen — I3 contract', () => {
    // I3 = "no row downstream of current_stage shows complete". The fix
    // gates freeze-green on stage position vs current_stage position.

    it('returns false when stage is downstream of fast_sync current_stage', () => {
      // fast_sync is on inferred_edges (idx 1). catalogue (idx 2),
      // validation (idx 3), knowledge (idx 4) are all downstream. They
      // were complete in a prior run; current_state regressed to queued.
      // Freeze-green must NOT fire — otherwise data-stage-state stays
      // 'complete' and I3 sees a stale leak.
      for (const stageId of ['catalogue', 'validation', 'knowledge']) {
        expect(shouldApplyFreezeGreen({
          stageId,
          isPreviouslyComplete: true,
          currentState: 'queued',
          regressedStates: REGRESSED,
          fastCurrentStage: 'inferred_edges',
          deepCurrentStage: undefined,
          finalizeCurrentStage: undefined,
        })).toBe(false);
      }
    });

    it('returns true when stage is AT-or-BEFORE fast_sync current_stage', () => {
      // fast_sync is on catalogue (idx 2). structural (0), inferred_edges
      // (1) are at-or-before. They were complete; current_state is now
      // 'waiting' (mid-rebuild flicker). Freeze-green SHOULD fire because
      // the rebuild has already passed those stages.
      for (const stageId of ['structural', 'inferred_edges', 'catalogue']) {
        expect(shouldApplyFreezeGreen({
          stageId,
          isPreviouslyComplete: true,
          currentState: 'waiting',
          regressedStates: REGRESSED,
          fastCurrentStage: 'catalogue',
          deepCurrentStage: undefined,
          finalizeCurrentStage: undefined,
        })).toBe(true);
      }
    });

    it('returns false for downstream deep_enrichment stages', () => {
      // deep_enrichment is on enrichment (idx 0). group_reasoning (1),
      // clustering (2), deepening (3), deep_knowledge (4) are downstream.
      for (const stageId of ['group_reasoning', 'clustering', 'deepening', 'deep_knowledge']) {
        expect(shouldApplyFreezeGreen({
          stageId,
          isPreviouslyComplete: true,
          currentState: 'queued',
          regressedStates: REGRESSED,
          fastCurrentStage: undefined,
          deepCurrentStage: 'enrichment',
          finalizeCurrentStage: undefined,
        })).toBe(false);
      }
    });

    it('returns false for downstream finalize stages', () => {
      // finalize on atlas (idx 0). rules, concepts, audit, antibodies are
      // downstream. The pre-fix code already had a finalize-specific
      // pattern at line 1497-1508 of GraphEnrichmentPipeline.tsx, but the
      // freeze-green override at line 1657 was group-blind. This pins the
      // gate uniformly.
      for (const stageId of ['rules', 'concepts', 'audit', 'antibodies']) {
        expect(shouldApplyFreezeGreen({
          stageId,
          isPreviouslyComplete: true,
          currentState: 'not_built',
          regressedStates: REGRESSED,
          fastCurrentStage: undefined,
          deepCurrentStage: undefined,
          finalizeCurrentStage: 'atlas',
        })).toBe(false);
      }
    });

    it('normalizes augment alias from backend so catalogue position is correct', () => {
      // Backend may emit `current_stage='augment'` (legacy). After
      // normalization, augment === catalogue (idx 2). Downstream
      // (validation idx 3, knowledge idx 4) must still be left alone.
      expect(shouldApplyFreezeGreen({
        stageId: 'validation',
        isPreviouslyComplete: true,
        currentState: 'queued',
        regressedStates: REGRESSED,
        fastCurrentStage: 'augment',
        deepCurrentStage: undefined,
        finalizeCurrentStage: undefined,
      })).toBe(false);

      // Catalogue itself is at-or-before its normalized self — freeze-green
      // applies.
      expect(shouldApplyFreezeGreen({
        stageId: 'catalogue',
        isPreviouslyComplete: true,
        currentState: 'waiting',
        regressedStates: REGRESSED,
        fastCurrentStage: 'augment',
        deepCurrentStage: undefined,
        finalizeCurrentStage: undefined,
      })).toBe(true);
    });

    it('returns false when stage was never previously complete', () => {
      // First-ever run — freeze-green has nothing to protect; the
      // legitimately-computed state (not_built, queued, etc.) is correct.
      expect(shouldApplyFreezeGreen({
        stageId: 'validation',
        isPreviouslyComplete: false,
        currentState: 'queued',
        regressedStates: REGRESSED,
        fastCurrentStage: 'inferred_edges',
        deepCurrentStage: undefined,
        finalizeCurrentStage: undefined,
      })).toBe(false);
    });

    it('returns false when current_state is not in regressed set', () => {
      // Stage is genuinely running or complete this run — freeze-green
      // would be a no-op anyway. Returning false here keeps the helper's
      // semantics tight ("should I override the computed state?").
      expect(shouldApplyFreezeGreen({
        stageId: 'catalogue',
        isPreviouslyComplete: true,
        currentState: 'running',
        regressedStates: REGRESSED,
        fastCurrentStage: 'inferred_edges',
        deepCurrentStage: undefined,
        finalizeCurrentStage: undefined,
      })).toBe(false);
    });

    it('fails open (returns true) when group lookup fails', () => {
      // Stage id we don't recognize. Helper preserves the pre-fix
      // unconditional freeze-green so an unknown stage doesn't regress.
      expect(shouldApplyFreezeGreen({
        stageId: 'mystery_stage',
        isPreviouslyComplete: true,
        currentState: 'queued',
        regressedStates: REGRESSED,
        fastCurrentStage: 'inferred_edges',
        deepCurrentStage: undefined,
        finalizeCurrentStage: undefined,
      })).toBe(true);
    });

    it('fails open when current_stage for the relevant group is undefined', () => {
      // No anchor for "downstream" — preserve pre-fix behavior (flicker
      // mitigation) for all of fast_sync's previously-complete stages.
      // This is the same fail-open contract I3 itself uses (see invariants.py
      // line 297-299).
      expect(shouldApplyFreezeGreen({
        stageId: 'validation',
        isPreviouslyComplete: true,
        currentState: 'waiting',
        regressedStates: REGRESSED,
        fastCurrentStage: undefined,
        deepCurrentStage: 'enrichment',
        finalizeCurrentStage: undefined,
      })).toBe(true);
    });

    it('groups are isolated: deep_enrichment current_stage does not affect fast_sync rows for freeze-green', () => {
      // While deep_enrichment is on stage 2 (clustering), fast_sync's
      // current_stage may also be set (e.g., to knowledge if fast hasn't
      // fully transitioned out). But fast_sync stages must be evaluated
      // against fast_sync current_stage, not deep_enrichment's. The helper
      // looks up the group from stageId, then reads only that group's
      // current_stage.
      //
      // Here: deep is on clustering; fast is on knowledge (idx 4, end).
      // validation (idx 3, fast) is BEFORE fast knowledge — freeze-green
      // should apply.
      expect(shouldApplyFreezeGreen({
        stageId: 'validation',
        isPreviouslyComplete: true,
        currentState: 'waiting',
        regressedStates: REGRESSED,
        fastCurrentStage: 'knowledge',
        deepCurrentStage: 'clustering',
        finalizeCurrentStage: undefined,
      })).toBe(true);
    });
  });

  // ── i3SafeStageState — second leak path ─────────────────────────
  //
  // Whereas shouldApplyFreezeGreen handles the rebuild-time freeze-green
  // override branch, i3SafeStageState handles the per-stage compute
  // functions (finStageState, computeXxxState) that return 'complete'
  // directly when data exists on disk from a prior run. Both close I3;
  // they're at different points in the state computation flow.

  describe('i3SafeStageState — I3 contract on computed states', () => {
    it('overrides downstream complete → not_built when group is active', () => {
      // Finalize on atlas (idx 0). rules (1), concepts (2), audit (3),
      // antibodies (4) have data on disk from prior run → compute fn
      // returns 'complete'. I3-safe wrapper must override to 'not_built'
      // so the harness's COMPLETE_DOM_STATES check passes.
      for (const stageId of ['rules', 'concepts', 'audit', 'antibodies']) {
        expect(i3SafeStageState('complete', stageId, 'atlas')).toBe('not_built');
      }
    });

    it('overrides downstream stale and warning the same as complete', () => {
      // DOM_STATE_TO_CANON treats {complete, stale, warning} all as
      // 'complete' for invariant purposes — override all three.
      expect(i3SafeStageState('stale', 'rules', 'atlas')).toBe('not_built');
      expect(i3SafeStageState('warning', 'rules', 'atlas')).toBe('not_built');
    });

    it('preserves complete for stages at or before current_stage', () => {
      // Finalize on concepts (idx 2). atlas (0), rules (1), concepts (2)
      // legitimately have run this rebuild and should stay 'complete'.
      for (const stageId of ['atlas', 'rules', 'concepts']) {
        expect(i3SafeStageState('complete', stageId, 'concepts')).toBe('complete');
      }
    });

    it('returns computed state unchanged when group has no current_stage', () => {
      // Group settled / not running → no anchor. Computed 'complete' is
      // the legitimate prior-run state and should display.
      expect(i3SafeStageState('complete', 'rules', undefined)).toBe('complete');
    });

    it('returns computed state unchanged for non-complete inputs', () => {
      // running / queued / failed are not leak candidates.
      expect(i3SafeStageState('running', 'rules', 'atlas')).toBe('running');
      expect(i3SafeStageState('queued', 'rules', 'atlas')).toBe('queued');
      expect(i3SafeStageState('not_built', 'rules', 'atlas')).toBe('not_built');
      expect(i3SafeStageState('error', 'rules', 'atlas')).toBe('error');
    });

    it('fail-opens when stage id or current_stage is unknown', () => {
      expect(i3SafeStageState('complete', 'mystery', 'atlas')).toBe('complete');
      expect(i3SafeStageState('complete', 'rules', 'mystery')).toBe('complete');
    });

    it('normalizes augment alias when looking up fast_sync current_stage', () => {
      // Backend may emit augment. Catalogue (idx 2) is at-or-before;
      // validation (3) and knowledge (4) are downstream.
      expect(i3SafeStageState('complete', 'catalogue', 'augment')).toBe('complete');
      expect(i3SafeStageState('complete', 'validation', 'augment')).toBe('not_built');
      expect(i3SafeStageState('complete', 'knowledge', 'augment')).toBe('not_built');
    });

    it('group isolation: passing a fast current_stage does not touch deep rows', () => {
      // current = inferred_edges (fast group). deep stages aren't in the
      // fast group, so groupForStage returns 'deep' for them and the
      // anchor lookup uses the DEEP anchor (not passed here). Result:
      // pass-through.
      expect(i3SafeStageState('complete', 'group_reasoning', 'inferred_edges')).toBe('complete');
    });

    it('deep_enrichment downstream override — real T4 fire scenario', () => {
      // Reproduces baseline SCORECARD_uat_baseline_2026-06-22 evidence:
      // deep on enrichment (0); group_reasoning, clustering, deepening
      // all returned 'complete' from their compute fns reading prior-run
      // data. Wrapper overrides each to 'not_built'.
      expect(i3SafeStageState('complete', 'enrichment', 'enrichment')).toBe('complete');
      expect(i3SafeStageState('complete', 'group_reasoning', 'enrichment')).toBe('not_built');
      expect(i3SafeStageState('complete', 'clustering', 'enrichment')).toBe('not_built');
      expect(i3SafeStageState('complete', 'deepening', 'enrichment')).toBe('not_built');
      expect(i3SafeStageState('complete', 'deep_knowledge', 'enrichment')).toBe('not_built');
    });

    // ── §9.3 #28/#29 — groupPhase='completed' coercion ────────────

    it('coerces running to complete when groupPhase is completed', () => {
      // §9.3 #28 — Deep Reasoning shows blue icon + spinner + 100% bar
      // (state='running') while API reports deep_enrichment.phase=completed.
      // The coercion turns the stale running render into a clean done row.
      expect(i3SafeStageState('running', 'enrichment', undefined, 'completed')).toBe('complete');
    });

    it('coerces idle/not_built to complete when groupPhase is completed', () => {
      // §9.3 #29 — Group Reasoning / Module Synthesis / Continuous Deepening
      // render as empty circle (state='idle' / 'not_built') despite carrying
      // real analyzed counts and the API reporting phase=completed.
      // Coercion forces the green chip on every stage in the completed group.
      expect(i3SafeStageState('idle', 'group_reasoning', undefined, 'completed')).toBe('complete');
      expect(i3SafeStageState('not_built', 'clustering', undefined, 'completed')).toBe('complete');
      expect(i3SafeStageState('queued', 'deepening', undefined, 'completed')).toBe('complete');
    });

    it('does NOT coerce when groupPhase is cancelled or failed', () => {
      // Cancel-mid-stage and stage-failure leave a mix of finished +
      // unfinished rows. The per-stage compute fns model this correctly;
      // a blanket coercion would lie about which stages actually ran.
      expect(i3SafeStageState('running', 'enrichment', 'enrichment', 'cancelled')).toBe('running');
      expect(i3SafeStageState('not_built', 'clustering', 'enrichment', 'failed')).toBe('not_built');
    });

    it('does NOT coerce when groupPhase is running or paused', () => {
      // Active phases must let the existing downstream-stale logic apply,
      // not bypass it via the completed-coercion shortcut.
      expect(i3SafeStageState('not_built', 'clustering', 'enrichment', 'running')).toBe('not_built');
      expect(i3SafeStageState('complete', 'clustering', 'enrichment', 'paused')).toBe('not_built');
    });

    it('groupPhase=completed takes precedence over an undefined groupCurrentStage', () => {
      // The previous code path early-returned computedState when
      // groupCurrentStage was undefined. With the new coercion, completed
      // wins regardless of whether the anchor is present.
      // Pre-fix: would have returned 'running' (stale).
      // Post-fix: returns 'complete'.
      expect(i3SafeStageState('running', 'deepening', undefined, 'completed')).toBe('complete');
    });

    it('groupPhase=undefined preserves existing behavior (backwards compat)', () => {
      // Callers that pre-date the new param keep working identically.
      expect(i3SafeStageState('complete', 'rules', undefined, undefined)).toBe('complete');
      expect(i3SafeStageState('running', 'rules', 'atlas', undefined)).toBe('running');
      expect(i3SafeStageState('complete', 'knowledge', 'augment', undefined)).toBe('not_built');
    });
  });
});
