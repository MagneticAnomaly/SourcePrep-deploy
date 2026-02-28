# Team Sync — Test Plan

> **Status:** Ready for testing
> **Last updated:** 2026-02-27

---

## 1. Unit Tests (Automated)

Run with:
```bash
.venv/bin/python -m pytest tests/test_layered_index.py tests/test_headless_runner.py tests/test_remote_sync.py tests/test_s3_storage.py tests/test_team_sync_integration.py -v
```

**Expected:** 120 tests pass (21 layered + 24 headless + 23 remote_sync + 14 s3_storage + 38 integration).

### Test Coverage

| Class | Tests | Covers |
|-------|-------|--------|
| `TestLayeredCodeIndex` | 4 | Remote-only, delta masking, tombstone invalidation, from_dirs |
| `TestLayeredCompatibility` | 7 | index_dir, embedder, _manifest, _documents merge, stats flag, trace expansion delegation |
| `TestBuildManagerLayeredIndex` | 3 | Fallback to plain CodeIndex, LayeredCodeIndex when remote exists, layered with delta |
| `TestRemoteSyncStartup` | 3 | Lazy creation, enabled config detection, disabled by default |
| `TestPruneStaleDelta` | 4 | Pruning merged files, no overlap, no manifest, no delta |
| **Integration (test_team_sync_integration.py)** | | |
| `TestArtifactConsistency` | 3 | INDEX_ARTIFACTS ⊇ _PRESERVE_FILES, core files, no dupes |
| `TestLicenseGating` | 5 | Free/pro blocked, team/enterprise allowed, require raises |
| `TestLayeredSearchMerge` | 6 | Search results, delta override, tombstones, k-limit, sort |
| `TestLayeredGetContext` | 4 | Returns string, includes content, empty, max_chars |
| `TestWatcherDeltaRouting` | 2 | Routes to delta build vs full build |
| `TestSyncAndPruneEndToEnd` | 2 | check_and_sync triggers prune, no-deltas case |
| `TestFullSyncLifecycle` | 1 | Full cycle: remote → delta → prune → fresh remote |
| `TestAPIIntegration` | 4 | /status, /search, /context, empty query error |
| `TestCacheCoherence` | 3 | Cache survives reads, invalidation refreshes, project-scoped |
| `TestHeadlessStagesCompleteness` | 3 | Labels, IDs, runner instantiation |
| `TestEdgeCases` | 5 | Empty remote/delta, corrupt manifest, missing .codrag, corrupt docs |
| **Unit (test_headless_runner.py)** | | |
| `TestHeadlessConfig` | 2 | Defaults, custom values |
| `TestHeadlessCreateLlmClient` | 5 | All 4 providers + unknown |
| `TestHeadlessCreateEmbedder` | 3 | Native, fallback, explicit ollama |
| `TestHeadlessWorkerFactory` | 2 | Lazy LLM init, batch profile |
| `TestHeadlessStages` | 4 | Count, uniqueness, first/last |
| `TestResolveRepo` | 3 | Exists, missing, neither |
| `TestS3Config` | 7 | from_env, validate, s3_key |
| `TestS3StorageProvider` | 4 | Upload/download manifest |
| `TestRemoteSyncService` | 7 | Config loading, sync disabled/enabled, leaked secrets |

---

## 2. Integration Test: Headless → S3 → Local Sync (Real-World)

### Prerequisites

- A CoDRAG Team or Enterprise license (or `CODRAG_TIER=team` env var for dev)
- An S3-compatible bucket (Cloudflare R2 recommended for zero egress fees)
- A test repository with ≥10 source files
- OpenAI API key (for CPU mode) OR local Ollama (for GPU mode)

### Step 1: Headless Build (Simulates CI/CD)

```bash
# Set tier for dev testing
export CODRAG_TIER=team

# Run headless sync (CPU + BYOK mode)
codrag sync-headless \
  --repo-path /path/to/test-repo \
  --branch main \
  --model-provider openai \
  --model-name gpt-4.1-mini \
  --embedder native \
  --s3-endpoint https://<account-id>.r2.cloudflarestorage.com \
  --s3-bucket codrag-team-indexes \
  --s3-prefix test-repo/main \
  --s3-access-key $CODRAG_S3_ACCESS_KEY \
  --s3-secret-key $CODRAG_S3_SECRET_KEY
```

**Verify:**
- [ ] All 10 stages complete (check console output for ✓/✗)
- [ ] `manifest.json` uploaded to S3 (check bucket)
- [ ] `index.zip` uploaded to S3
- [ ] Zip contains all 17 expected artifact files (trace_nodes.jsonl, trace_augmented.jsonl, atlas.json, etc.)

### Step 2: Local Client Sync

```bash
# In the test repository, create team_config.json
mkdir -p .codrag
cat > .codrag/team_config.json << 'EOF'
{
  "sync": {
    "enabled": true,
    "s3_endpoint": "https://<account-id>.r2.cloudflarestorage.com",
    "s3_bucket": "codrag-team-indexes",
    "s3_prefix": "test-repo/main",
    "poll_interval_minutes": 5
  }
}
EOF

# Create .codrag/.secrets (gitignored)
cat > .codrag/.secrets << 'EOF'
{
  "s3_access_key": "YOUR_READ_ONLY_KEY",
  "s3_secret_key": "YOUR_READ_ONLY_SECRET"
}
EOF

# Start the daemon
export CODRAG_TIER=team
codrag serve --port 8400
```

**Verify:**
- [ ] Daemon logs show "Team sync polling started for project ..."
- [ ] Remote index downloaded to `.codrag/index/remote/`
- [ ] `documents.json` exists in remote dir
- [ ] `GET /projects/{id}/status` includes sync status with `enabled: true`

### Step 3: Search Uses Layered Index

```bash
# Search via API
curl -X POST http://localhost:8400/projects/{id}/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication middleware", "k": 5}'
```

**Verify:**
- [ ] Search returns results from the remote (shared) index
- [ ] Response status 200 with `chunks` array

### Step 4: Local Delta Override

1. Edit a file that exists in the remote index (e.g., `src/auth.py`)
2. Trigger a local rebuild: `POST /projects/{id}/build`
3. Search again for the same query

**Verify:**
- [ ] The edited file's results come from the local delta, not the remote version
- [ ] Other files still return results from the remote index
- [ ] `GET /projects/{id}/status` shows `layered: true` in stats (if stats endpoint exposes it)

### Step 5: Delta Pruning After Re-Sync

1. Commit the local edit and push to `main`
2. Re-run the headless sync (Step 1)
3. Wait for the local client to poll and download the new remote index

**Verify:**
- [ ] Stale local delta for the edited file is pruned
- [ ] Search results now come from the fresh remote index

---

## 3. License Gate Test

```bash
# Test that free tier can't run sync-headless
unset CODRAG_TIER
codrag sync-headless --repo-path . --model-provider openai --model-name gpt-4.1-mini
```

**Verify:**
- [ ] Error message: "sync-headless requires a Team or Enterprise license"
- [ ] Exit code 1

```bash
# Test that team tier can
export CODRAG_TIER=team
codrag sync-headless --repo-path . --help
```

**Verify:**
- [ ] Help text displayed (no license error)

---

## 4. Docker Image Test

### CPU Image

```bash
docker build -f public/codrag-deploy/Dockerfile.cpu -t codrag/headless:cpu .

docker run --rm codrag/headless:cpu sync-headless --help
```

**Verify:**
- [ ] Image builds without errors
- [ ] Help text displayed
- [ ] `codrag` binary is on PATH inside the container

### GPU Image

```bash
docker build -f public/codrag-deploy/Dockerfile.gpu -t codrag/headless:gpu .

docker run --rm codrag/headless:gpu sync-headless --help
```

**Verify:**
- [ ] Image builds without errors (requires Docker with BuildKit)
- [ ] Ollama is installed (`docker run --rm codrag/headless:gpu ollama --version`)
- [ ] qwen3:4b model is pre-baked (`docker run --rm codrag/headless:gpu ollama list`)

---

## 5. Secrets Leakage Detection Test

```bash
cat > /tmp/test_team_config.json << 'EOF'
{
  "sync": {
    "enabled": true,
    "s3_endpoint": "https://example.com",
    "s3_bucket": "test",
    "s3_access_key": "AKIAIOSFODNN7EXAMPLE",
    "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  }
}
EOF
```

Start daemon with this config and check logs.

**Verify:**
- [ ] Warning logged: "SECURITY: ... appears to contain credential-like keys"

---

## 6. Checklist Before Ship

### Code
- [x] `sync-headless` CLI has license gate (Team/Enterprise required)
- [x] `INDEX_ARTIFACTS` in s3_storage.py matches `_PRESERVE_FILES` in index.py (17 files)
- [x] `RemoteSyncService` auto-starts on daemon startup for enabled projects
- [x] `LayeredCodeIndex` wired into search + context endpoints
- [x] `LayeredCodeIndex` has duck-type compatibility (index_dir, embedder, _documents, _manifest, get_context_with_trace_expansion)

### Pricing Page
- [x] Team card expanded (7 bullet points)
- [x] Enterprise card expanded (7 bullet points)
- [x] "How Team Sync Works" section
- [x] Links to docs guides

### Docs Site
- [x] Team Sync guide (existing, verified)
- [x] Enterprise Deployment guide (new)
- [x] Deployment section in sidebar
- [x] team_config.json schema reference
- [x] Enterprise features table (Available/Roadmap)

### Deploy Templates
- [x] Dockerfile.cpu builds
- [x] Dockerfile.gpu builds
- [x] GitHub Actions workflow (CPU + GPU modes)
- [x] Modal adapter
- [x] RunPod handler
- [x] AWS ECS task definition
- [x] Docker build CI workflow

### Tests
- [x] 21 layered_index tests
- [x] 24 headless_runner tests
- [x] 23 remote_sync tests
- [x] 14 s3_storage tests
- [x] 38 integration tests (total: 120 Team Sync tests)
- [x] All existing tests pass (1,051 tested, 0 regressions)

### Known Limitations (Document, Don't Block)
- ~~RemoteSyncService polling doesn't auto-trigger delta pruning after download~~ **RESOLVED** — `_prune_stale_deltas` auto-called after sync
- ~~LayeredCodeIndex doesn't cache across requests~~ **RESOLVED** — cached in BuildManager with invalidation on build/sync
- No dashboard UI for sync status (status available via API only)
- ~~Delta creation (local_deltas/) is not yet wired into the watcher rebuild path~~ **RESOLVED** — watcher `trigger_build` routes to delta build when remote exists

### Bug Fixes Found During Testing
- Fixed `LayeredCodeIndex.search()` — caller-supplied `exclude_paths` conflicted with internal tombstone `exclude_paths` via `**kwargs` passthrough (duplicate keyword argument error)
