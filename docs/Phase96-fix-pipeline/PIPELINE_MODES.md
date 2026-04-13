# Pipeline Execution Modes

**Last updated:** 2026-04-13

The CoDRAG pipeline has three execution modes. Each mode determines how the 15 stages process data and what the UI should display.

## The 15 Stages

```
FAST SYNC (1-5)          DEEP ENRICHMENT (6-10)     FINALIZE (11-15)
├─ 1. Structural Graph   ├─ 6. Deep Reasoning       ├─ 11. Atlas Building
├─ 2. Edge Discovery     ├─ 7. Group Reasoning      ├─ 12. Rules Generation
├─ 3. Fast Catalogue     ├─ 8. Module Synthesis      ├─ 13. Concept Seeding
├─ 4. Validation         ├─ 9. Continuous Deepening  ├─ 14. Structural Audit
└─ 5. Knowledge Embed    └─ 10. Deep Knowledge Embed └─ 15. Immune System
```

## Mode 1: Initial Build

**Trigger:** First time a project's pipeline runs (no existing data on disk).

**Behavior:**
- All 15 stages run from scratch
- Structural builds the full trace graph via Rust engine
- Catalogue augments ALL nodes with LLM descriptions
- Knowledge embeds ALL chunks
- No baseline data → single-color progress bars (blue)
- Manifests written for each stage on completion

**UI Indicators:**
- Progress bars: solid blue, 0→100%
- Stage status: "Building..." → checkmark
- No 2-tone bars (no baseline exists)

**Chaining:** Fast Sync → Deep Enrichment → Finalize (all automatic in Auto mode)

---

## Mode 2: Incremental

**Trigger:** File watcher detects changes (Auto mode) or user clicks "Update Map" / "Run".

**Behavior:**
- Structural rebuilds ONLY changed files (Rust engine incremental)
- Catalogue augments ONLY new/changed nodes (skips existing augmentations)
- Knowledge re-embeds ONLY new/changed chunks
- Deep Reasoning enriches ONLY new file nodes (skips already-enriched)
- Group Reasoning re-analyzes groups that contain changed files
- Module Synthesis re-synthesizes clusters with changed members
- Deepening re-scores only changed nodes
- Finalize stages run but skip if outputs are newer than inputs

**UI Indicators:**
- Progress bars: **2-tone** — green (pre-existing baseline) + orange (new work)
  - Example: "28 / 30 files" where 28 existed, 2 are new
- `progress_baseline` in API response indicates pre-existing count
- Manifests store `incremental_baseline` for persistence across refresh (F-66)

**Chaining:** Same as initial — Fast Sync chains to Deep Enrichment chains to Finalize.

**Data preservation:** Existing enrichment data (epistemic, group reasoning, modules, deepening) is NEVER deleted during incremental. Workers skip already-processed items internally.

---

## Mode 3: Rebuild (Danger Zone)

**Trigger:** User clicks "Rebuild" in the Danger Zone settings panel.

**Behavior:**
- `force_from_start=True` flag set on the pipeline orchestrator
- Structural rebuilds the ENTIRE trace graph from scratch
- ALL downstream manifests are invalidated (F-67)
- Manifest mtime sync is SKIPPED (so freshness checks don't skip stages)
- ALL stages re-run, but workers are still incremental internally:
  - Catalogue re-augments all nodes (may reuse existing if unchanged)
  - Knowledge re-embeds everything
  - Enrichment re-processes all files
- Write guard bypass: force_from_start runs are exempt from shrinkage checks (F-51/F-52)
- Backup restore is skipped for force_from_start runs

**UI Indicators:**
- Progress bars: solid blue (like initial — no baseline since it's a full rebuild)
- All stages show as running/queued
- "Rebuild" mode shown in pipeline status

**Chaining:** Same chain — Fast Sync → Deep Enrichment → Finalize.

**When to use:**
- After major refactoring (many files renamed/moved)
- When the trace graph is corrupted or inconsistent
- After changing include/exclude globs significantly
- When enrichment quality needs to be reset

---

## Stage Execution Flow

```
                    ┌─────────────┐
                    │ File Change  │
                    │  Detected    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Watcher     │
                    │  Debounce    │
                    │  (5s)        │
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │  Pipeline Orchestrator   │
              │  _detect_resume_point()  │
              │  → determines start stage│
              └────────────┬────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐       ┌──────────┐       ┌──────────┐
   │Fast Sync│──────▶│  Deep    │──────▶│ Finalize │
   │ (1-5)   │chain  │Enrichment│chain  │ (11-15)  │
   │         │       │ (6-10)   │       │          │
   └─────────┘       └──────────┘       └──────────┘
```

## Manifest-Based Resume

Each stage writes a manifest on completion (`*_manifest.json`). On daemon restart:

1. `detect_resume_point()` checks which manifests exist
2. First stage WITHOUT a manifest = resume point
3. Stages before resume point are skipped (data exists)
4. F-67: Manifests are deleted at stage START (not end) so crashes leave no manifest → correct resume detection

## Per-Project Auto/Manual/Scheduled

Each project has independent pipeline mode settings stored in `project.config.auto_config`:

```json
{
  "fastSync": true,           // Auto watcher for stages 1-5
  "deepEnrichment": "auto",   // "manual" | "auto" | "scheduled"
  "finalize": "auto"          // "manual" | "auto"
}
```

The backend reads per-project config (F-65) for:
- Startup auto-run decisions (`server.py:_startup_auto_run`)
- Chain-after-fast decisions (`_is_deep_enrichment_auto`)
- Chain-after-deep decisions (`_is_finalize_auto`)

## Interruption & Recovery

**Pause:** User clicks Manual while running → pipeline pauses at current stage, flushes partial results.

**Daemon restart during run:**
- F-67: Active stage's manifest was deleted at start → resume detects it as incomplete
- F-67: `has_active_run()` includes PAUSED runs → clean shutdown marker NOT written for active projects
- Recovery hydrates PAUSED state from disk manifests
- Auto-run resumes from the incomplete stage

**Project deactivation:** F-69 guards prevent deactivated projects from starting any pipeline.
