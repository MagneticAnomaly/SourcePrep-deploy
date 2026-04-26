import type { Meta, StoryObj } from '@storybook/react';

/**
 * Phase 119 — Old vs New SidebarPipelineQueue rendering.
 *
 * This file does NOT exercise the production component end-to-end (see the
 * sibling `src/stories/navigation/SidebarPipelineQueue.stories.tsx` for that).
 * It exists purely as a side-by-side visual comparison of the pre- and
 * post-Phase-119 node-summary rendering, so reviewers can see what the
 * scheduler-state pill replaces.
 *
 * - `OldNode` reproduces the pre-Phase-119 inline render verbatim:
 *     `in_flight / current_limit (max max_concurrent)`
 *   The `(max 1)` annotation is the visibly nonsensical part — it came from a
 *   saved-endpoint config where `cloud_concurrency` was never persisted and a
 *   fallback path used `1`.
 *
 * - `NewNode` reproduces the post-Phase-119 inline render verbatim:
 *     `in_flight / cap [state badge] (cap N if explicitly set below ceiling)`
 *   where `cap` is `discovered_ceiling` when locked, otherwise `current_limit`.
 *
 * The OLD rendering is intentionally inlined here — we do NOT restore old code
 * in the production component just to power a story. The two render functions
 * share the same prop shape so the same `nodes` map drives both panels.
 */

// ── Types ─────────────────────────────────────────────────────────

interface NodeSummary {
  max_concurrent: number;
  current_load: number;
  in_flight_requests: number;
  current_limit: number;
  // Phase 119 additions (optional on the wire)
  discovered_ceiling?: number | null;
  locked_until?: number | null;
  aimd_mode?: string | null;
  state?: 'probing' | 'locked' | 'backing_off' | 'recovering';
}

type NodesMap = Record<string, NodeSummary>;

// ── Old render (pre-Phase-119) ───────────────────────────────────

function OldNode({ nid, n }: { nid: string; n: NodeSummary }) {
  // Verbatim shape of the pre-Phase-119 line in SidebarPipelineQueue.tsx:
  //   {n.in_flight_requests} / {n.current_limit} (max {n.max_concurrent})
  return (
    <div className="flex items-center justify-between text-[10px] text-text-muted tabular-nums">
      <span className="truncate max-w-[140px]" title={nid}>{nid}</span>
      <span className="inline-flex items-center gap-1">
        {n.in_flight_requests} / {n.current_limit}
        <span className="ml-1 opacity-60">(max {n.max_concurrent})</span>
      </span>
    </div>
  );
}

// ── New render (post-Phase-119) ──────────────────────────────────

function NewNode({ nid, n }: { nid: string; n: NodeSummary }) {
  const ceiling = n.discovered_ceiling ?? null;
  const state = n.state ?? 'probing';
  const cap = ceiling != null && state === 'locked' ? ceiling : n.current_limit;
  const stateBadge = (() => {
    switch (state) {
      case 'locked': return { icon: '\u{1F512}', label: 'locked' };
      case 'backing_off': return { icon: '\u{1F53B}', label: 'backing off' };
      case 'recovering': return { icon: '↗', label: 'recovering' };
      case 'probing':
      default: return { icon: '\u{1F4C8}', label: 'probing' };
    }
  })();
  const userCap =
    n.max_concurrent > 1 && ceiling != null && n.max_concurrent < ceiling
      ? n.max_concurrent
      : null;
  return (
    <div className="flex items-center justify-between text-[10px] text-text-muted tabular-nums">
      <span className="truncate max-w-[140px]" title={nid}>{nid}</span>
      <span className="inline-flex items-center gap-1">
        {n.in_flight_requests} / {cap}
        <span title={stateBadge.label} aria-label={stateBadge.label} className="opacity-70">
          {stateBadge.icon}
        </span>
        {userCap != null && (
          <span className="ml-1 opacity-60">(cap {userCap})</span>
        )}
      </span>
    </div>
  );
}

// ── Side-by-side comparison panel ────────────────────────────────

interface ComparisonProps {
  nodes: NodesMap;
  caption?: string;
  oldNote?: string;
  newNote?: string;
}

function Comparison({ nodes, caption, oldNote, newNote }: ComparisonProps) {
  const entries = Object.entries(nodes);
  return (
    <div className="space-y-3">
      {caption && (
        <p className="text-xs text-text-muted italic max-w-[640px]">{caption}</p>
      )}
      <div className="grid grid-cols-2 gap-0 border border-border rounded-lg overflow-hidden">
        <div className="bg-surface p-3 border-r border-border">
          <h3 className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-2">
            Pre-Phase-119
          </h3>
          <div className="space-y-0.5">
            {entries.map(([nid, n]) => (
              <OldNode key={nid} nid={nid} n={n} />
            ))}
          </div>
          {oldNote && (
            <p className="mt-3 text-[10px] text-amber-500/80 leading-snug">
              {oldNote}
            </p>
          )}
        </div>
        <div className="bg-surface p-3">
          <h3 className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-2">
            Post-Phase-119
          </h3>
          <div className="space-y-0.5">
            {entries.map(([nid, n]) => (
              <NewNode key={nid} nid={nid} n={n} />
            ))}
          </div>
          {newNote && (
            <p className="mt-3 text-[10px] text-emerald-500/80 leading-snug">
              {newNote}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Storybook meta ───────────────────────────────────────────────

const meta: Meta<typeof Comparison> = {
  title: 'Phase 119 / Old vs New SidebarPipelineQueue',
  component: Comparison,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'Side-by-side visual comparison of the pre- and post-Phase-119 node-summary rendering in SidebarPipelineQueue. The OLD rendering is reconstructed inline in the story file — production code is not regressed.',
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof Comparison>;

// ── Stories ──────────────────────────────────────────────────────

export const RandomWalkBug: Story = {
  name: 'Random-walk bug (probing)',
  args: {
    caption:
      'Pre-Phase-119: the limit walked from 53 to 67+ over ~75 min via idle recovery, with no backoff observed. The (max 1) annotation came from an unconfigured cloud_concurrency setting and was visibly nonsensical against current_limit=58. Post-Phase-119: a single primary number with a probing badge — no misleading max annotation.',
    oldNote:
      'The (max 1) annotation contradicts current_limit=58 and gives the user no signal about whether the scheduler is probing or steady.',
    newNote:
      'The probing badge tells the user growth is still happening; the cap reflects the current AIMD operating point.',
    nodes: {
      'cloud:default_ollama': {
        max_concurrent: 1,
        current_load: 1,
        in_flight_requests: 2,
        current_limit: 58,
      },
    },
  },
};

export const LockedCeiling: Story = {
  name: 'Locked ceiling (post-edge)',
  args: {
    caption:
      'After the first MD edge, Phase 119 persists the discovered ceiling with a 24h TTL. The OLD render had no way to express "we backed off here, hold this number" — it just showed the raw current_limit. The NEW render shows a lock icon with the ceiling as the denominator.',
    oldNote:
      'No signal that the scheduler has converged on a stable ceiling — looks identical to the still-probing case.',
    newNote:
      'Lock badge (\u{1F512}) signals the discovered_ceiling is held; idle recovery cannot push it higher until the TTL expires.',
    nodes: {
      'cloud:default_ollama': {
        max_concurrent: 1,
        current_load: 1,
        in_flight_requests: 2,
        current_limit: 51,
        discovered_ceiling: 51,
        locked_until: Date.now() / 1000 + 86400,
        aimd_mode: 'congestion_avoidance',
        state: 'locked',
      },
    },
  },
};

export const BackingOff: Story = {
  name: 'Backing off (MD just fired)',
  args: {
    caption:
      'Pre-Phase-119: a transient timeout collapsed 67 → 3, but the UI showed only the new low number with no indication that a backoff had just happened. Post-Phase-119: the backing-off badge surfaces the MD event for the cooldown window.',
    oldNote:
      'The number drops from 67 to 3 with no visible reason — looks like the scheduler just lost capacity for no reason.',
    newNote:
      'Backing-off badge (\u{1F53B}) makes the MD event visible; the user knows growth is paused while the cooldown runs.',
    nodes: {
      'cloud:default_ollama': {
        max_concurrent: 1,
        current_load: 1,
        in_flight_requests: 1,
        current_limit: 6,
        discovered_ceiling: 12,
        locked_until: Date.now() / 1000 + 86400,
        aimd_mode: 'congestion_avoidance',
        state: 'backing_off',
      },
    },
  },
};
