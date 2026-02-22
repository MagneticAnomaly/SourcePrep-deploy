# Phase 06 — Team & Enterprise TODO

## Links
- Spec: `README.md`
- Research + decisions: `RESEARCH_AND_DECISIONS.md`
- Implementation plan: `IMPLEMENTATION_PLAN.md`
- Test plan: `TEST_PLAN.md`
- Opportunities: `opportunities.md`
- Master orchestrator: `../MASTER_TODO.md`
- Research backlog: `../RESEARCH_BACKLOG.md`
- Decision log: `../DECISIONS.md` (ADR-012 MVP boundary)
- Workflow backbone: `../WORKFLOW_RESEARCH.md`

## Research completion checklist (P06-R*)
- [x] P06-R1 Define embedded mode behavior (See: `RESEARCH_AND_DECISIONS.md` — P06-R1):
  - what files exist
  - what can be committed
  - format/version compatibility behavior
- [x] P06-R2 Define merge conflict and corruption handling for committed indexes (See: `RESEARCH_AND_DECISIONS.md` — P06-R2)
- [x] P06-R3 Define network mode security baseline (See: `RESEARCH_AND_DECISIONS.md` — P06-R3):
  - binding defaults
  - auth required rules
  - threat model assumptions
- [x] P06-R4 Specify onboarding UX for team mode (CLI + dashboard) (See: `RESEARCH_AND_DECISIONS.md` — P06-R4)

## Implementation backlog (P06-I*)
**Note:** post-MVP implementation. These items can be executed later, but should remain coherent with earlier phase constraints.

### Shared configuration (Team Tier)
- [ ] P06-I1 Define `.codrag/team_config.json` schema (secret-free) (See: `IMPLEMENTATION_PLAN.md` — P06-I1)
- [ ] P06-I2 Config merge precedence rules (See: `IMPLEMENTATION_PLAN.md` — P06-I2):
  - defaults → global → team → project overrides
- [ ] P06-I3 Config provenance reporting plan (UI/diagnostics) (See: `IMPLEMENTATION_PLAN.md` — P06-I3)

### Embedded mode
- [ ] P06-I4 Embedded index directory layout (`.codrag/index/**`) aligned with Phase01 formats (See: `IMPLEMENTATION_PLAN.md` — P06-I4)
- [ ] P06-I5 Incompatible index detection and remediation UX (“Full rebuild required”) (See: `IMPLEMENTATION_PLAN.md` — P06-I5)
- [ ] P06-I6 Watch-loop avoidance requirements (Phase03): `.codrag/**` excluded always (See: `IMPLEMENTATION_PLAN.md` — P06-I6)

### Network mode
- [ ] P06-I7 Remote bind requires auth; refuse unsafe startup unless explicit override (See: `IMPLEMENTATION_PLAN.md` — P06-I7)
- [ ] P06-I8 Auth header standardization (`Authorization: Bearer <api_key>`) (See: `IMPLEMENTATION_PLAN.md` — P06-I8)
- [ ] P06-I9 Remote-mode redaction rules (See: `IMPLEMENTATION_PLAN.md` — P06-I9):
  - do not leak server filesystem paths
  - sanitize logs/diagnostics

## Testing & validation (P06-T*)
- [ ] P06-T1 Embedded committed index flow (See: `TEST_PLAN.md` — P06-T1):
  - build on machine A
  - commit `.codrag/index/**`
  - clone on machine B
  - instant search without rebuild
- [ ] P06-T2 Merge conflict handling (See: `TEST_PLAN.md` — P06-T2):
  - conflict markers inside `.codrag/index/**` → index invalid → rebuild required
- [ ] P06-T3 Network mode safety (See: `TEST_PLAN.md` — P06-T3):
  - remote bind without auth is rejected
  - remote bind with auth works

## Cross-phase strategy alignment
Relevant entries in `../MASTER_TODO.md`:
- [ ] STR-03 Manifest + versioning (embedded index compatibility)
- [ ] STR-06 Watcher strategy (loop avoidance rules must be universal)
- [ ] STR-09 Licensing + feature gating (tier mapping to features)

## Notes / blockers
- [ ] Decide default guidance for committing `.codrag/index/**` (explicit opt-in vs recommended) (See: `RESEARCH_AND_DECISIONS.md` — D06-01)
- [ ] Decide TLS posture for network mode (reverse proxy acceptable vs built-in) (See: `RESEARCH_AND_DECISIONS.md` — D06-02)

---

# Phase 06 — Team Sync Roadmap (P06-S*)

*Added: February 2026*
*References: `TEAM_PRICING_AND_INFRA_EXPLORATION.md`, `UNIFIED_BUILD_STRATEGY.md`, `RUNPOD_SERVERLESS_ARCHITECTURE.md`, `RESEARCH_LLM_PREFERENCES.md`, `RESEARCH_SHARED_TRACE_VS_LOCAL_KB.md`*

This section tracks the implementation of the **Shared Remote Indexing** feature — the killer feature that justifies the Team tier pricing. The architecture is: a headless CI/CD server builds the trace graph once, uploads it to S3, and every developer's local CoDRAG client downloads it.

## Milestone 1: Headless CLI (`codrag sync-headless`)
The foundational CLI command that runs the full pipeline in batch mode and syncs artifacts to/from S3-compatible storage.

- [ ] **P06-S01** Design the `sync-headless` CLI argument schema
  - `--repo-url`, `--branch` (default: `main`), `--repo-path` (for pre-cloned repos in CI)
  - `--s3-bucket`, `--s3-prefix`, `--s3-endpoint`, `--s3-access-key`, `--s3-secret-key`
  - `--model-provider` (`local` | `openai` | `anthropic` | `google`), `--model-name`, `--api-key`
  - `--embedder` (`native` | `ollama`), `--full` (force full rebuild)
  - All S3 and API credentials also readable from environment variables
  - File: `src/codrag/cli.py`

- [ ] **P06-S02** Implement `S3StorageProvider` class
  - Upload: zip index artifacts → upload to `s3://{bucket}/{prefix}/index-{timestamp}.zip`
  - Download: list objects in prefix → download latest zip → extract
  - Atomic upload: write to `.tmp` key, then copy to final key, then delete `.tmp`
  - Version manifest: upload `s3://{bucket}/{prefix}/manifest.json` alongside the zip containing `{version, timestamp, branch, commit_sha, content_hash_of_zip}`
  - Support S3-compatible APIs: AWS S3, Cloudflare R2, MinIO, Backblaze B2
  - Dependency: `boto3` (already an optional dep) or `minio` SDK
  - File: `src/codrag/services/s3_storage.py`

- [ ] **P06-S03** Implement incremental headless rebuild
  - On `sync-headless` run: check S3 for existing `manifest.json`
  - If found: download existing index, load `trace_manifest.json`, diff against current repo state
  - Only re-index files where `content_hash` differs, plus new files, minus deleted files
  - If `--full` flag: skip diffing, rebuild from scratch
  - This is the single biggest cost saver (2 hours → 5 minutes for typical PRs)
  - Files: `src/codrag/cli.py`, `src/codrag/services/headless_runner.py`

- [ ] **P06-S04** Implement Git clone / checkout logic for headless mode
  - Support `--repo-url` with `$GIT_TOKEN` env var (HTTPS clone with token auth)
  - Support `--repo-url` with `$SSH_KEY` env var (SSH clone)
  - Support `--repo-path` for pre-cloned repos (GitHub Actions already checks out the repo)
  - Shallow clone by default (`--depth 1`) to minimize clone time
  - File: `src/codrag/services/headless_runner.py`

- [ ] **P06-S05** Wire headless mode into the existing pipeline orchestrator
  - The headless runner must call the same 10-stage pipeline as the interactive daemon
  - It must support both LLM modes:
    - `--model-provider local`: start embedded Ollama, use specified model
    - `--model-provider openai/anthropic/google`: use BYOK API key, no GPU needed
  - The native ONNX embedder must work on CPU (no GPU required for embeddings)
  - Must generate all standard artifacts: `documents.json`, `embeddings.npy`, `trace_manifest.json`, `atlas_routing.json`, `atlas_routing_embeddings.npy`
  - Files: `src/codrag/services/headless_runner.py`, `src/codrag/services/pipeline_orchestrator.py`

## Milestone 2: Docker Images
Two image tiers to support both CPU+BYOK and GPU+Local deployment patterns.

- [ ] **P06-S06** Create `Dockerfile.cpu` (the slim image)
  - Base: `ubuntu:22.04`
  - Contents: Python 3.11+, `codrag` package, Rust binaries, ONNX models, `boto3`, Git CLI
  - No Ollama, no CUDA libs, no GPU support
  - Target size: ~2–3 GB
  - Use case: GitHub Actions, GitLab CI runners, any CPU-only environment
  - File: `deploy/Dockerfile.cpu`

- [ ] **P06-S07** Create `Dockerfile.gpu` (the fat image)
  - Base: `nvidia/cuda:12.x-runtime-ubuntu22.04`
  - Contents: Everything in `cpu`, plus Ollama runtime + pre-baked Qwen3:4b model weights
  - Baking the model avoids a 5GB download on every serverless cold start
  - Target size: ~8–10 GB
  - Use case: RunPod Serverless, Modal, AWS SageMaker
  - File: `deploy/Dockerfile.gpu`

- [ ] **P06-S08** GitHub Actions CI to build and publish both images
  - Trigger: on release tag (e.g., `v1.0.0`) or manual dispatch
  - Push to GitHub Container Registry (`ghcr.io/ericbintner/codrag-headless:cpu`, `:gpu`)
  - Multi-arch builds (amd64 at minimum; arm64 if feasible)
  - File: `.github/workflows/headless-images.yml`

## Milestone 3: Platform Adapters & Templates
Thin wrappers that make the Docker images work on specific serverless providers.

- [ ] **P06-S09** Modal adapter
  - A Python script that imports the GPU image and exposes a POST webhook endpoint
  - Accepts `{repo_url, branch, s3_bucket, s3_prefix}` in the request body
  - Calls `codrag sync-headless` inside the container
  - Include README with step-by-step setup instructions
  - Files: `deploy/modal/modal_adapter.py`, `deploy/modal/README.md`

- [ ] **P06-S10** RunPod Serverless adapter
  - `Dockerfile.runpod`: inherits from `codrag/headless:gpu`, adds `runpod` pip package and handler script
  - `runpod_handler.py`: parses RunPod job input, calls `codrag sync-headless`
  - Include README with step-by-step setup instructions
  - Files: `deploy/runpod/Dockerfile.runpod`, `deploy/runpod/runpod_handler.py`, `deploy/runpod/README.md`

- [ ] **P06-S11** GitHub Actions workflow template (the CI/CD trigger)
  - A reusable workflow that teams copy into their repo
  - Triggers on push to configurable branches (default: `main`)
  - For CPU+BYOK teams: runs `codrag sync-headless` directly in the Actions runner
  - For GPU teams: sends a webhook to their RunPod/Modal endpoint
  - Files: `deploy/github-actions/codrag-sync.yml`, `deploy/github-actions/README.md`

- [ ] **P06-S12** AWS ECS task definition (Enterprise reference)
  - A JSON task definition for running `codrag/headless:gpu` on AWS ECS/Fargate with GPU
  - Documents IAM role requirements for S3 access (no static keys needed)
  - Files: `deploy/aws/ecs-task-definition.json`, `deploy/aws/README.md`

## Milestone 4: Local Client Sync
The desktop CoDRAG daemon must know how to download and use remote indexes.

- [ ] **P06-S13** Define `team_config.json` sync schema
  - Committed to repo at `.codrag/team_config.json` (secret-free)
  - Schema: `{ sync: { enabled: bool, s3_endpoint: str, s3_bucket: str, s3_prefix: str, poll_interval_minutes: int (default 30) } }`
  - Credentials: read from env vars `CODRAG_S3_ACCESS_KEY` / `CODRAG_S3_SECRET_KEY`, or from gitignored `.codrag/.secrets` file, or from OS keychain
  - File: extends `P06-I1` schema definition

- [ ] **P06-S14** Implement client-side S3 download logic
  - On daemon startup: if `team_config.json` has `sync.enabled: true`, check S3 for `manifest.json`
  - Compare remote `manifest.json` version/timestamp against local `.codrag/index/remote/manifest.json`
  - If remote is newer: download zip, extract to `.codrag/index/remote/`, update local manifest
  - Atomic extraction: extract to `.codrag/index/remote.tmp/`, then rename
  - Also triggered on manual "Sync" button press in Dashboard and on configurable poll interval
  - File: `src/codrag/services/remote_sync.py`

- [ ] **P06-S15** Dashboard UI: Sync status indicator
  - Show "Remote index: up to date" / "syncing..." / "X hours behind" in the project status area
  - Add a manual "Sync Now" button
  - Show last sync timestamp and remote commit SHA
  - Files: `packages/ui/src/components/team/SyncStatusCard.tsx`, wired into `App.tsx`

## Milestone 5: Layered Index Reading
The search engine must merge remote + local indexes at query time.

- [ ] **P06-S16** Refactor `index.py` to support layered document loading
  - Currently: `get_context()` loads a single `documents.json` + `embeddings.npy`
  - New: load from multiple directories: `.codrag/index/remote/`, `.codrag/index/local_deltas/`
  - Concatenate document lists and embedding matrices (numpy `vstack`)
  - Apply tombstone mask: if a document path exists in both remote and delta, exclude the remote version
  - File: `src/codrag/core/index.py`

- [ ] **P06-S17** Implement local delta detection and indexing
  - When the file watcher detects a change to a file that exists in the remote `trace_manifest.json`:
    - Run the enrichment pipeline on only that file (using local LLM or BYOK)
    - Save the result to `.codrag/index/local_deltas/`
  - When a remote sync downloads a new index:
    - Compare each local delta's `content_hash` against the new remote manifest
    - If remote now has the same or newer hash: discard the local delta (it was merged)
    - If delta has further local edits beyond what was merged: keep the delta
  - Files: `src/codrag/services/delta_indexer.py`, `src/codrag/core/index.py`

- [ ] **P06-S18** Integration test: end-to-end layered search
  - Build a remote index for a test repo
  - Modify one file locally (creating a delta)
  - Query and verify that the delta version is returned (not the stale remote version)
  - Sync a new remote index that includes the merged file
  - Verify the delta is discarded and the remote version is used
  - File: `tests/test_layered_index.py`

## Milestone 6: Testing & Validation

- [ ] **P06-S19** Unit tests for `S3StorageProvider`
  - Mock S3 client (using `moto` library)
  - Test: upload, download, atomic swap, version manifest, error handling
  - File: `tests/test_s3_storage.py`

- [ ] **P06-S20** Unit tests for `headless_runner`
  - Test: Git clone with token, incremental diff logic, full rebuild flag
  - File: `tests/test_headless_runner.py`

- [ ] **P06-S21** Integration test: headless CLI end-to-end
  - Run `codrag sync-headless` against a fixture repo with a mock S3 (MinIO container)
  - Verify artifacts are uploaded correctly
  - Run again with one file changed, verify incremental rebuild
  - File: `tests/test_headless_e2e.py`

- [ ] **P06-S22** Integration test: client sync end-to-end
  - Seed a mock S3 bucket with a pre-built index
  - Start the CoDRAG daemon with `team_config.json` pointing to the mock bucket
  - Verify the daemon downloads and uses the remote index
  - File: `tests/test_client_sync_e2e.py`

## Milestone 7: Documentation & Public Docs

- [ ] **P06-S23** Update public docs draft: `websites/apps/docs/src/app/guides/team-sync/page.md`
  - Add Quick Start path (CPU + BYOK via GitHub Actions — zero infrastructure)
  - Add Advanced path (GPU + RunPod/Modal)
  - Add Enterprise reference (AWS ECS)
  - Add credential security guidance (never commit keys)
  - Add FAQ: incremental vs full rebuilds, sync frequency, branch configuration

- [ ] **P06-S24** Write `deploy/README.md` overview
  - Index of all adapter directories with links
  - Quick decision tree: "Which deployment is right for my team?"

## Pricing decision (deferred — to be finalized after MVP)
- [ ] **P06-S25** Finalize Team tier pricing
  - Option A: $15/seat/month (SaaS subscription)
  - Option B: $149/seat/year (Anti-SaaS annual license)
  - Decision depends on how much value the shared indexing feature delivers in practice
  - Blocked on: MVP implementation + internal dogfooding

## Dependency map
```
P06-S01 (CLI schema)
  ├─▶ P06-S02 (S3 provider)
  ├─▶ P06-S04 (Git clone)
  └─▶ P06-S05 (Pipeline wiring)
        └─▶ P06-S03 (Incremental rebuild)
              └─▶ P06-S06/S07 (Docker images)
                    ├─▶ P06-S08 (Image CI/CD)
                    ├─▶ P06-S09 (Modal adapter)
                    ├─▶ P06-S10 (RunPod adapter)
                    └─▶ P06-S11 (GitHub Actions template)
P06-S13 (team_config schema)
  └─▶ P06-S14 (Client sync)
        └─▶ P06-S15 (Dashboard UI)
P06-S16 (Layered index)
  └─▶ P06-S17 (Delta detection)
        └─▶ P06-S18 (Integration test)
P06-S19–S22 (Tests) — can run in parallel after their dependencies
P06-S23–S24 (Docs) — can be written incrementally
```
