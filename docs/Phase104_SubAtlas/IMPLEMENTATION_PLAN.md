# Phase 104 — Implementation Plan

> Build order, checkpoints, and verification steps for rebuilding the Atlas panel as a role-lens policy editor. See `README.md` for design and rationale.

## Work breakdown

Ordered by dependency. Each step ends at a checkpoint where the app should still run and tests should pass.

### Step 1 — Backend: unify atlas response + surface segments

**Why first:** UI cannot show a sub-atlas tree until `GET /atlas` returns segments. Also the cheapest change.

**Files:**
- `src/codrag/api/routers/projects/atlas_endpoints.py`

**Tasks:**
- Extract `_build_atlas_response(doc, segments, overrides, role_payload)` helper used by both `get_atlas` and `regenerate_atlas`.
- Add `segments` array to the GET response (fields: `segment_id`, `segment_name`, `dir_path`, `file_count`, `char_count`, `stale`).
- No change to response envelope; only new fields on the payload.

**Tests:**
- Extend `tests/api/test_atlas_endpoints.py` (create if absent): GET returns segments for a segmented project; GET returns empty `segments: []` for unsegmented; regenerate still returns segments unchanged.

**Checkpoint:** `curl /projects/{id}/atlas` returns segments on a segmented project. Old dashboard still renders (new fields are additive).

---

### Step 2 — Backend: role-overrides store

**Why:** Needed before any write affordance lands on the UI.

**Files (new):**
- `src/codrag/core/role_overrides.py` — dataclass + CRUD against `codrag_data/codrag_settings.db`.
- `src/codrag/api/routers/projects/role_overrides_endpoints.py` — four endpoints (GET all, GET one, PUT, DELETE).

**Files (edited):**
- `src/codrag/api/server.py` (or wherever routers are registered) — mount the new router.
- Migration: add `role_overrides` and `concept_role_pins` tables on settings DB init.

**Tasks:**
- Implement table creation idempotently (`CREATE TABLE IF NOT EXISTS`) on settings-DB open.
- `RoleOverrideStore.get(project_id, role_id) -> Optional[RoleOverride]`
- `.list(project_id) -> list[RoleOverride]`
- `.upsert(project_id, role_id, max_chars=None, pinned_concept_ids=None)`
- `.delete(project_id, role_id)`
- Pydantic request/response models for the endpoints.

**Tests:**
- `tests/core/test_role_overrides.py` — store CRUD, concurrent writes, USB-mode fallback.
- `tests/api/test_role_overrides_endpoints.py` — 200/404 paths, validation errors, round-trip.

**Checkpoint:** `curl -X PUT /projects/{id}/role-overrides/engineering -d '{"max_chars": 3500}'` persists across daemon restart.

---

### Step 3 — Backend: projection reads overrides

**Why:** Writes are worthless until the projection honors them.

**Files:**
- `src/codrag/core/atlas/role_projection.py` — add `overrides` parameter to `project_atlas_for_role()`.
- Callers of `project_atlas_for_role()` (audit with `rg`): MCP `codrag()` tool, `atlas_endpoints.py` `?role=` branch.

**Tasks:**
- Load override before scoring; apply `max_chars` to the working `RoleVector.copy()` before passing to assembly functions.
- `atlas_endpoints.py` populates `applied_role` on the response with the post-override RoleVector and echoes the override itself under `override`.
- MCP `codrag(role=X)` call path also consults overrides (same helper).

**Tests:**
- `tests/core/test_role_projection.py` — projection with override halves/doubles output size as expected; no override → built-in budget.
- `tests/api/test_atlas_endpoints.py` — `?role=engineering` returns `applied_role.max_chars` reflecting override when set.

**Checkpoint:** `codrag(role="engineering")` MCP call returns sub-atlas sized by the override.

---

### Step 4 — Backend: concept→role pins

**Files:**
- `src/codrag/core/concepts.py` (or wherever the concept store lives) — add pin/unpin functions reading `concept_role_pins`.
- `src/codrag/api/routers/concepts/` — `POST /concepts/{id}/pin` and `DELETE /concepts/{id}/pin` endpoints; body `{role}`.
- `role_projection.py` — after loading overrides, fetch pinned concepts for the role, prepend a "Pinned for this role:" block (bounded by 20% of the role's budget; truncate with ellipsis).

**Tests:**
- Pin/unpin round-trip.
- Projection output contains the pinned block when pins exist; omits block when none.
- Budget enforcement: pinned block never exceeds 20% of `max_chars`.

**Checkpoint:** Pinning a concept to `engineering` makes it appear in the engineering sub-atlas, bounded by budget.

---

### Step 5 — Frontend: types + hook scaffolding

**Files:**
- `packages/ui/src/types.ts` — add `AtlasSegmentStatus`, `RoleVectorPayload`, `RoleOverride`; extend `AtlasStatus` with `segments`, `applied_role`, `override`.
- `packages/ui/src/api/client.ts` + `mock.ts` — methods: `getAtlas(projectId, role?)`, `getRoleOverrides(projectId)`, `putRoleOverride(projectId, role, override)`, `deleteRoleOverride(projectId, role)`, `pinConcept(projectId, conceptId, role)`, `unpinConcept(projectId, conceptId, role)`.
- `src/codrag/dashboard/src/hooks/useAtlasLens.ts` (new) — coordinator hook; AbortSignal-based, debounced role switch (200ms).
- `src/codrag/dashboard/src/hooks/useRoleOverrides.ts` (new) — override map + mutators.

**Tests:**
- Hook tests with MSW or the existing mock client: role change cancels in-flight request; PUT invalidates the override map.

**Checkpoint:** Hook returns typed data in the dashboard; existing `AtlasStatusCard` still renders using the old field subset.

---

### Step 6 — Frontend: `AtlasLensPanel` (read-only first)

**Files (new, all under `packages/ui/src/components/trace/AtlasLensPanel/`):**
- `AtlasLensPanel.tsx` — top-level composer, consumes hooks.
- `StatusStrip.tsx` — freshness badge + counts + regenerate button (lift from `AtlasStatusCard`).
- `SubAtlasTree.tsx` — segment rows with expand-to-preview.
- `RoleLens.tsx` — role picker + preview pane + applied-lens summary.
- `BudgetSlider.tsx` — placeholder, non-interactive in this step.
- `PinnedConceptsChip.tsx` — read-only badge showing pin count; click opens a popover list.

**Storybook:**
- One story per state matrix: {segmented, unsegmented} × {structural, LLM} × {role selected, no role} × {override present, no override}. Not exhaustive — pick ~6 representative combinations.

**Tasks:**
- `useDashboardPanels.tsx` — swap `AtlasStatusCard` slot for `AtlasLensPanel`.
- Keep `AtlasStatusCard` exported but deprecated until Step 8.

**Verification:** Dev server + browser. Open the panel, switch roles, confirm preview updates and applied-lens strip matches the role. Edge cases: project with no atlas yet, project with only structural atlas, project still building.

**Checkpoint:** Panel is a functional read-only viewer in the running dashboard.

---

### Step 7 — Frontend: writable affordances

**Files edited:**
- `BudgetSlider.tsx` — make it interactive; debounced PUT on release (not on every drag tick).
- `PinnedConceptsChip.tsx` — popover with search + pin/unpin actions wired to concept endpoints.
- `RoleLens.tsx` — show a "Reset to default" button when an override is active.

**Tests:**
- Dashboard hook test: PUT failure rolls back optimistic state.
- Storybook play function: drag slider → fetch called with debounced value.

**Verification:** Pull up the panel, set engineering max_chars to 2000, reload, confirm the preview shrinks. Call `codrag(role="engineering")` via MCP, confirm response reflects the new budget.

**Checkpoint:** Policy authoring works end-to-end: UI edit → MCP call sees new lens.

---

### Step 8 — Cleanup

- Delete `AtlasStatusCard.tsx` + its stories.
- Remove `AtlasStatusCard` exports from `packages/ui/src/index.ts` and `components/trace/index.ts`.
- Update any docs referencing the old component name.
- Run the full typecheck + lint sweep.

**Checkpoint:** `grep -r AtlasStatusCard` returns no hits outside the changelog.

---

## Verification gates

These must hold before the branch merges:

- [ ] `ruff check src/` and `mypy src/` pass.
- [ ] `pytest tests/ -v` passes including new tests in Steps 1–4.
- [ ] `npm run typecheck` and `npm run lint` pass across workspaces.
- [ ] Storybook renders all new stories without console errors.
- [ ] Dev-server golden path (Step 6 checkpoint + Step 7 checkpoint) tested manually in browser.
- [ ] `codrag_audit` on the branch shows no new cycles or hub violations.

## Known risks / watchpoints

- **SQLite WAL on USB** — the overrides writes hit the settings DB on the 4TB-BAD volume during dev. Confirm DELETE-mode fallback kicks in (known issue — see user memory).
- **Role projection currently has a Rust fast path** (`_try_rust_scoring`). When we add override handling, make sure the override application happens **after** both the Rust and Python code paths return, so we don't have to port override logic into Rust for a v1 feature that might change shape.
- **Atlas regeneration races** — if the user clicks Regenerate while a role projection is in-flight, the projection may reference stale content. Cancel in-flight role fetches when regenerate starts.
- **Concept pin budget overflow** — cap pinned-concept block at 20% of `max_chars`. If pins exceed, truncate with a stable ordering (pin date ascending) so reruns are deterministic.

## Touch list (quick audit)

Modified:
- `src/codrag/api/routers/projects/atlas_endpoints.py`
- `src/codrag/api/server.py` (router mount)
- `src/codrag/core/atlas/role_projection.py`
- `src/codrag/core/atlas/__init__.py` (if exports change)
- `src/codrag/mcp/server.py` (projection call site passes overrides)
- `src/codrag/core/concepts.py`
- `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`
- `packages/ui/src/types.ts`
- `packages/ui/src/api/client.ts`, `packages/ui/src/api/mock.ts`
- `packages/ui/src/index.ts`, `packages/ui/src/components/index.ts`, `packages/ui/src/components/trace/index.ts`

New:
- `src/codrag/core/role_overrides.py`
- `src/codrag/api/routers/projects/role_overrides_endpoints.py`
- `src/codrag/api/routers/concepts/pin_endpoints.py` (or folded into existing concepts router)
- `src/codrag/dashboard/src/hooks/useAtlasLens.ts`
- `src/codrag/dashboard/src/hooks/useRoleOverrides.ts`
- `packages/ui/src/components/trace/AtlasLensPanel.tsx` + subcomponents
- `packages/ui/src/stories/trace/AtlasLensPanel.stories.tsx`
- `tests/core/test_role_overrides.py`
- `tests/api/test_role_overrides_endpoints.py`

Deleted (Step 8):
- `packages/ui/src/components/trace/AtlasStatusCard.tsx`
- `packages/ui/src/stories/trace/AtlasStatusCard.stories.tsx`

## Not in this plan (Phase 105+ preview)

- Per-role file-tree scope editor. Current global Scope panel continues to own project-wide scope.
- Full weight editing (layer bars, domain chips) — read-only in v1.
- Registered-agent-level overrides layered over role overrides.
- Role-call telemetry panel.
