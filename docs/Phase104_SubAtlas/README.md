# Phase 104 — Sub-Atlas & Role Lens Dashboard Panel

> The dashboard Atlas panel is a badge + three numbers + a collapsible blob. Meanwhile the backend already supports segmented atlases, role projection, agent scope, and 366 seed concepts — none of which the panel surfaces. Phase 104 rebuilds the panel as a **policy-authoring surface** for the role-weighted sub-atlases that agents consume anonymously over MCP.

## Core reframe

The Atlas panel is not a live-steering console for in-flight agent calls. It is a **role policy editor**.

Agents calling CoDRAG over MCP pass a `role` (or nothing) and receive whatever lens is currently saved for that role — layer weights, domain affinity, char budget, pinned concepts. The human was in the loop once, when they tuned the role. After that, every anonymous agent using that role benefits automatically until the lens is edited again.

Role is the stable identifier. Agent identity is optional (a registered agent in `codrag_data/agents/<id>.yaml` can layer its own lens on top of the role's, but this is not required).

This reframe resolves the apparent paradox of a "tweakable UI for anonymous agents": tweaking is persistent config, not real-time steering.

## Success criteria

- A human opening the Atlas panel can, in one view:
  1. See atlas freshness and the sub-atlas tree (segments).
  2. Pick a role and see the exact sub-atlas an agent with that role would receive right now.
  3. See the weights and budget that produced the projection.
  4. Adjust char budget and pinned concepts, save, and have the next MCP call pick up the change.
- The MVP panel surfaces features the backend already has (segments, role projection, concepts) without requiring any new atlas-generation logic.
- Per-role file-tree scope is scaffolded-for but **not built in this phase** — the current global Scope panel continues to own scope until Phase 105+.

## Scope

### In scope (v1, this phase)

- **Backend: augment existing atlas endpoints** to return segment metadata and applied role vector.
- **Backend: role-overrides store** — per-role `{max_chars, pinned_concept_ids}`, persisted in the existing settings.db table pattern (not a new JSON file; see Design Notes).
- **Backend: concept→role pin** — lightweight link from concepts to roles, consumed at projection time.
- **Frontend: `AtlasLensPanel`** — three-band layout (status strip / sub-atlas tree / role lens preview) replacing `AtlasStatusCard`.
- **Frontend: minimal writes** — char-budget slider per role, pin-concept-to-role action. Both go through the new role-overrides endpoint.
- **Storybook coverage** for the three bands across segmented/unsegmented × structural/LLM × override-present states.

### Explicitly out of scope (tracked as follow-on)

- Per-role file-tree scope editor (the global Scope panel stays global in this phase).
- Full weight sliders for `layer_weights`, `domain_affinity`, `centrality_weight`, `detail_level`. Surfaced read-only in v1.
- Registered-agent lens layering (agents register via `codrag_data/agents/<id>.yaml`; their own overrides are a separate phase).
- Automatic weight learning / telemetry-driven weight adjustment.
- Changes to `RoleVector` data model or `project_atlas_for_role()` signature.

## Design

### Panel structure

```
┌─────────────────────────────────────────────────────────────┐
│  Atlas Status Strip                                          │
│  [Fresh] 1,100 files · 8 modules · 4.2K chars · structural  │
│  Generated 2h ago · Model: structural · [Regenerate]        │
├─────────────────────────────────────────────────────────────┤
│  Sub-Atlas Tree (segments)                                  │
│  ▸ src/codrag/         47 files · 2.1K chars · Fresh        │
│  ▸ packages/ui/        291 files · 1.8K chars · Stale       │
│  ▸ websites/           73 files · 0.8K chars · Fresh        │
│  (click a segment to expand its rendered content)           │
├─────────────────────────────────────────────────────────────┤
│  Role Lens                                                  │
│  Role: [engineering ▾]  Budget: ═══════○═══  3.2K / 4K      │
│                                                              │
│  ┌─────────────────────┬─────────────────────────────────┐  │
│  │ Preview             │ Applied lens                    │  │
│  │ (rendered sub-atlas │ Layers: [bars]                  │  │
│  │  for this role)     │ Domain: [chips]                 │  │
│  │                     │ Centrality: 0.4                 │  │
│  │                     │ Detail: practitioner            │  │
│  │                     │ Pinned concepts: 2  [manage]    │  │
│  └─────────────────────┴─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data flow

1. Panel mounts → `useAtlasLens(projectId, role)` fetches `/projects/{id}/atlas` (segments + root).
2. User selects role → hook fetches `/projects/{id}/atlas?role=X` (returns projection + applied RoleVector + any override in effect).
3. User adjusts budget / pins a concept → `PUT /projects/{id}/role-overrides/{role}` → preview re-fetches.
4. Next MCP `codrag(role=X)` call reads the same override store → serves the new lens to the anonymous agent.

Cancellation and debouncing reuse the existing `useHydrationController` pattern so rapid role switches don't race.

### API contract changes

| Endpoint | Change |
|---|---|
| `GET /projects/{id}/atlas` | Add `segments: AtlasSegmentStatus[]` (already returned by regenerate; get endpoint omits it today). |
| `GET /projects/{id}/atlas?role=X` | Add `applied_role: RoleVectorPayload` — the effective RoleVector (built-in merged with override). |
| `GET /projects/{id}/role-overrides` | **New.** Returns all per-role overrides for the project. |
| `GET /projects/{id}/role-overrides/{role}` | **New.** Returns single role's override or `null`. |
| `PUT /projects/{id}/role-overrides/{role}` | **New.** Upserts `{max_chars?}`. Pins are managed via the separate pin endpoints below so optimistic UI updates don't have to rewrite the whole override. |
| `DELETE /projects/{id}/role-overrides/{role}` | **New.** Removes override AND all pinned concepts for the role. |
| `POST /projects/{id}/role-overrides/{role}/pin` | **New.** Body: `{concept_id: string}`. Role-rooted URL keeps the role-lens panel (the primary caller) self-contained. |
| `DELETE /projects/{id}/role-overrides/{role}/pin/{concept_id}` | **New.** Unpins a concept from the role. |

### Persistence

Role overrides and concept↔role pins live in **the existing project settings SQLite DB** (`codrag_data/codrag_settings.db`). The original plan called for two new tables; implementation found a cleaner path — reuse the existing `settings_store` namespaced key/value layer:

```
project/<pid>/role_overrides/<role_id>  → {max_chars, updated_at}
project/<pid>/role_pins/<role_id>       → {concept_id: pinned_at, ...}
```

This keeps the change at zero new schema, reuses the WAL-safe lifecycle (including the DELETE-mode fallback on USB drives), and lets project cleanup (`settings.project_clear(pid)`) sweep overrides automatically. Listing all overrides for a project is a namespace scan with a prefix filter.

**Known limitation (v1):** pin-map writes are read-modify-write. Two concurrent pin/unpin operations on the same role could lose a write. For a single human at the UI this never fires. If we ever drive pins from an automated loop, swap to a row-per-pin table or add an atomic-update helper to `settings_store`.

### Projection integration

`project_atlas_for_role()` gains an `overrides: Optional[RoleOverride]` parameter. When present:
- `max_chars` replaces `role.max_chars` before budget assembly.
- `pinned_concept_ids` are fetched and prepended to the projection output as a short "Pinned for this role:" section before the normal module/file listing.

Pinned concepts do **not** cause re-scoring of files — they're additive context, not a filter. This keeps the change surface small and avoids polluting the role-vector scoring math.

### Component structure

```
packages/ui/src/components/trace/
├── AtlasLensPanel.tsx           ← new top-level
├── AtlasLensPanel/
│   ├── StatusStrip.tsx
│   ├── SubAtlasTree.tsx
│   ├── RoleLens.tsx
│   ├── BudgetSlider.tsx
│   └── PinnedConceptsChip.tsx
└── AtlasStatusCard.tsx           ← deleted once stories migrate
```

New hook in `src/codrag/dashboard/src/hooks/`:
- `useAtlasLens(projectId, role)` — replaces today's direct atlas fetch in `useDashboardPanels.tsx`.
- `useRoleOverrides(projectId)` — caches the override map; invalidates on PUT/DELETE.

### Type additions (`packages/ui/src/types.ts`)

```ts
export interface AtlasSegmentStatus {
  segment_id: string;
  segment_name: string;
  dir_path: string;
  file_count: number;
  char_count: number;
  stale?: boolean;
}

export interface RoleVectorPayload {
  role_id: string;
  display_name: string;
  layer_weights: Record<string, number>;
  domain_affinity: string[];
  centrality_weight: number;
  detail_level: number;
  max_chars: number;
}

export interface RoleOverride {
  role_id: string;
  max_chars?: number;
  pinned_concept_ids?: string[];
  updated_at: string;
}

export interface AtlasStatus {
  // existing fields…
  segments?: AtlasSegmentStatus[];            // new
  role_atlas?: string;                         // existing
  role?: string;                                // existing
  applied_role?: RoleVectorPayload;            // new
  override?: RoleOverride | null;              // new
}
```

## Future work (explicit follow-ons, not this phase)

1. **Per-role file-tree scope** (Phase 105 candidate). Clone the global Scope panel into a per-role variant. Role lens gains an "Edit scope" button that opens a role-scoped file tree with in/out/boost toggles. Persistence extends `role_overrides` with a `scope_paths` payload.
2. **Full weight editing** — sliders for `layer_weights`, `domain_affinity` chips add/remove, `centrality_weight`, `detail_level`. UI is drafted in the read-only strip in v1; v2 makes it interactive.
3. **Registered-agent lens layering** — agents in `codrag_data/agents/<id>.yaml` get their own overrides layered on the role. Panel adds an "Agents using this role" section.
4. **Auto-promotion integration** — when a concept seed is promoted (Phase 103d F6), offer a "pin to matching role" shortcut based on the concept's domain tags.
5. **Projection telemetry** — log which roles/agents called which projections; feed into weight-tuning suggestions.

## Design notes / optimizations found while planning

- `GET /atlas` and `POST /atlas/regenerate` have drifted: regenerate returns `segments`, get does not. Extract a single response-builder helper and use it from both.
- `project_atlas_for_role()` currently has no override seam — adding the `overrides` parameter now, even with only `max_chars` and `pinned_concept_ids`, avoids a bigger refactor when v2 introduces weight overrides.
- Concept pins reuse the concepts store rather than a new "role favorites" table; this keeps the immune-system / concept-promotion flywheel (Phase 103d) pointing at one source of truth.
- Storybook is already used for `AtlasStatusCard`; replace rather than parallel-add so the design system doesn't accumulate dead components.

## Dogfooding notes captured during planning

- `codrag()` correctly surfaced role projection files (`role_projection.py`, `role_vectors.py`, `agent_scope.py`) as the anchors for this work.
- `codrag_search("agent_scope_manager persistence file paths per role", intent=EXPLAIN)` returned marketing pages because the user had scoped the index to `websites/` only at query time. **This is correct behavior**, not a retrieval miss. Worth surfacing in the UI that a search is scoped when scope is active, so the user doesn't have to remember they set a scope.

## Out of this phase's scope, but worth acknowledging

This panel shows *what an agent sees*. It does not yet show *how often each lens gets called*, *which agent called it last*, or *whether the projection produced a good answer*. Those are telemetry questions that should live in a separate "Role Telemetry" panel driven by MCP call logs. Tracked for post-104 roadmap.
