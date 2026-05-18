# Phase 139 — Results

> PR 1 committed in `10a1add5` + `01ba3252`, pushed.
> PR 2 implementation below (also locally complete).

## What landed (PR 1)

| Tier | What | Files |
|---|---|---|
| T1.1 | Process-wide embedder singleton, factory cache | `src/prep/services/embedder_factory.py` |
| T1.1 | `is_available()` made static; introspection callsites no longer construct | `src/prep/core/embedder.py`, `src/prep/api/routers/llm.py`, `src/prep/services/config_manager.py`, `src/prep/services/pipeline/orchestrator.py` |
| T1.1 | Direct-construction warning (Q11) | `src/prep/core/embedder.py` |
| T1.1 | `close_shared_embedders()` wired to shutdown + `/pipeline/rebuild/stop` | `src/prep/server.py`, `src/prep/api/routers/pipeline.py` |
| T1.2 | `enable_cpu_mem_arena=False`, `enable_mem_pattern=False` | `src/prep/core/embedder.py` |
| T1.2 | macOS CoreML provider opts: `CPUAndGPU`, `MLProgram`, `RequireStaticInputShapes=1`, `ModelCacheDirectory`, `FastPrediction` | `src/prep/core/embedder.py` |
| T1.2 | Bucket-padded fixed shapes `[128, 256, 512, 1024]` | `src/prep/core/embedder.py` |
| T1.3 | `MAX_LENGTH: 8192 → 1024`, batch GPU 16 / CPU 8, flat scaling | `src/prep/core/embedder.py` |
| T1.3 | Env knobs: `PREP_EMBED_MAX_BATCH`, `PREP_EMBED_MAX_LEN`, `PREP_COREML_USE_ANE`, `PREP_EMBED_LEGACY` | `src/prep/core/embedder.py` |
| T1.4 | Memory guard module with dynamic ceiling | `src/prep/core/memory_guard.py` (new) |
| T1.4 | `embed_batch()` shrinks on guard trip; raises if at batch 1 | `src/prep/core/embedder.py` |
| T1.4 | `PREP_DAEMON_MAX_RSS_GB` env override | `src/prep/core/memory_guard.py` |
| T5.1 | Opt-in daemon RSS sampler thread | `src/prep/services/rss_sampler.py` (new) |
| T5.1 | Wired into daemon lifespan | `src/prep/server.py` |
| Tests | 44 new unit tests | `tests/test_phase139_embedder_memory.py` (new) |
| Tests | Singleton fixture in existing factory tests | `tests/test_embedder_factory.py` |
| CI | Linux + Windows smoke matrix | `.github/workflows/phase139-embedder-smoke.yml` (new) |
| Docs | New CLAUDE.md section "Embedder behavior and memory (Phase 139)" | `CLAUDE.md` |

## Measured wins on this repo (Apple Silicon, 128 GB RAM, macOS 15.0)

Acceptance test: factory-create one shared embedder, embed N real chunks
from `.sourceprep/knowledge_documents.json`, measure peak RSS.

| Workload | Peak RSS | vs incident | Notes |
|---|---:|---:|---|
| Baseline (no embed) | 0.09 GB | — | factory imports only |
| 500 chunks | **0.94 GB** | 100× lower | ~21 s, CoreML CPUAndGPU, batch 16, buckets in use |
| 5000 chunks | **1.94 GB** | 50× lower | ~175 s, ~28 chunks/s |
| Incident (B=128, S=8192) | 100.8 GB | — | for reference, pre-Phase-139 |

Memory guard ceiling computed as `min(32 GB, max(4 GB, 25% × 128 GB))` = **32 GB**;
RSS never approached it during testing.

## Test results

```
tests/test_phase139_embedder_memory.py   44 passed, 1 skipped, 0 failed
tests/test_embedder_factory.py            9 passed, 0 failed
tests/services/pipeline/                 10 passed (no regressions)
tests/services/test_pipeline_provenance   7 passed (no regressions)
```

Broader suite ran clean except for two pre-existing failures unrelated to
Phase 139 (`test_agent_core.py::test_save_observation_delegates` and
`test_agent_prep_data.py::test_delegates_to_observation_store` — both about
`save_observation` signature mismatch with `created_by`/`visibility`).

## Behavioral notes / known properties

### Cross-bucket embedding variance

Embedding the **same chunk** at different bucket sizes produces vectors
with cosine similarity **~0.98**. Verified this is present on **CPU EP
too**, so it is a property of the ONNX model's response to padding
length — not a Phase-139 regression. The pre-Phase-139 code had the same
property (it padded to longest-in-batch, so embeddings already varied
with batch composition). Acceptable for retrieval/clustering use.

### Restart-to-reclaim

Per ORT issues #26831, #22007, #14455, the CoreML EP does not
deterministically release memory after session destruction. `close()`
drops the Python reference and triggers `gc.collect()`, but the
underlying CoreML/ANE allocations may persist until process exit. This
is now documented in CLAUDE.md and is the intended user expectation.

### `model_quantized.onnx` did not need to change

Per RESEARCH.md §3.2 it shrinks weights, not activations; the 100 GB
came from activations. Keeping the quantized model is fine.

## What deferred (not in PR 1)

- **Tier 2 (PR 2):** TEI-style `max_batch_tokens`, length-sorted bucket
  dispatch, `io_binding`. Slated for the next PR.
- **Tier 3 (PR 2):** `NativeEmbedder.close()` is implemented, but the
  idle-timeout release thread is not yet — only explicit close at
  shutdown / rebuild/stop.
- **Tier 4 (deferred):** cloud-only mode. Eric chose not to build this
  since `embedding_source=ollama` already routes to a remote Ollama if
  needed, and cloud embeddings are 3-5× slower for indexing.
- **Tier 5 partial:** RSS sampler is in (T5.1). Embedder-call telemetry
  (T5.2) and CoreML-fallback warning (T5.3) are PR 2.

---

## PR 2 — Tier 2 batching + Tier 3 idle release + Tier 5 telemetry

### What landed (PR 2)

| Tier | What | Files |
|---|---|---|
| T2.1 | Token-budget batching: `PREP_EMBED_MAX_BATCH_TOKENS` (default 8192) instead of fixed batch size. Dispatcher accumulates items until budget × bucket = `len(batch) × bucket_seq > budget`. | `src/prep/core/embedder.py` |
| T2.2 | Length-sorted bucket dispatch: tokenize once, group by smallest matching bucket, sort longest-first within bucket, dispatch one ONNX call per assembled batch, reassemble in original order. | `src/prep/core/embedder.py` |
| T2.3 | **Deferred** — `io_binding` reuse. The PR2 work didn't show a peak-memory win that would justify the complexity, and the cross-bucket cosine quirk noted in PR1 makes buffer-reuse a determinism risk. Reconsider in PR3 if profiling shows it. | — |
| T3.2 | Idle-timeout release thread. On by default at 600s; `PREP_EMBED_IDLE_RELEASE_SEC=0` disables. Polls every `PREP_EMBED_IDLE_POLL_SEC` (default 60s). Calls `close_shared_embedders()` when all cached embedders idle ≥ threshold. | `src/prep/services/idle_release.py` (new), `src/prep/server.py` |
| T5.2 | Per-batch `embed_batch` telemetry event with `batch_size`, `seq_len`, `wall_ms`, `rss_gb`, `provider`. Routed through the same `daemon_rss.jsonl` as T5.1. Opt-in via `PREP_RSS_TELEMETRY=1`. | `src/prep/core/embedder.py` |
| T5.3 | Silent CoreML/GPU → CPU downgrade detection. If the requested first provider differs from the active provider after session create, emits a `WARNING` log line and a `provider_downgrade` telemetry event. | `src/prep/core/embedder.py` |
| Tests | 17 new unit tests (token budget, bucket dispatch correctness, order preservation, idle release timing, telemetry shape). | `tests/test_phase139_pr2_batching.py` (new) |
| Docs | CLAUDE.md env-var table updated with 3 new PR2 knobs. | `CLAUDE.md` |

### Measured numbers (PR 2 acceptance, same repo, same Mac)

| Workload | Peak RSS (PR2) | PR1 | Note |
|---|---:|---:|---|
| 5000 chunks | **2.06 GB** | 1.94 GB | Identical memory; no regression. |
| Time | **177.6 s** | 174.6 s | Identical throughput (~28 chunks/s). |
| Telemetry events | **313** `embed_batch` records | n/a | All in 128-token bucket — confirms CORPUS_PROFILE.md prediction (81% in 128 bucket). |

The corpus profile turned out to be exactly right: every single dispatch
went into the 128-token bucket. Token budget never tightened batch size
below `PREP_EMBED_MAX_BATCH=16` because `8192 // 128 = 64` (the
provider-default cap of 16 was the binding constraint, not the budget).
The budget is the safety rail for "what if someone raises MAX_BATCH to
128 and feeds longer inputs" — it would still cap memory at
~1 GB per call.

### Tuning headroom

For users who want more throughput on machines with headroom, raising
`PREP_EMBED_MAX_BATCH=64` would 4× the per-call work in the 128-token
bucket (the dominant case), while the token budget keeps peak memory
bounded even when longer inputs sneak in. Worth surfacing in the
dashboard as a "performance" preset.

### Tests (PR 2)

```
tests/test_phase139_pr2_batching.py        17 passed, 0 failed
tests/test_phase139_embedder_memory.py     44 passed, 1 skipped (same as PR1)
tests/test_embedder_factory.py              9 passed (same as PR1)
```

Total Phase-139 test surface: **70 passing, 1 skipped, 0 failed.**

### Followup notes for PR 3 (if needed)

1. **`io_binding`** — deferred. Revisit if profiling shows ONNX
   allocator churn in the hot path. Initial PR2 numbers don't suggest
   it's currently a bottleneck.
2. **CoreML EP supports only 96/1422 nodes** of the nomic ONNX graph
   (per the ORT capability log). Most work falls back to CPU EP, so
   the "CoreML acceleration" is marginal. PR3 could measure a clean
   CPU-only baseline and consider defaulting CoreML off entirely.
3. **Cross-bucket cosine ~0.98** for the same content remains. Not a
   PR-2 regression; ONNX-model property. May be investigable by
   forcing single-bucket-per-call (lose memory bound) or by checking
   if there's a `token_type_ids`/positional interaction.
4. **Dashboard surfacing** — `embed_batch` telemetry lands in
   `daemon_rss.jsonl` but isn't shown anywhere in the UI yet. Could
   become a "memory + throughput" panel on the dashboard observability
   page in a follow-up.

## Followup observations for PR 2

1. `_seq_buckets` is set lazily inside `_ensure_loaded()`. We added
   `getattr(self, "_seq_buckets", None)` guards in `_embed_texts()`, but
   any external code that reads `emb._seq_buckets` before the first call
   will hit `AttributeError`. Either init it eagerly in `__init__` or
   wrap external access. Low priority — only matters for introspection.
2. The CoreML EP currently supports only 96/1422 nodes for the
   nomic-embed-text-v1.5 graph (per the ORT warning at session create).
   Most of the work falls back to CPU EP. The "CoreML acceleration" is
   marginal for this model. Worth measuring CPU-only vs CoreML-with-
   options performance in PR 2 to see if the CoreML path is even worth
   keeping.
3. The cross-bucket cosine drop (0.98) is acceptable but worth
   investigating in PR 2 — there may be a `token_type_ids` or
   positional-encoding interaction that's avoidable.
4. `pre-commit` hooks may want to flag `NativeEmbedder()` direct
   construction. The runtime warning is in place; a static check would
   be belt-and-suspenders.
