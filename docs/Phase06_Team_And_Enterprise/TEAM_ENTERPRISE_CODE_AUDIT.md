# Team/Enterprise Code Audit — Security, Architecture & Optimization

*Audit Date: Mar 9, 2026*
*Scope: All Team/Enterprise code paths, Docker images, deployment templates, and sync infrastructure.*

---

## Files Reviewed

| File | Lines | Role |
|------|-------|------|
| `src/codrag/services/headless_runner.py` | 618 | Core headless pipeline orchestration |
| `src/codrag/services/s3_storage.py` | 313 | S3-compatible upload/download with atomic swap |
| `src/codrag/services/remote_sync.py` | 382 | Client-side polling, delta pruning, secrets detection |
| `src/codrag/core/layered_index.py` | 366 | Merged remote + local delta search |
| `src/codrag/core/team_config.py` | 155 | Team config schema (enforcement, policy, models) |
| `src/codrag/core/feature_gate.py` | 214 | License tier gating |
| `src/codrag/cli.py` (sync-headless) | 132 | CLI entry point for headless sync |
| `src/codrag/server.py` (startup) | 30 | Daemon auto-start of team sync polling |
| `src/codrag/services/project_helpers.py` | 30 | Syncer creation and status helpers |
| `public/codrag-deploy/Dockerfile.cpu` | 51 | CPU headless Docker image |
| `public/codrag-deploy/Dockerfile.gpu` | 66 | GPU headless Docker image |
| `public/codrag-deploy/entrypoint.sh` | 25 | GPU image entrypoint (Ollama startup) |
| `public/codrag-deploy/github-actions/codrag-sync.yml` | 72 | Reusable GitHub Actions workflow |
| `public/codrag-deploy/runpod/runpod_handler.py` | 65 | RunPod serverless adapter |
| `public/codrag-deploy/modal/modal_adapter.py` | 82 | Modal.com serverless adapter |
| `public/codrag-deploy/aws/ecs-task-definition.json` | 51 | AWS ECS reference task definition |

---

## 🔴 Critical Security Issues

### SEC-1: Docker Images Run as Root
**Files:** `Dockerfile.cpu`, `Dockerfile.gpu`
**Risk:** HIGH — Container escape vulnerabilities are amplified when running as root.
**Issue:** Neither Dockerfile includes a `USER` directive. All processes (CoDRAG, Ollama, git clone) run as root inside the container. If a malicious repo is cloned and exploits a vulnerability in the parser or git, the attacker has root access inside the container.
**Fix:** Add a non-root user and switch to it after installation.

### SEC-2: CLI Accepts Secrets as Command-Line Arguments
**File:** `src/codrag/cli.py` lines 1196, 1202-1203
**Risk:** MEDIUM — Secrets visible in process listings (`ps aux`), shell history, and CI logs.
**Issue:** `--api-key`, `--s3-access-key`, and `--s3-secret-key` are accepted as CLI flags. While env vars are also supported (and preferred), the mere existence of these flags invites misuse.
**Fix:** Deprecate the CLI flags and document env-var-only usage. Add a warning if secrets are passed via CLI.

### SEC-3: Modal Webhook Has No Authentication
**File:** `public/codrag-deploy/modal/modal_adapter.py`
**Risk:** MEDIUM — Anyone who discovers the Modal endpoint URL can trigger expensive GPU builds.
**Issue:** The `trigger_sync` webhook endpoint has no authentication check. Modal provides URL-based security (obscure URLs), but this is security-through-obscurity.
**Fix:** Add a shared secret check (e.g., `Authorization: Bearer $WEBHOOK_SECRET` header validation).

### SEC-4: Redundant Soft License Gate in HeadlessRunner
**File:** `src/codrag/services/headless_runner.py` lines 438-463
**Risk:** LOW — Confusing dual-gate architecture.
**Issue:** The CLI entry point (`cli.py`) enforces a hard gate via `check_feature("team_config")`. But `HeadlessRunner._verify_license()` implements a completely separate, softer check using `CODRAG_LICENSE_KEY` env var with prefix matching. These two systems don't interact. The soft gate in the runner checks a different env var than the feature gate system.
**Fix:** Remove the redundant `_verify_license()` from HeadlessRunner. The CLI's feature gate is the canonical check. If someone calls HeadlessRunner programmatically, they should use `require_feature("team_config")`.

---

## 🟡 Outdated Model References

### MODEL-1: GPU Image and CLI Default to `qwen3:4b`
**Files:** `Dockerfile.gpu` line 40, `headless_runner.py` line 55, `cli.py` line 1195, `ecs-task-definition.json` line 20, `runpod_handler.py` line 22, `modal_adapter.py` line 47
**Issue:** All headless infrastructure defaults to `qwen3:4b`, which Phase 46 research determined is below the quality floor (8b minimum). The GPU VRAM Model Reference document recommends `qwen3.5:9b` as the entry-level model and `qwen3.5:35b-a3b` as the baseline.
**Fix:** Update all defaults to `qwen3.5:9b` (the minimum viable model). Update the GPU image to pre-bake `qwen3.5:9b` instead of `qwen3:4b`. This increases image size by ~3GB but ensures quality output.

---

## 🟡 Architecture Improvements

### ARCH-1: Single-Model Headless Pipeline (No Fast/Reasoning Split)
**File:** `src/codrag/services/headless_runner.py`
**Issue:** The `HeadlessWorkerFactory` creates a single `_llm_client` shared across ALL 11 stages. Per our `INSTITUTION_MODEL_ASSIGNMENTS.md`, the optimal strategy uses different models for Fast stages (cheap/fast) vs Reasoning stages (expensive/accurate). Currently, a team must choose one model for the entire pipeline.
**Impact:** Teams using Claude Sonnet for reasoning stages are also paying Sonnet prices for simple JSON extraction (augmentation, cataloging) — a ~10x overspend on Fast stages.
**Fix (Future):** Add `--fast-model` and `--reasoning-model` CLI flags. Modify `HeadlessWorkerFactory` to maintain two LLM clients and select the appropriate one per stage category.

### ARCH-2: Duplicate Team Config Systems
**Files:** `src/codrag/core/team_config.py` vs `src/codrag/services/remote_sync.py`
**Issue:** There are two separate team configuration schemas:
  - `core/team_config.py`: `TeamConfig` — enforcement mode, policy globs, embedding config, config hash.
  - `services/remote_sync.py`: `TeamSyncConfig` — S3 endpoint, bucket, prefix, poll interval.
Both read from `.codrag/team_config.json` but parse different sections. They are not cross-referenced or validated together.
**Fix (Future):** Unify into a single `TeamConfig` loader that parses the complete schema. The `remote_sync.py` should import from `core/team_config.py` rather than re-implementing JSON parsing.

### ARCH-3: Entrypoint.sh Silently Ignores Ollama Startup Failure
**File:** `public/codrag-deploy/entrypoint.sh`
**Issue:** If Ollama fails to start within 30 seconds (e.g., GPU driver mismatch, OOM), the script continues silently. The `codrag sync-headless` command will then fail 10 minutes later when it tries to call the LLM, wasting CI minutes and compute costs.
**Fix:** Exit with an error if Ollama isn't ready after the timeout when `model-provider local` is specified.

---

## 🟢 Well-Designed Patterns (Keep These)

### GOOD-1: Atomic S3 Upload with Copy+Delete
`s3_storage.py` uses upload-to-temp → copy-to-final → delete-temp. This prevents partial uploads from corrupting the remote index if a CI job is killed mid-upload. Minor: the S3 copy doubles write costs, but correctness > cost here.

### GOOD-2: Zip-Slip Protection on Download
`s3_storage.py` line 290-293 validates that extracted zip entries don't escape the target directory. This prevents a compromised S3 bucket from writing files outside the index directory.

### GOOD-3: Secrets Leakage Detection
`remote_sync.py` scans `team_config.json` for credential-like keys and warns if found. This prevents the most common misconfiguration (committing S3 keys to Git).

### GOOD-4: Git Token Sanitization in Error Output
`headless_runner.py` line 507 sanitizes stderr to remove the `GIT_TOKEN` if the clone fails. Prevents token leakage in CI logs.

### GOOD-5: Feature Gate Architecture
`feature_gate.py` cleanly separates tier logic from feature access. The `FEATURE_TIERS` dict is easy to audit and extend. The `check_feature` / `require_feature` / `get_feature_limit` API is well-designed.

### GOOD-6: LayeredCodeIndex Tombstone System
The tombstone-based merge strategy (delta overrides remote by source_path) is correct and efficient. The `invalidate_tombstones()` method properly handles cache coherence after delta rebuilds.

### GOOD-7: GitHub Actions Workflow
The `codrag-sync.yml` uses `concurrency` with `cancel-in-progress: true` to prevent stale builds from piling up. It supports both CPU+BYOK and GPU webhook modes with a simple toggle. Secrets are properly injected via GitHub Secrets.

---

## Implementation Priority

| ID | Category | Priority | Effort | Description |
|----|----------|----------|--------|-------------|
| SEC-1 | Security | 🔴 Critical | Low | Add non-root user to Dockerfiles |
| SEC-2 | Security | 🟡 Medium | Low | Deprecate CLI secret flags, add warnings |
| SEC-3 | Security | 🟡 Medium | Low | Add webhook auth to Modal adapter |
| SEC-4 | Security | 🟢 Low | Low | Remove redundant soft license gate |
| MODEL-1 | Quality | 🟡 Medium | Low | Update all model defaults to qwen3.5:9b |
| ARCH-1 | Architecture | 🟡 Medium | Medium | Multi-model headless (fast + reasoning) |
| ARCH-2 | Architecture | 🟢 Low | Medium | Unify team config systems |
| ARCH-3 | Reliability | 🟡 Medium | Low | Fix entrypoint.sh silent failure |
