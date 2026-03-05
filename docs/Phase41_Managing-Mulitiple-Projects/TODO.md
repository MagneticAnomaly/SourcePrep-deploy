# Phase 41: Managing Multiple Projects - Implementation Plan

## 1. LLM "Always On" Feature
**Objective:** Allow models to be flagged as always available to prevent them from being caught up in VRAM thrashing logic, while forcing this to true/disabled for Cloud APIs.

- [ ] **Types & Config**
  - [ ] Add `always_on?: boolean` to `LLMSlotConfig` in `packages/ui/src/types.ts`.
  - [ ] Add `always_on?: boolean` to `LLMAssignmentBlock` in `packages/ui/src/types.ts`.
  - [ ] Update backend `config_manager.py` to support `always_on` flag in default configs and parsing.
- [ ] **UI Components (`AIModelsSettings.tsx`, `LLMAssignmentBlockCard.tsx`)**
  - [ ] Add a checkbox: *"Always available (Keep loaded)"*.
  - [ ] Add logic to check the provider of the selected endpoint (`openai`, `anthropic`, `google`, `openai-compatible`). If it's a cloud provider, force the checkbox to `checked` and `disabled`.
- [ ] **Backend Orchestration (`server.py` / `llm_lifecycle`)**
  - [ ] Ensure the model unloading/lifecycle manager reads this `always_on` flag.
  - [ ] Bypass eviction logic for models flagged as `always_on`.

## 2. Max Active Projects Setting
**Objective:** Allow Pro+ users to define a strict limit on how many projects can be active simultaneously (1-5 or Infinite) to prevent overwhelming system resources.

- [ ] **Types**
  - [ ] Add `max_active_projects?: number | 'infinite'` to `GlobalConfig` in `packages/ui/src/types.ts`.
- [ ] **UI (Global Settings Panel)**
  - [ ] Add a new section for "Resource Limits" in Global Settings (likely `GlobalSettingsPanel.tsx` or similar).
  - [ ] Add a Dropdown/Select: `1, 2, 3, 4, 5, Infinite`.
- [ ] **Backend Enforcement (`project_helpers.py` & `projects/crud.py`)**
  - [ ] Update project activation logic. When the user attempts to toggle `config.active = True` on a project, check `get_project_activity_status` for all projects. 
  - [ ] If the active count is `>= max_active_projects`, return a `400` error indicating the user must deactivate another project first.

## 3. Enforce Inactive Project Restrictions
**Objective:** Stop inactive projects from utilizing LLMs, embeddings, and builds, while still allowing folder structure and settings adjustments.

- [ ] **UI Guardrails**
  - [ ] Update `WatchControlPanel.tsx` to check if `activity_status === 'inactive'`. Disable Build, Sync, and Pipeline buttons, and add a tooltip: *"Activate this project to run builds."*
  - [ ] Update `IndexStatusCard.tsx` similarly for Build buttons.
  - [ ] Update `GraphEnrichmentPipeline.tsx` similarly for pipeline Auto/Run buttons.
- [ ] **Backend Guardrails (`project_helpers.py`)**
  - [ ] Create a `require_project_active` guard (or extend `require_project_writable` based on the endpoint).
  - [ ] Apply the guard to block `POST /build`, `POST /trace/build`, `POST /watch/start`, and `POST /pipeline/*` for `inactive` projects.
  - [ ] Ensure settings endpoints (`PUT /projects/{id}/config`) still use `require_project_writable` only, so they remain editable for inactive projects.

## 4. Free Tier Project Deletion Warning & Purge
**Objective:** Prevent Free tier users from gaming the 1-active-project limit by adding/removing projects while keeping their local `.codrag` databases intact.

- [ ] **API Client Update (`packages/ui/src/api/client.ts`)**
  - [ ] Update the `deleteProject` API call to accept a `purge?: boolean` query parameter.
- [ ] **UI (Delete Project Action)**
  - [ ] Update the "Delete Project" confirmation logic (likely in `ProjectSettingsPanel.tsx` or `ProjectList`).
  - [ ] Check `license.tier`. If `license.tier === 'free'`, show a custom modal: *"You are on the Free tier. Deleting this project will permanently delete its trace graph and the entire `.codrag` folder. This action cannot be undone."*
  - [ ] If the user accepts, send `DELETE /projects/{id}?purge=true`.
- [ ] **Backend Verification (`crud.py`)**
  - [ ] Verify that `purge=True` successfully wipes the `.codrag` directory as expected (the current `remove_project` logic has `purge` built in, verify it works correctly for Free tier).
