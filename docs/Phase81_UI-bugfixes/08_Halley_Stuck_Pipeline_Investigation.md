# Phase 81 — Halley Project Investigation

**Date:** 2026-04-07
**Project:** Haley (`7230f731-55ff-4a80-b2c3-a82235625940`)
**Path:** `/Volumes/4TB-BAD/HumanAI/LinuxBrain` (46,067 files)

---

## Issue 1: Catalogue Stuck at 99%

**Symptom:** Fast Catalogue showed 99% for hours.

**Root cause:** Not actually stuck — processing 46K files through `kimi-k2.5:cloud` via Ollama. The last 250 files took disproportionately long due to:
- Cloud API rate limiting at the tail
- Only 3 concurrent workers for cloud models (`CLOUD_SMALL` profile)
- Last batches process with fewer than 3 active threads (2 finish, 1 still going = 99%)

**Fix applied:** Show file counts under progress bar (`45,815 / 46,067 files`) so user knows it's alive. Committed in `03b4bbd4`.

**Not a bug** — expected behavior for very large repos on cloud models.

---

## Issue 2: Deep Enrichment UI Reverted After Completion

**Symptom:** After deep enrichment completed, Module Synthesis showed "Ready to synthesize", Atlas showed "Waiting for modules", Deepening showed "Waiting for clusters", Deep Knowledge showed "Waiting for enrichment + clusters". All reverted to grey/disabled despite the pipeline completing.

**Root cause:** The clustering stage was **skipped** by the pipeline orchestrator. Evidence:

1. `pipeline_run_metadata.json` shows `clustering: { status: "pending" }` — never ran
2. `trace_modules_manifest.json` shows `elapsed_seconds: 0.13` — completed instantly (early return)
3. `trace_modules.jsonl` does NOT exist — the JSONL data file was never written
4. The module status API (`/modules/status`) reads from `trace_modules.jsonl` and returns `enabled: false, module_count: 0` when the file is missing
5. The compute functions (`computeModuleState`, `computeAtlasState`, etc.) see `module_count: 0` and return `not_built`/`disabled`

The clustering stage is in `DEEP_ENRICHMENT_STAGES` (stage 3 of 6) but the pipeline jumped from `group_reasoning` (stage 2) directly to `atlas` (stage 4). The metadata confirms: `group_reasoning: status=pending`, `clustering: status=pending`, `atlas: status=completed`.

**This is a pipeline orchestrator bug**, not a UI bug. The `_advance_pipeline` method or a stage gate skipped the clustering stage.

### Where to investigate

- `src/codrag/services/pipeline/orchestrator.py` — `_advance_pipeline()` method
- Look for conditions that skip stages (e.g., checking if the stage's model slot is available, or if prerequisites are met)
- The clustering stage requires the `large_model` (Thinking slot) — check if the model was configured/available at the time
- The LLM slots status showed `large_model: { enabled: false }` — this may be why clustering was skipped

### Likely cause

The LLM slot status for this project shows `large_model: { enabled: false }`. The clustering worker checks for an LLM client:

```python
# workers.py line 630-635
try:
    llm_client = WorkerFactory._get_llm_client_for_task("clustering")
except RuntimeError:
    logger.info("[Module Synthesis] No model available for clustering task — skipping")
    return {"stage": "clustering", "skipped": True, "reason": "no_llm"}
```

If the large model isn't configured, clustering silently skips with `skipped: True`. The pipeline orchestrator treats this as a successful completion and advances to atlas. But the skipped stage writes no `trace_modules.jsonl`, so all downstream status checks fail.

### Impact on UI

The UI correctly reflects the backend state — modules genuinely don't exist. The "revert" appearance is accurate but confusing. The user sees completed pipeline but incomplete stages because a prerequisite (large model) wasn't met.

### Recommended fixes

1. **Backend:** When a stage is skipped due to missing model, the pipeline should surface this clearly in the status (e.g., `phase: "skipped"` instead of `"completed"`)
2. **UI:** Add a `'skipped'` StageState that shows a distinct visual (e.g., grey with skip icon and tooltip explaining why)
3. **UI:** Show model availability warnings in the pipeline panel before running deep enrichment
