# Research Brief — Role Lens as a Standalone Dashboard Panel

> **For another AI agent.** Research question: what is the right shape, interaction model, and data-wiring for a standalone Role Lens dashboard panel that complements (but does not duplicate) the existing Atlas panel?

## Why this matters

CoDRAG's anonymous-agent MCP contract serves each agent a role-weighted sub-atlas on every call. The human configures that role lens once through the UI and every agent using that role picks up the tuned lens automatically. Phase 104 shipped this as three bands inside one `AtlasLensPanel`: atlas status, sub-atlas tree, role lens. The user wants the **Role Lens band promoted to its own dashboard panel** so it can be docked independently and given its own vertical space.

This is not a cosmetic split. The role lens is where policy authoring happens — role picker, projection preview, applied-lens summary, budget slider, pinned-concepts chips. It will grow in Phase 105+ (per-role file-tree scope, full weight editors, registered-agent layering). The Atlas panel is where the codebase snapshot lives — freshness, segments, raw content. They are different jobs with different refresh cadences.

## What you are producing

A written design recommending **one of 3+ approaches** for splitting the Role Lens into its own panel. Include tradeoffs, a recommended option, and enough detail that an engineer can turn it into an implementation plan. Deliverable: a markdown doc in `docs/Phase104_SubAtlas/` (or a new sibling folder if the scope grows).

## Required reading (in order)

1. `docs/Phase104_SubAtlas/README.md` — the spec for Phase 104. Grounds you in the policy-authoring reframe, anonymous-agent contract, and why the lens exists.
2. `docs/Phase104_SubAtlas/IMPLEMENTATION_PLAN.md` — how Phase 104 landed.
3. `packages/ui/src/components/trace/AtlasLensPanel/` — all subcomponents. Specifically read `AtlasLensPanel.tsx`, `RoleLens.tsx`, `BudgetSlider.tsx`, `PinnedConceptsList.tsx`, `StatusStrip.tsx`, `SubAtlasTree.tsx`.
4. `src/codrag/dashboard/src/components/AtlasLensContainer.tsx` — current container that mounts hooks and renders the full panel.
5. `src/codrag/dashboard/src/hooks/useAtlasLens.ts` — atlas + role projection fetcher with 200ms role-switch debounce and AbortSignal cancellation.
6. `src/codrag/dashboard/src/hooks/useRoleOverrides.ts` — override CRUD with optimistic updates + rollback.
7. `packages/ui/src/config/panelRegistry.ts` — how other panels register. Atlas is id `'atlas'` (line ~203). Note the `minHeight`, `defaultHeight`, `category`, `closeable`, `resizable` contract.
8. `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` — how panel slots are composed. The `atlas:` slot currently returns `<AtlasLensContainer projectId={...} />`. You will add a new `role-lens:` slot alongside.

## Hard constraints

- Cannot re-fetch `/atlas` from two panels independently. Both panels opened at once must share one network fetch. The current hook mounts per-container; splitting naively double-fetches.
- Panel must live inside `@codrag/ui` (the component) + `src/codrag/dashboard/` (the container). No project-specific dependencies inside `@codrag/ui`.
- Must compose with the `panelRegistry` shape — id, title, icon, minHeight, defaultHeight, category, closeable, resizable, docsUrl.
- MCP integration is untouched. Anonymous agents consume `/atlas?role=X` directly; the UI is policy authoring only.
- The role lens already has write affordances (budget slider, unpin). Any split must preserve those flowing to `useRoleOverrides`.
- Must respond to project switch (AbortSignal pattern, see `useHydrationController.ts`).

## Open design questions — answer these

### Q1. Shared state strategy for the atlas fetch

Two panels both need the atlas response (Atlas panel needs status + segments; Role Lens needs the projection when a role is picked + applied_role + override). Four options:

- **Lift `useAtlasLens` to a project-level provider** (React context) owned by the dashboard's top-level container. Both panels subscribe. One network fetch, one shared state.
- **Keep per-panel hooks, memoize by project** via a module-level cache keyed on project_id + role. No context plumbing.
- **Split the hook** into `useAtlasBase(projectId)` (status + segments) and `useRoleProjection(projectId, role)` (role-specific). Atlas panel uses the first, Role Lens uses both.
- **Query-library approach** (React Query / SWR). CoDRAG does not use these today — would introduce a new dependency.

Recommend one with justification. Note what happens when only one panel is docked (no wasted fetches).

### Q2. Role state persistence

When the user picks a role in the Role Lens panel:
- Does that selection survive dashboard reload?
- Does it survive project switch?
- Is it per-project or global?

Current hook keeps role in local `useState`, so it resets on unmount. Options: persist to `localStorage`, persist to `settings_store` (per project), or stay ephemeral.

### Q3. Idle state when no role is picked

The panel could:
- Show a "Pick a role to preview the agent lens" empty state with a role picker front and center.
- Default to the last-used role (persisted per Q2).
- Default to a heuristic (CEO if no concepts are architectural, Engineering otherwise).
- Default to "engineering" flat.

Recommend the lightest-touch option.

### Q4. Compare-two-roles mode (future hook)

Longer term, "how does the engineering lens differ from the security lens?" is a real question for tuning. The panel could support side-by-side role preview. Should the initial design carve out space for this (layout) without implementing it, or should the initial panel stay single-role and extend later?

### Q5. Write affordances — stay or leave

Role Lens currently includes a budget slider and pin chips. Options:
- Keep them inline in the Role Lens panel (present direction).
- Move write affordances to a separate "Role Tuning" drawer that the panel opens.
- Make the panel pure observer and move tuning to a new panel.

Consider user-flow cost: how many clicks to go from "I see the agent is getting a bloated projection" to "I halved the budget"?

### Q6. Relationship to Agent Scope panel

The existing Agent Scope panel (`FolderTreePanel`) lets the user tune project-wide scope. Per-role scope is marked Phase 105 in the Phase 104 README. How should the Role Lens panel anticipate this — a disabled "Edit scope for this role" button? An adjacent "Role Scope" panel that reads the same role state?

### Q7. Minimum panel height

`AtlasLensPanel` today renders three stacked bands. Role Lens alone has: picker + preview + applied lens summary + pinned concepts + budget slider + optional error pill. What height do those need to avoid looking cramped?

### Q8. Panel category and icon

Atlas is in `category: 'status'`. Role Lens could be:
- Same (`status`)
- A new category (`agents` or `governance`)
- Part of an existing agent-oriented category

What category/icon fits the dashboard's existing taxonomy? (Read `panelRegistry.ts` fully before answering.)

## Non-goals

- Do not redesign the MCP anonymous-agent contract.
- Do not design Phase 105 per-role scope tree — only identify the seam for it.
- Do not add analytics/telemetry for role usage — tracked as a separate Phase 105 item.
- Do not touch the Python backend. All changes are UI + hook wiring.

## Deliverable structure

Recommend:

1. **Summary** (3-5 sentences) — the chosen approach and why.
2. **Panel architecture** — components, hooks, data flow diagram in text/ASCII.
3. **Answers to Q1–Q8** with justification.
4. **Component breakdown** — what moves to `@codrag/ui`, what stays in `src/codrag/dashboard/`, what new files, what deletions.
5. **Migration path** — how to roll out without breaking the current Atlas panel mid-flight.
6. **Open questions for humans** — anything you can't resolve.
7. **Sketched panelRegistry entry** — the exact id, title, minHeight, etc.

## Timebox + length target

~2 hours of research, ~1500-2500 words. If it balloons past that, flag it — probably indicates a design-scope problem that deserves decomposition.

## Success criteria

The human reading your design should be able to hand it to an engineer and get an implementation plan out of it without needing to re-investigate the codebase. The engineer should not have to guess which hook feeds which panel, where role state lives, or what happens when both panels are docked versus only one.
