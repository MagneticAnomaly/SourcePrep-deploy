# Phase 139 — Embedder Memory Hardening

> **The rule:** the embedder must never silently consume tens of GB of RAM,
> must release memory when work ends, and must be opt-out-able when the user
> wants pure-cloud inference.

## Why this phase exists

On 2026-05-15 the SourcePrep daemon reached a **100.8 GB physical
footprint** on a 128 GB Mac and got stuck inside CoreML's
`MLNeuralNetworkEngine.setEspressoBlobShapes` while the user thought
"all cloud Ollama" meant no local inference was running. It did not.
**Cloud Ollama applies only to LLM augmentation; embeddings still run
locally** via `NativeEmbedder` (ONNX + CoreMLExecutionProvider).

This phase fixes the memory profile, the lifecycle (release on stop),
and the user expectation (cloud-only mode that means cloud-only).

See [INCIDENT.md](./INCIDENT.md) for evidence and timeline.

## Scope

In:
- Embedder singleton + explicit lifecycle (release on pipeline stop)
- Batch-size and max-length policy that does not scale *upward* on big machines
- Hard memory ceiling (env-configurable, sensible default)
- `embedding_source=cloud` / `=disabled` user-facing option
- RSS telemetry in `pipeline_telemetry.jsonl`

Out:
- Switching default embedding model
- Replacing ONNX with a different runtime
- Rust-side rewrites (the Rust engine is not implicated in this incident)

## Status

- [x] Diagnosis complete — see INCIDENT.md
- [x] Phase folder scaffolded
- [ ] Research synthesis — see RESEARCH.md (in progress, 3 parallel agents)
- [ ] Implementation plan signed off — see IMPLEMENTATION_PLAN.md
- [ ] Implementation
- [ ] Validation + RESULTS.md

## Files in this phase

| File | Purpose |
|---|---|
| `README.md` | This file — phase summary and status |
| `INCIDENT.md` | What happened, evidence, timeline |
| `RESEARCH.md` | Best-practice review with citations (whitepapers, ONNX/CoreML docs, TEI patterns) |
| `CORPUS_PROFILE.md` | Token-length distribution of real workload — informs bucket boundaries |
| `IMPLEMENTATION_PLAN.md` | Ordered, scoped diff list with risk + ROI, decisions locked in |
| `RESULTS.md` | Post-merge: what landed, before/after numbers, follow-ups |
