# Phase 41 — Managing Multiple Projects

## The Problem

CoDRAG's pipeline (10-stage graph enrichment) is designed around a single-project mental model. When a user has multiple projects open and Auto mode is enabled, the daemon naively triggers pipeline runs for ALL trace-enabled projects simultaneously. This causes:

1. **Resource exhaustion**: Ollama receives concurrent LLM requests from N projects, causing mass timeouts (60s) and wasted GPU cycles
2. **Unreadable logs**: Progress from different projects interleaves (`21/29 — 72%` next to `21/4167 — 0%`)
3. **No prioritization**: The project the user is actively working on gets the same priority as a project they haven't touched in weeks
4. **Free tier confusion**: A user who downgrades has 25 projects but can only use 1 — what happens to the other 24?
5. **Team scaling**: Multiple developers on different codebases sharing one GPU server — no concept of concurrency limits or project scheduling

---

## Current Infrastructure Audit

### Project Registry (`project_registry.py`)
- SQLite table: `id, name, path, mode, config, created_at, updated_at`
- **No `active` or `status` field** — every project is implicitly "active"
- `mode` is about storage location (`standalone` / `embedded` / `custom`), NOT activity state
- `config` is a JSON blob with trace settings, globs, etc.

### Feature Gating (`feature_gate.py`)
- `projects_max`: FREE=1, PRO/TEAM/ENTERPRISE=999
- `is_over_project_limit()` only checks count, not which projects are active
- Watcher (`auto_rebuild`) is gated at MONTHLY+ tier
- No concept of "active project slots" vs "total projects"

### Pipeline Orchestrator (`pipeline_orchestrator.py`)
- `_start_group()` blocks concurrent runs for the **same** project
- But nothing prevents N **different** projects from running simultaneously
- Startup auto-run iterates ALL trace-enabled projects sequentially (recent fix)
- No concept of a project queue or priority

### Watcher (`watcher.py`)
- `AutoRebuildWatcher` — one per project, watches filesystem for changes
- Started via `POST /projects/{id}/watch/start`
- Each watcher is independent — N watchers = N debounce timers + N watchdog observers

### Team Sync (`remote_sync.py`, `headless_runner.py`, `layered_index.py`)
- **HeadlessRunner**: Runs on CI/CD (GitHub Actions), builds index, uploads to S3
- **RemoteSyncService**: Client-side, polls S3 for updates, downloads to `remote/`
- **LayeredCodeIndex**: Merges remote (shared team) + local_deltas (dev's changes)
- Architecture: One S3 bucket per team, one prefix per project/branch
- **The GPU is NOT shared in real-time** — headless builds run in CI, devs get pre-built indexes

### Build Manager (`build_manager.py`)
- Caches per-project: CodeIndex, TraceIndex, KnowledgeIndex
- Each type has its own lock + thread dict
- No global concurrency limit across projects

---

## Problem Decomposition by Tier

### 1. Pro (Solo Developer) — Simplest

**Scenario**: Developer has 5-25 projects. Works on 1-3 actively. Others are reference or inactive.

**Problems**:
- Auto mode tries to run all 25 projects on startup → GPU overwhelmed
- No way to say "only auto-sync these 3 projects"
- No priority: actively-edited project waits behind stale reference projects

**Proposed Solution: Active/Inactive Toggle**

| Concept | Behavior |
|---|---|
| **Active** | Watcher runs, auto-sync enabled, pipeline runs on startup/changes |
| **Inactive** | Watcher stopped, no auto-sync, pipeline only runs on manual trigger |
| Default | New projects start as Active. Switching to inactive stops watcher + removes from auto-run queue |

**Implementation scope**:
- Add `active: boolean` to project config (persisted in project registry)
- Startup auto-run: only iterate `active` projects
- Watcher management: auto-stop watcher when project goes inactive
- Dashboard: toggle in project settings, visual indicator in project list
- **Concurrency limit**: Even among active projects, process one at a time (already fixed via sequential startup). Could add a setting: "Max concurrent pipeline projects" (default: 1)

**Open questions**:
- P1: Should the "currently selected" project in the UI be auto-promoted to active?
- P2: Should there be a maximum number of active projects? (e.g., Pro = 5 active, rest inactive)
- P3: When a user switches to a project in the sidebar, should it auto-activate?

---

### 2. Free Tier — Locked Down

**Scenario**: User was Pro, downgraded to Free. Has 15 projects. Free tier allows 1 project.

**Current behavior**: `is_over_project_limit()` returns True, but nothing enforces which project is the "allowed" one. User can still view all projects, just can't start watchers.

**Problems**:
- Which project is the "one allowed project"?
- Can they switch? Or are they stuck with whatever was last active?
- What happens to the trace graphs of the other 14 projects? (Data still on disk)

**Proposed Solution: Auto-Determined Slots (1 Active + 2 Frozen + Rest Locked)**

The key constraint: **Free users cannot manually choose which project is active.**
If they could switch freely, someone could pay for 1 month, build 10 repos, cancel,
and continue working all 10 forever — undermining the entire pricing model.

| Slot | Count | Behavior | How determined |
|---|---|---|---|
| **Active** | 1 | Full functionality: build, search, trace, pipeline, MCP, watcher | Most recently used project (by `updated_at`) |
| **Frozen** | 2 | Read-only: can view existing trace data, search works on stale index, no rebuild/pipeline | 2nd and 3rd most recent by `updated_at` |
| **Locked** | All others | Not visible in MCP, no data served, project exists in registry but completely inert | 4th+ by `updated_at` |

**Advertised as: "1 active project"** — the 2 frozen slots are a grace period, not a feature.

**Anti-abuse logic**:
- Active project is auto-determined by `updated_at` timestamp (most recent wins)
- Opening a project in the dashboard updates `updated_at` → it becomes active
- The PREVIOUS active project drops to frozen (slot 2)
- The previous slot-2 project drops to slot 3
- Slot 3 drops to locked
- **No manual override** — you can't "pin" a project on Free tier
- This means a Free user who cancels Pro can still work on their LAST project,
  can reference 2 more read-only, but the other 7+ are completely dark

**Implementation scope**:
- `get_free_tier_slots(projects) -> (active_id, frozen_ids, locked_ids)` — pure function, sorted by `updated_at`
- On Free tier: write endpoints check `project_id == active_id`, return 403 otherwise
- Frozen projects: read endpoints work (search, context, status), write endpoints return 403
- Locked projects: ALL endpoints return 403 with "Upgrade to Pro to access this project"
- MCP: only routes to the active project on Free tier
- Dashboard: locked projects shown dimmed with lock icon; frozen shown with snowflake icon
- **Data preservation**: we never delete data on downgrade — if they re-subscribe, everything comes back
- **No new projects**: `is_over_project_limit()` blocks `POST /projects` on Free tier (already exists)

**Open questions**:
- F1: Should opening a locked project in the sidebar auto-promote it to active (bumping others down)?
  **Proposed: Yes** — this is the natural "switching" mechanism. They can only have 1 active at a time.
- F2: Should MCP serve frozen projects in read-only mode? (Could be useful for cross-repo context)
  **Proposed: No** — MCP only serves active project. Keeps it simple and maintains upgrade incentive.
- F3: Grace period after downgrade? (e.g., 7 days of full access before slots kick in)
  **Proposed: No** — slots take effect immediately on downgrade. They already got the value while paying.

---

### 3. Team Tier — Deep Architecture Analysis

#### The Core Question

> "Don't we need a centralized graph DB for the whole team, a means to sync
> with it, AND access to dedicated GPU(s) for this task?"

**Answer: Not with the current architecture.** The existing team system was
deliberately designed as a **distribution model**, not a shared-state model.
Here's how it actually works:

#### What EXISTS Today

```
┌─────────────────────────────────────────────────────────────────┐
│  CI/CD (GitHub Actions / Modal / AWS)                           │
│                                                                  │
│  codrag sync-headless --repo-url=... --branch=main              │
│                                                                  │
│    1. git clone (shallow)                                       │
│    2. Download existing index.zip from S3 (incremental)         │
│    3. Run 10-stage pipeline:                                    │
│       - Stages 1,4: Rust (CPU, fast)                            │
│       - Stages 2,3: Fast LLM (cloud API: GPT-4.1-nano $0.10/M) │
│       - Stages 5,10: ONNX embeddings (CPU)                     │
│       - Stages 6-9: Thinking LLM (cloud: Claude Sonnet $3/M)   │
│    4. Upload index.zip + manifest.json to S3                    │
│                                                                  │
│  Triggers: git push to main, nightly cron, manual dispatch      │
│  Cost: ~$0.50-5.00 per full pipeline run (cloud LLM tokens)     │
│  Duration: 5-30 min depending on repo size                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │  S3 bucket (the "centralized store")
                           │  s3://codrag-team-acme/
                           │    backend/index.zip        (~50-200 MB)
                           │    backend/manifest.json    (version, hash)
                           │    frontend/index.zip
                           │    frontend/manifest.json
                           │    mobile-app/index.zip
                           │    mobile-app/manifest.json
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Developer Machine (macOS / Windows / Linux)                    │
│                                                                  │
│  CoDRAG daemon (localhost:8400) — runs per developer            │
│                                                                  │
│  RemoteSyncService                                              │
│    → Polls S3 every 30 min (configurable)                       │
│    → Compares manifest.json hash with local copy                │
│    → If newer: downloads index.zip → extracts to /remote/       │
│    → Prunes stale local deltas covered by new remote index      │
│                                                                  │
│  LayeredCodeIndex (the merge layer)                             │
│    → Remote layer: .codrag/index/remote/ (the team's index)     │
│    → Delta layer:  .codrag/index/local_deltas/ (dev's edits)    │
│    → Search merges both: delta results override remote           │
│    → Tombstone masking: if file X is in delta, remote X hidden  │
│                                                                  │
│  What devs' local daemon actually does:                         │
│    → Watcher detects file changes → delta build only            │
│    → Delta = re-embed just the changed files (ONNX CPU, fast)   │
│    → NO full pipeline, NO LLM calls, NO GPU needed              │
│    → MCP serves merged (remote + delta) results to IDE          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Architecture Decisions Already Made

| Decision | Rationale |
|---|---|
| **S3 is the "centralized store"** | No always-on server needed. Devs pull when ready. S3 is $0.023/GB/month. |
| **GPU lives in CI/CD, not on a server** | Pay-per-minute (GitHub Actions: $0.008/min). No idle GPU cost. Team doesn't need to provision hardware. |
| **Each dev runs own daemon** | No auth needed. No single point of failure. Works offline (stale index still useful). |
| **30-min poll interval** | Code graphs change on merge-to-main, not per-keystroke. 30 min is fine. |
| **Cloud LLM for CI builds** | CI doesn't need a local GPU — use BYOK cloud APIs (OpenAI/Anthropic/Google). Cost: $0.50-5.00 per run. |
| **Local deltas are CPU-only** | Structural parsing (Rust) + embedding (ONNX) = no GPU, no LLM calls. Subsecond for single-file changes. |

#### Why This Design Works (And When It Doesn't)

**It works when:**
- Team has 2-20 repos
- Code merges to main a few times per day
- Devs need code graph for AI context, not real-time collaboration
- Team has CI/CD (GitHub Actions, GitLab CI, etc.)
- Budget: $50-200/month for cloud LLM tokens in CI

**It breaks down when:**
- Team needs **real-time cross-repo queries** ("find all callers of UserService.create across all 15 microservices") — requires a live graph DB, not zip files
- Team needs **instant sync** (< 1 min after merge) — requires webhooks + persistent server
- Team has **no CI/CD** and wants CoDRAG to host the GPU
- Team wants **collaborative graph editing** (annotations, manual edges)

Those are Enterprise features, not Team tier.

#### What's Missing for a Shippable Team Product

| Gap | Severity | Description |
|---|---|---|
| **No branch support at scale** | Medium | S3 prefix supports branches but no cleanup of stale branch indexes |
| **No conflict handling** | Low | If two CI runs for same branch overlap, last-write-wins. Rare in practice. |
| **No dashboard sync indicator** | Medium | Devs can't see "Last synced from CI: 2h ago" in the UI |
| **No webhook trigger** | Low | Could speed up sync from 30-min poll to near-instant via S3 event notification |
| **No multi-repo query** | High (future) | Can't query across repos. Each repo is isolated. Enterprise feature. |
| **Setup is manual** | Medium | No "team onboarding wizard" — devs must manually configure S3 creds + team_config.json |

#### What Teams Configure

All configuration is already implemented:

| Setting | Where | Status |
|---|---|---|
| S3 bucket/endpoint | `.codrag/team_config.json` (committed to repo) | ✅ Exists |
| S3 credentials | Env vars or `.codrag/.secrets` (gitignored) | ✅ Exists |
| CI pipeline template | GitHub Actions / Docker | ✅ Exists in `public/codrag-deploy/` |
| Poll interval | `team_config.json` → `poll_interval_minutes` | ✅ Exists (default 30) |
| LLM for CI builds | Headless config `--model-provider` + `--api-key` | ✅ Exists (OpenAI/Anthropic/Google) |
| Which branches | Headless config `--branch` | ✅ Exists |

#### Team Tier Pricing Model Implication

The Team tier ($15/seat/month) pays for:
1. **The license** (Team features: shared config, policy management)
2. **NOT the compute** — teams bring their own CI/CD and S3

This is important: CoDRAG doesn't run GPU infrastructure for teams. Teams pay
for CI minutes (GitHub Actions ~$0.008/min) and cloud LLM tokens (~$0.50-5.00/run)
separately. CoDRAG's Team tier is a software license, not a hosting service.

#### Future: Enterprise (Hosted GPU)

If there's demand for CoDRAG-hosted compute:
- CoDRAG runs the headless pipeline on our infrastructure
- Customer connects their repo (GitHub App integration)
- We manage GPU scheduling, S3 storage, index distribution
- Pricing: per-repo per-month (e.g., $50/repo/month includes compute)
- This is a fundamentally different business model (SaaS, not license)

---

## Recommended Implementation Order

### Sprint 1: Active/Inactive Projects (Pro + Free)

1. **Add `active` field to Project config**
   - Default: `true` for existing projects (backward compat)
   - Persisted in project registry config JSON
   - API: `PUT /projects/{id}` with `{ config: { active: true/false } }`

2. **Filter startup auto-run to active projects only**
   - `_startup_auto_run()` in server.py: skip inactive projects
   - Watcher management: don't start watchers for inactive projects

3. **Dashboard: Active/Inactive toggle**
   - Project list sidebar: visual indicator (dimmed for inactive)
   - Project settings: toggle switch
   - Confirmation dialog when deactivating: "This will stop auto-sync for this project"

4. **Concurrency setting**
   - `pipeline_config.max_concurrent_projects` (default: 1)
   - Startup auto-run respects this limit
   - Future: pipeline orchestrator could manage a global project queue

### Sprint 2: Free Tier Pinned Project

5. **Implement pinned project for Free tier**
   - `settings.set("pinned_project_id", project_id)`
   - Enforce in write endpoints (build, pipeline, watcher)
   - Allow switching (no rate limit)

6. **Frozen project UX**
   - Read-only badge in project list
   - Informative message when trying to build/sync

### Sprint 3: Team Improvements (CI/CD Mode)

7. **Headless runner: skip unchanged repos**
   - Check git diff since last build
   - If no changes, skip pipeline (save CI minutes)

8. **Multi-repo workflow template**
   - GitHub Actions matrix strategy for N repos
   - Shared S3 bucket with per-repo prefixes

---

## Resource Budget Estimates

| Projects Active | Ollama VRAM (4b model) | Pipeline Duration (per project) | Startup Delay |
|---|---|---|---|
| 1 | ~3 GB | 5-30 min | 3s |
| 3 | ~3 GB (sequential) | 15-90 min total | 3s |
| 5 | ~3 GB (sequential) | 25-150 min total | 3s |
| 10+ | Not recommended for local | Hours | 3s |

**Recommendation**: Default `max_concurrent_projects = 1`. Power users with dedicated GPU servers can increase to 2-3.

---

## Open Questions Summary

| ID | Question | Tier |
|---|---|---|
| P1 | Auto-promote selected project to active? | Pro |
| P2 | Max active projects per tier? | Pro |
| P3 | Auto-activate on project switch in sidebar? | Pro |
| F1 | Auto-run pipeline when switching pinned project? | Free |
| F2 | MCP only serves pinned project on Free? | Free |
| F3 | Rate limit on switching pinned project? | Free |
| T1 | When to build T2 (shared GPU server)? | Team |
| T2 | Auth model for shared daemon? | Team |
| T3 | GPU scheduling algorithm? | Team |
