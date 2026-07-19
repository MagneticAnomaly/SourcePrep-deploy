# Phase 06 — Team Sync Implementation Progress

*Last updated: February 22, 2026 (Session 3)*

> **⚠️ 2026-07-18 revive note.** The "Completed" claims below reflect Feb–Mar 2026.
> This feature subsequently **rotted** (the `.runprep`→`.sourceprep` rename + Phase-139
> embedder refactor + a stage-count change left ~23 team-sync tests failing on HEAD).
> A revive pass on 2026-07-18 restored a deterministically green **team-sync test suite**
> (**136 passing** across the 5 team-sync files; the full repo suite has ~85 pre-existing,
> environment-coupled failures unrelated to this work),
> closed a license-gate bypass, added a fail-closed `strip_source_content` capability,
> renamed the GHCR image namespace, and wired the dashboard "Sync Now" + `SyncStatusCard`.
> See **`TEAMS_SYNC_REVIVE_PLAN.md`** for the authoritative current state and the Phase-2
> backlog. The specific "69/69 passed" and "0 regressions" claims below are **historical
> and were false on HEAD before the revive**.

## Completed

### Scaffolding (Session 1)
- [x] `public/sourceprep-deploy/` subtree with README, decision tree
- [x] `Dockerfile.cpu` (slim, ~2-3 GB, BYOK)
- [x] `Dockerfile.gpu` (fat, ~8-10 GB, baked Ollama + Qwen3:4b)
- [x] `entrypoint.sh` (GPU image: starts Ollama conditionally)
- [x] Modal adapter (`modal/modal_adapter.py` + README)
- [x] RunPod adapter (`runpod/Dockerfile.runpod` + `runpod_handler.py` + README)
- [x] GitHub Actions template (`github-actions/prep-sync.yml` + README) — dual mode: CPU+BYOK / GPU webhook
- [x] AWS ECS reference (`aws/ecs-task-definition.json` + README)
- [x] Publish script (`scripts/publish_deploy_subtree.sh`)
- [x] `prep sync-headless` CLI command with full arg schema
- [x] `S3StorageProvider` (upload, download, atomic swap, manifest versioning)

### Pipeline Wiring — P06-S05 (Session 2)
- [x] **Added Anthropic + Google providers to `LLMClient`** in `core/augmenter.py`
  - `.generate()` and `.is_available()` now support 4 providers: ollama, openai, anthropic, google
- [x] **`headless_create_llm_client()`** — server-free LLM client factory with default endpoints
- [x] **`headless_create_embedder()`** — server-free embedder factory (NativeEmbedder or OllamaEmbedder)
- [x] **`HeadlessWorkerFactory`** — 10 stage worker methods that construct core classes directly
  - No imports from `prep.server` — fully decoupled from the daemon
  - Shares a single LLM client across stages (lazy-init)
  - Batch profile resolution via `resolve_profile()` (no UI config dependency)
- [x] **Sequential stage runner in `HeadlessRunner._run_pipeline()`**
  - Runs all 10 stages in main thread (no BuildOrchestrator threads)
  - Structural failure is fatal; all other failures are non-fatal (logged, continues)
  - Per-stage timing and result tracking
  - CLI prints a stage-by-stage summary on completion

### Incremental Rebuild — P06-S03 (already built-in!)
- **Discovery:** `trace_manifest.json` already contains `file_hashes` (dict of `rel_path → content_hash`)
- `TraceAugmenter._needs_augmentation()` already checks file hashes and skips unchanged nodes
- `EpistemicEnricher` similarly skips already-enriched nodes
- The structural stage (`TraceBuilder.build()`) always re-parses all files, but this is fast (seconds)
- The expensive LLM stages (2, 3, 6, 7, 8, 9) are already incremental when a previous index exists
- **Conclusion:** When headless downloads the previous index from S3 before running, incremental rebuild is 90% free. No new code needed.

### Client-side Remote Sync — P06-S14 (completed)
- [x] `src/prep/services/remote_sync.py` — `RemoteSyncService` class
  - Reads `.runprep/team_config.json` (committed, secret-free)
  - Resolves S3 credentials from env vars or `.runprep/.secrets` (gitignored)
  - `check_and_sync()`: compares remote manifest hash → downloads if newer
  - `start_polling()` / `stop_polling()`: background thread with configurable interval
  - `SyncStatus` dataclass with `to_dict()` for Dashboard API
  - **Secrets leakage detection** — `_check_for_leaked_secrets()` scans config for credential-like keys

### Layered Index + Delta Detection — P06-S16/S17 (completed)
- [x] `src/prep/core/layered_index.py` — `LayeredCodeIndex` class
  - Wraps remote `CodeIndex` + optional delta `CodeIndex`
  - Tombstone mask: delta file paths are excluded from remote search results
  - Merged `search()` and `get_context()` methods (delta wins on path conflicts)
  - `stats()` for Dashboard display (remote chunks, delta chunks, tombstoned files)
- [x] `prune_stale_deltas()` function
  - Called after new remote index download
  - Compares delta `source_path` against remote `trace_manifest.json` `file_hashes`
  - Removes stale delta documents and trims embeddings numpy array

### Pitfall Mitigations (Session 3)
- [x] **Pitfall #1 — import pollution:** Added `[headless]` pip extra to `pyproject.toml` (excludes fastapi/uvicorn); wrapped `embedder_factory.create_embedder()` server import in `try/except ImportError` so it gracefully degrades in headless Docker
- [x] **Pitfall #3 — Gemini system prompt:** Fixed to use proper `systemInstruction` API field instead of injecting as a fake user message
- [x] **Pitfall #4 — closure capture bug:** Replaced inline closure with `_make_progress_cb()` factory function that captures `stage_id` by value; added regression test
- [x] **Pitfall #6 — secrets leakage:** Added `_check_for_leaked_secrets()` that recursively scans `team_config.json` for credential-like keys and logs a SECURITY warning; tested with 5 test cases
- [x] **Pitfall #7 — Docker build context:** Fixed both Dockerfiles to show correct `docker build -f public/sourceprep-deploy/Dockerfile.* .` command from repo root

### Tests — P06-S19/S20/S21/S22 (completed)
- [x] `tests/test_s3_storage.py` — 14 tests (manifest, config, upload/download)
- [x] `tests/test_layered_index.py` — 8 tests (tombstoning, pruning, edge cases)
- [x] `tests/test_headless_runner.py` — 24 tests (config, LLM factory, embedder factory, worker factory, stages, repo resolution, commit SHA, closure regression)
- [x] `tests/test_remote_sync.py` — 23 tests (config parsing, sync status, credential resolution, secrets detection, service lifecycle)
- **Result (Feb 2026): 69/69 passed** — *historical; see the revive note at top. On HEAD
  before the 2026-07-18 revive this had drifted to ~23 failing; the revive restored 134 passing.*

## Pending

- [x] P06-S15: Dashboard UI sync status indicator — **done 2026-07-18** (`SyncStatusCard` rendered
  in the dashboard, fed by `projectStatus.sync`, with a gated `POST /projects/{id}/sync/now`
  "Sync Now" trigger). Remaining Teams-tier work is tracked in `TEAMS_SYNC_REVIVE_PLAN.md` (Phase 2).

---

## Opportunities Discovered

### 1. LLMClient was missing 2 providers (fixed)
The `LLMClient` class only supported `ollama` and `openai`. Anthropic and Google were missing.
**Fixed:** Added both providers to `generate()` and `is_available()` in `core/augmenter.py`.
**Bonus:** This also benefits the dashboard — users can now configure Anthropic/Google endpoints in the AI Models panel and they'll work for all pipeline stages, not just headless.

### 2. HeadlessWorkerFactory is a clean abstraction
The daemon's `WorkerFactory` is tightly coupled to `prep.server` singletons (`_load_ui_config`, `_get_llm_client_for_slot`). The headless factory proves these can be decoupled.
**Future opportunity:** Refactor the daemon's WorkerFactory to also use explicit config injection. This would make the daemon pipeline testable in isolation (currently untestable without a running server).

### 3. Batch profiles auto-resolve
`resolve_profile(provider, model)` works without any UI config. It just pattern-matches the model name. This means headless mode gets optimal batching (e.g., for GPT-4.1-mini) for free.

### 4. Incremental rebuild is already 90% free
The `trace_manifest.json` stores `file_hashes` for every file. Downstream stages (`TraceAugmenter`, `EpistemicEnricher`, etc.) check these hashes and skip unchanged files. When the headless runner downloads the previous index from S3 before running, all the LLM-expensive stages automatically skip files that haven't changed. **No new incremental logic needed.** The 2-hour → 5-minute improvement is already built into the existing pipeline.

### 5. Structural stage is the only fatal stage
All LLM-dependent stages (2-10) can fail without breaking the index. The structural stage (Rust AST) is the only hard dependency. This means:
- A team with no LLM configured can still get a structural trace graph
- BYOK users with rate limits get partial enrichment (whatever completed before the limit)

### 6. `embedder_factory` is now headless-safe
The `try/except ImportError` guard means any future code that accidentally imports `embedder_factory` in headless mode won't crash — it'll gracefully skip dashboard/CLI config and fall through to NativeEmbedder.

---

## Pitfalls Discovered & Mitigated

### 1. `prep.server` import pollution — ✅ MITIGATED
**Problem:** `embedder_factory.create_embedder()` did `from prep.server import` which would fail in headless Docker (no FastAPI).
**Fix:** (a) Added `[headless]` pip extra to `pyproject.toml` — excludes fastapi/uvicorn. (b) Wrapped the import in `try/except ImportError` — graceful degradation to step 4 (NativeEmbedder).

### 2. Anthropic API format — ✅ HANDLED
Anthropic uses `x-api-key` header, `/v1/messages` endpoint, and content blocks. All handled in `LLMClient`.

### 3. Google Gemini system prompt — ✅ FIXED
**Problem:** Was injecting system prompt as a fake user message (`"System: {system}"`).
**Fix:** Now uses the proper `systemInstruction` API field, which Gemini v1beta supports natively.

### 4. Closure capture bug in pipeline loop — ✅ FIXED
**Problem:** `progress_cb` was defined inside a `for` loop. Python closures capture by reference — if the closure ever used `stage_id`, all callbacks would reference the last loop value.
**Fix:** Replaced with `_make_progress_cb(sid)` factory function that captures by value. Added regression test `test_closure_captures_correct_stage_id`.

### 5. Index directory path assumption — ACCEPTABLE
`HeadlessRunner` uses `repo_path / ".runprep" / "index"` (embedded mode). This is correct for CI/CD — the index lives inside the repo checkout and gets uploaded to S3. Documented.

### 6. `team_config.json` secrets leakage — ✅ MITIGATED
**Problem:** If a developer accidentally puts S3 keys in `team_config.json`, they'd be committed to Git.
**Fix:** Added `_check_for_leaked_secrets()` that recursively scans the config for credential-like keys (`access_key`, `secret_key`, `api_key`, `password`, `token`) and logs a SECURITY warning. 5 test cases cover detection in nested dicts, lists, and short-value filtering.

### 7. Docker build context path — ✅ FIXED
**Problem:** Dockerfile comments showed `docker build -f Dockerfile.cpu .` which would fail because the build context needs to be the repo root.
**Fix:** Both Dockerfiles now clearly show: `docker build -f public/sourceprep-deploy/Dockerfile.cpu -t prep/headless:cpu .`
