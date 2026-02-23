# Phase 06 — Team Sync Testing Strategy & TODO

*Created: February 22, 2026*
*References: `PROGRESS.md`, `TODO.md`, implementation files*

---

## Current Test Coverage

### Existing Unit Tests (69/69 passing, 0.75s)

| File | Tests | Covers |
|------|-------|--------|
| `tests/test_s3_storage.py` | 14 | SyncManifest roundtrip, S3Config env resolution, validation, key generation, upload/download mocks |
| `tests/test_layered_index.py` | 8 | Tombstone masking, delta pruning, from_dirs fallback, stats |
| `tests/test_headless_runner.py` | 24 | HeadlessConfig, LLM/embedder factories (all 4 providers), WorkerFactory lazy init, batch profile, stage definitions, repo resolution, commit SHA, closure regression |
| `tests/test_remote_sync.py` | 23 | TeamSyncConfig parsing, SyncStatus serialization, credential resolution (env/file/priority), secrets leakage detection, RemoteSyncService lifecycle |

### What's Tested Well
- **Config parsing and validation** — all config dataclasses have roundtrip tests
- **Credential resolution** — env vars, .secrets file, priority ordering
- **Security** — secrets leakage detection with 5 scenarios (nested, lists, short-value filtering)
- **Factory functions** — all 4 LLM providers, native/ollama embedder, batch profile resolution
- **Data structures** — SyncManifest, SyncStatus, StageResult, S3Config

### What's NOT Tested Yet

#### Critical Gaps
1. **HeadlessRunner._run_pipeline() end-to-end** — The 10-stage sequential runner (lines 490-561 of headless_runner.py) is the core logic but has no test. Each stage worker is mocked individually, but the orchestration logic (fatal vs non-fatal failure handling, stage ordering, progress callbacks, timing) is untested.

2. **S3StorageProvider real I/O** — Upload/download are mocked. No test verifies actual zip creation, extraction, or manifest writing to disk.

3. **LayeredCodeIndex search merging** — Tests verify tombstone masking on mocked data but don't test actual embedding-based search across two real CodeIndex instances.

4. **RemoteSyncService.check_and_sync() with real S3** — The sync loop is tested for config/credential resolution but the actual download+compare flow is only tested against mocks.

5. **CLI `codrag sync-headless` integration** — No test invokes the CLI command end-to-end.

6. **Dashboard wiring** — `TeamSyncIndicator.tsx` exists but is not wired into `App.tsx`. No API endpoint exposes `RemoteSyncService.status_dict()`.

---

## Testing Strategy

### Tier 1: Unit Tests (extend existing — LOW effort)

These can be added immediately with mocks, no infrastructure needed.

#### T1-1: HeadlessRunner orchestration logic
- Test that structural failure raises RuntimeError (fatal)
- Test that non-structural failures are logged and skipped (non-fatal)
- Test stage ordering matches HEADLESS_STAGES
- Test stage_results are populated correctly on mixed success/failure
- Test total timing is reported
- Mock all workers to return instantly

#### T1-2: HeadlessRunner._clone_repo()
- Test GIT_TOKEN injection into HTTPS URL
- Test SSH URL is passed unmodified
- Test stderr sanitization (token not leaked in error messages)
- Test shallow clone flags (--depth 1, --single-branch)

#### T1-3: HeadlessRunner._download_existing_index()
- Test no-op when manifest is None (full build fallback)
- Test graceful fallback when download fails

#### T1-4: S3StorageProvider zip creation
- Test upload_index creates a valid zip from a temp directory with real files
- Test download_index extracts a zip to the correct directory
- Test atomic swap (tmp key → final key)
- Test manifest.json is written alongside the zip

#### T1-5: LayeredCodeIndex.get_context()
- Test context string assembly with mixed remote/delta results
- Test max_chars truncation
- Test header formatting (section, source_path, score)

#### T1-6: SyncStatus.behind_minutes edge cases
- Test None when both timestamps are None
- Test None when local is newer than remote
- Test correct calculation when remote is newer

### Tier 2: Integration Tests (MEDIUM effort)

These test real interactions between components but still use local mocks for S3.

#### T2-1: Headless CLI end-to-end (fixture repo)
- Use `tests/fixtures/mini_repo/` as a pre-cloned repo
- Mock the LLM client to return canned responses
- Mock S3 to write to a temp directory
- Run `HeadlessRunner.run()` and verify:
  - Index directory has expected artifacts (documents.json, embeddings.npy, trace_manifest.json)
  - Stage results show 10 entries
  - Structural stage succeeds
  - SyncManifest has correct branch and commit_sha
- File: `tests/test_headless_e2e.py`

#### T2-2: Incremental rebuild
- Seed an index directory with a previous trace_manifest.json containing file_hashes
- Run headless pipeline with one file changed
- Verify that only the changed file was re-augmented (check augmenter call count)
- File: `tests/test_headless_e2e.py`

#### T2-3: Layered search with real indexes
- Build a small CodeIndex from fixture data (remote)
- Build another small CodeIndex with one modified file (delta)
- Create LayeredCodeIndex and run search
- Verify delta version is returned for the modified file
- Verify remote version is returned for unchanged files
- File: `tests/test_layered_index.py` (extend existing)

#### T2-4: Client sync + delta pruning
- Create a fake remote index in a temp directory
- Create a fake delta index with overlapping files
- Call prune_stale_deltas()
- Verify documents.json is rewritten with stale entries removed
- Verify embeddings.npy is trimmed to match
- File: `tests/test_layered_index.py` (extend existing)

### Tier 3: System Tests (HIGH effort — deferred)

These require real infrastructure or Docker. Not needed for MVP.

#### T3-1: Docker image build verification
- Build Dockerfile.cpu and verify `codrag sync-headless --help` runs
- Build Dockerfile.gpu and verify Ollama starts
- Requires: Docker, CI runner
- File: `.github/workflows/headless-images.yml`

#### T3-2: Real S3 round-trip
- Upload an index to a MinIO container
- Download it and verify integrity
- Requires: Docker (MinIO), or a test Cloudflare R2 bucket
- File: `tests/test_s3_e2e.py`

#### T3-3: Full pipeline on a real repo
- Run `codrag sync-headless` on `tests/fixtures/mini_repo/` with a real (or mocked) LLM
- Verify all 10 stages complete
- Verify search returns relevant results from the built index
- Requires: Ollama or OpenAI API key
- File: `scripts/e2e_team_sync.py`

---

## Remaining Implementation TODO

### Must-have (before Team tier launch)

- [ ] **API endpoint for sync status** — Add `GET /projects/{id}/sync/status` to expose `RemoteSyncService.status_dict()`. Wire into `api/routers/projects.py`.
- [ ] **Wire TeamSyncIndicator into App.tsx** — Fetch sync status on project change, pass to TeamSyncIndicator component. Add "Sync Now" button handler.
- [ ] **Wire RemoteSyncService into daemon startup** — When a project has `team_config.json` with `sync.enabled: true`, create a RemoteSyncService and start polling.
- [ ] **Wire LayeredCodeIndex into search path** — When remote index exists, create LayeredCodeIndex instead of plain CodeIndex in the context endpoint.
- [ ] **Docker image CI** — `.github/workflows/headless-images.yml` to build and push images to GHCR on release tags.

### Nice-to-have (post-launch)

- [ ] **P06-S15 polish** — "Sync Now" button, last sync timestamp in Dashboard, remote commit SHA display
- [ ] **Branch-aware sync** — S3 prefix includes branch name, client resolves correct branch
- [ ] **OS keychain credential storage** — macOS Keychain / Windows Credential Manager integration for S3 keys
- [ ] **Webhook-triggered client sync** — Instead of polling, server pushes a notification when new index is available
- [ ] **Delta indexer service** — Automatic local delta enrichment when watcher detects changes to remote-indexed files

---

## Priority Order

1. **T1-1** (orchestration) — Highest value, catches fatal/non-fatal logic bugs
2. **T2-1** (headless E2E) — Proves the whole pipeline works end-to-end
3. **API endpoint + Dashboard wiring** — Completes the user-facing feature
4. **T1-2 through T1-6** — Fill remaining unit test gaps
5. **T2-2** (incremental) — Validates the cost-saving claim
6. **Docker image CI** — Needed before public release
7. **T3-*** — Only needed for production hardening

---

## Running Tests

```bash
# All team sync tests
.venv/bin/python -m pytest tests/test_s3_storage.py tests/test_layered_index.py tests/test_headless_runner.py tests/test_remote_sync.py -v

# Quick smoke test
.venv/bin/python -m pytest tests/test_headless_runner.py -v -k "TestHeadlessStages or TestHeadlessConfig"

# Full suite (should still pass)
.venv/bin/python -m pytest tests/ -v --tb=short
```
