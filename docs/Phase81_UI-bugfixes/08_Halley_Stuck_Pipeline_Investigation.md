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

### Updated Analysis (second pass)

The pipeline metadata reveals a deeper issue: enrichment, group_reasoning, and clustering all have `status: "pending"` with **no worker_result**. Only atlas (stage 4), deepening (stage 5), and deep_knowledge (stage 6) ran. This means the first 3 deep stages were skipped by the incremental detection — their data existed from a prior run.

But **clustering has NEVER produced `trace_modules.jsonl` across any run.** The pipeline skips it each time because either:
1. The large model wasn't available/enabled when clustering ran
2. The worker caught RuntimeError ("no model") and returned `skipped: True`
3. The incremental detector sees the manifest file exists and skips the stage

The embedding model IS configured and working. The issue is specifically the **large/Thinking model slot** being `enabled: false` while `configured: true, status: connected`. This is confusing — the model exists and is reachable, but the slot is disabled.

### Recommended fixes (revised)

1. **Backend (P0): Don't start deep enrichment if required model slots are disabled.** The pipeline orchestrator should pre-check that all required model slots for the stage group are enabled before starting. If not, fail immediately with a clear error message (not silently skip).

2. **Backend (P1): Don't treat "skipped due to no model" as successful completion.** When a worker returns `skipped: True, reason: "no_llm"`, the orchestrator should transition to FAILED with a clear error, not advance to the next stage.

3. **UI (P1): Show model slot requirements in the deep enrichment section.** Before the "Run" button, show which model slots are needed and their status. Disable the Run button if required slots aren't enabled.

4. **UI (P2): Distinguish "never ran" from "ran successfully" in stage status.** The current compute functions can't tell the difference between "stage ran and produced 0 modules" vs "stage was silently skipped".
