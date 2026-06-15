# Part 09 Step 2 — Chunked synthesis design

> **Status:** Design — pending implementation
> **Parent:** Part 09 README (this directory) · work order in `docs/PARALLEL_LANES_2026-05-26.md`
> **Depends on:** Step 1 (commit `7a338adb` on `phase-136-part09`) for the diagnostic surface
> **Merge strategy:** Option A — build on branch, gate the merge on Step 1 telemetry

## Background

The 2026-05-17 / 5/18 / 5/28 `concepts_synthesis_failed` events share a fingerprint: ~1795 fallback concepts, ~1334 fallback questions, ~798 successful workers. The README's revised diagnosis says synthesis returns empty or unparseable on the consolidation prompt. The likely cause (per the README's "Path A" hypothesis) is that the consolidation prompt for 798 workers × ~2.5K chars of T4 enrichment hits the model's output-token cap before it can emit valid JSON.

Step 1 added a diagnostic surface (`raw_synthesis_text`, `synthesis_prompt_chars`, `failure_mode` classifier) so the next live `concepts_synthesis_failed` event will tell us which of four modes actually fires: `no_workers`, `no_text`, `parse_failed`, `parsed_but_empty`. Step 2 is the Path A fix.

## Goal

When the synthesis input would otherwise exceed what the LLM can consolidate in a single output budget, split it into chunks, synthesize each chunk, then synthesize-the-syntheses into a final consolidated result. Preserve the existing single-call path for runs that don't need chunking.

## Non-goals

- Path B (wire fallback seed concepts into Phase 125c refinement) — that's Step 3.
- Auto-tuning chunk size by model. Single hardcoded default with one env override.
- Per-chunk retry on failure. Best-effort: a chunk either parses or doesn't.
- Parallelizing chunks. Serial dispatch in V1. The AIMD gate already throttles concurrent requests; parallelizing would add coordination without changing the scheduler-imposed real-world rate.
- Telemetry per-chunk raw text. Step 1's head/tail of the meta response is sufficient for diagnosis.

## Caveat — we may be fixing the wrong problem

Step 2 is being built before Step 1 telemetry has come in. If the live failure mode turns out to be `parse_failed` (model emitting `<think>` tags or pure prose instead of JSON), chunking will not help — each chunk would emit the same reasoning text. Threshold-gating prevents regression on healthy runs, but the fix would be a no-op.

Merge gate: do not merge Step 2 to `main` until the next post-restart rebuild produces a `concepts_synthesis_failed` event whose `failure_mode` is `parsed_but_empty` AND `synthesis_prompt_chars` is above the chunking threshold. If those don't hold, Step 2 stays on the branch and Step 3 (Path B) takes priority.

## Architecture

### Dispatch layer

`SwarmOrchestrator._synthesize` becomes a thin dispatcher:

```
def _synthesize(self, worker_results, synthesis_prompt, event_log=None):
    successful = [r for r in worker_results if r.success and r.parsed]
    if not successful:
        # existing skip-synthesis path (unchanged)
        return None, 0, None, 0

    if len(successful) > self.synthesis_chunk_max_workers:
        return self._synthesize_chunked(
            successful, synthesis_prompt, event_log=event_log,
        )
    return self._synthesize_single(
        successful, synthesis_prompt, event_log=event_log,
    )
```

- `_synthesize_single` is the existing `_synthesize` body, renamed. No behavior change.
- `_synthesize_chunked` is new. Returns the same 4-tuple as `_synthesize_single`: `(parsed, tokens, raw_text, prompt_chars)`.

### Threshold + configuration

- Trigger: `len(successful_workers) > synthesis_chunk_max_workers`.
- `synthesis_chunk_max_workers` is read from `PREP_SYNTHESIS_CHUNK_MAX_WORKERS` env at `__init__`, default `200`. Stored as an instance attribute so tests can construct an orchestrator with a smaller threshold.
- Char-based trigger considered and rejected: input prompt size is a noisy proxy for output JSON size (consolidation deduplicates aggressively), so a worker-count threshold is more honest.

### Chunking

- Sort successful workers by `item_id` (deterministic, makes test fixtures + production debug logs reproducible).
- Slice into consecutive batches of up to `synthesis_chunk_max_workers`. Last chunk may be smaller.
- For 798 workers at threshold 200: 4 chunks of (200, 200, 200, 198).

### Per-chunk dispatch

Each chunk runs the existing `_synthesize_single` LLM-call path with the same synthesis prompt. Per-chunk outcome is one of:

- success → chunk's parsed JSON joins the meta input list
- parse_failed → chunk is dropped from meta input; counted in event log
- LLM timeout/error → chunk is dropped; counted

Between every chunk dispatch (and before the meta call), the orchestrator checks `_hold_paused()`. On hold, `HoldPausedError` is raised — `execute()`'s existing handler catches it and returns a `paused=True` SwarmResult.

### Meta synthesis

After all chunks are processed (call the running tally of per-chunk LLM-call tokens `sum_chunk_tokens` and the running tally of per-chunk prompt sizes `sum_chunk_prompt_chars`):

- If 0 chunks succeeded → return `(None, sum_chunk_tokens, None, sum_chunk_prompt_chars)`. The meta call is skipped. The existing concept_seeder fallback runs against raw worker outputs. `failure_mode = chunked_all_failed`. **Per-chunk raw response text is not persisted** in SwarmResult — operators wanting per-chunk failure detail should consult the swarm event log (`event_log.parse_failure(where="synthesis", ...)` is recorded per chunk).
- If ≥1 chunk succeeded → call `_synthesize_single` once more with the chunk parsed results formatted as the `{worker_outputs}` payload (each chunk's parsed dict serialized as JSON, joined the same way the original prompt joins workers).
  - Meta succeeds → return `(meta_parsed, sum_chunk_tokens + meta_tokens, meta_text, sum_chunk_prompt_chars + meta_prompt_chars)`. `failure_mode` does not apply (synthesis succeeded).
  - Meta fails → return `(union_of_chunk_results, sum_chunk_tokens + meta_tokens, meta_text, sum_chunk_prompt_chars + meta_prompt_chars)`. `failure_mode = chunked_meta_failed`. Manually dedupe concepts by `title.lower().strip()` and questions by `(question.lower().strip(), target_module.lower().strip())` — mirrors the existing `concept_seeder.py:889-909` fallback dedup so behavior is consistent.

### Meta prompt — reuse same template

V1 uses the same `synthesis_prompt` for the meta call. The prompt's `{worker_outputs}` placeholder gets the per-chunk parsed dicts, formatted the same way single-call formats worker outputs (`### {item_id}\n```json\n{json.dumps(parsed, indent=2)}\n```\n\n`). Item id for each chunk is `chunk-N`.

Known risk: the same prompt may over-deduplicate legitimate cross-module patterns when the input is already-deduped partial syntheses. V1 accepts this risk; if quality telemetry shows the effect, V2 adds a `meta_synthesis_prompt` parameter that consumers can override.

### Telemetry — SwarmResult

New field:

```python
synthesis_chunk_count: int = 1
```

`1` means single-call path (or chunking was eligible but only one chunk's worth of workers). `N > 1` means N chunks + 1 meta call. No `synthesis_chunks_succeeded` counter — the existing `failure_mode` classifier in `_synthesis_diagnostic_fields` carries that information.

### Telemetry — diagnostic helper

`concept_seeder._synthesis_diagnostic_fields` gains two new `failure_mode` values:

| `failure_mode` | Meaning | Path |
|---|---|---|
| `chunked_meta_failed` | Chunks succeeded, meta failed, returned manually-deduped union | `synthesis_chunk_count > 1` AND meta returned None AND we returned a non-empty parsed dict |
| `chunked_all_failed` | All chunks failed, returned None | `synthesis_chunk_count > 1` AND every chunk returned None |

Classification logic in `_synthesis_diagnostic_fields`:

```python
chunk_count = getattr(result, "synthesis_chunk_count", 1)
meta_failed = getattr(result, "synthesis_meta_failed", False)

if raw_text is None:
    if prompt_chars == 0:
        failure_mode = "no_workers"
    elif chunk_count > 1:
        failure_mode = "chunked_all_failed"
    else:
        failure_mode = "no_text"
elif synthesis is None:
    failure_mode = "parse_failed"
elif chunk_count > 1 and meta_failed:
    failure_mode = "chunked_meta_failed"
else:
    failure_mode = "parsed_but_empty"
```

The `chunked_meta_failed` detection from outside `SwarmOrchestrator` is awkward: by the time concept_seeder reads the result, `synthesis` carries the union-of-chunks (truthy) and `raw_text` carries the meta failure response — indistinguishable from a single-call run that returned an empty parsed dict. To make this unambiguous, `SwarmOrchestrator` exposes an explicit `synthesis_meta_failed: bool = False` field that is set to `True` only when chunks-survived-meta-failed. The diagnostic classifier reads this field rather than re-deriving.

### Logging

`SwarmOrchestrator._synthesize_chunked` logs at INFO:

- on entry: `Chunked synthesis: %d workers split into %d chunks of ~%d`
- per chunk: `Chunk %d/%d: synthesizing %d workers...` and `Chunk %d/%d: %s (%d tokens)` (success / parse_failed / no_text)
- meta dispatch: `Meta-synthesis: %d/%d chunks succeeded, dispatching meta over %d partial syntheses` (or skip + log `chunked_all_failed` and return early)
- meta outcome: `Meta-synthesis: success (%d tokens)` or `Meta-synthesis: failed; returning manually-deduped union of %d chunks`

`event_log.phase_end("synthesizer", ...)` fires once at the end with the same shape as today — the dashboard doesn't need to know about chunks at the swarm-event level.

### Cost + latency

- Cost: K+1 LLM calls vs 1. For 798 workers at threshold 200, that's 5 LLM calls. At cloud rates, roughly 5× more expensive on the synthesis phase ONLY when the threshold fires. Worker fan-out cost (~798 calls) dwarfs this.
- Latency: serial dispatch. K+1 × per-call latency. At ~30s per cloud synthesis call, 5 calls = ~150s where 1 call was ~30-60s. Acceptable vs. total failure.
- These trade-offs only apply on runs that would otherwise fail. Healthy runs (fewer workers) stay on the cheap single-call path.

## Failure modes summary

| Outcome | `synthesis` | `raw_synthesis_text` | `synthesis_chunk_count` | `synthesis_meta_failed` | `failure_mode` |
|---|---|---|---|---|---|
| Single-call success | dict | str | 1 | False | n/a |
| Single-call no workers | None | None | 1 | False | `no_workers` |
| Single-call LLM timeout | None | None | 1 | False | `no_text` |
| Single-call parse failed | None | str | 1 | False | `parse_failed` |
| Single-call parsed but empty concepts | dict (no concepts) | str | 1 | False | `parsed_but_empty` |
| Chunked success | meta dict | meta str | N>1 | False | n/a |
| Chunked all chunks failed | None | None | N>1 | False | `chunked_all_failed` |
| Chunked meta failed, survivors deduped | union dict | meta str | N>1 | True | `chunked_meta_failed` |
| Chunked meta parsed but empty | meta dict (no concepts) | meta str | N>1 | False | `parsed_but_empty` |

## Tests

New file `tests/test_synthesis_chunked.py`. Coverage:

| # | Test | What it pins |
|---|---|---|
| 1 | `test_below_threshold_uses_single_call` | At 199 successful workers and threshold 200, `_synthesize_single` runs once, `_synthesize_chunked` is not invoked. `synthesis_chunk_count == 1`. |
| 2 | `test_above_threshold_dispatches_correct_chunk_count` | At 798 workers, threshold 200, chunks dispatched in sizes (200, 200, 200, 198). `synthesis_chunk_count == 4`. |
| 3 | `test_chunk_results_deterministic_by_item_id` | Workers fed in shuffled order produce the same chunk boundaries as sorted-by-item_id workers. |
| 4 | `test_meta_synthesis_called_with_chunk_outputs` | After all chunks succeed, meta receives one `{worker_outputs}` payload containing the per-chunk parsed dicts. |
| 5 | `test_chunked_some_chunks_fail_meta_gets_survivors` | 2 of 4 chunks parse-fail; meta is called with the 2 survivors. |
| 6 | `test_chunked_all_chunks_fail_returns_none` | All chunks return None; result is `(None, sum_tokens, None, sum_prompt_chars)`; `synthesis_chunk_count == 4`. |
| 7 | `test_chunked_meta_fails_returns_deduped_union` | Chunks succeed; meta fails; result.synthesis is the union; duplicate titles + duplicate questions are collapsed. `synthesis_meta_failed == True`. |
| 8 | `test_chunked_pause_between_chunks_propagates_hold_paused` | Mock `_hold_paused` to return True after chunk 1; the function raises `HoldPausedError`; chunks 2-4 and meta are NOT dispatched. |
| 9 | `test_chunked_pause_before_meta_propagates_hold_paused` | Mock `_hold_paused` to return True after all chunks succeed but before meta; raises HoldPausedError. |
| 10 | `test_env_var_overrides_default_threshold` | `monkeypatch.setenv("PREP_SYNTHESIS_CHUNK_MAX_WORKERS", "10")` → 11 workers triggers chunking. |
| 11 | `test_diagnostic_failure_mode_chunked_all_failed` | `_synthesis_diagnostic_fields` returns `chunked_all_failed` for a result with `synthesis_chunk_count > 1`, `synthesis=None`, `raw_text=None`. |
| 12 | `test_diagnostic_failure_mode_chunked_meta_failed` | Returns `chunked_meta_failed` for a result with `synthesis_chunk_count > 1`, `synthesis=dict(survivors)`, `synthesis_meta_failed=True`. |
| 13 | `test_swarm_result_synthesis_chunk_count_default_is_1` | Backward compat: existing callers see `synthesis_chunk_count == 1`. |
| 14 | `test_swarm_result_synthesis_meta_failed_default_is_false` | Backward compat: existing callers see `synthesis_meta_failed is False`. |

All tests run in-process with mocked `_llm_call_with_timeout`. No daemon, no real LLM, no I/O.

## Acceptance criteria

Step 2 is shipped when:

1. All 14 tests above pass on the `phase-136-part09` branch.
2. Existing `test_synthesis_diagnostic.py` (Step 1's 14 tests) still passes — no regression in classification logic.
3. Existing `test_soft_hold_primitive.py` still passes — `HoldPausedError` propagation unchanged.
4. Existing `test_cluster_parallel_batched.py` still passes — small-N callers stay on single-call path.
5. The branch is **not** merged until Step 1 telemetry from the next live rebuild produces a `concepts_synthesis_failed` event with `failure_mode = parsed_but_empty` AND `synthesis_prompt_chars > 1_500_000`. If telemetry shows a different cause, the branch is kept for reference and Step 3 takes priority.

## Risks (acknowledged)

| Risk | Mitigation |
|---|---|
| Wrong root cause — failure is `parse_failed` not output-cap | Threshold-gated, single-call path preserved. Merge gate above prevents wasted production rollout. |
| Same prompt over-dedupes at meta level | V1 accepts. V2 adds `meta_synthesis_prompt` override if quality telemetry shows it. |
| Cross-module patterns scattered across chunks | V1 accepts. Better than total synthesis failure. |
| 5× cost on synthesis phase when chunking fires | Documented. Worker fan-out cost dwarfs synthesis cost; net rebuild cost change is small. |
| 5× latency on synthesis phase when chunking fires | Documented. Better than re-running synthesis from scratch after silent failure. |

## File scope

```
src/prep/core/swarm_orchestrator.py
  - rename _synthesize body → _synthesize_single
  - new dispatcher _synthesize (calls _single or _chunked)
  - new _synthesize_chunked method
  - SwarmResult gains synthesis_chunk_count + synthesis_meta_failed

src/prep/core/concept_seeder.py
  - _synthesis_diagnostic_fields gains two failure_mode branches

tests/test_synthesis_chunked.py          (new, 14 tests)
tests/test_synthesis_diagnostic.py       (extend with chunked classifier cases)
```

No changes to cluster.py / atlas/generator.py / group_reasoning.py. Their swarm-worker counts stay well under the 200 threshold; they keep using the existing single-call path.

## Out of scope for Step 2

- Path B (Phase 125c refinement intake) — Step 3.
- Per-model auto-tuning of threshold — V2 if telemetry shows distinct per-model failure profiles.
- Parallelizing chunk dispatch — V2 if latency becomes a complaint.
- A `meta_synthesis_prompt` parameter — V2 if same-prompt over-dedup shows up.
- User-pause (`cancel_token`) checks between chunks. The existing API doesn't plumb `cancel_token` into `_synthesize`; soft-hold checks via `_hold_paused()` are honored between chunks, but a user-initiated pause would only be detected at `execute()`'s next phase boundary (i.e., after the full chunked synthesis completes). Acceptable for V1 — V2 adds `cancel_token` if user-pause latency becomes a complaint.
- Persisting per-chunk raw response text in `SwarmResult`. Per-chunk parse failures are recorded in the swarm event log via `event_log.parse_failure(...)`; only the meta response text is bubbled to `SwarmResult.raw_synthesis_text` to keep memory + telemetry payload sizes bounded.

## Cross-refs

- Step 1: commit `7a338adb` on `phase-136-part09`
- Part 09 README: `docs/Phase136_Dogfood-fixes/Part09_SynthesizerWallTimeRegression/README.md`
- Lane B closeout: `docs/PARALLEL_LANES_2026-05-26.md` (Lane B section)
- Phase 141 swarm machinery: `compute_swarm_wall_budget`, `IntegrityGuard` — Part 09 leans on these, doesn't duplicate
