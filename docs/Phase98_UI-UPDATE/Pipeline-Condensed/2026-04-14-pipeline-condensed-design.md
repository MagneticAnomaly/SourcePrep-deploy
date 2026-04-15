---
phase: 98
topic: Pipeline-Condensed
status: approved-for-planning
owner: Eric Bintner
date: 2026-04-14
target_file: packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx
---

# Pipeline Condensed — Design Spec

## Goal

Add a per-group collapse/expand control to the Graph Enrichment Pipeline panel so the 15 stages can be viewed either as today (expanded, all stages visible) or as three condensed summary rows — one per existing group. The current expanded UI remains **100% intact**. Collapse only adds a new render branch; it does not rewrite the existing one.

## Non-Goals

- No changes to stage ordering, naming, icons, or the stage data model.
- No changes to the 3-group partitioning (Fast Sync / Deep Enrichment / Finalize). Groups and their 5-stage membership remain hard-coded as they are today.
- No changes to the SSE wiring, reducer, orchestrator endpoints, or `useEnrichment` hook's public shape.
- No new collapsible primitive in `packages/ui`. One-off inline implementation.
- No animation polish required for v1 (a simple `max-height` CSS transition is acceptable but optional).

## Scope (single file)

Primary change: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`.

Supporting changes:

- `codrag_data/ui_config.json` schema gains three boolean keys (see Persistence below). Dashboard config-read and config-write call sites consume them.
- Unit test file for the roll-up function (new, colocated with the component or under an existing test folder — follow whatever convention the file currently uses).

No changes anywhere else in the dashboard or backend pipeline.

## Condensed Row — Visual Contract

When a group is collapsed, the five `StageRow` renders are replaced by a single row with this left-to-right layout:

```
[chevron ▸]  [state icon]  Group Label         [progress bar]     [group action btn]
                           stats line
```

Element responsibilities:

| Element | Source |
|---|---|
| Chevron | New. Toggles `collapsed` for this group only. |
| State icon + color | Output of the roll-up function (see below). Uses same lucide icons the existing `StageRow` already uses for each state. |
| Group label | Unchanged literal: "Fast Sync", "Deep Enrichment", "Finalize". |
| Stats line | One-line summary string derived from roll-up: `"5 stages · idle"`, `"running stage 3 of 5"`, `"complete · 2h ago"`, `"mixed — expand to inspect"` (orange case), etc. |
| Progress bar | The same progress-bar element used by the existing `StageRow`. Shown only when rolled-up state is `running`; fed the average `progress` of the five stages. Hidden otherwise. |
| Group action button | The existing group-level pause / resume / run button, moved/rendered into this row unchanged. Click handler is the same. |

When a group is expanded, render today's layout exactly as-is, with the chevron prepended to the existing group header. No other expanded-mode changes.

## Roll-up Function

Pure function. Input: array of five `EnrichmentStage` objects. Output:

```ts
type GroupRollup = {
  state: 'complete' | 'disabled' | 'idle' | 'running' | 'error' | 'mixed'
  progress: number | undefined   // 0-100, only when state === 'running'
  stats: string                  // one-line human summary
}
```

Rules, evaluated in order (first match wins):

1. All five `state === 'complete'` → `{ state: 'complete', progress: undefined, stats: "complete · <relative time of oldest provenance>" }`
2. All five `state === 'disabled'` → `{ state: 'disabled', progress: undefined, stats: "disabled" }`
3. All five in `{waiting, queued}` (and not already `complete`) → `{ state: 'idle', progress: undefined, stats: "5 stages · idle" }`
4. Any `state === 'running'` AND no `state === 'error'` → `{ state: 'running', progress: avgRunningProgress, stats: "running stage <n> of 5" }`
5. Any `state === 'error'` → `{ state: 'error', progress: undefined, stats: "error — expand to inspect" }`
6. Otherwise → `{ state: 'mixed', progress: undefined, stats: "mixed — expand to inspect" }` (rendered with the orange warning color)

Note: **mixed should be rare in healthy runs.** The orange warning is an escape hatch for the long tail; operational users are expected to expand to investigate rather than read a packed condensed row.

## Persistence

Three new booleans in `codrag_data/ui_config.json`:

- `pipeline_group_fast_collapsed`
- `pipeline_group_deep_collapsed`
- `pipeline_group_finalize_collapsed`

All three default to `true` — first load shows three condensed rows.

Persistence uses the same read/write path the dashboard already uses for other `ui_config.json` preferences (no new endpoint). Toggling the chevron updates component state optimistically and PATCHes the config asynchronously; a failed PATCH logs and does not roll back local state (acceptable for a purely cosmetic preference).

## Interaction Rules

- Chevron click → toggle collapse for that group only.
- Group action button (pause / resume / run) → same behavior as today; does not toggle collapse even though it lives in the condensed row.
- In condensed mode there is no way to target an individual stage (pause a single stage, rerun one). That is intentional and matches the "simple aggregate" choice — users who need stage-level control expand the group.
- The existing Phase-49 "Details" provenance toggle is unaffected. It only influences expanded mode.

## Testing

Required:

1. **Unit tests for the roll-up function.** One test per rule above, plus an explicit test for the "4 complete + 1 running" mixed-ish case (should resolve to `running`, not `mixed`, per rule 4). Include an all-error and an all-stale case.
2. **Component test — default collapsed.** Render `GraphEnrichmentPipeline` with fresh config → asserts three condensed rows visible, no `StageRow` components mounted.
3. **Component test — expand preserves functionality.** Simulate chevron click on one group → expanded rows visible, stage-level pause button clickable and fires the same handler as before.
4. **Component test — group action button in condensed mode.** Click the group pause/run button while collapsed → correct handler fires, collapse state unchanged.
5. **Manual smoke test on running dashboard.** Verify default-collapsed on first load, expand/collapse each group, refresh page → collapse state persists. Verify with a real pipeline run that the rolled-up progress bar moves.

## Stability Constraints (from the user)

> "This pipeline is a little unstable still so triple check and theoretically reverse-engineer each plan before implementation."

Carried into the implementation plan:

- Every task in the implementation plan must include a **reverse-engineering note**: given the proposed change, what upstream or downstream behavior could it break? Cite the lines it touches and the lines that read what it touches.
- Prefer additive edits (new render branch, new state) over modifications to existing render paths. Do not refactor or "clean up" adjacent code during this work.
- Before editing `GraphEnrichmentPipeline.tsx`, run `codrag_impact` on it to confirm the blast radius is limited to the dashboard.
- Do not touch `useEnrichment.ts`, the reducer, or the orchestrator client in this phase. If the plan ever proposes such a change, treat it as a scope violation and stop.
- Run `ruff`/`mypy`/frontend lint before committing — even though this is a TS-only change, the full check ensures nothing adjacent is broken.
- Manual smoke on a live pipeline run is mandatory before declaring complete.

## Out of Scope / Deferred

- Per-stage collapse-within-a-group.
- Persisting an "all collapsed" / "all expanded" master toggle.
- Animations beyond a basic `max-height` transition.
- Keyboard shortcuts for collapse/expand.
- A shared `<Collapsible>` primitive in `packages/ui`.

## Open Risks

- **Mixed-state corner cases.** If the roll-up function misclassifies a common real-world mix, users will see orange warnings constantly and lose trust. Mitigation: rule 4 (any running wins over mixed) is the main release valve; add more named rules only after the condensed view has been used with real pipeline runs.
- **Progress averaging.** Averaging the five stage progresses can look jumpy if one stage jumps from 0 → 100 quickly. Acceptable for v1 because the progress bar is a secondary signal; the state icon carries the primary state.
- **Config write latency.** A slow PATCH to `ui_config.json` could make the toggle feel laggy if we wait for the round trip. Mitigation: optimistic local update, PATCH in background.
