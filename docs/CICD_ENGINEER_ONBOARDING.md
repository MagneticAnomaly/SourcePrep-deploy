# CoDRAG — CI/CD Engineer Onboarding Guide

*Created: March 8, 2026*
*Role: CI/CD Engineer — Team & Enterprise Infrastructure*

---

## Your Role

You are the first engineer joining the CoDRAG team beyond the founder. Your primary responsibility is to **own the CI/CD infrastructure that powers the Team and Enterprise product tiers**. This means:

1. Getting the Docker images building and publishing reliably
2. Ensuring the headless indexing pipeline works end-to-end in CI environments
3. Maintaining the deployment templates that customers copy into their repos
4. Eventually operating the license server and monitoring infrastructure

You are NOT responsible for the desktop app code, the LLM pipeline logic, or the UI. Those are handled by the core product team. You ARE responsible for everything that happens after the code leaves a developer's machine and before it reaches a customer's CI runner.

---

## What CoDRAG Does (60-Second Version)

CoDRAG is a desktop developer tool (like a smarter Cursor/Copilot context engine). It:

1. **Parses a codebase** into a structural graph (Rust AST parser)
2. **Enriches it with LLMs** — inferred edges, semantic cataloguing, epistemic analysis, etc. (8 LLM-powered stages)
3. **Embeds everything** into vectors for semantic search (ONNX embedder)
4. **Serves context** to IDEs via MCP protocol (VS Code extension, Cursor, Windsurf, Claude Code)

### The Three Tiers

| Tier | What the user gets | Where it runs | Your involvement |
|---|---|---|---|
| **Pro** | Desktop app, local LLMs, local compute | User's Mac/PC | None — fully local |
| **Team** | Shared index built in CI, synced to all devs via S3 | Customer's CI + S3 bucket | **This is your primary focus** |
| **Enterprise** | Same as Team + VPC deployment, air-gapped, managed compute | Customer's private infra | Future — after Team is stable |

### The Team Tier Value Proposition

Without Team tier, every developer on a team runs the full 8-stage LLM pipeline locally. For a 500K-line codebase, this takes **2+ hours** and requires a powerful GPU or expensive API keys.

With Team tier:
1. **CI builds the index once** (on push to `main`) using a headless Docker image
2. **Uploads it to S3** (Cloudflare R2, AWS S3, MinIO, etc.)
3. **Every developer's desktop app downloads it** on startup (~30 seconds)
4. **Local deltas only** — developers only compute embeddings for their uncommitted changes

This is the killer feature that justifies the Team pricing.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CUSTOMER'S REPO                      │
│                                                         │
│  .github/workflows/codrag-sync.yml  ← copied from us    │
│  .codrag/team_config.json           ← S3 bucket config  │
│  .codrag/.secrets                   ← gitignored creds  │
└──────────────┬──────────────────────────────────────────┘
               │ push to main
               ▼
┌─────────────────────────────────────────────────────────┐
│              GITHUB ACTIONS (or GitLab, etc.)           │
│                                                         │
│  ┌──────────────────────────────────┐                   │
│  │  codrag/headless:cpu  (our image)│                   │
│  │  - Clones repo                   │                   │
│  │  - Runs 11-stage pipeline        │                   │
│  │  - Uses OpenAI/Anthropic API     │                   │
│  │  - Uploads index to S3           │                   │
│  └──────────────────────────────────┘                   │
│                      OR                                 │
│  ┌──────────────────────────────────┐                   │
│  │  Webhook → RunPod/Modal (GPU)    │                   │
│  │  codrag/headless:gpu             │                   │
│  │  - Has Ollama + Qwen3:4b baked   │                   │
│  │  - Self-contained, no API keys   │                   │
│  └──────────────────────────────────┘                   │
└──────────────┬──────────────────────────────────────────┘
               │ uploads index artifacts
               ▼
┌─────────────────────────────────────────────────────────┐
│                 S3-COMPATIBLE STORAGE                   │
│  (Cloudflare R2 / AWS S3 / MinIO / Backblaze B2)        │
│                                                         │
│  bucket/prefix/                                         │
│    ├── manifest.json    (version, timestamp, commit SHA)│
│    └── index-{ts}.zip   (documents, embeddings, traces) │
└──────────────┬──────────────────────────────────────────┘
               │ download on startup / poll every 30min
               ▼
┌─────────────────────────────────────────────────────────┐
│            DEVELOPER'S DESKTOP (CoDRAG Pro+Team)        │
│                                                         │
│  RemoteSyncService polls S3 for new manifest            │
│  Downloads zip → extracts to .codrag/index/remote/      │
│  LayeredCodeIndex merges remote + local deltas          │
│  Developer gets instant search from day 1               │
└─────────────────────────────────────────────────────────┘
```

---

## Repository Layout (What You'll Work With)

```
CoDRAG/
├── .github/workflows/              ← OUR CI/CD (builds our product)
│   ├── docker-headless.yml         ← Builds + pushes headless Docker images
│   ├── engine-wheels.yml           ← Builds Rust engine wheels (macOS/Windows/Linux)
│   ├── release.yml                 ← Full app release (Tauri desktop app)
│   ├── security-audit.yml          ← Weekly npm/cargo/pip security audit + test suite
│   └── websites-ci.yml             ← Docs/marketing site builds
│
├── public/codrag-deploy/           ← CUSTOMER-FACING deployment templates
│   ├── Dockerfile.cpu              ← Slim headless image (~2-3 GB, BYOK)
│   ├── Dockerfile.gpu              ← Fat headless image (~8-10 GB, baked Ollama)
│   ├── entrypoint.sh               ← GPU image Ollama startup
│   ├── github-actions/             ← Workflow template customers copy
│   │   └── codrag-sync.yml
│   ├── modal/                      ← Modal.com serverless GPU adapter
│   │   └── modal_adapter.py
│   ├── runpod/                     ← RunPod Serverless adapter
│   │   ├── Dockerfile.runpod
│   │   └── runpod_handler.py
│   └── aws/                        ← AWS ECS/Fargate reference
│       └── ecs-task-definition.json
│
├── src/codrag/
│   ├── cli.py                      ← `codrag sync-headless` command
│   ├── services/
│   │   ├── headless_runner.py      ← Headless pipeline runner (no daemon)
│   │   ├── s3_storage.py           ← S3 upload/download/manifest
│   │   ├── remote_sync.py          ← Client-side S3 download + polling
│   │   └── pipeline/              ← Pipeline scheduler, orchestrator
│   └── core/
│       ├── layered_index.py        ← Merges remote + local delta indexes
│       └── ...
│
├── tests/                          ← Test suite (see TEST_STATUS.md)
├── engine/                         ← Rust AST parser (compiled to Python wheel)
└── packages/ui/                    ← React component library (desktop app UI)
```

---

## What's Built vs What's Not

### ✅ Built and Working (Code Complete)

| Component | Status | Notes |
|---|---|---|
| `codrag sync-headless` CLI | ✅ Code complete, 24 tests | Runs full 11-stage pipeline headlessly |
| `S3StorageProvider` | ✅ Code complete, 14 tests | Upload, download, atomic swap, manifest |
| `Dockerfile.cpu` | ✅ Written | Needs first real build+push test |
| `Dockerfile.gpu` | ✅ Written | Needs first real build+push test |
| `docker-headless.yml` (our CI) | ✅ Written | Triggers on `app-v*` tags, pushes to `ghcr.io` |
| `codrag-sync.yml` (customer template) | ✅ Written | CPU+BYOK and GPU webhook modes |
| Modal adapter | ✅ Written | Python script for Modal.com |
| RunPod adapter | ✅ Written | Dockerfile + handler |
| AWS ECS reference | ✅ Written | Task definition JSON |
| `RemoteSyncService` (client) | ✅ Code complete, 23 tests | Polls S3, downloads new indexes |
| `LayeredCodeIndex` | ✅ Code complete, 8 tests | Merges remote + local with tombstoning |
| Incremental rebuild | ✅ Built-in | `trace_manifest.json` file hashes enable 90% skip |
| Secrets leakage detection | ✅ 5 tests | Scans `team_config.json` for credential-like keys |

### ⚠️ Written but NEVER Tested in Production

| Component | What needs to happen |
|---|---|
| **Docker images** | Build locally, push to `ghcr.io`, verify they actually work |
| **GitHub Actions workflow** | Run `codrag-sync.yml` against a real test repo |
| **Full end-to-end flow** | Push → headless build → S3 upload → client download → search works |
| **RunPod adapter** | Deploy to RunPod, trigger via webhook, verify index uploaded |
| **Modal adapter** | Deploy to Modal, trigger via webhook, verify index uploaded |
| **AWS ECS** | Deploy task definition, verify it runs |

### ✅ Recently Built (March 8, 2026)

| Component | Status | Notes |
|---|---|---|
| **Enterprise Admin panel** | ✅ Built | `EnterpriseAdminPanel.tsx` — compute fleet, sync fleet, usage KPIs. Gated by tier (team/enterprise) + role (admin). |
| **Admin role override** | ✅ Built | Developer settings → Role Override (User / IT Admin). Persists to localStorage. |
| **License verification in headless** | ✅ Built (soft gate) | Checks `CODRAG_LICENSE_KEY` env var for `codrag_team_` / `codrag_ent_` prefix. Warns but doesn't block (harden before launch). |
| **Panel registry entry** | ✅ Built | `enterprise-admin` in panel picker (Shield icon, status category). |

### ❌ Not Built Yet

| Component | Priority | Notes |
|---|---|---|
| **Dashboard sync status wiring** | High | `SyncStatusCard.tsx` exists and is imported but not rendered — needs sync API endpoint + sync status state in App.tsx |
| **Public docs** | High | Team Sync setup guide, Enterprise deployment guide |
| **Usage/billing telemetry** | Medium | Need to track indexing minutes per team in headless runner, store in S3 manifest |
| **License hard gate** | Medium | Headless runner currently soft-gates (warns). Needs to block before public Team launch. |
| **Health monitoring** | Low | Alert if headless builds fail repeatedly |
| **CoDRAG Manager** (Enterprise) | Future | Was planned as separate web service — now an in-app Enterprise Admin panel instead. May still need a lightweight coordinator for multi-user slot reservation. |

---

## Your First Week: Getting the Pipeline to Production

### Day 1: Verify Docker images build

```bash
# From the CoDRAG repo root:

# Build CPU image locally
docker build -f public/codrag-deploy/Dockerfile.cpu -t codrag/headless:cpu .

# Build GPU image locally (needs ~10GB disk)
docker build -f public/codrag-deploy/Dockerfile.gpu -t codrag/headless:gpu .

# Quick smoke test: does the CLI work?
docker run --rm codrag/headless:cpu codrag sync-headless --help
```

**Expected issues:**
- The Rust engine wheel may need to be pre-built or compiled during Docker build
- The ONNX model pre-download step may fail if HuggingFace is rate-limiting
- The GPU image needs Ollama's model pull to succeed during build

### Day 2: End-to-end test with a real repo

```bash
# 1. Create a test S3 bucket (Cloudflare R2 is free for <10GB)
# 2. Run headless against a small open-source repo:
docker run --rm \
  -e OPENAI_API_KEY=sk-... \
  codrag/headless:cpu \
  codrag sync-headless \
    --repo-url https://github.com/some-small-public-repo \
    --branch main \
    --s3-bucket your-test-bucket \
    --s3-prefix test/repo \
    --s3-endpoint https://your-r2-endpoint.r2.cloudflarestorage.com \
    --s3-access-key $R2_ACCESS_KEY \
    --s3-secret-key $R2_SECRET_KEY \
    --model-provider openai \
    --model-name gpt-4.1-mini \
    --embedder native

# 3. Verify artifacts in S3:
#    - manifest.json (version, timestamp, commit SHA)
#    - index-{timestamp}.zip (documents, embeddings, traces)
```

### Day 3: Push images to GHCR

```bash
# Trigger the workflow manually:
gh workflow run "Build Headless Docker Images" --ref main

# Or tag a release:
git tag app-v0.1.0-beta
git push origin app-v0.1.0-beta
# → docker-headless.yml will build and push to ghcr.io
```

### Day 4: Test the customer workflow

1. Fork a test repo
2. Copy `public/codrag-deploy/github-actions/codrag-sync.yml` to `.github/workflows/`
3. Add secrets: `CODRAG_S3_ENDPOINT`, `CODRAG_S3_BUCKET`, etc.
4. Push a commit and watch the workflow run
5. Verify the index appears in S3

### Day 5: Test client-side download

1. On a developer machine with CoDRAG installed:
2. Create `.codrag/team_config.json` in the test repo:
   ```json
   {
     "sync": {
       "enabled": true,
       "s3_endpoint": "https://your-r2-endpoint.r2.cloudflarestorage.com",
       "s3_bucket": "your-test-bucket",
       "s3_prefix": "test/repo/main"
     }
   }
   ```
3. Set credentials: `export CODRAG_S3_ACCESS_KEY=... CODRAG_S3_SECRET_KEY=...`
4. Start the CoDRAG daemon — it should download the remote index
5. Run a search query — it should return results from the remote index

---

## Our CI Workflows (for CoDRAG itself)

These are the workflows that build and test CoDRAG as a product. You'll maintain these.

| Workflow | Trigger | What it does | Status |
|---|---|---|---|
| `security-audit.yml` | Push to main, PRs, weekly cron | npm/cargo/pip security audit + Python tests + Rust tests | ✅ Working |
| `engine-wheels.yml` | Push to main, engine changes | Builds Rust engine wheels for macOS/Windows/Linux | ✅ Working |
| `release.yml` | `app-v*` tags | Builds Tauri desktop app for macOS/Windows | ✅ Working |
| `docker-headless.yml` | `app-v*` tags, manual | Builds + pushes headless Docker images to GHCR | ⚠️ Written, never tested |
| `websites-ci.yml` | Changes to websites/ | Builds docs and marketing sites | ✅ Working |

### Known CI Issues

1. **`security-audit.yml` runs Python tests** — some tests hang (see `docs/TEST_STATUS.md`). Need to add `pytest-timeout` and fix hanging test files.
2. **`docker-headless.yml` has never been triggered** — the images have never actually been built and pushed.
3. **No integration test workflow** — there's no CI job that runs the full headless → S3 → client download flow.
4. **Linux desktop release is commented out** in `release.yml` — needs uncommenting when ready.

---

## Key Decisions Already Made

These decisions are documented in the codebase and should not be revisited without discussion:

1. **Docker, not Lambda** — headless indexing runs in Docker containers, not serverless functions (too much state, too long-running)
2. **S3-compatible storage** — all cloud storage goes through the S3 API (boto3). This covers AWS S3, Cloudflare R2, MinIO, Backblaze B2.
3. **Customer-managed infrastructure** — we provide templates, customers run them in their own CI. We don't host anything for Team tier.
4. **No CoDRAG-hosted compute for Team** — customers bring their own OpenAI keys or GPU infrastructure. We don't proxy API calls.
5. **License check is now in headless (soft gate)** — the headless runner checks `CODRAG_LICENSE_KEY` env var and warns if missing. Needs hardening to a hard gate before public Team launch.
6. **Incremental rebuild is automatic** — when a previous index exists in S3, the pipeline downloads it first and only re-processes changed files. No special configuration needed.

---

## Communication & Access

- **Repository:** `github.com/EricBintner/CoDRAG` (private)
- **Docker registry:** `ghcr.io/ericbintner/codrag-headless` (`:cpu`, `:gpu`)
- **Test S3:** TBD — set up a Cloudflare R2 bucket for CI testing
- **Secrets needed:** GitHub repo secrets for GHCR push, S3 test credentials, OpenAI API key for integration tests
- **Key files to start with:**
  - This document
  - `docs/TEST_STATUS.md` — current test suite status and known failures
  - `docs/Phase06_Team_And_Enterprise/PROGRESS.md` — what's been built
  - `docs/Phase06_Team_And_Enterprise/TODO.md` — full backlog
  - `public/codrag-deploy/README.md` — customer-facing deployment overview

---

## FAQ

**Q: Do I need to understand the LLM pipeline to do this job?**
A: No. The headless runner is a black box — it takes a repo path and outputs index artifacts. You need to understand the Docker image, the S3 flow, and the CI workflow, not the 11 internal pipeline stages.

**Q: What languages/tools do I need?**
A: Docker, GitHub Actions (YAML), basic Python (for debugging), bash. The Rust engine and React UI are not your concern.

**Q: What's the difference between "our CI" and "customer CI"?**
A: Our CI (`/.github/workflows/`) builds and tests the CoDRAG product itself. Customer CI uses our templates (`/public/codrag-deploy/`) to run headless indexing on their codebases. You maintain both.

**Q: Why are there two Docker images?**
A: Cost and privacy trade-off:
- **CPU image** (~2-3 GB): Uses customer's OpenAI/Anthropic API key. Cheap to run, no GPU needed. Code leaves the customer's network via API calls.
- **GPU image** (~8-10 GB): Runs a local LLM (Qwen3:4b via Ollama). More expensive (needs GPU), but code never leaves the customer's infrastructure. Required for air-gapped/regulated environments.

**Q: What does the Enterprise tier add beyond Team?**
A: Enterprise extends Team with:
- **Enterprise Admin panel** — already built as an in-app dashboard panel (gated by admin role). Shows compute fleet status, sync fleet, and usage metrics.
- **VPC/air-gapped deployment** — the GPU image already supports this, but Enterprise adds managed support
- **SSO/OIDC** — authentication integration (future)
- **Multi-user compute coordination** — may need a lightweight coordinator service for cross-user slot reservation (future)
- Your role will expand to include operating any shared infrastructure when it's needed.

---

## CI/CD Roadmap — What's Next

### Sprint 1: Validate the Pipeline (CI/CD Engineer — Week 1)

These are the **blocking items** before Team tier can be sold:

| # | Task | Owner | Est. | Notes |
|---|---|---|---|---|
| 1 | Build Docker images locally (CPU + GPU) | CI/CD | 1 day | See "Day 1" above. Fix any build failures. |
| 2 | Push images to `ghcr.io` via `docker-headless.yml` | CI/CD | 0.5 day | Trigger manually or with a test tag. |
| 3 | End-to-end test: headless → S3 → client download | CI/CD | 1 day | Use Cloudflare R2 (free tier). Must verify search works after download. |
| 4 | Test the GitHub Actions customer template | CI/CD | 0.5 day | Fork a test repo, add `codrag-sync.yml`, push, verify. |
| 5 | Fix CI test hanging (`pytest-timeout`) | CI/CD | 0.5 day | Add `pytest-timeout` to dev deps, add `--timeout=60` to `security-audit.yml`. Ignore hanging files. |

### Sprint 2: Harden for Launch (CI/CD + Product — Week 2-3)

| # | Task | Owner | Est. | Notes |
|---|---|---|---|---|
| 6 | Harden license gate in headless | Product | 0.5 day | Change `_verify_license()` from soft gate (warn) to hard gate (reject). Need license server API. |
| 7 | Wire SyncStatusCard in dashboard | Product | 1 day | Add sync API endpoint, poll sync status, render `SyncStatusCard` below project status. |
| 8 | Wire Enterprise Admin panel with live data | Product | 1 day | Connect `syncFleet` and `usage` props to real backend data instead of empty stubs. |
| 9 | Write Team Sync public docs | Product | 2 days | Quick Start (CPU+BYOK), Advanced (GPU), Enterprise (ECS). |
| 10 | Test RunPod adapter | CI/CD | 1 day | Deploy to RunPod, trigger via webhook, verify index uploaded. |
| 11 | Test Modal adapter | CI/CD | 1 day | Deploy to Modal, trigger via webhook, verify index uploaded. |

### Sprint 3: Production Readiness (Week 4+)

| # | Task | Owner | Est. | Notes |
|---|---|---|---|---|
| 12 | Usage telemetry in headless | Product | 1 day | Track indexing minutes, store in S3 manifest. Display in Enterprise Admin panel. |
| 13 | Health monitoring | CI/CD | 1 day | Alert (email/Slack) if headless builds fail 3x in a row for a customer. |
| 14 | Finalize Team pricing | Product | Decision | $15/seat/month or $149/seat/year — depends on dogfooding results. |
| 15 | Linux desktop release | CI/CD | 0.5 day | Uncomment Linux matrix entry in `release.yml`. |
| 16 | Fix remaining test rot (9 failures) | Product | 1 day | See `docs/TEST_STATUS.md` for categorized list. |
| 17 | Fix hanging test files | Product | 1 day | `test_pipeline_orchestrator.py` and `test_scope_orchestrator.py` need rewrite. |

### Future (Enterprise Tier)

| Task | Notes |
|---|---|
| SSO/OIDC integration | Auth between desktop apps and org admin |
| Multi-user slot coordinator | Lightweight service for cross-user compute reservation |
| Cost tracking & billing | Per-team usage metering, invoice generation |
| Air-gapped deployment guide | Customer-facing docs for VPC/private cloud |
