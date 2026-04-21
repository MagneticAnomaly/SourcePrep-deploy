# Pipeline HTTP Endpoints

All defined in `src/prep/api/routers/pipeline.py` except reset endpoints (which live in `src/prep/api/routers/trace_routes/enrichment.py`).

## Read

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/projects/{id}/pipeline/status` | Live state per stage/group | Cached 2–3s per project; dedicated 4-thread pool (Phase 60D-3) |
| GET | `/projects/{id}/pipeline/history` | Completed run journal | from `prep_pipeline_history.db` |

### Status response shape

Per-stage fields (merged from orchestrator state + disk manifest):

```json
{
  "stage_id": "enrichment",
  "exists": true,
  "running": false,
  "item_count": 1234,
  "total_items": 1500,
  "avg_confidence": 0.87,
  "progress_current": 1234,
  "progress_total": 1500,
  "progress_baseline": 1000,
  "extra": { "enriched_nodes": 1234, "settled_ratio": 0.82 }
}
```

Per-group fields:

```json
{
  "fast_sync":       { "is_active": false, "current_stage": null, "phase": "idle", "stages": { ... } },
  "deep_enrichment": { "is_active": true,  "current_stage": "group_reasoning", "phase": "running", "stages": { ... } },
  "finalize":        { "is_active": false, "current_stage": null, "phase": "idle", "stages": { ... } }
}
```

## Run / pause / resume

| Method | Path | Body | Purpose |
|---|---|---|---|
| POST | `/projects/{id}/pipeline/rebuild` | `{}` | Full reset + `run_all(force_from_start=true)` |
| POST | `/projects/{id}/pipeline/run` | `{groups?: [...]}` | Run selected groups; incremental |
| POST | `/projects/{id}/pipeline/pause` | `{group: "fast_sync"\|"deep_enrichment"\|"finalize"}` | Checkpoint and transition to paused |
| POST | `/projects/{id}/pipeline/resume` | `{group: str}` | Resume paused group (re-reads LLM config) |
| POST | `/pipeline/resume` | `{run_id: str}` | Resume crashed run from journal (no project_id in path) |
| POST | `/projects/{id}/pipeline/cancel` | `{group: str}` | Cancel running or paused group |

## Reset (destructive)

Scoped resets — fast sync always survives. Writes `.reset_barrier` to block selfheal.

| Method | Path | Scope | Defined |
|---|---|---|---|
| DELETE | `/projects/{id}/enrichment/full-reset` | Stages 6–15 | `trace_routes/enrichment.py:1048` |
| DELETE | `/projects/{id}/finalize/full-reset` | Stages 11–15 | `trace_routes/enrichment.py:1069` |

Both endpoints clear `antibody_store` and `concept_store` rows for the project (user concepts are not distinguishable from auto-generated; reset means clean slate — see `tests/test_scoped_full_reset.py`).

## Rebuild vs scoped reset

- `POST /pipeline/rebuild` — wipes everything including stages 1–5, runs all 15 from scratch. Use for "start over" tests.
- `DELETE /enrichment/full-reset` + `POST /pipeline/run` — keeps fast sync, re-runs 6–15. Use for "invalidate semantic state" tests.
- `DELETE /finalize/full-reset` + `POST /pipeline/run` — keeps 1–10, re-runs 11–15. Use for "regenerate atlas/audit/concepts" tests.
