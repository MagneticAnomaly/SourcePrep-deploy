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
