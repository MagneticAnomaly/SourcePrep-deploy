# Phase 120 — Named Scopes

> A project-wide RAG primitive: any agent or human can ask Prep for the
> `marketing` scope, the `data-cleaning` scope, the `global` scope, etc.,
> and get retrieval bounded to the files they care about — without
> touching the trace graph, role projection, or the build pipeline.

## Motivation

Today the dashboard's **Scope** panel (`FolderTreePanel`, Phase 24) edits one
project-wide file list — `project.config.included_paths` — that defines what
gets embedded into the RAG index. Phase 67 added a parallel concept,
**Agent Knowledge Scopes** (`AgentScopePanel`, `agent_scope_manager`,
`/projects/{id}/agent-scope/{role}/*`), which let the user keep per-role
file lists. Phase 67 was an incomplete first attempt at the feature this
phase finishes:

- Per-role lists were keyed to a role string, but role and file-tree
  scoping are orthogonal axes — role *projects* the trace graph
  (centrality + layer + domain weights), file-tree scope *masks* RAG
  retrieval. There is no architectural reason a file mask must be keyed
  to a role.
- The Phase 67 panel was framed as "Agent Knowledge Scopes" with a role
  dropdown rather than as a universal "switch which file tree is active"
  affordance, so it stayed Paperclip-flavored and never replaced the
  global Scope panel for everyday use.
- Without a way to ask for a non-global scope **per request**, agents
  default to the global RAG every time even when the question is
  obviously about, say, marketing copy or a self-contained data-cleaning
  subdirectory.

This phase universalizes the file-tree axis: any user-defined scope can
be selected from the existing Scope panel via a dropdown and addressed
by name from MCP (`prep(scope="marketing")`). The Phase 67 panel and
manager are deleted; one panel, one concept, one store.

## Core architecture

Three independent axes, none of which interact except by composition at
query time:

| Axis | Owns | Touched by this phase |
|---|---|---|
| **Trace graph** (Phase 04+) | Single project-wide AST/import graph from `include_globs`/`exclude_globs`. | No. |
| **Role projection** (Phase 64A+) | `RoleVector` lens that re-weights and budgets the trace-graph view. | No. |
| **Named scope** (this phase) | Disjoint named lists of file paths used as a retrieval mask. | Yes. |

Locking the boundary: scopes never touch the trace graph or role
projection. Role projection never reads scope membership. The
embedding pipeline does not know about scopes — it embeds the union of
files referenced by any scope (deduped, exactly as today's incremental
embedder already does for `included_paths`).

### Default scope is virtual

`global` is not a stored record. It is a view onto today's
`project.config.included_paths` (the existing global Knowledge Sources).
All read/write paths for `global` proxy to the existing Phase 24
mutation pattern: an atomic `_get_registry().mutate_config(...)` RMW
on `included_paths`, followed by `scope_orchestrator.on_files_added`
or `on_files_removed` to trigger the debounced rebuild.

### Disjointness

Named scopes are not subsets or supersets of `global`. Asking for the
`marketing` scope returns retrieval over `marketing` files only —
results from `global` are not blended in. If a path is needed in
multiple scopes the user lists it in each; embeddings are deduped at
the file level because index membership is the deduped union.

Excluded paths (`project.config.excluded_paths`) and path weights
(`project.config.path_weights`) remain global-only in v1. A non-global
scope cannot define its own excludes or weights.

### Index-membership integration (the wiring this phase adds)

**Today, the build pipeline reads only `project.config.included_paths`**
to decide what to embed. Five sites:
`pipeline/post_flight.py:91`, `pipeline/post_flight.py:153`,
`pipeline/post_flight.py:202`, `pipeline/workers.py:896`, and
`routers/scope.py:42` (the `_build_fn` registered with the scope
orchestrator). Per-role file lists from Phase 67 were stored but
*never* fed back into the embedder — `agent_scope_manager.get_merged_rag_scope`
exists for that purpose but has zero callers in the codebase. That is
why a Phase 67 scope listing files outside `included_paths` would
silently fail to embed them.

This phase wires the union explicitly:

- New helper `prep.services.project_helpers.compute_index_membership(project_id) → Set[str]`
  returns `set(included_paths) ∪ ⋃(scope.paths for scope in scopes)`.
- The five sites above are updated to call `compute_index_membership(project_id)`
  in place of `pcfg.get("included_paths")`. Each site already accepts
  a `Set[str]` or `List[str]` for inclusion; the call signature into
  `build_manager.start_project_build(included_paths=…)` is unchanged
  (the parameter name stays — only the source of truth shifts).
- `included_paths` remains the user's *global* pick (what they
  toggle in the global Scope panel). Named scopes live in
  `scope.<id>.paths`. Neither field is derived from the other.
- The build pipeline thus embeds the deduped union; search-time
  masking (`scope_resolver.resolve_mask`) selects which subset of
  that union is visible to a request.

### Add/remove/delete semantics

- **Add path to global scope:** mutates `included_paths`, calls
  `scope_orchestrator.on_files_added` — same as Phase 24 today.
  Triggers debounced incremental embed.
- **Add path to named scope:** mutates `scope.<id>.paths`. If the
  path was not already in `compute_index_membership(project_id)`
  before the add, the scope router calls
  `scope_orchestrator.on_files_added(project_id, [new_paths])` to
  schedule the incremental embed. If it was already in the union
  (e.g. global covers it), no rebuild is triggered.
- **Remove path from named scope:** mutates `scope.<id>.paths`. If
  the path is no longer in `compute_index_membership(project_id)`
  after the remove, the router calls
  `scope_orchestrator.on_files_removed` so embeddings GC. Otherwise
  no-op for the build pipeline.
- **Delete a named scope:** equivalent to removing all its paths.
- **Delete `global`:** rejected (400).

A full rebuild is never required, but adding paths to any scope can
trigger an incremental embed — exactly the same cost model as today's
global Scope panel.

## Data model

### Scope record

Stored per-project in the existing `settings_store` (the WAL-aware
SQLite key/value layer Phase 104 chose for role overrides — DELETE-mode
fallback already handled, project cleanup already sweeps the
namespace):

```
project/<pid>/scope/<scope_id>  →
{
  "id": "marketing",
  "display_name": "Marketing",
  "paths": ["websites/marketing/", "docs/MARKETING_MASTER_TODO.md"],
  "weights": {},                    // reserved for v1.1 — see Deferred
  "assigned_to_role": "copywriter", // optional, see Resolution rules
  "created_at": "2026-04-27T10:00:00Z",
  "updated_at": "2026-04-27T10:00:00Z"
}
```

`scope_id` is a slug (`[a-z0-9_]+`) derived from `display_name` on
create; collisions auto-suffix (`marketing_2`). `id == "global"` is
reserved.

Listing all scopes for a project is a namespace prefix scan
(`project/<pid>/scope/`) plus a synthetic `global` record built from
`project.config.included_paths`.

### Why no migration of Phase 67 data

This codebase has no external installs to preserve. Phase 67's
`agent_scope.<role>` keys, the `agent_scope_manager`, the
`/agent-scope/*` router, and `AgentScopePanel.tsx` are deleted in this
phase. Any orphaned `agent_scope.<role>` keys left in a developer's
local settings DB are inert — no code reads them after this phase. An
optional one-line cleanup pass at scope-router boot can sweep them; not
required for correctness.

## HTTP API

New router at `/projects/{id}/scopes` (note plural — distinct from the
existing Phase 24 `/projects/{id}/scope/*` endpoints, which keep
working unchanged for backwards-compat with the old global-only Scope
panel and stay as a thin facade over the same `included_paths` store).

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/projects/{id}/scopes` | List all scopes including the synthetic `global`. Each entry: `{id, display_name, path_count, assigned_to_role}`. |
| `POST` | `/projects/{id}/scopes` | Create a scope. Body: `{display_name, paths?, assigned_to_role?}`. Returns the new record. 409 on slug collision after auto-suffix exhaustion. |
| `GET` | `/projects/{id}/scopes/{scope_id}` | Read one. For `global`, returns a synthesized record reading from `included_paths`. |
| `PUT` | `/projects/{id}/scopes/{scope_id}` | Update `display_name` and/or `assigned_to_role`. Path edits go through the add/remove endpoints. |
| `POST` | `/projects/{id}/scopes/{scope_id}/add` | Add paths. Body: `{paths: string[]}`. Idempotent; descendants of an added prefix are pruned to keep the path list minimal. |
| `POST` | `/projects/{id}/scopes/{scope_id}/remove` | Remove paths. |
| `DELETE` | `/projects/{id}/scopes/{scope_id}` | Delete. Returns 400 for `scope_id == "global"`. |

For `global`, the add/remove endpoints reuse the Phase 24 mutation
pattern (atomic `mutate_config` RMW on `included_paths`, then
`scope_orchestrator.on_files_added/removed` to trigger debounced
rebuild). To prevent drift between Phase 24's `/scope/*` endpoints and
this phase's `/scopes/global/*` endpoints, both share a new helper:

```
services/project_helpers.py
  mutate_global_scope(project_id, action: "add"|"remove", paths: List[str])
```

`/scope/add`, `/scope/remove`, `/scopes/global/add`, and
`/scopes/global/remove` all call into this helper. One mutator, two
URL surfaces.

## MCP signature & resolution

Two orthogonal optional parameters added to relevant MCP tools:

```
prep(role?: str, scope?: str, project_id?: str)
prep_search(query, role?: str, scope?: str, intent?: str, ...)
prep_impact(file_path, scope?: str, ...)
prep_concepts(scope?: str, action?: str, ...)
prep_observe(scope?: str, action?: str, ...)
```

**`prep_audit` is intentionally excluded from v1.** Its existing
`scope` parameter already means "limit the structural scan to this
file or directory path" (`mcp/server.py:1940`,
`mcp_tools.py` audit schema). The semantics overlap but are not
identical, and conflating them in v1 risks regressions in the audit
flow. A future phase can teach `prep_audit(scope=…)` to resolve a
named scope first and fall back to literal-path filtering.

**Phase 67 description cleanup.** The current `role` parameter
description on `prep_search` ("results are filtered to only include
files in the agent's configured scope", `mcp_tools.py` around line
129) advertises the auto-mask behavior that this phase removes. The
description must be rewritten to: *"Optional role for trace-graph
projection (centrality + layer + domain weights). Does not filter
files. Use `scope=` to limit retrieval to a named file scope."*

`role` continues to drive trace-graph projection via `RoleVector`
(unchanged from today). `scope` selects the file-mask used at query
time. They compose freely; either, both, or neither may be omitted.

### Resolution rules at request time

1. If `scope=X` is passed and `scope.<X>` exists → mask = that scope's
   `paths`. End.
2. Else if `scope=X` is passed but no such scope exists → mask = global
   (i.e. fall through to step 4); response carries
   `applied_scope: "global"` plus
   `scope_warning: "requested 'X' not found, used global"`.
3. Else if `role=Y` is passed AND a stored scope has
   `assigned_to_role == Y` → mask = that scope's `paths`. (Convenience
   carry-over: lets a Paperclip-style assignment keep working without
   the agent passing `scope=` explicitly.)
4. Else → mask = global (no per-scope filtering; full RAG over
   `included_paths`).

`role` always drives projection regardless of which branch fires. The
`role` parameter never auto-applies a file mask in v1 except via
explicit `assigned_to_role` linkage in step 3 — this is the clean
break from Phase 67's role-keyed mask lookup.

### Response envelope

All MCP tool results gain two fields:

```json
{
  "results": [...],
  "applied_scope": "marketing",   // always a string; "global" when no/unknown scope
  "applied_role":  "copywriter",  // null when no role passed
  "scope_warning": "requested 'marketin' not found, used global"  // optional
}
```

### Ambient `prep()` call

When `scope=X` is passed without a query, the atlas/segment selection
returned in the orientation payload is filtered to segments whose
`dir_path` overlaps the scope's paths. Module summaries and hub-file
lists from outside the scope are dropped. This makes
`prep(scope="marketing")` a real "give me marketing-flavored
orientation" call without changing the atlas generator.

### AGENTS.md generation

`_build_managed_content()` in `src/prep/core/rules_generator.py`
learns to render a "Scopes" sub-section listing the project's named
scopes plus a one-line hint:

> Pass `scope=<name>` to limit retrieval to that surface. Scopes:
> `global`, `marketing`, `data-cleaning`.

This way every IDE that picks up the auto-generated rules file shows
the available scopes without per-IDE doc edits.

### Multi-scope (deferred — see below)

The HTTP and MCP layers will accept `scope: str | str[]` at the
schema level. v1 only honors the singleton form; passing an array
returns `400 NOT_IMPLEMENTED`. The mask-resolver consumes a
`Set[str]` of paths internally, so flipping multi-scope on later is a
union at one resolver function — no API break.

## UI

`FolderTreePanel` (the panel titled "Scope") absorbs the entire
feature. `AgentScopePanel.tsx`, its dashboard slot, its stories, and
its dependent endpoints are deleted in this phase.

### Header

```
┌─ Scope ─────────────────────────────────────────────────┐
│  [global ▾]  [+]                                  Edit  │
├──────────────────────────────────────────────────────────┤
│  ▸ src/                                                  │
│  ▸ packages/                                             │
│  …                                                       │
└──────────────────────────────────────────────────────────┘
```

- **Dropdown** lists every scope: `global (1,247)`, `marketing (12)`,
  `data-cleaning (34)`. File counts ride inline in the dropdown rows;
  no aggregate count or freshness badge in the header (per-row dots in
  the tree below already carry inclusion/pending state).
- **`+` button** opens an inline name input
  (`Name: [_____] [Create]`); on confirm creates an empty scope and
  switches to it.
- **Edit** popover (visible only when a non-global scope is active):
  rename + delete. Delete prompts for confirmation. `global` shows
  no Edit affordance; it is fixed-name and undeletable.

### Tree

Same `FolderTree` component as today. Behavior depends on active
scope:

| Affordance | `global` | Named scope |
|---|---|---|
| Toggle include | yes | yes |
| Toggle exclude | yes | disabled (excludes are global; tooltip points to the global scope) |
| Path weight controls | yes | disabled in v1 (see Deferred) |
| `alwaysIgnoredPatterns` strikethrough | yes | yes (read from same global list) |

A freshly created named scope shows the full repo tree with all rows
unchecked plus a small inline banner: *"This scope is empty. Click
files and folders to add them."*

### Hooks

New `src/prep/dashboard/src/hooks/useScopes.ts`:

```ts
useScopes(projectId): {
  scopes: ScopeRecord[];          // includes synthetic "global"
  activeScopeId: string;          // session-state, defaults to "global"
  setActiveScopeId: (id: string) => void;
  createScope: (display_name: string) => Promise<ScopeRecord>;
  renameScope: (id: string, display_name: string) => Promise<void>;
  deleteScope: (id: string) => Promise<void>;
  addPaths:    (id: string, paths: string[]) => Promise<void>;
  removePaths: (id: string, paths: string[]) => Promise<void>;
}
```

Optimistic updates with rollback on failure, mirroring the existing
include-toggle hook in `useDashboardPanels`. `useDashboardPanels.tsx`
is modified: the `file-tree` slot consumes `useScopes`, the
`agent-scope` slot is removed.

### State persistence

The active scope ID lives in component state — refreshing the page
resets to `global`. Keeps "global is the safe default" obvious and
prevents an agent or user from forgetting they are in a narrow scope.
Promotion to `localStorage` is a candidate for v1.1 if session-only
proves annoying.

### Storybook

Five new stories appended to
`packages/ui/src/stories/project/FolderTree.stories.tsx` (the existing
stories file — there is no separate `FolderTreePanel.stories.tsx`):

1. Global scope, populated.
2. Named scope, populated.
3. Empty named scope (post-creation banner).
4. Create-scope inline input visible.
5. Named scope active with the exclude column rendered disabled and
   tooltipped.

## Touch list

Modified:
- `src/prep/api/routers/scope.py` — refactor to delegate
  `/scope/add` and `/scope/remove` to the new
  `services/project_helpers.mutate_global_scope` helper. Keep the
  endpoints (Phase 24 callers untouched).
- `src/prep/api/server.py` — register the new
  `/projects/{id}/scopes` router; unregister the deleted
  `agent_scope` router.
- `src/prep/api/routers/projects/search.py` — replace **both**
  `agent_scope_manager` call sites: line ~56 (basic search endpoint)
  and line ~1078 (segment-routed/atlas-aware search). Both now consume
  `scope_resolver.resolve_mask(project_id, scope, role)` and the
  public `path_matches_any_scope` helper. Remove the
  `_path_matches_scope` private import.
- `src/prep/services/project_helpers.py` — add
  `compute_index_membership(project_id) -> Set[str]` and
  `mutate_global_scope(project_id, action, paths)`. The five build
  pipeline sites switch to the former.
- `src/prep/services/pipeline/post_flight.py` — three sites
  (`:91`, `:153`, `:202`) read `compute_index_membership` instead of
  `pcfg.get("included_paths")`.
- `src/prep/services/pipeline/workers.py` — site `:896`, same
  swap.
- `src/prep/mcp/server.py` — add `scope` parameter and resolution
  call to `prep`, `prep_search`, `prep_impact`, `prep_concepts`,
  `prep_observe` handlers. Thread `applied_scope`/`applied_role`/
  optional `scope_warning` into responses.
- `src/prep/mcp_tools.py` — add `scope` to the tool schemas for the
  same five tools. Update the `role` description on `prep_search` to
  remove the Phase 67 "results are filtered" wording.
- `src/prep/agents/shared/prep_data.py` — line ~173: replace the
  `agent_scope_manager.get_agent_mask` call with
  `scope_resolver.resolve_mask`. Paperclip integration touchpoint —
  smoke-test before merge.
- `src/prep/core/rules_generator.py` — `_build_managed_content()`
  (`:340`) renders the Scopes sub-section listing project scopes plus
  the one-line `scope=<name>` hint. Treat scope CRUD as a debounce
  trigger for AGENTS.md regeneration (parallels existing
  `included_paths` debounce).
- `src/prep/dashboard/src/hooks/useDashboardPanels.tsx` — consume
  `useScopes`; remove the `agent-scope` slot and its endpoint
  callbacks.
- `packages/ui/src/components/project/FolderTreePanel.tsx` — header
  dropdown, `+`, Edit popover; disabled-exclude/disabled-weight
  affordances when a non-global scope is active.
- `packages/ui/src/api/client.ts` and `mock.ts` — scope CRUD methods.
- `packages/ui/src/types.ts` — `ScopeRecord`, `ScopesListResponse`.
- `packages/ui/src/index.ts`, `packages/ui/src/components/index.ts`,
  `packages/ui/src/components/agents/index.ts` — drop
  `AgentScopePanel` exports.
- `packages/ui/src/stories/project/FolderTree.stories.tsx` — extend
  with the five new stories listed under UI > Storybook (this is the
  existing stories file; there is no `FolderTreePanel.stories.tsx`).

New:
- `src/prep/core/scope_store.py` — CRUD against
  `project/<pid>/scope/<id>` keys; `synthesize_global(project_id)`
  reads `included_paths` and returns the synthetic `global` record.
- `src/prep/core/scope_resolver.py` — `resolve_mask(project_id,
  scope, role) -> tuple[Optional[Set[str]], MaskOrigin]` implementing
  the four resolution rules. Exposes `path_matches_any_scope(file_path,
  paths)` as a public replacement for `_path_matches_scope`.
- `src/prep/api/routers/scopes.py` — the new `/projects/{id}/scopes`
  router. `/scopes/global/*` write endpoints delegate to
  `mutate_global_scope`; non-global writes call the scope_store and,
  when needed, fire `scope_orchestrator.on_files_added/removed` for
  paths newly in or newly out of `compute_index_membership`.
- `src/prep/dashboard/src/hooks/useScopes.ts` — frontend hook.
- `tests/test_scope_store.py` — store CRUD, slug collision, `global`
  synthesis, no-leak between projects.
- `tests/test_scope_resolver.py` — all four resolution branches +
  unknown-scope warning shape.
- `tests/test_compute_index_membership.py` — union dedup, empty
  scopes, large-N performance smoke.
- `tests/api/test_scopes_endpoints.py` — endpoint round-trips +
  validation errors + delete-global rejection.
- `tests/api/test_search_with_scope.py` — `prep_search(scope=...)`
  filters results; `scope=` and `role=` compose; unknown scope
  fallback returns `applied_scope: "global"` with `scope_warning`;
  named scope adds files outside `included_paths` triggers an
  incremental embed.
- `packages/ui/src/components/project/__tests__/FolderTreePanel.test.tsx`
  — dropdown, create flow, exclude-disabled-on-named-scope.

Deleted:
- `packages/ui/src/components/agents/AgentScopePanel.tsx` and its
  story file.
- `src/prep/api/routers/agent_scope.py`.
- `src/prep/core/agent_scope_manager.py`.

## Risks / watchpoints

- **SQLite WAL on USB.** Scope CRUD writes hit the settings DB on the
  4TB-BAD volume during dev. The DELETE-mode fallback Phase 104
  established already covers this; verify scope writes survive a daemon
  restart on that volume.
- **`included_paths` proxying for `global`.** Two endpoints
  (`/scope/*` from Phase 24 and `/scopes/global/*` from this phase)
  now mutate the same store. They must share one mutator helper to
  avoid drift. Solution: extract `mutate_global_scope(project, action,
  paths)` in `services/project_helpers.py` and have both routers call
  it.
- **Search result citations.** `prep_search(scope="marketing")` must
  carry `applied_scope: "marketing"` in every response, otherwise the
  agent cannot tell whether a thin result set is genuine or a
  too-narrow scope. The envelope field is required in v1 — wiring it
  later is harder than wiring it now.
- **`assigned_to_role` invariants.** Two scopes with the same
  `assigned_to_role` value would make the role-fallback rule
  ambiguous. The PUT endpoint enforces uniqueness across a project's
  scopes — last writer wins is rejected with 409.
- **Multi-scope storage shape locking.** The `paths` field is plural
  for a single scope record, but the resolver's input is conceptually
  a set-of-paths union of one or more scopes. Keep the resolver
  signature (`Set[str] | None`) stable so v1.1 multi-scope is a
  single-function change.
- **Embed-pipeline-membership coverage.** Five build sites switch
  from `pcfg.get("included_paths")` to `compute_index_membership`.
  Any site missed will silently fail to embed scope-only files; that
  failure is observable only at search time (empty results from a
  populated scope). A single regression test in
  `tests/test_compute_index_membership.py` plus the manual golden
  path step "add a path NOT in `included_paths` to a named scope and
  confirm an incremental embed fires" catches this.
- **`prep_audit(scope=…)` overlap.** v1 deliberately does not extend
  `prep_audit` with named-scope resolution because the parameter
  already exists with a different meaning. Anyone reading the spec
  may expect `prep_audit(scope="marketing")` to work after this
  phase — it does not. Future phase to harmonize.

## Future work / deferred

1. **Per-scope path weights.** Storage shape already reserves
   `weights: Record<string, number>` (empty in v1). v1.1 wires the
   existing weight slider through the embedding scoring path on a
   per-scope basis.
2. **Multi-scope per request.** `scope=["marketing","data-cleaning"]`
   — wire-friendly; flip the API guard off and surface a multi-select
   in the dropdown.
3. **Auto-populate via role projection.** Re-wire the existing Phase
   67 sparkles feature (`/agent-scope/{role}/auto-populate` →
   `role_projection._python_scoring`) onto the new panel as "fill from
   role projection." Available on any scope with `assigned_to_role`
   set.
4. **Persist active scope across sessions.** Move `activeScopeId` from
   component state to `localStorage` if the session-only default is
   annoying in practice.
5. **Per-scope freshness/build status.** Today the panel shows one
   freshness badge; if a scope-specific freshness signal is useful
   (e.g. some paths in `marketing` are stale), expose it as a
   per-scope status.
6. **Per-scope concept pins / overrides.** Phase 104's `role_overrides`
   table stores per-role pinned concepts. A future phase can let a
   scope carry its own pinned concepts so `prep(scope="marketing")`
   not only filters retrieval but also injects the marketing-specific
   pins.

## Verification gates

- `ruff check src/`, `mypy src/`, `pytest tests/ -v` pass.
- `npm run typecheck` and `npm run lint` pass across workspaces.
- Storybook renders all five new stories without console errors.
- Manual dev-server golden path:
  - Create `marketing` scope, add `websites/marketing/` (a path NOT
    in `included_paths`), save, switch to it, see the tree narrowed.
  - Confirm an incremental embed pass fires for the newly-added paths
    (existing build-status indicator transitions: idle → debouncing →
    building → idle).
  - Call `prep_search(query="hero copy", scope="marketing")` via MCP,
    confirm only marketing files appear and `applied_scope:
    "marketing"` is in the envelope.
  - Call `prep_search(query="hero copy", scope="marketin")` via MCP,
    confirm `applied_scope: "global"` plus `scope_warning`.
  - Remove a path from `marketing` that is referenced ONLY by the
    `marketing` scope. Confirm the path leaves
    `compute_index_membership` and an incremental GC pass runs.
  - Remove a path from `marketing` that is also in `global`. Confirm
    no rebuild is triggered (path stays in the union).
  - Delete the scope, confirm dropdown updates, all marketing-only
    embeddings GC'd on the next pass.
  - Confirm the Phase 24 `/scope/add` endpoint and the new
    `/scopes/global/add` endpoint produce identical writes (both
    routed through `mutate_global_scope`).
  - Confirm `prep_search(role="copywriter")` (no `scope=` passed,
    no scope assigned-to-role exists) returns full-RAG results
    (i.e. role no longer auto-applies a file mask).
- `prep_audit` on the branch shows no new import cycles or hub
  violations.
