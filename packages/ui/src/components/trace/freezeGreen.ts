/**
 * Phase 145 I3 — pure helper for the rebuild-time "freeze green" decision.
 *
 * Background: during a rebuild, `GraphEnrichmentPipeline` historically applied
 * `state = 'complete'` to ANY stage that (a) was previously complete and (b)
 * currently shows a regressed state ({not_built, disabled, queued, waiting,
 * idle, stale, warning}). The intent was to prevent flicker for stages the
 * rebuild hadn't reached yet — their prior data is still on disk.
 *
 * Bug surfaced by Phase 145 T4 baseline (SCORECARD_uat_baseline_2026-06-22):
 * the unconditional freeze-green also fires on stages *downstream of the
 * current rebuild stage* — those stages have NOT been re-run yet in this
 * rebuild, so rendering them as 'complete' is a stale leak from the prior
 * run. UAT invariant I3 fires in 11/12 iters on this exact symptom.
 *
 * Fix shape: gate the freeze-green decision on stage position relative to
 * its group's current_stage. Downstream of current_stage → do NOT freeze
 * green (let the legitimately-computed state, usually 'not_built' or
 * 'queued', show through). At-or-before current_stage → preserve the
 * pre-fix behavior so flicker mitigation still works for stages the
 * rebuild has already passed.
 *
 * The helper is exported and pure so the I3 contract can be pinned by
 * vitest without rendering the full component (the existing test pattern
 * in packages/ui/src/components/trace/__tests__/).
 */

// StageState is defined in GraphEnrichmentPipeline.tsx; type-only import
// avoids a runtime cycle (the component also imports
// `shouldApplyFreezeGreen` from this file).
import type { StageState } from './GraphEnrichmentPipeline';

// ── Canonical stage ordering per group ───────────────────────────
//
// These mirror tools/phase145_uat/constants.py STAGE_ORDER for the UI
// layer. Defined here (not imported) because packages/ui must not depend
// on the Python tools directory. The canonical 15-stage order is also
// the contract documented in REFERENCE_canonical-pipeline-behavior.md.

export const FAST_STAGE_ORDER: ReadonlyArray<string> = [
  'structural',
  'inferred_edges',
  'catalogue',
  'validation',
  'knowledge',
];

export const DEEP_STAGE_ORDER: ReadonlyArray<string> = [
  'enrichment',
  'group_reasoning',
  'clustering',
  'deepening',
  'deep_knowledge',
];

export const FINALIZE_STAGE_ORDER: ReadonlyArray<string> = [
  'atlas',
  'rules',
  'concepts',
  'audit',
  'antibodies',
];

// ── Helpers ──────────────────────────────────────────────────────

/**
 * Normalize legacy stage-name aliases the backend may still emit.
 * `augment` was the original name for what is now `catalogue` — the
 * three SYNC_RUNNING dispatch sites in useEnrichment.ts still defend
 * against both spellings (lines 98, 259, 624).
 */
export function normalizeFastStage(s: string | undefined): string | undefined {
  if (s === 'augment') return 'catalogue';
  return s;
}

export type StageGroup = 'fast' | 'deep' | 'finalize' | null;

export function groupForStage(stageId: string): StageGroup {
  if (FAST_STAGE_ORDER.includes(stageId)) return 'fast';
  if (DEEP_STAGE_ORDER.includes(stageId)) return 'deep';
  if (FINALIZE_STAGE_ORDER.includes(stageId)) return 'finalize';
  return null;
}

/**
 * Return the 0-based position of `stageId` within its group, or -1 if
 * the stage is not recognized.
 */
export function stagePositionInGroup(stageId: string): number {
  const fast = FAST_STAGE_ORDER.indexOf(stageId);
  if (fast >= 0) return fast;
  const deep = DEEP_STAGE_ORDER.indexOf(stageId);
  if (deep >= 0) return deep;
  const fin = FINALIZE_STAGE_ORDER.indexOf(stageId);
  if (fin >= 0) return fin;
  return -1;
}

// ── Freeze-green decision ────────────────────────────────────────

export interface FreezeGreenInputs {
  stageId: string;
  /** True iff this stage was complete at any point in a prior run
   * (the `wasCompleteRef.current[stage.id]` value from the component). */
  isPreviouslyComplete: boolean;
  /** The state computed by the per-group `compute*State` functions before
   * the freeze-green override runs. */
  currentState: StageState;
  /** The set of states that the freeze-green override treats as regressed.
   * Defined in the component; passed in so the helper has zero global
   * state and the test can vary the set explicitly. */
  regressedStates: ReadonlyArray<StageState>;
  /** Current stage IDs from the API. `fastCurrentStage` is post-normalize
   * (so a `catalogue` value here represents what the backend may emit as
   * either `catalogue` or `augment`). Undefined when the group is not
   * active or the API hasn't yet reported a stage. */
  fastCurrentStage: string | undefined;
  deepCurrentStage: string | undefined;
  finalizeCurrentStage: string | undefined;
}

/**
 * Decide whether to apply the rebuild freeze-green override for one stage.
 *
 * Returns `true` when the caller should set `stage.state = 'complete'`.
 * Returns `false` when the caller should leave `stage.state` alone (the
 * stage is downstream of the current rebuild stage and its 'complete'
 * would be a stale-leak from a prior run — the §2r intra-group leak that
 * UAT invariant I3 detects).
 *
 * Fail-open paths (return `true`, preserve pre-fix behavior) when group /
 * position lookup cannot be resolved — better to over-show 'complete'
 * than to introduce a regression in stages the helper doesn't recognize.
 */
/**
 * Phase 145 I3 — second leak path.
 *
 * The freeze-green override in the rebuild loop is one source of stale
 * 'complete' on downstream rows; the per-stage `compute*State` functions
 * are another. For example `finStageState('rules', dataComplete=true)`
 * returns 'complete' as soon as `rules.json` exists on disk — even if the
 * current rebuild is still on `atlas` (idx 0) and rules (idx 1) has NOT
 * been re-run yet in this run. The freeze-green helper above does not
 * fire because the computed state (`complete`) is not in the regressed
 * set — but the row still violates I3.
 *
 * This helper wraps a computed StageState and overrides any
 * `complete`/`stale` value to `not_built` when the row is downstream of
 * its group's current_stage. Applied at every stage-construction site
 * in `GraphEnrichmentPipeline.tsx` (deepStages, finalizeStages — fastStages
 * are already correct because their compute fns return regressed states
 * which the freeze-green helper handles).
 *
 * Fail-open paths mirror `shouldApplyFreezeGreen`: if group / position
 * lookup fails, return the computed state unchanged so unknown stages
 * don't regress.
 */
export function i3SafeStageState(
  computedState: StageState,
  stageId: string,
  groupCurrentStage: string | undefined,
): StageState {
  if (!groupCurrentStage) return computedState;
  // Only override the three states the harness's I3 invariant treats as
  // 'complete' (see tools/phase145_uat/constants.py DOM_STATE_TO_CANON).
  // 'running' / 'pending' / 'failed' are not leaks even if downstream.
  if (computedState !== 'complete' && computedState !== 'stale' && computedState !== 'warning') {
    return computedState;
  }

  const group = groupForStage(stageId);
  if (group === null) return computedState;

  // Normalize so an `augment`/`catalogue` anchor compares correctly with
  // the `catalogue` row id.
  const normalizedCurrent =
    group === 'fast' ? normalizeFastStage(groupCurrentStage) : groupCurrentStage;
  if (!normalizedCurrent) return computedState;

  const stagePos = stagePositionInGroup(stageId);
  const currentPos = stagePositionInGroup(normalizedCurrent);
  if (stagePos < 0 || currentPos < 0) return computedState;

  if (stagePos > currentPos) return 'not_built';
  return computedState;
}


export function shouldApplyFreezeGreen(inputs: FreezeGreenInputs): boolean {
  const {
    stageId,
    isPreviouslyComplete,
    currentState,
    regressedStates,
    fastCurrentStage,
    deepCurrentStage,
    finalizeCurrentStage,
  } = inputs;

  if (!isPreviouslyComplete) return false;
  if (!regressedStates.includes(currentState)) return false;

  const group = groupForStage(stageId);
  if (group === null) return true;

  const groupCurrentStage =
    group === 'fast' ? normalizeFastStage(fastCurrentStage) :
    group === 'deep' ? deepCurrentStage :
    finalizeCurrentStage;

  if (!groupCurrentStage) return true;

  const stagePos = stagePositionInGroup(stageId);
  const currentPos = stagePositionInGroup(groupCurrentStage);
  if (stagePos < 0 || currentPos < 0) return true;

  return stagePos <= currentPos;
}
