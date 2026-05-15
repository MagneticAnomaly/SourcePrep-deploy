# Phase 139 — Implementation Plan

> Read [INCIDENT.md](./INCIDENT.md) and [RESEARCH.md](./RESEARCH.md)
> first. This plan assumes the diagnosis (compound: ORT/CoreML memory
> non-release + dynamic-shape recompile hangs + upward-scaling batch
> policy + 9 duplicate sessions) and the research conclusions
> (fixed shapes, token-budget batching, singleton, psutil watchdog,
> OpenAI-compat cloud route).

## Design principles for this phase

1. **Smaller batches on bigger machines, not larger.** The scaling
   was backwards. A 128 GB Mac should batch the same way (or smaller)
   than a 16 GB laptop — peak memory is what matters, not throughput
   for a one-time index.
2. **The user's expectation is the spec.** "All cloud Ollama" must
   mean "no local inference of any kind." Today it only means LLMs.
3. **Restart-to-reclaim is the documented ORT/CoreML reality.** We
   stop pretending we can release CoreML memory at runtime; we
   minimize what we allocate in the first place and make daemon
   restart cheap and explicit.
4. **One InferenceSession per process.** Always. Lazy init, no
   per-call-site duplication, explicit close at shutdown.
5. **Fixed shapes everywhere CoreML can see.** Dynamic shapes are
   what made CoreML hang.
6. **Telemetry first.** We add RSS sampling before changing batch
   policy so we can measure the win.

## Tier 1 — emergency safety net (do before next pipeline run)

These four changes together prevent another 100 GB incident on the next
run. Each is small and independent; ship as separate commits.

### T1.1 — Process-wide embedder singleton

**Problem:** 9+ call sites construct a fresh `NativeEmbedder()`. Each
holds its own InferenceSession + CoreML arena. On macOS each session
costs hundreds of MB minimum, multi-GB once exercised.

**Fix:** Cache one instance per (provider, model) tuple inside
`src/prep/services/embedder_factory.py`.

```python
# sketch — final design TBD
_SHARED_EMBEDDER: dict[tuple[str, str], Any] = {}
_SHARED_EMBEDDER_LOCK = threading.Lock()

def create_embedder(embedding_source=None) -> Any:
    cfg = _resolve_config(embedding_source)        # existing logic
    key = (cfg.kind, cfg.model_id)                 # e.g. ("native", "nomic-...")
    with _SHARED_EMBEDDER_LOCK:
        emb = _SHARED_EMBEDDER.get(key)
        if emb is None:
            emb = _construct(cfg)
            _SHARED_EMBEDDER[key] = emb
        return emb
```

Why thread-safe: ORT `InferenceSession.run()` releases the GIL and is
documented thread-safe (RESEARCH.md §2.1).

Touches:
- `src/prep/services/embedder_factory.py` — add cache.
- `src/prep/services/build_manager.py` (5 call sites) — no change needed; they call the factory.
- `src/prep/services/pipeline/workers/__init__.py:939` — no change needed.
- `src/prep/services/pipeline/orchestrator.py:4395` — replace
  `NativeEmbedder()` direct call with `create_embedder("native")`.
- `src/prep/api/routers/llm.py:320, 362` — same.
- `src/prep/api/routers/trace_routes/enrichment.py:1150` — already uses factory.
- `src/prep/services/headless_runner.py:135` — replace direct call.
- `src/prep/cli.py:685` — leave as-is (one-shot CLI path).

Add `close_shared_embedders()` for shutdown / `pipeline/rebuild/stop`.
Note: per RESEARCH.md §1.1, this will not actually reclaim CoreML
memory at runtime — but it does prevent the duplicate-session
multiplier and gives shutdown a clean release point.

Tests: at least one integration test that constructs two embedders
back-to-back and asserts the same `id(emb._session)`.

**Risk:** low. Thread-safety of ORT is documented; multiple call sites
already happily reuse the same embedder via `build_manager`.

**ROI:** eliminates the duplicate-loading multiplier. ~3× reduction
in baseline embedder footprint on a busy daemon.

---

### T1.2 — Fixed input shapes for CoreML EP

**Problem:** dynamic batch + seq up to 8192 triggers Espresso
recompile + per-shape allocation; the recompile path has hangs in
macOS 15+ (RESEARCH.md §1.2).

**Fix (two-part):**

(a) **At runtime — clamp via SessionOptions and provider options.** In
`NativeEmbedder._ensure_loaded()`:

```python
sess_opts.enable_cpu_mem_arena = False     # RESEARCH.md §2.3
sess_opts.enable_mem_pattern = False       # same
# CoreML provider opts (macOS):
coreml_opts = {
    "MLComputeUnits": "CPUAndGPU",          # skip ANE recompile/hang
    "ModelFormat": "MLProgram",
    "RequireStaticInputShapes": "1",        # dynamic ops fall back to CPU
    "ModelCacheDirectory": str(CACHE_DIR),  # avoid .mlmodelc recompile
    "SpecializationStrategy": "FastPrediction",  # macOS 14+
}
providers = [("CoreMLExecutionProvider", coreml_opts), "CPUExecutionProvider"]
```

(b) **Pad to a single fixed `(batch, seq)` per call.** Pad inputs to
the next bucket ceiling from `[128, 256, 512, 1024]` (per
`CORPUS_PROFILE.md` — 100% of observed corpus fits in ≤512 tokens, the
1024 bucket is safety margin for chunker slack). Pad batch to a
fixed B per provider. Reuse `numpy` buffers via `io_binding`.

Touches:
- `src/prep/core/embedder.py:540-571` — add SessionOptions tuning.
- `src/prep/core/embedder.py:588-622` (`_embed_texts`) — add bucket
  selection + dynamic padding to bucket ceiling + io_binding.

**Risk:** medium. `io_binding` is new code; CoreML provider options
have historically been version-dependent (test against the
onnxruntime version pinned in `pyproject.toml`).

**ROI:** the largest single fix. Eliminates the documented hang path
and bounds per-call memory to bucket size.

---

### T1.3 — Default max_length 1024, batch defaults flat (not upward)

**Problem:** `MAX_LENGTH = 8192` + `_memory_scaled_batch_size()` that
*increases* batch on big machines (RESEARCH.md §3.1).

**Fix (revised after CORPUS_PROFILE.md):**

- Change `NativeEmbedder.MAX_LENGTH` from 8192 → **1024** (was 2048
  in initial plan; profile shows max corpus token-length is 322 with
  chunker capping raw chunks at ~675 worst-case — 1024 gives a clean
  1.5× safety margin).
- Replace `_memory_scaled_batch_size()` with a **flat, conservative**
  default and clamp:
  - GPU/CoreML: batch 16 (was 128)
  - CPU: batch 8 (was 32)
- Expose `PREP_EMBED_MAX_BATCH` and `PREP_EMBED_MAX_LEN` env vars for
  power users to override.

Touches:
- `src/prep/core/embedder.py:473` (MAX_LENGTH)
- `src/prep/core/embedder.py:421-451` (`_PROVIDER_BATCH_SIZES`,
  `_memory_scaled_batch_size`)

**Risk:** low. Worst case: indexing takes longer (acceptable —
correctness > throughput).

**ROI:** moves us off the worst-case quadratic. At batch=16, seq=1024:
- Activations (fp16): ~6.3 GB worst case
- vs ~24 GB at seq=2048
- vs ~380 GB at seq=8192 (original)
- vs ~1.5 TB at batch=128 × seq=8192 (the incident config)

---

### T1.4 — RSS watchdog (refuse new batches above soft ceiling)

**Problem:** no cap on memory at all; only protection is the OS swap.

**Fix:** before each `embed_batch()` call, sample
`psutil.Process().memory_info().rss`. If above the dynamic ceiling
(see formula below), log a warning and either:
(a) shrink the batch to size 1 and continue, or (b) raise
`MemoryCeilingExceeded` if already at batch 1 (true OOM-ahead).

**Ceiling formula (per Eric's Q3 answer):**

```python
ceiling_bytes = min(
    32 * 1024**3,                              # hard cap: 32 GB
    max(4 * 1024**3,                           # floor: 4 GB
        0.25 * psutil.virtual_memory().total)  # 25% of system RAM
)
```

Examples:
- 8 GB box → ceiling 4 GB (floor wins)
- 16 GB box → ceiling 4 GB (floor wins)
- 32 GB box → ceiling 8 GB
- 64 GB box → ceiling 16 GB
- 128 GB box → ceiling 32 GB (cap wins)

Overridable via `PREP_DAEMON_MAX_RSS_GB` env var (absolute GB, takes
precedence).

Touches:
- New `src/prep/core/memory_guard.py` — small module, ~50 lines.
- `src/prep/core/embedder.py:638-652` (`embed_batch`) — wrap with
  guard.
- `src/prep/api/routers/pipeline.py` — surface guard tripped events
  to pipeline_telemetry.jsonl.

**Risk:** low. Read-only telemetry + a soft refusal path.

**ROI:** the early-warning system. We see the spike instead of
hitting swap.

---

## Tier 2 — proper batching (do after Tier 1 is verified)

Bigger refactor; ship after we've measured the Tier-1 footprint and
have a baseline to compare against.

### T2.1 — Token-budget batching (TEI-style)

**Replace** flat `batch_size` with `max_batch_tokens` (default 8192).
The dispatcher sorts the incoming chunk queue by length, fills until
the budget hits, fires.

Touches:
- `src/prep/core/embedder.py:638-652` (`embed_batch`) — replace the
  fixed-stride loop with token-budget accumulator.
- All call sites that pass batches still work (no API change).

**ROI:** memory becomes O(max_batch_tokens × bucket), independent of
input mix. Per RESEARCH.md §3.5, **up to 273× more useful work per
unit memory** on small inputs.

### T2.2 — Length-sorted bucket dispatch

Sort each pipeline-stage's chunk queue by token length, batch
internally so each batch only contains chunks from one bucket.
Buckets: `[128, 256, 512, 1024, 2048]`. Pad within batch to bucket
ceiling.

Touches:
- `src/prep/core/embedder.py` — bucket helper.
- `src/prep/services/pipeline/workers/__init__.py:939+` — pass
  pre-tokenized lengths if available; otherwise tokenize once,
  bucket, then embed.

**ROI:** removes "30-token snippet paying 8192-token cost" pathology.
Realistic 5-20× memory win on our code corpus.

### T2.3 — Pre-allocated `io_binding`

Once shapes are bucketed and fixed (T1.2 + T2.2), allocate one
output buffer per bucket and reuse via `OrtValue` + `io_binding`.
Avoids fp32 (B, S, 768) allocation per call.

Touches:
- `src/prep/core/embedder.py:_embed_texts`.

**ROI:** mostly latency, some peak-memory cleanup. Do last in this
tier.

---

## Tier 3 — lifecycle / cleanup

### T3.1 — Explicit `close()` on the embedder

Add `NativeEmbedder.close()` that:
- Releases tokenizer.
- Sets `_session = None` (no guarantee of CoreML reclaim per
  RESEARCH.md §1.1, but at least drops the Python-side reference).
- `gc.collect()`.

Wire to:
- `close_shared_embedders()` in factory (T1.1).
- `/pipeline/rebuild/stop` handler.
- Graceful daemon shutdown (`SIGTERM`).

### T3.2 — Idle-timeout release

Optional background thread: if no `embed()` call for
`PREP_EMBED_IDLE_RELEASE_SEC` (default 600, opt-in via env), call
`close_shared_embedders()`. Re-init lazily on next call.

Document the trade-off: cold-start latency on re-init (~3–6 s on
macOS per RESEARCH.md §2.2 vLLM Sleep figures).

### T3.3 — Document the restart-as-reclaim reality

Add a note to `CLAUDE.md` and `docs/CONCEPTS.md`: ORT/CoreML do not
deterministically release memory. After a major indexing run, the
daemon's footprint will not return to startup levels until restart.
Set user expectations.

---

## Tier 4 — true cloud-only escape hatch  ❌ DEFERRED

> **Decision (2026-05-15, Eric):** Defer Tier 4 entirely. Cloud
> embeddings are 3-5× slower (network-RTT bound), come with cost and
> rate-limit friction, and the existing `embedding_source=ollama`
> setting already lets users point at a remote Ollama server if they
> need an escape valve. Revisit only if Tier 1-3 prove unable to make
> the local path reliable.

The original T4.1/T4.2 design is preserved below for the historical
record and in case we need it later.

<details>
<summary>Original T4.1 / T4.2 spec (deferred)</summary>

### T4.1 — `embedding_source=cloud` config

Add a third embedding source: `cloud`. Implementation:

- Use OpenAI-compatible `/v1/embeddings` HTTP client (existing
  `OpenAIEmbedder` if any, otherwise new ~60-line class).
- Config shape:
  ```yaml
  llm_config:
    embedding:
      source: cloud
      api_base: https://api.openai.com/v1   # or Ollama Cloud / TEI URL
      api_key_env: PREP_EMBEDDING_API_KEY
      model: text-embedding-3-small         # or nomic-embed-text via TEI
  ```
- Auto-batch via TEI-style `max_batch_tokens` against the remote.

Touches:
- New `src/prep/core/cloud_embedder.py`.
- `src/prep/services/embedder_factory.py` — add the cloud branch.
- `src/prep/api/routers/llm.py` — add settings UI hook.
- Dashboard component — add provider dropdown ("native | ollama |
  cloud (OpenAI-compat)").

### T4.2 — `PREP_EMBED_DISABLE_LOCAL=1` env var

Hard kill switch: if set, the factory refuses to construct a
`NativeEmbedder` at all — raises clear error pointing to cloud
config. Useful for users who never want local inference.

Touches:
- `src/prep/services/embedder_factory.py`.

</details>

---

## Tier 5 — telemetry & observability

### T5.1 — RSS sampling in `pipeline_telemetry.jsonl`

Background thread samples daemon RSS every N seconds, emits
`{"event": "daemon_memory", "rss_gb": ..., "stage": ...}` event.
Correlated with current pipeline stage.

### T5.2 — Embedder-call telemetry

Per-batch event with: bucket, batch size, token count, wall time,
RSS delta. Enables us to see if any stage is hitting a worst-case
path.

### T5.3 — CoreML-fallback warning

Detect when CoreML EP silently downgrades to CPU (per
RESEARCH.md §1.3 it can happen invisibly). Log + telemetry event.

---

## Open questions for Eric

These shape the design — please weigh in before I write code.

1. **Default `MLComputeUnits` on macOS.** RESEARCH says
   `CPUAndGPU` (no ANE) is the conservative pick that avoids the
   hang. But your hardware's ANE is meant to be the fast path. Two
   options:
   - **A:** default to `CPUAndGPU`; add `PREP_COREML_USE_ANE=1`
     opt-in for users who want to try ANE.
   - **B:** keep `ALL` (ANE) but add bucket-fixed shapes to make
     ANE recompiles a one-time cost.
   I lean (A) — getting unstuck matters more than the 2–3× ANE
   speedup, and ANE is unreliable per Apple's own forums on
   macOS 15+.

   --- YES A

2. **Default max_batch_tokens.** 8192 (3× the 768-d embedder model's
   2048-token clamp) is conservative; TEI defaults 16384. Yours is
   a 128 GB box but most users will be on 8–32 GB. Lean **8192
   default** with `PREP_EMBED_MAX_BATCH_TOKENS` override.

   --- sure slightly slower is fine as long as it's reliable 

3. **Default `PREP_DAEMON_MAX_RSS_GB` watchdog ceiling.** 16 GB
   default? Or fraction of `psutil.virtual_memory().total`
   (e.g. 25%)? Fraction is more portable but has the same problem
   as the current "batch up on big machines" — a 128 GB box would
   pick 32 GB, which is still way more than needed.

   --- I think you are saying dynamically use 32GB on larger maching and that's pleanty, if so perdect.

4. **Cloud-only mode rollout.** Ship T4.1 (cloud embedding source)
   and T4.2 (`PREP_EMBED_DISABLE_LOCAL`) in the same release as
   Tier 1, or sequence after? Argument for shipping together:
   users who say "all cloud Ollama" should get a working
   cloud-only path in the same patch. Argument for sequencing:
   T1–T3 fix the existing path; T4 is net-new surface.

   --- I don't see very good reasoon to use cloud here unless this proves to be too unreliable. Cloud is a lot slower with embeddings, right?

5. **Idle-timeout release (T3.2).** Off by default with
   opt-in env, or on by default at 10 min? Cold-start cost is
   real for the dashboard's interactive search.

    -- this seems about right.

6. **Default embedding model going forward.** We currently ship
   nomic-embed-text-v1.5. RESEARCH.md §2.6 notes Ollama bugs on
   it specifically. We could keep it as default but document that
   if you cloud-route to Ollama, switch to a different model.

   --- I don't understand, we reccommend NOT using ollama and just the CPU, and we are now mitigating the CPU issue correct?

---

## Decisions locked in (2026-05-15, Eric)

| # | Question | Decision |
|---|---|---|
| Q1 | macOS `MLComputeUnits` | **A:** default `CPUAndGPU` (no ANE). `PREP_COREML_USE_ANE=1` opt-in. |
| Q2 | `max_batch_tokens` default | **8192.** Slower-but-reliable beats fast-but-stuck. |
| Q3 | Watchdog ceiling | **`min(32 GB, max(4 GB, 25% of total RAM))`.** Env override via `PREP_DAEMON_MAX_RSS_GB`. |
| Q4 | Cloud-only mode | **Defer Tier 4.** Existing `embedding_source=ollama` is the escape valve. |
| Q5 | Idle-timeout release | **On by default, 10 min.** Env override via `PREP_EMBED_IDLE_RELEASE_SEC`. |
| Q6 | Default embedding model | **Keep `nomic-embed-text-v1.5`.** No model change; we're fixing the local path, not abandoning it. |

## Sequencing recommendation

Two PRs, in order:

**PR 1 — "Tier 1: emergency safety net"** (T1.1 + T1.2 + T1.3 + T1.4 +
basic T5.1 + T3.3 docs).
Small, surgical, ships fast. Addresses the immediate incident.
Validate: re-run a full pipeline, confirm peak RSS < 12 GB.

**PR 2 — "Tier 2-3: batching + lifecycle"** (T2.1 + T2.2 + T2.3 +
T3.1 + T3.2 + T5.2 + T5.3).
Larger refactor; ships after PR 1 proves the diagnosis was right.

Tier 4 deferred — no PR planned unless Tier 1-3 prove insufficient.

## Validation plan

For each tier, define a "before/after" measurement:

- **Tier 1:** peak RSS during `prep build --rebuild` on this repo.
  Target: < 12 GB peak vs 100 GB before.
- **Tier 2:** time-to-index this repo + peak RSS. Target: peak < 8 GB,
  time within 1.5× of Tier 1.
- **Tier 3:** RSS after pipeline stop vs at startup. Target: within
  2× of startup (full reclaim is not achievable per ORT bugs).
- **Tier 4:** end-to-end build with `PREP_EMBED_DISABLE_LOCAL=1` +
  cloud Ollama endpoint. Target: works, no local inference threads
  in `sample(daemon-pid)`.
- **Tier 5:** `daemon_memory` telemetry events present for every
  pipeline stage in `pipeline_telemetry.jsonl`.

A regression test will assert peak RSS during a small synthetic
indexing run is below a configurable ceiling, run in CI on macOS.

---

## Followup decisions (Q7-Q11, locked 2026-05-15)

| # | Question | Decision |
|---|---|---|
| Q7 | Sample real corpus token-length distribution before locking bucket boundaries? | **Yes — do it now.** Results go in `CORPUS_PROFILE.md`. |
| Q8 | Wire `close_shared_embedders()` to `/pipeline/rebuild/stop`? | **Yes.** Cold-start cost (3-6s) is acceptable. |
| Q9 | `PREP_EMBED_LEGACY=1` rollback env? | **Yes.** ~10 lines of guard for emergency revert. |
| Q10 | macOS CI smoke job? | **No CI for macOS — Eric validates locally.** But add CI smoke jobs for **Linux + Windows** since Eric has no way to test those platforms. |
| Q11 | Block direct `NativeEmbedder()` calls? | **Runtime warning only.** Recommendation below. |

**Q11 recommendation:** add a one-line `logger.warning(...)` inside
`NativeEmbedder.__init__` that fires when the constructor is called
from outside `embedder_factory.create_embedder`. Cheap (3 lines via
`inspect.stack`), no new tooling, leaves a clear breadcrumb in logs if
a future regression slips in. A ruff rule is overkill for a 9-call-site
surface that already lints clean.

## Cross-platform CI implications (Q10 follow-up)

Tier 1 changes split by platform:

| Change | macOS | Linux | Windows |
|---|---|---|---|
| T1.1 singleton | ✓ | ✓ | ✓ |
| T1.2 SessionOptions (`enable_cpu_mem_arena=False`) | ✓ | ✓ | ✓ |
| T1.2 CoreML provider opts | ✓ | n/a | n/a |
| T1.2 fixed-shape padding + io_binding | ✓ | ✓ | ✓ |
| T1.3 batch/max_length defaults | ✓ | ✓ | ✓ |
| T1.4 RSS watchdog | ✓ | ✓ | ✓ |
| T5.1 telemetry | ✓ | ✓ | ✓ |

Platform-specific provider options must be gated by `sys.platform`:

```python
if sys.platform == "darwin":
    coreml_opts = {...}
    providers = [("CoreMLExecutionProvider", coreml_opts), "CPUExecutionProvider"]
elif sys.platform == "linux":
    # CUDA if available, else CPU. No CoreML.
    providers = _detect_linux_providers()
elif sys.platform == "win32":
    # DirectML if available, else CPU. No CoreML.
    providers = _detect_windows_providers()
```

**Proposed CI matrix for PR 1:**

- GitHub Actions `ubuntu-latest` — runs the full unit test suite + a
  synthetic 100-chunk embed at the fixed shapes, asserts peak RSS
  reasonable.
- GitHub Actions `windows-latest` — same.
- macOS smoke test — manual, Eric runs locally with
  `pytest -m macos_smoke`.

Cost: ubuntu + windows runners are cheap; ~3-5 min for the smoke job.
This catches accidental macOS-only regressions in the singleton /
batching code.

---

## Followup questions (resolved — kept for context)

**Q7 — Token-length distribution of our corpus.**
Bucket boundaries `[128, 256, 512, 1024, 2048]` are based on common
conventions. Before locking them in, I want to sample the actual
token-length distribution of this repo's chunks to confirm
(e.g. is the median 200 or 800?). 5-minute analysis — can run before
writing T2.2. Want me to do that now or fold it into PR 2?

--- YES

**Q8 — Wire `close_shared_embedders()` to `/pipeline/rebuild/stop`?**
Pro: stop button drops embedder cleanly, next run gets a fresh load
(useful if state is weird). Con: 3-6 s cold-start on next embed call.
I lean **yes** — users hit "stop" precisely when they want a clean
slate.

 --- YES

**Q9 — Rollback escape for PR 1.**
`PREP_EMBED_LEGACY=1` reverts T1.2 + T1.3 to pre-Phase-139 behavior
(no CoreML opts, no fixed shapes, original batch sizes). One-line
guard at the top of `_ensure_loaded()`. Lets you revert without a
deploy if PR 1 breaks something on a user's box. Worth ~10 lines?

--- YES

**Q10 — macOS CI for PR 1.**
GitHub Actions `macos-latest` runners are slower and ~5× more
expensive than ubuntu, but we need at least one synthetic CoreML
test or T1.2 is unverified. Add a single macOS smoke job that
loads the embedder, embeds 100 chunks at fixed shapes, and asserts
peak RSS < 4 GB? Or skip CI and rely on local validation?

-- we can test MacOS locally that's fine, we will need to be certian this works on win/linux and I have no way to test

**Q11 — Hard-prohibit direct `NativeEmbedder()` calls?**
With the singleton in `embedder_factory.py`, any future code that
calls `NativeEmbedder()` directly silently regresses to "extra
session per call site." A custom ruff rule or a `__init__` warning
when `_SHARED_EMBEDDER_LOCK` isn't held would catch it. Worth it,
or trust the docstring + code review?

--- I don't understand, I trust your reccommendation here
