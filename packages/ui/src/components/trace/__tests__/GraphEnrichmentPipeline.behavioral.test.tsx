/**
 * GraphEnrichmentPipeline — behavioural pin for §9.3 #30
 *
 * PR-H complement to the 39 structural pins in statsSafeState.test.ts.
 * The structural pins prove every per-stage stats IIFE wraps its raw
 * computed state with i3SafeStageState(promoteForRebuild(...)) and that
 * the literal 'Not run' is guarded by a safeState check. They cannot
 * prove behaviour: that given a fixture where deep_enrichment.phase ===
 * 'completed' AND the per-stage raw computed state is 'not_built' (the
 * §9.3 #30 race window — group has settled, current_stage cleared, but
 * the per-stage data payload hasn't been refreshed by the next poll
 * yet), the rendered Deep Knowledge Embedding row does NOT show the
 * literal text 'Not run'.
 *
 * That behavioural contract is what this file pins.
 *
 * Test pattern: mount the component into happy-dom via RTL, assert on
 * the textContent / data-stage-state of the rendered row. First DOM
 * render test in packages/ui — the other 16 test files are pure-logic
 * / source-inspection by convention (vitest + happy-dom + RTL are now
 * available; choose source-inspection when the contract is syntactic
 * shape / pure helpers / exported constants, DOM render when the
 * contract is what the user sees given a state snapshot).
 *
 * Infra inventory: vitest@^3, happy-dom@^20 (post-PR-H/3 bump from
 * ^15 for CRITICAL GHSA-37j7-fg3j-429f), @testing-library/react@^14.3,
 * @testing-library/jest-dom@^6.4. Wired in PR-H/1 (b3ca8d5f).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
// Imported here AS WELL AS in vitest.setup.ts so the `declare module 'vitest'`
// augmentation in @testing-library/jest-dom/types/vitest.d.ts is visible to
// tsc when typechecking this file (setupFiles is a runtime concept; tsc
// doesn't load it). Without this, toHaveTextContent/toHaveAttribute fail
// TS2339 even though they work at runtime.
import '@testing-library/jest-dom/vitest';
import { GraphEnrichmentPipeline } from '../GraphEnrichmentPipeline';
import type { GraphEnrichmentPipelineProps } from '../GraphEnrichmentPipeline';

// ── Fixture A — primary §9.3 #30 starting condition ────────────
//
// The race window: API has flipped deep_enrichment.phase to 'completed'
// AND nulled current_stage (group has authoritatively settled). The
// per-stage payloads (epistemic / modules / deepening) carry real data
// because the group has actually run, but deepKnowledge.deep_chunks_
// embedded is still 0 (the deep_knowledge stage's data payload writes
// last in the deep_enrichment group; the next poll tick hasn't landed).
//
// Without i3SafeStageState coercion in the deepKnowledgeStats IIFE,
// the raw deepKnowledgeState resolves to 'not_built' (deep is present
// with total_scored > 0 but no deep_chunks_embedded), and the IIFE
// returns 'Not run' next to a green badge. §9.3 #30 fix: the IIFE
// passes deepEnrichmentPhase to i3SafeStageState, which coerces every
// in-group raw state to 'complete' when the phase is 'completed'.
//
// Scrutiny note (PRH-R1-001): under THIS fixture the raw states resolve
// to enrichment='disabled' (no aug), deepening='stale' (settled_ratio
// 0.20), deep_knowledge='not_built'. Only deep_knowledge's stats IIFE
// would otherwise hit the literal 'Not run' branch — the other 4 deep
// stages render their non-'Not run' fallback strings even without
// coercion, so this fixture's assertions #3 and #4 (loop assertions)
// are vacuous for 4 of 5 deep stages. The gap-coverage fixture below
// (Fixture B) exercises the missed group_reasoning + clustering paths.

const phase30Fixture: GraphEnrichmentPipelineProps = {
  // Required props
  trace: {
    enabled: true,
    exists: true,
    building: false,
    counts: { nodes: 1240, edges: 3815 },
    last_build_at: '2026-06-24T10:00:00Z',
  },
  onStopRebuild: () => {},

  // Fast sync: completed. All payloads omitted so PR-F F5 (§9.3 #33)
  // 'Complete' fallthrough fires for stages whose data hasn't loaded.
  fastSyncPhase: 'completed',
  fastCurrentStage: undefined,
  inferredEdgesRunning: false,
  augmenting: false,
  validating: false,
  fastKnowledgeBuilding: false,

  // Deep enrichment payloads — present with real data so the raw
  // per-stage compute functions don't short-circuit to 'disabled'.
  // deepKnowledge / knowledge intentionally undefined so deepChunks=0
  // and computeDeepKnowledgeState returns 'not_built' (its terminal
  // branch, lines 692-696 of GraphEnrichmentPipeline.tsx). That's the
  // raw state the safeState coercion must hide.
  epistemic: {
    enabled: true,
    enriched_nodes: 1240,
    avg_confidence: 0.84,
    running: false,
  },
  modules: {
    enabled: true,
    module_count: 35,
    total_files_clustered: 1100,
    running: false,
  },
  deepening: {
    running: false,
    total_scored: 500,
    settled_count: 100,
    settled_ratio: 0.20,
    avg_score: 0.5,
  },
  groupReasoning: {
    enabled: true,
    group_count: 35,
    analyzed: 35,
    running: false,
  },

  // The §9.3 #30 trigger: group settled, current_stage cleared.
  deepEnrichmentPhase: 'completed',
  deepCurrentStage: undefined,
  epistemicRunning: false,
  clusterRunning: false,
  atlasRunning: false,
  deepeningRunning: false,
  groupReasoningRunning: false,
  deepKnowledgeBuilding: false,

  // Finalize idle (irrelevant to §9.3 #30 but kept consistent)
  finalizePhase: 'idle',
  finalizeGroupRunning: false,
  finalizeCurrentStage: undefined,

  // Barrier inactive — this is not a rebuild. freeze-green path
  // explicitly out of scope for this test.
  barrier: { active: false },

  // Groups expanded so per-stage rows render (defaults are all collapsed;
  // rows then have data-testid="pipeline-stage-row-<id>" selectable below).
  fastCollapsed: false,
  deepCollapsed: false,
  finalizeCollapsed: false,
};

// ── Fixture B — gap coverage (PR-H/3 addenda) ──────────────────
//
// PRH-R1-001 (scrutiny): the primary fixture's modules.module_count=35
// and deepening.settled_ratio=0.20 cause clustering and group_reasoning's
// raw states to resolve to 'complete' BEFORE i3SafeStageState's coercion
// runs — so a regression that broke safeState ONLY for those stages
// (the exact regression class PR-G addenda fixed for group_reasoning)
// would not be caught by Fixture A's loop assertions.
//
// Fixture B forces:
//   - clustering raw → 'not_built'  (modules.enabled with module_count=0)
//   - group_reasoning raw → 'not_built'  (no downstream complete/stale)
// With phase='completed', BOTH must coerce to 'complete' and render
// non-'Not run' stats text. Inline adversarial proof verifies this.
//
// enrichment / deepening / deep_knowledge raw states under Fixture B
// are 'complete' (or close enough) — those are pinned by Fixture A's
// 'not_built'/'disabled'/'stale' cascades. Fixture B is purpose-built
// for the two stages Fixture A misses.

const phase30FixtureGapCoverage: GraphEnrichmentPipelineProps = {
  ...phase30Fixture,
  // ep.enriched_nodes > 0 keeps downstream raw states out of the
  // ep-not-enabled 'disabled' early-return, so clustering/group_reasoning
  // proceed to their module_count / group_count checks.
  epistemic: { enabled: true, enriched_nodes: 100, avg_confidence: 0.84, running: false },
  // mod present + module_count=0  →  computeModuleState returns 'not_built'
  modules: { enabled: true, module_count: 0, total_files_clustered: 0, running: false },
  // deep present + total_scored=0  →  computeDeepeningState returns 'not_built'
  // (also keeps deepeningState !== 'complete'/'stale' so group_reasoning's
  // downstream-complete short-circuit doesn't fire)
  deepening: { running: false, total_scored: 0, settled_count: 0, settled_ratio: 0, avg_score: 0 },
  // groupReasoning enabled + group_count=0  →  inline IIFE falls through to 'not_built'
  groupReasoning: { enabled: true, group_count: 0, analyzed: 0, running: false },
};

// ── Fixture C — partial-payload variant (PR-H/3 addenda) ───────
//
// PRH-R1-005 (scrutiny): Fixture A routes through the PR-F F5 fallthrough
// `if (!deepKnowledgeSource) return 'Complete'` because deepKnowledge is
// undefined. But the documented §9.3 #30 production scenario is
// "deepKnowledge.deep_chunks_embedded is still 0" — i.e. the payload
// is PRESENT with zero chunks. That triggers the
// `${deepKnowledgeSource.chunks_embedded} chunks embedded` fallthrough
// branch instead. Both must work; Fixture C pins the partial-payload
// branch that Fixture A does not exercise.

const phase30FixtureWithPartialPayload: GraphEnrichmentPipelineProps = {
  ...phase30Fixture,
  deepKnowledge: {
    enabled: true,
    running: false,
    chunks_embedded: 0,
    deep_chunks_embedded: 0,
    last_run_at: null,
  },
};

const DEEP_ENRICHMENT_STAGE_IDS = [
  'enrichment',
  'group_reasoning',
  'clustering',
  'deepening',
  'deep_knowledge',
] as const;

const FAST_SYNC_STAGE_IDS = [
  'structural',
  'inferred_edges',
  'catalogue',
  'validation',
  'knowledge',
] as const;

// ── Tests ──────────────────────────────────────────────────────

describe('GraphEnrichmentPipeline — §9.3 #30 behavioural pin', () => {
  let consoleError: ReturnType<typeof vi.spyOn>;
  let consoleWarn: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // PRH-R1-002 (scrutiny): keep the no-op mock so React internal
    // warnings don't pollute test output, but in the hygiene
    // assertion below we surface any captured calls to stderr so the
    // developer can see WHAT was logged when the assertion fails.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    consoleError.mockRestore();
    consoleWarn.mockRestore();
  });

  // PRIMARY — §9.3 #30 contract.
  // FORBIDDEN: row shows literal 'Not run' when groupPhase is 'completed'.
  // PR-J addenda: ALSO assert positive presence of 'Complete' — the
  // PR-F F5 fallthrough literal — so mutation tests can't quietly
  // change the return value to "" or any other string and still pass.
  it("Deep Knowledge Embedding row does NOT render 'Not run' AND DOES render 'Complete' when deepEnrichmentPhase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).not.toHaveTextContent('Not run');
    expect(row).toHaveTextContent('Complete');
  });

  // PRIMARY — badge and stats must agree.
  // The row's data-stage-state attribute is set from the SAME i3SafeStageState
  // call that drives the badge styling (GraphEnrichmentPipeline.tsx:839 +
  // :1567). Pinning it to 'complete' proves the §9.3 #28/#29 coercion is
  // applied — without it the attribute would be 'not_built' under this fixture.
  it("Deep Knowledge Embedding row badge coerces to 'complete' under phase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).toHaveAttribute('data-stage-state', 'complete');
  });

  // GROUP — coercion applies uniformly across all 5 deep_enrichment stages.
  // Assertions pin both text and data-stage-state (PRH-R1-006 addenda).
  it("all 5 deep_enrichment stage rows do NOT render 'Not run' AND data-stage-state='complete' under phase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    for (const id of DEEP_ENRICHMENT_STAGE_IDS) {
      const row = screen.getByTestId(`pipeline-stage-row-${id}`);
      expect(row, `deep_enrichment stage '${id}' regressed to 'Not run' under phase='completed'`)
        .not.toHaveTextContent('Not run');
      expect(row, `deep_enrichment stage '${id}' badge not coerced to 'complete'`)
        .toHaveAttribute('data-stage-state', 'complete');
    }
  });

  // GROUP — same contract for fast_sync (fastSyncPhase='completed' must
  // coerce every fast stage too; PR-D shipped the pattern for all 5).
  it("all 5 fast_sync stage rows do NOT render 'Not run' AND data-stage-state='complete' under phase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    for (const id of FAST_SYNC_STAGE_IDS) {
      const row = screen.getByTestId(`pipeline-stage-row-${id}`);
      expect(row, `fast_sync stage '${id}' regressed to 'Not run' under phase='completed'`)
        .not.toHaveTextContent('Not run');
      expect(row, `fast_sync stage '${id}' badge not coerced to 'complete'`)
        .toHaveAttribute('data-stage-state', 'complete');
    }
  });

  // GAP COVERAGE (PR-H/3 addenda — PRH-R1-001) — group_reasoning and
  // clustering raw states forced to 'not_built' so the coercion path
  // is actually exercised for those stages, not short-circuited by
  // upstream 'complete' (as in Fixture A).
  it("Fixture B: group_reasoning + clustering rows do NOT render 'Not run' AND data-stage-state='complete' (gap coverage)", () => {
    render(<GraphEnrichmentPipeline {...phase30FixtureGapCoverage} />);
    for (const id of ['group_reasoning', 'clustering'] as const) {
      const row = screen.getByTestId(`pipeline-stage-row-${id}`);
      expect(row, `gap-coverage: '${id}' regressed to 'Not run' under phase='completed'`)
        .not.toHaveTextContent('Not run');
      expect(row, `gap-coverage: '${id}' badge not coerced to 'complete'`)
        .toHaveAttribute('data-stage-state', 'complete');
    }
  });

  // PARTIAL-PAYLOAD variant (PR-H/3 addenda — PRH-R1-005) — pins the
  // production race shape where deepKnowledge IS present but
  // deep_chunks_embedded=0. Routes through a different IIFE branch
  // than Fixture A.
  // PR-J addenda: positive-presence assertion on 'chunks embedded'
  // so the realistic-payload fallthrough literal (the
  // `${chunks_embedded} chunks embedded` template) is pinned.
  // Mutation testing surfaced this template string as a surviving
  // mutant (could change to '' silently).
  it("Fixture C: deep_knowledge row with partial payload (chunks_embedded=0) does NOT render 'Not run' AND DOES render 'chunks embedded'", () => {
    render(<GraphEnrichmentPipeline {...phase30FixtureWithPartialPayload} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).not.toHaveTextContent('Not run');
    expect(row).toHaveTextContent('chunks embedded');
    expect(row).toHaveAttribute('data-stage-state', 'complete');
  });

  // FIXTURE D — running branch coverage (PR-J).
  //
  // Mutation testing on deepKnowledgeStats IIFE found that the literal
  // 'Re-embedding with deep data...' string is unpinned — a mutant
  // changing it to "" or removing the running branch entirely silently
  // passes. Cause: no fixture exercises the safeState='running' path
  // for deep_knowledge. Fixture D fixes that.
  //
  // Trigger: deepKnowledgeBuilding=true makes computeDeepKnowledgeState
  // return 'running' BEFORE its 'disabled' cascade. We use
  // deepEnrichmentPhase='running' (NOT 'completed') so the
  // i3SafeStageState exception list doesn't fire — safeState stays
  // 'running' and the IIFE hits its 'Re-embedding' branch.
  it("Fixture D: deep_knowledge row with deepKnowledgeBuilding=true renders 'Re-embedding'", () => {
    const runningFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      deepEnrichmentPhase: 'running',
      deepCurrentStage: 'deep_knowledge',
      deepKnowledgeBuilding: true,
    };
    render(<GraphEnrichmentPipeline {...runningFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).toHaveTextContent('Re-embedding');
    expect(row).not.toHaveTextContent('Not run');
  });

  // FIXTURE E — disabled branch coverage (PR-J).
  //
  // Mutation testing found the 'Waiting for enrichment + clusters'
  // literal unpinned for the same reason as Fixture D — no fixture
  // exercises the safeState='disabled' path. Use minimal upstream
  // (epistemic disabled) so computeDeepKnowledgeState returns 'disabled'
  // at its first early-return. Phase 'running' keeps safeState
  // unchanged from the raw 'disabled'.
  it("Fixture E: deep_knowledge row with disabled upstream renders 'Waiting for enrichment'", () => {
    const disabledFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      deepEnrichmentPhase: 'running',
      deepCurrentStage: 'enrichment',
      // Force computeDeepKnowledgeState to return 'disabled' at the
      // `!ep || !ep.enabled || ep.enriched_nodes === 0` early-return.
      epistemic: { enabled: true, enriched_nodes: 0, avg_confidence: 0, running: false },
      modules: undefined,
      deepening: undefined,
      groupReasoning: undefined,
    };
    render(<GraphEnrichmentPipeline {...disabledFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).toHaveTextContent('Waiting for enrichment');
    expect(row).not.toHaveTextContent('Not run');
  });

  // FIXTURE F — rebuilding branch coverage (PR-J).
  //
  // Mutation testing found the `safeState === 'rebuilding'` disjunct
  // in `(safeState === 'running' || safeState === 'rebuilding')` was
  // unpinned — no fixture sets isRebuilding=true so promoteForRebuild
  // never flips the raw 'running' state to 'rebuilding'. Mutants
  // collapsing the disjunct to just the 'running' check passed all
  // tests because no test traversed the 'rebuilding' branch.
  //
  // Trigger: barrier.active=true AND barrier.reason='rebuild' makes
  // isPipelineRebuilding(barrier)=true, which makes promoteForRebuild
  // map 'running'→'rebuilding'. Combined with deepKnowledgeBuilding=true
  // (raw='running'), the safeState resolves to 'rebuilding' and the
  // IIFE hits its 'Re-embedding' branch via the second disjunct.
  it("Fixture F: deep_knowledge row in active rebuild renders 'Re-embedding' via the 'rebuilding' disjunct", () => {
    const rebuildingFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      deepEnrichmentPhase: 'running',
      deepCurrentStage: 'deep_knowledge',
      deepKnowledgeBuilding: true,
      barrier: { active: true, reason: 'rebuild' },
    };
    render(<GraphEnrichmentPipeline {...rebuildingFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).toHaveTextContent('Re-embedding');
    expect(row).toHaveAttribute('data-stage-state', 'rebuilding');
  });

  // FIXTURE G — downstream-position override coverage (PR-K).
  //
  // PR-J's final 1-of-27 mutation survivor was the stageId literal
  // `'deep_knowledge'` in the IIFE's i3SafeStageState call:
  //   const safeState = i3SafeStageState(
  //     promoteForRebuild(deepKnowledgeState),
  //     'deep_knowledge',  // <-- this literal; mutant changes to ""
  //     deepCurrentStage,
  //     deepEnrichmentPhase,
  //   );
  //
  // Survived because no fixture exercised the downstream-position
  // override path of i3SafeStageState — the path that actually USES
  // stageId via stagePositionInGroup(stageId). All other fixtures
  // either hit the `groupPhase === 'completed'` early-return (ignores
  // stageId), or returned `computedState` without entering the override
  // (also ignores stageId).
  //
  // To enter the override and exercise the stageId argument:
  //   - groupPhase NOT 'completed' (otherwise early-return fires)
  //   - groupCurrentStage SET (otherwise `if (!groupCurrentStage)`
  //     early-return fires)
  //   - computedState ∈ {complete, stale, warning} (otherwise the
  //     `computedState !== 'complete' && ...` short-circuit returns
  //     computedState unchanged)
  //   - stagePositionInGroup(stageId) > stagePositionInGroup
  //     (groupCurrentStage)  (so the override actually triggers)
  //
  // Recipe for raw computeDeepKnowledgeState='complete': ep present
  // with enriched_nodes>0 (not running), mod with module_count>0
  // (not running), deep with total_scored>0 (not running), AND
  // deepKnowledge.deep_chunks_embedded>0 (the fast-path on lines
  // 685-690 of GraphEnrichmentPipeline.tsx). All conditions in Fixture
  // G below. Then deepEnrichmentPhase='running' + deepCurrentStage=
  // 'enrichment' (position 0) puts deep_knowledge (position 4)
  // downstream → override fires → returns 'not_built'.
  //
  // The IIFE then sees safeState='not_built' and returns 'Not run'.
  // With the stageId mutant the override fails open (groupForStage('')
  // returns null → return computedState='complete') and the IIFE sees
  // safeState='complete' → returns `${chunks_embedded} chunks embedded`.
  // The text-content assertions distinguish the two behaviors.
  //
  // Closes PR-J's deferred Class-C survivor: 96.30% → 100% mutation
  // score on the deepKnowledgeStats IIFE scope.
  //
  // 'Not run' under groupPhase='running' is the CORRECT render — the
  // stage hasn't run YET in this rebuild cycle. This does not
  // contradict §9.3 #30 (which forbids 'Not run' under groupPhase=
  // 'completed' specifically).
  it("Fixture G: downstream-position override pins stageId literal — deep_knowledge row renders 'Not run' when downstream of running stage", () => {
    const downstreamFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      // Deep enrichment is running with current stage at enrichment
      // (position 0). deep_knowledge (position 4) is downstream.
      deepEnrichmentPhase: 'running',
      deepCurrentStage: 'enrichment',
      // Recipe for raw computeDeepKnowledgeState='complete' — the
      // upstream-stable fast-path on lines 685-690.
      epistemic: { enabled: true, enriched_nodes: 1240, avg_confidence: 0.84, running: false },
      modules: { enabled: true, module_count: 35, total_files_clustered: 1100, running: false },
      deepening: { running: false, total_scored: 500, settled_count: 250, settled_ratio: 0.50, avg_score: 0.5 },
      deepKnowledge: {
        enabled: true,
        running: false,
        chunks_embedded: 5000,
        deep_chunks_embedded: 120,
        last_run_at: '2026-06-23T10:00:00Z',
      },
      // No active rebuild — promoteForRebuild is a no-op on 'complete'.
      barrier: { active: false },
    };
    render(<GraphEnrichmentPipeline {...downstreamFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    // Correct stageId → override returns 'not_built' → IIFE returns 'Not run'
    expect(row).toHaveTextContent('Not run');
    // With the stageId mutant the IIFE's safeState would stay 'complete'
    // and the IIFE would return the chunks-embedded string instead.
    // Assert the FORBIDDEN-under-correct-behavior text is absent.
    expect(row).not.toHaveTextContent('chunks embedded');
  });

  // NEGATIVE CONTROL — proves the test responds to phase changes.
  //
  // Identical fixture but deepEnrichmentPhase='idle'. The race window
  // is NOT triggered: i3SafeStageState falls through to the raw state
  // because groupPhase is not 'completed', and the deepKnowledgeStats
  // IIFE returns 'Not run' because the raw deepKnowledgeState IS
  // legitimately 'not_built'. Without this control, the primary
  // assertion would pass even if i3SafeStageState were broken.
  //
  // PR-H/3 addenda (PRH-R1-004): also assert data-stage-state='not_built'
  // so a rename refactor of 'Not run' to 'Not built' produces a
  // self-documenting structural failure ('attribute is X' rather than
  // 'expected Not run, received Not built').
  it("negative control: phase='idle' — deep_knowledge row DOES render 'Not run' AND data-stage-state='not_built'", () => {
    const idleFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      deepEnrichmentPhase: 'idle',
    };
    render(<GraphEnrichmentPipeline {...idleFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).toHaveTextContent('Not run');
    expect(row).toHaveAttribute('data-stage-state', 'not_built');
  });

  // NEGATIVE CONTROL — exception list (PR-H/3 addenda — PRH-R1-003).
  //
  // freezeGreen.ts:171-173 explicitly states `cancelled` and `failed`
  // are NOT coerced — cancel-mid-stage and stage-failure leave a mix
  // of finished + unfinished rows that the per-stage compute fns model
  // correctly. Without these tests the documented exception list is
  // unenforced: mutating `if (groupPhase === 'completed')` to also
  // accept 'cancelled'/'failed' would pass the rest of the suite.
  it("exception list: phase='cancelled' is NOT coerced — deep_knowledge row renders 'Not run'", () => {
    const cancelledFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      deepEnrichmentPhase: 'cancelled',
    };
    render(<GraphEnrichmentPipeline {...cancelledFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).toHaveTextContent('Not run');
    expect(row).toHaveAttribute('data-stage-state', 'not_built');
  });

  it("exception list: phase='failed' is NOT coerced — deep_knowledge row renders 'Not run'", () => {
    const failedFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      deepEnrichmentPhase: 'failed',
    };
    render(<GraphEnrichmentPipeline {...failedFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).toHaveTextContent('Not run');
    expect(row).toHaveAttribute('data-stage-state', 'not_built');
  });

  // HYGIENE — render must not surface React errors / warnings.
  // PR-H/3 addenda (PRH-R1-002): dump any captured console calls to
  // stderr BEFORE the assertion so the developer can see WHAT was
  // logged when this assertion fails — the no-op mock otherwise
  // converts a debuggable runtime warning into an opaque AssertionError.
  it('renders without console.error or console.warn', () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    if (consoleError.mock.calls.length > 0) {
      process.stderr.write(
        'PR-H hygiene: unexpected console.error captured during render:\n' +
        JSON.stringify(consoleError.mock.calls, null, 2) + '\n',
      );
    }
    if (consoleWarn.mock.calls.length > 0) {
      process.stderr.write(
        'PR-H hygiene: unexpected console.warn captured during render:\n' +
        JSON.stringify(consoleWarn.mock.calls, null, 2) + '\n',
      );
    }
    expect(consoleError).not.toHaveBeenCalled();
    expect(consoleWarn).not.toHaveBeenCalled();
  });
});

// ───────────────────────────────────────────────────────────────
// structuralStats IIFE — PR-L behavioural pins
// ───────────────────────────────────────────────────────────────
//
// Stryker baseline on src/components/trace/GraphEnrichmentPipeline.tsx
// :1241-1257 (the structuralStats IIFE) reported 5.00% mutation
// score (2 killed / 23 survived / 15 no-cov) before PR-L — Fixture A
// only exercises one branch ('complete' with counts>0), and even
// then asserts absence not presence.
//
// PR-L adds per-branch fixtures so each return path is exercised
// and each return literal has a positive-presence assertion. Same
// methodology as PR-J / PR-K for deepKnowledgeStats.
//
// IIFE branches:
//   safeState === 'not_built' → 'Not run'
//   safeState === 'disabled'  → 'Disabled'
//   safeState === 'running' || 'rebuilding':
//     counts.nodes > 0 → `${nodes} nodes · ${edges} edges`
//     counts.nodes === 0 → 'Building...'
//   safeState === 'complete':
//     counts.nodes === 0 && downstream-flag → 'Completing...'
//     else → `${nodes} nodes · ${edges} edges`

describe('GraphEnrichmentPipeline — structuralStats IIFE (PR-L)', () => {
  let consoleError: ReturnType<typeof vi.spyOn>;
  let consoleWarn: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    consoleError.mockRestore();
    consoleWarn.mockRestore();
  });

  // PRESENCE — Fixture A's complete-path render (PR-L).
  // Pins the `${nodes.toLocaleString()} nodes · ${edges.toLocaleString()} edges`
  // template literal. Without this assertion mutants changing the
  // template to "" survive (the loop assertion at the §9.3 #30
  // describe only checks absence-of-Not-run + data-stage-state).
  it("Fixture A: structural row renders '1,240 nodes · 3,815 edges' under fastSyncPhase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-structural');
    // toLocaleString() puts the thousands separator in for en-US locale
    // (and most CI locales). If happy-dom defaults change locales this
    // could need adjustment.
    expect(row).toHaveTextContent('1,240 nodes');
    expect(row).toHaveTextContent('3,815 edges');
  });

  // FIXTURE S1 — Building... branch (running + counts=0).
  // trace.building=true makes computeTraceState return 'running'.
  // counts.nodes=0 routes the running branch to the 'Building...'
  // literal instead of the nodes·edges template.
  // Phase 'running' (not 'completed') so safeState stays 'running'.
  it("Fixture S1: structural row renders 'Building...' when trace.building=true and counts=0", () => {
    const buildingFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      trace: {
        enabled: true,
        exists: true,
        building: true,
        counts: { nodes: 0, edges: 0 },
        last_build_at: null,
      },
      fastSyncPhase: 'running',
      fastCurrentStage: 'structural',
    };
    render(<GraphEnrichmentPipeline {...buildingFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-structural');
    expect(row).toHaveTextContent('Building...');
    expect(row).toHaveAttribute('data-stage-state', 'running');
  });

  // FIXTURE S2 — running with counts (>0).
  // Same as Fixture S1 but with counts present. Pins the template
  // literal in the running branch separately from the complete-path
  // template (mutants in the two templates would otherwise both have
  // to be killed by Fixture A's assertion, but Fixture A's path is
  // 'complete' — the 'running' template is a distinct mutation site).
  it("Fixture S2: structural row renders 'nodes · edges' when trace.building=true and counts>0", () => {
    const runningWithCountsFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      trace: {
        enabled: true,
        exists: true,
        building: true,
        counts: { nodes: 500, edges: 1200 },
        last_build_at: null,
      },
      fastSyncPhase: 'running',
      fastCurrentStage: 'structural',
    };
    render(<GraphEnrichmentPipeline {...runningWithCountsFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-structural');
    expect(row).toHaveTextContent('500 nodes');
    expect(row).toHaveTextContent('1,200 edges');
    expect(row).toHaveAttribute('data-stage-state', 'running');
  });

  // FIXTURE S3 — 'Completing...' branch.
  // safeState='complete' (computeTraceState's forward-progression
  // heuristic returns 'complete' when a later stage is running),
  // counts.nodes=0, AND one of (inferredEdgesRunning | augmenting |
  // validating | fastKnowledgeBuilding) is true. Pins the
  // 'Completing...' literal and exercises ONE disjunct of the four-way
  // OR. (The other three disjuncts are deferred — see scope note.)
  it("Fixture S3: structural row renders 'Completing...' when complete + counts=0 + inferredEdgesRunning", () => {
    const completingFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      trace: {
        enabled: true,
        exists: true,
        building: false,
        counts: { nodes: 0, edges: 0 },
        last_build_at: null,
      },
      inferredEdgesRunning: true,
      fastSyncPhase: 'running',
      fastCurrentStage: 'inferred_edges',
    };
    render(<GraphEnrichmentPipeline {...completingFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-structural');
    expect(row).toHaveTextContent('Completing...');
    // safeState='complete' but stage is downstream of inferred_edges?
    // No — structural is upstream of inferred_edges, so the I3 override
    // doesn't fire and the badge stays 'complete'.
    expect(row).toHaveAttribute('data-stage-state', 'complete');
  });

  // FIXTURE S4 — 'Not run' branch.
  // raw='not_built' requires !trace.exists AND no forward-progression
  // flag AND !trace.building. Then computeTraceState falls through to
  // the `if (!trace.exists) return 'not_built';` branch.
  //
  // Gotcha: the component has a cold-start gate at line 1893
  // (traceNotBuilt) that renders the build-trace HERO instead of the
  // pipeline rows when trace.exists=false AND no rebuild/active flags.
  // We bypass with barrier.active=true (active rebuild), which the
  // gate treats as a sign the user has explicitly invoked work.
  // promoteForRebuild('not_built') === 'not_built' (the rebuilding
  // promotion only applies to 'running'/'queued'), so safeState stays
  // 'not_built' and the IIFE hits its 'Not run' branch.
  it("Fixture S4: structural row renders 'Not run' when trace.exists=false during active rebuild", () => {
    const notRunFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      trace: {
        enabled: true,
        exists: false,
        building: false,
        counts: { nodes: 0, edges: 0 },
        last_build_at: null,
      },
      fastSyncPhase: 'idle',
      fastCurrentStage: undefined,
      inferredEdgesRunning: false,
      augmenting: false,
      validating: false,
      fastKnowledgeBuilding: false,
      barrier: { active: true, reason: 'rebuild' },
    };
    render(<GraphEnrichmentPipeline {...notRunFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-structural');
    expect(row).toHaveTextContent('Not run');
    expect(row).toHaveAttribute('data-stage-state', 'not_built');
  });

  // FIXTURE S5 — 'Disabled' branch.
  // raw='disabled' requires !trace.exists && !trace.enabled.
  // computeTraceState's first check fires.
  // Same hero-gate bypass as S4 via barrier.active=true.
  it("Fixture S5: structural row renders 'Disabled' when !trace.exists && !trace.enabled during active rebuild", () => {
    const disabledFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      trace: {
        enabled: false,
        exists: false,
        building: false,
        counts: { nodes: 0, edges: 0 },
        last_build_at: null,
      },
      fastSyncPhase: 'idle',
      fastCurrentStage: undefined,
      barrier: { active: true, reason: 'rebuild' },
    };
    render(<GraphEnrichmentPipeline {...disabledFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-structural');
    expect(row).toHaveTextContent('Disabled');
    expect(row).toHaveAttribute('data-stage-state', 'disabled');
  });
});


// ───────────────────────────────────────────────────────────────
// validationStats IIFE — PR-N behavioural pins
// ───────────────────────────────────────────────────────────────
//
// Stryker baseline on src/components/trace/GraphEnrichmentPipeline.tsx
// :1321-1328 (the validationStats IIFE) reported 8.70% mutation
// score (2 killed / 19 survived / 2 no-coverage). The IIFE is small
// (4 branches) but completely untouched by the existing PR-H / PR-L
// behavioural pins — none of the literals / conditionals were tested.
//
// PR-N adds 5 per-branch fixtures + 1 Fixture A presence assertion.
// Same methodology as PR-J / PR-K / PR-L / PR-M.
//
// IIFE branches (lines 1321-1328):
//   safeState === 'running' || 'rebuilding' → 'Validating...'
//   safeState === 'disabled'                → 'Waiting for catalogue'
//   safeState === 'not_built'               → 'Not run'
//   default (typically safeState='complete') → '0 issues found'
//
// Note: computeValidationState never returns 'not_built' directly —
// the not_built branch is reachable only via i3SafeStageState's
// downstream-position override path (same shape as PR-M's CG).

describe('GraphEnrichmentPipeline — validationStats IIFE (PR-N)', () => {
  let consoleError: ReturnType<typeof vi.spyOn>;
  let consoleWarn: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    consoleError.mockRestore();
    consoleWarn.mockRestore();
  });

  // PRESENCE — Fixture A's default-fallthrough render.
  // phase30Fixture has augmentation=undefined; computeValidationState
  // returns 'disabled' for that input, but under fastSyncPhase=
  // 'completed' i3SafeStageState coerces 'disabled' → 'complete'.
  // safeState='complete' falls past all three IIFE guards and hits
  // the '0 issues found' default. Pins the literal at line 1327 —
  // without this, mutants on the default literal survive.
  it("Fixture A: validation row renders '0 issues found' under fastSyncPhase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-validation');
    expect(row).toHaveTextContent('0 issues found');
    expect(row).toHaveAttribute('data-stage-state', 'complete');
  });

  // FIXTURE V1 — running branch (safeState='running').
  // validating=true → computeValidationState returns 'running'.
  // Group phase 'running' (not 'completed') so i3SafeStageState's
  // early-coerce doesn't fire. Pins 'Validating...' literal + the
  // line-1324 running-disjunct ConditionalExpression / LogicalOperator
  // (||→&&) / EqualityOperator (===→!==) / StringLiteral ('running'→"")
  // mutants.
  it("Fixture V1: validation row renders 'Validating...' when validating=true with data-stage-state='running'", () => {
    const fixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      validating: true,
      fastSyncPhase: 'running',
      fastCurrentStage: 'validation',
    };
    render(<GraphEnrichmentPipeline {...fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-validation');
    expect(row).toHaveTextContent('Validating...');
    expect(row).toHaveAttribute('data-stage-state', 'running');
  });

  // FIXTURE V2 — rebuilding disjunct.
  // barrier.active=true + barrier.reason='rebuild' triggers
  // isPipelineRebuilding, which makes promoteForRebuild flip raw
  // 'running' → 'rebuilding'. Asserts text + data-stage-state=
  // 'rebuilding' to differentiate from V1's 'running' rendering.
  // Pins 'rebuilding' literal at line 1324:51 and the rebuilding-
  // disjunct ConditionalExpression mutant.
  it("Fixture V2: validation row renders 'Validating...' with data-stage-state='rebuilding' during active rebuild", () => {
    const fixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      validating: true,
      fastSyncPhase: 'running',
      fastCurrentStage: 'validation',
      barrier: { active: true, reason: 'rebuild' },
    };
    render(<GraphEnrichmentPipeline {...fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-validation');
    expect(row).toHaveTextContent('Validating...');
    expect(row).toHaveAttribute('data-stage-state', 'rebuilding');
  });

  // FIXTURE V3 — disabled branch.
  // augmentation=undefined + augmenting=false + validating=false +
  // fastKnowledgeBuilding=false routes computeValidationState to its
  // !aug 'disabled' early-return (line 512). Group phase 'running'
  // (not 'completed') so i3SafeStageState's early-coerce doesn't fire,
  // and 'disabled' isn't in the override-eligible set {complete, stale,
  // warning} so safeState stays 'disabled'. Pins 'Waiting for catalogue'
  // literal at line 1325 + the disabled-check ConditionalExpression /
  // EqualityOperator / StringLiteral mutants.
  it("Fixture V3: validation row renders 'Waiting for catalogue' when aug payload absent and group phase not completed", () => {
    const fixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      fastSyncPhase: 'running',
      fastCurrentStage: 'catalogue',
      augmenting: false,
      validating: false,
      fastKnowledgeBuilding: false,
      augmentation: undefined,
    };
    render(<GraphEnrichmentPipeline {...fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-validation');
    expect(row).toHaveTextContent('Waiting for catalogue');
    expect(row).toHaveAttribute('data-stage-state', 'disabled');
  });

  // FIXTURE V4 — not_built branch via downstream-position override.
  // computeValidationState NEVER returns 'not_built' directly — the
  // branch is reachable only via i3SafeStageState's override. Recipe:
  //   - raw='complete' via aug.validated_nodes>0 (previouslyValidated
  //     fast-path at line 509)
  //   - fastSyncPhase='running' (not 'completed' → no early-coerce)
  //   - fastCurrentStage='structural' (position 0, validation is
  //     position 3) → override fires → returns 'not_built'
  // Pins 'Not run' literal + not_built mutants on line 1326 AND the
  // 'validation' stageId StringLiteral mutant on line 1323:76
  // (with mutant stageId='', groupForStage('') returns null →
  // fail-open → returns computedState='complete' → IIFE renders
  // '0 issues found' instead of 'Not run').
  it("Fixture V4: validation row renders 'Not run' (not '0 issues') when downstream of running stage — pins stageId + not_built literals", () => {
    const fixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      fastSyncPhase: 'running',
      fastCurrentStage: 'structural',
      augmenting: false,
      validating: false,
      fastKnowledgeBuilding: false,
      augmentation: {
        enabled: true,
        total_nodes: 100,
        augmented_nodes: 100,
        validated_nodes: 100,
        avg_confidence: 0.93,
        low_confidence_count: 0,
        last_validate_at: '2026-06-23T10:00:00Z',
      },
    };
    render(<GraphEnrichmentPipeline {...fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-validation');
    expect(row).toHaveTextContent('Not run');
    expect(row).not.toHaveTextContent('0 issues found');
    expect(row).toHaveAttribute('data-stage-state', 'not_built');
  });
});

