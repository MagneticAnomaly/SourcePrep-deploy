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
 * / source-inspection. See vitest.config.ts and vitest.setup.ts.
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

// ── Fixture: §9.3 #30 starting condition ───────────────────────
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
  it("Deep Knowledge Embedding row does NOT render 'Not run' when deepEnrichmentPhase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).not.toHaveTextContent('Not run');
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
  // PR-G addenda was the 15th-and-final fix (group_reasoning). This asserts
  // the pattern holds for every deep stage, not just deep_knowledge.
  it("all 5 deep_enrichment stage rows do NOT render 'Not run' under phase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    for (const id of DEEP_ENRICHMENT_STAGE_IDS) {
      const row = screen.getByTestId(`pipeline-stage-row-${id}`);
      expect(row, `deep_enrichment stage '${id}' regressed to 'Not run' under phase='completed'`)
        .not.toHaveTextContent('Not run');
    }
  });

  // GROUP — same contract for fast_sync (fastSyncPhase='completed' must
  // coerce every fast stage too; PR-D shipped the pattern for all 5).
  it("all 5 fast_sync stage rows do NOT render 'Not run' under phase='completed'", () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    for (const id of FAST_SYNC_STAGE_IDS) {
      const row = screen.getByTestId(`pipeline-stage-row-${id}`);
      expect(row, `fast_sync stage '${id}' regressed to 'Not run' under phase='completed'`)
        .not.toHaveTextContent('Not run');
    }
  });

  // NEGATIVE CONTROL — proves the test responds to phase changes.
  //
  // Identical fixture but deepEnrichmentPhase='idle'. The race window
  // is NOT triggered: i3SafeStageState falls through to the raw state
  // because groupPhase is not 'completed', and the deepKnowledgeStats
  // IIFE returns 'Not run' because the raw deepKnowledgeState IS
  // legitimately 'not_built' (the deep_knowledge data payload hasn't
  // been written). Without this control, the primary assertion would
  // pass even if i3SafeStageState were broken — because 'Not run'
  // never appears under any state — and would not pin behaviour.
  //
  // This control is intentionally coupled to the literal string 'Not
  // run' as part of the contract being pinned. If a future refactor
  // renames 'Not run' to something else, this assertion will need
  // updating alongside the corresponding structural pin in
  // statsSafeState.test.ts (which also greps the literal string).
  // That coupling is consistent across the test suite, not new.
  it("Deep Knowledge Embedding row DOES render 'Not run' when deepEnrichmentPhase='idle' (control)", () => {
    const idleFixture: GraphEnrichmentPipelineProps = {
      ...phase30Fixture,
      deepEnrichmentPhase: 'idle',
    };
    render(<GraphEnrichmentPipeline {...idleFixture} />);
    const row = screen.getByTestId('pipeline-stage-row-deep_knowledge');
    expect(row).toHaveTextContent('Not run');
  });

  // HYGIENE — render must not surface React errors / warnings.
  // Catches missing-key warnings, prop-type warnings, hydration
  // errors that would indicate the fixture is incomplete in a way
  // that could mask the real regression.
  it('renders without console.error or console.warn', () => {
    render(<GraphEnrichmentPipeline {...phase30Fixture} />);
    expect(consoleError).not.toHaveBeenCalled();
    expect(consoleWarn).not.toHaveBeenCalled();
  });
});
