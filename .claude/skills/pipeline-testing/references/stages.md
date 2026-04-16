# Stage Reference

Defined in `src/codrag/services/pipeline/stages.py:12-31`.

## Stage list

| # | stage_id | Group | Queue type | Swarm-capable | Output artifacts |
|---|---|---|---|---|---|
| 1 | `structural` | Fast Sync | RUST | no | `trace_nodes.jsonl`, `trace_edges.jsonl`, `trace_manifest.json` |
| 2 | `inferred_edges` | Fast Sync | LLM | no | `trace_inferred_edges.jsonl`, `trace_inferred_manifest.json` |
| 3 | `catalogue` | Fast Sync | LLM | no | `trace_augmented.jsonl`, `trace_augment_manifest.json` |
| 4 | `validation` | Fast Sync | RUST | no | (validation pass — updates manifests) |
| 5 | `knowledge` | Fast Sync | EMBEDDING | no | knowledge index artifacts (ONNX) |
| 6 | `enrichment` | Deep Enrichment | LLM | no | `trace_epistemic.jsonl`, `trace_epistemic_manifest.json` |
| 7 | `group_reasoning` | Deep Enrichment | LLM | **yes** | `trace_group_reasoning.jsonl`, `group_reasoning_manifest.json` |
| 8 | `clustering` | Deep Enrichment | LLM | **yes** | `trace_modules.jsonl`, `trace_modules_manifest.json` |
| 9 | `deepening` | Deep Enrichment | LLM | no | `deepening_manifest.json` |
| 10 | `deep_knowledge` | Deep Enrichment | EMBEDDING | no | `deep_knowledge_manifest.json` |
| 11 | `atlas` | Finalize | LLM | **yes** | `atlas.json`, `atlas_manifest.json`, `atlas_routing.json`, `atlas_roles/` |
| 12 | `rules` | Finalize | RUST | no | `rules_manifest.json` |
| 13 | `concepts` | Finalize | LLM | **yes** | `concepts_manifest.json` |
| 14 | `audit` | Finalize | LLM | **yes** | `audit_manifest.json`, `audit/findings.json` |
| 15 | `antibodies` | Finalize | RUST | no | `antibodies_manifest.json` |

## Queue types

`STAGE_QUEUE_TYPE` in scheduler.py:

- **LLM**: competes for LLM slots (global concurrency cap applies)
- **EMBEDDING**: independent ONNX path — does not contend with LLM work
- **RUST**: CPU-only, no slot needed

## Swarm capability

`SWARM_CAPABLE_STAGES` frozenset in `src/codrag/services/pipeline/scheduler.py:53`:

```python
SWARM_CAPABLE_STAGES = frozenset({
    "group_reasoning",
    "clustering",
    "atlas",
    "concepts",
    "audit",
})
```

Swarm path requires:
- Stage is in `SWARM_CAPABLE_STAGES`
- Model supports swarm
- Capacity > 3 workers (Phase 91 floor)
- Swarm window not on cooldown (45s between windows)
- No competing project draining capacity

If any fail, falls back to sequential stage with `cloud_concurrency` cap.
