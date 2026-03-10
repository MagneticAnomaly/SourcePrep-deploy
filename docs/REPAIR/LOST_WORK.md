# Lost Work Recovery Plan (March 9, 2026)

Based on the git diffs of the lost changes, we need to rebuild the following features that were accidentally reverted/deleted:

## 1. Developer Tools & Selective Resets (Phase 47)
- **`src/codrag/api/routers/trace_routes/enrichment.py`**:
  - `_backup_files_if_debug()` logic.
  - `_selective_delete()` helper.
  - `DELETE /projects/{id}/atlas/destroy`
  - `DELETE /projects/{id}/group-reasoning/destroy`
  - `DELETE /projects/{id}/deep-enrichment/destroy`
- **`packages/ui/src/api/client.ts` & `mock.ts`**:
  - Added `destroyAtlas`, `destroyGroupReasoning`, `destroyDeepEnrichment` methods.
- **`src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx`**:
  - "Debug Tools" section (Verbose Telemetry toggle).
  - "Selective Reset" section (Atlas, Group Reasoning, Deep Enrichment danger buttons).
- **`src/codrag/server.py`**:
  - Re-add `developer_debug_mode` to `_load_ui_config` injections.

## 2. LLM Client / LM Studio SSE Support
- **`src/codrag/core/llm_client.py`**:
  - `CloudRateLimitError` and HTTP 429 detection.
  - Native LM Studio SSE parsing (`_generate_lmstudio`) for `message.delta` and `reasoning.delta`.
  - `debug_mode` verbose logging for LLM prompts and timings.
  - LM Studio `unload` model logic.

## 3. Global vs Per-Model Concurrency (Phase 45/46)
- **`packages/ui/src/types.ts`**:
  - Added `concurrency?: number` to `LLMSlotConfig` and `LLMAssignmentBlock`.
- **`src/codrag/dashboard/src/App.tsx`**:
  - Removed global `concurrencyFast`, `concurrencyCode`, `concurrencyDeep` state and handlers.
- **`packages/ui/src/components/llm/AIModelsSettings.tsx` & Cards**:
  - (Need to verify if we need to rebuild these as they weren't fully in the diff, but related to the types changes).

## 4. Pipeline Fixes (Phase 48)
- **`src/codrag/services/pipeline/orchestrator.py`**:
  - `_maybe_retrigger_deepening()` logic (scheduling a 30s timer if `settled_ratio` < 0.70).
- **`packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`**:
  - Rerun visualization (stale vs done percent), paused state fixes, complete state calculations for deepening vs atlas.

## 5. Enterprise Admin / Types
- **`packages/ui/src/index.ts`**:
  - Re-export Enterprise Admin components and roles.
