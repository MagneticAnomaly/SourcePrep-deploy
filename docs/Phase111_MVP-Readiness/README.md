# Phase 111 -- MVP Readiness & Shipping Surface

> **Scope:** Trim the product surface for a shippable MVP, resolve dev/prod separation, fix remaining diagnostics, and validate the golden path.
> **Prior art:** Phases 78, 90, 97, 98, 99, 100, 101, 102
> **Status:** Research & TODO (**reality-checked 2026-04-15** — see §1.5; **new security gap surfaced**)
> **Date:** 2026-04-15

> **⚠️ Reality-check delta (2026-04-15):** Three significant findings.
> **(1) NEW SECURITY GAP:** `/admin/*` endpoints in `api/routers/settings.py:599-755` (audit-log, security-health, security-report, quarantine-project, block-endpoint, approve-config) are **exposed in production with zero guards**. Any client can call quarantine-project or block-endpoint. `test-model` endpoint (`llm.py:1088`) is also ungated. This is a **blocking** MVP issue.
> **(2) Marketing reframe:** §5.8 concern that path weights are "advertised but not implemented" is **inverted** — path weights ARE shipped (`index.py:1088-1114`). The real gap is that the **dashboard has no UI to write `path_weights` to config**; users must edit JSON or hit the API. "No LLM required" claim is honest: Fast Sync stages 2-3 skip gracefully (`pipeline/workers.py:351, 414`).
> **(3) Two Haley (§5.5) questions resolved:** `/trace/hub_files` returns `"path"` (not `"file_path"`); URL is `/trace/hub_files` (underscore). Three others remain.
> `CODRAG_DEV_MODE` is **worse than Phase 101 reported** — can be toggled at runtime via `license.py:580`. 17 dashboard pollers still active (not 14+); no `useSSEStatus` hook. DevToolbar correctly gated (marketing only, dashboard has none). See §1.5 for full verdict.

---

## 1. Problem Statement

CoDRAG has grown to 15 pipeline stages, 5 MCP tools, 76+ API endpoints, 37 dashboard panels, and a complex multi-model LLM orchestration system. This is impressive engineering -- but it's also too much surface area for a confident v1.0 release. The core question: **what is the MVP golden path, and does it work reliably?**

Phase 101 researched dev-only architecture trimming but found gaps: `CODRAG_DEV_MODE` is read inconsistently, the Python backend has debug endpoints exposed in production, and there's no runtime stripping of dev-only UI components.

Phase 90 diagnosed why Phases 83-88 showed partial results on the real "Haley" project -- a mix of API field name mismatches, missing initializations, and trace config flags gating features that should work regardless of config.

Phase 98 researched dashboard polling architecture and identified the polling storm issue (fixed in Phase 96 F-11), but the deeper fix (SSE-only status streams) was deferred.

Phase 97 researched free tier project limits but implementation status is unclear.

## 1.5 Reality Check Against Current Code (2026-04-15)

| Claim | Verdict | Evidence |
|---|---|---|
| §3.1 Haley Q1 `/trace/hub_files` field name | **FIXED** — returns `"path"` | `api/routers/trace_routes/query.py:637` |
| §3.1 Haley Q2 URL `-` vs `_` | **FIXED** — is `/trace/hub_files` | `query.py:609` |
| §3.1 Haley Q3 atlas cycle data API | **PARTIAL** | atlas.json has cycles; no dedicated project-level `/audit/findings` endpoint found |
| §3.1 Haley Q4 `run_structural_audit` detect cycles from trace graph | **DESIGN-OPEN** | `core/audit/structural.py:328` uses legacy findings approach |
| §3.2 `CODRAG_DEV_MODE` read inconsistently | **CONFIRMED** (worse than reported) | `feature_gate.py:146`, `security_health.py:307`, `license.py:149`, `mcp_tools.py:13`. `license.py:580` **sets at runtime** via API. |
| §3.2 DevToolbar in marketing | **CORRECTLY GATED** | `websites/apps/marketing/src/app/page.tsx:25, 32` uses `process.env.NODE_ENV !== 'production'`. Dashboard has no DevToolbar import. |
| §3.2 Debug endpoints exposed in production | **CONFIRMED + EXPANDED** | `/admin/*` at `api/routers/settings.py:599-755` has **zero guards**: admin/audit-log, /security-health, /security-report, /actions/quarantine-project, /actions/block-endpoint, /actions/approve-config. `llm.py:1088` `/api/llm/proxy/test-model` also ungated. |
| §3.3 "14+ pollers" | **CONFIRMED — 17 found** | `App.tsx` (4), `useEnrichment.ts`, `useDeepAnalysis.ts`, `useRoadmapSystem.ts`, `useProjectManager.ts` (2), `useLLMConfig.ts`, `useOpportunitiesSystem.ts`, `useGoalpostsSystem.ts`, `useTraceSystem.ts`, `UpdateBanner.tsx` |
| §3.3 SSE stream exists but limited to build/pipeline events | **CONFIRMED** | `App.tsx:315-316` connects to `/events`; no `useSSEStatus` hook found |
| §3.4 MCP resilience / retry / circuit breaker | **NOT FOUND** | No circuit breaker, retry logic, cached-context fallback visible |
| §3.5 Free tier enforcement | **LIVE** | `services/project_helpers.py:165-260`: `is_project_archived`, `is_project_active`, `get_free_tier_slots` (1 active + 2 frozen), `require_project_writable` |
| §5.8 "path weights advertised but not implemented" | **INVERTED — SHIPPED but no UI** | `index.py:1088-1114` applies path_weights; `repo_policy.py:132` config schema. Dashboard has no Knowledge Graph path-weight UI; users must edit JSON/API. |
| §5.8 "No LLM required" | **TRUE** | `pipeline/workers.py:351, 414` stages 2-3 return `{"skipped": True, "reason": "no_llm"}` when no LLM configured |
| §5.8 Intent classification marketing claim | **TRUE & SHIPPED** | 7-intent classifier in `core/intent.py` (see Phase 110 reality check) |

**Commits landed since draft touching §5 areas:**
- `cd26590d` feat(marketing): merge feat/research-page (adds path-weights mention on research page)
- Phase 105a/b series — affects §5.5 Haley endpoint audit (see Phase 107 reality check)
- No commits since draft address `/admin/*` guards, SSE migration, or dev-mode consistency.

**Bottom line:** §3.1 partly resolved; §3.2 is worse than reported (runtime-toggleable + unguarded admin routes); §3.3 polling count is 17 not 14; §5.8 inverted (path weights shipped, UI missing). Three new items added to §5.3. Security-gap remediation should block MVP release.

## 2. The MVP Golden Path

The minimum viable experience a new user must have:

```
1. Install CoDRAG (Tauri .dmg / pip install)
2. Add a project (select folder)
3. Wait for pipeline (Fast Sync 1-5 runs automatically)
   - Structural graph: Rust engine, seconds
   - Inferred edges: LLM, minutes
   - Catalogue: LLM, minutes
   - Validation: Rust, seconds
   - Knowledge embedding: ONNX, seconds
4. Open Cursor/Windsurf/Claude Code
5. Type a question about their codebase
6. codrag MCP tool returns useful structural context
7. codrag_search returns relevant code chunks
```

**Everything else is enhancement.** Deep Enrichment (stages 6-10), Finalize (stages 11-15), Swarm, Compression, Role Lens, Atlas Routing -- all valuable, all optional for MVP.

## 3. Diagnostic Findings

### 3.1 Phase 90: Haley Diagnostic

21 pending verification tasks, including:
- Does `/trace/hub_files` return `"path"` or `"file_path"`?
- Is the URL `/trace/hub-files` or `/trace/hub_files`?
- Does the atlas cycle data from `atlas.json` have a dedicated API?
- Should `run_structural_audit` detect cycles from the trace graph directly instead of relying on legacy findings?

These are small but indicative: API surface inconsistencies that would confuse any integrator.

### 3.2 Phase 101: Dev-Only Architecture

Key findings:
- `CODRAG_DEV_MODE` is read inconsistently across Python backend
- Can be set at runtime (should only be set at build/startup time)
- No stripping of dev-only UI components in production Vite build
- DevToolbar is wired into marketing site (correct for dev, wrong for prod)
- Debug API endpoints (test-model, test-endpoint) are exposed in production

### 3.3 Phase 98: Dashboard Polling

Phase 96 F-11 fixed the immediate polling storm. But the architecture is still poll-based:
- 14+ pollers, each hitting the daemon at 5-30s intervals
- SSE `/events` stream exists but only carries build/pipeline events, not status updates
- Consolidating to SSE-only would eliminate the entire polling class of bugs

### 3.4 Phase 78: Dev Server Stability

MCP server stability research. The MCP server disconnects during heavy pipeline activity (F-13, diagnosed as F-11 manifestation). Fix was polling reduction, but the MCP server should be resilient to daemon overload.

### 3.5 Phase 97: Pricing & Tier Enforcement

Free tier project limits (1 active + 2 frozen + rest locked) are implemented in `project_helpers.py` but:
- Archive vs Purge strategy was designed but unclear if shipped
- Free tier upgrade prompts in UI may not be wired

### 3.6 Phase 99: Content

Content phase -- unclear what was planned or completed.

### 3.7 Phase 102: Prep & Rename

Preparation for rename/rebrand. Unclear scope and status.

## 4. Proposed Solutions

### Solution A: MVP Feature Gate

Define a `MVP_FEATURES` list that gates what runs automatically for new users:
- Fast Sync (stages 1-5): ALWAYS
- Deep Enrichment (stages 6-10): ONLY if user explicitly triggers or has Pro license
- Finalize (stages 11-15): ONLY if user explicitly triggers or has Pro license
- Swarm: OFF by default
- Compression: OFF by default (LOD is zero-cost, but LLMLingua needs model download)
- Atlas routing: AUTO (runs if >= 150 files, transparent to user)

This reduces the "time to first value" from potentially hours (full 15-stage pipeline) to minutes (5-stage fast sync).

### Solution B: API Surface Audit

Systematically verify every public API endpoint:
1. Does it return the envelope format `{success, data, error}`?
2. Are field names consistent (`file_path` vs `path` vs `filePath`)?
3. Does it work when pipeline hasn't run yet (graceful degradation)?
4. Does it work on a brand-new empty project?
5. Is it documented in API.md?

### Solution C: Dev/Prod Separation

1. Make `CODRAG_DEV_MODE` a build-time constant (set via env var at package/bundle time, not runtime)
2. Vite: use `import.meta.env.MODE` to tree-shake dev-only components
3. Python: use a `_DEV_ONLY` decorator on debug endpoints; production startup skips registration
4. Remove DevToolbar from production builds

### Solution D: SSE Status Consolidation

Extend the existing `/events` SSE stream to carry all status updates:
- Pipeline stage progress
- Build status
- Scheduler queue changes
- Health status

Dashboard switches from polling to SSE subscription. Pollers removed. Connection count drops from 14+ to 1.

## 5. TODO

### 5.0 NEW — Security Gaps (BLOCKING for MVP)
Discovered during reality check. Must be closed before public release.
- [ ] Guard `/admin/*` endpoints in `api/routers/settings.py:599-755` (require `CODRAG_DEV_MODE` OR auth token) — **[STILL-OPEN, BLOCKING]**
- [ ] Guard `/api/llm/proxy/test-model` at `llm.py:1088` — **[STILL-OPEN, BLOCKING]**
- [ ] Make `CODRAG_DEV_MODE` startup-time-only; remove runtime write at `license.py:580` (or gate behind a signed dev token) — **[STILL-OPEN, BLOCKING]**
- [ ] Enumerate all `/admin/*`, `/dev/*`, `/debug/*` routes; apply consistent guard decorator — **[STILL-OPEN]**

### 5.1 MVP Golden Path Validation — all human QA
- [ ] Fresh install on clean macOS — **[NEEDS-VERIFICATION]**
- [ ] Add small test repo (~50 files) — **[NEEDS-VERIFICATION]**
- [ ] Fast Sync stages 1-5 auto-complete in ≤5m — **[NEEDS-VERIFICATION]**
- [ ] KB Status shows "Ready" — **[NEEDS-VERIFICATION]**
- [ ] Open Cursor w/ CoDRAG MCP — **[NEEDS-VERIFICATION]**
- [ ] `codrag` returns structural overview — **[NEEDS-VERIFICATION]**
- [ ] `codrag_search("where is the main entry point")` returns relevant result — **[NEEDS-VERIFICATION]**
- [ ] Medium repo (~500 files) ≤15m — **[NEEDS-VERIFICATION]**
- [ ] Large repo (~2000 files) ≤30m — **[NEEDS-VERIFICATION]**
- [ ] Document failures in phase findings file — **[NEEDS-VERIFICATION]**

### 5.2 API Surface Audit
- [ ] Enumerate all public endpoints (currently 76+) — **[STILL-OPEN]**
- [x] Verify envelope format — **[PARTIAL]** sampled routers use `ok(...)` wrapper consistently; full audit not done
- [x] Verify field name consistency (`path` vs `file_path`) — **[PARTIAL]** hub_files confirmed `"path"`; other routers not audited
- [ ] Verify graceful degradation on empty/new projects — **[STILL-OPEN]**
- [ ] Fix any inconsistencies found — **[STILL-OPEN]**
- [ ] Update API.md with undocumented endpoints — **[STILL-OPEN]**

### 5.3 Dev/Prod Separation (Phase 101 completion)
- [ ] Audit all `CODRAG_DEV_MODE` reads — standardize to single import module — **[STILL-OPEN]** (5+ separate reads found)
- [ ] Make dev mode startup-time-only (not runtime-changeable) — **[STILL-OPEN]** (see §5.0 — `license.py:580` writes at runtime)
- [ ] Add `_dev_only` decorator for debug endpoints — **[STILL-OPEN]**
- [x] Vite production build: DevToolbar tree-shaken — **[CORRECTLY GATED]** (`NODE_ENV !== 'production'` check in marketing; dashboard has no DevToolbar)
- [ ] Vite production build: no debug console.log ships — **[NEEDS-VERIFICATION]**
- [ ] Tauri production build: sidecar without dev deps — **[NEEDS-VERIFICATION]**
- [ ] Create BUILD_MODES.md — **[STILL-OPEN]** (file does not exist)

### 5.4 Dashboard Polling -> SSE Migration
- [x] Audit pollers — **[PARTIAL]** 17 confirmed: `App.tsx` (4), `useEnrichment.ts`, `useDeepAnalysis.ts`, `useRoadmapSystem.ts`, `useProjectManager.ts` (2), `useLLMConfig.ts`, `useOpportunitiesSystem.ts`, `useGoalpostsSystem.ts`, `useTraceSystem.ts`, `UpdateBanner.tsx`
- [ ] Extend `/events` SSE schema (pipeline_progress, build_status, scheduler_queue, health) — **[STILL-OPEN]**
- [ ] Implement `useSSEStatus` hook — **[STILL-OPEN]** (not in tree)
- [ ] Replace pollers one-by-one — **[STILL-OPEN]**
- [ ] Remove `setInterval` polling from hooks — **[STILL-OPEN]**
- [ ] Verify dashboard works SSE-only — **[STILL-OPEN]**
- [ ] Measure: steady-state TCP connections 1-3 — **[STILL-OPEN]**

### 5.5 Phase 90 Diagnostics (Haley findings)
- [x] `/trace/hub_files` field name — **[FIXED]** returns `"path"` (`query.py:637`)
- [x] URL normalization — **[FIXED]** is `/trace/hub_files` (`query.py:609`)
- [ ] `GET /projects/{id}/audit/findings` returns data — **[NEEDS-VERIFICATION]** (endpoint not located in this pass)
- [ ] Atlas cycle data accessibility — **[PARTIAL]** data lives in atlas.json; dedicated API unconfirmed
- [ ] `run_structural_audit` detect cycles from trace graph directly — **[DESIGN-OPEN]**
- [ ] Fix API inconsistencies found — **[PARTIAL]** (two closed; others depend on enumeration)
- [ ] Verify remaining Phase 90 tasks — **[STILL-OPEN]** (2 of 21 closed here; others likely QA-level)

### 5.6 Free Tier Enforcement
- [x] 1 active + 2 frozen + rest locked — **[FIXED]** (`project_helpers.py:206-225`)
- [ ] Upgrade prompts in dashboard — **[NEEDS-VERIFICATION]** (LicenseStatusCard not inspected)
- [x] Archive vs purge behavior — **[FIXED]** (archive sets `config.archived`; `require_project_writable` blocks locked)
- [ ] Tier display in LicenseStatusCard — **[NEEDS-VERIFICATION]**

### 5.7 MCP Server Resilience — **STILL-OPEN (0/4)**
- [ ] Handle daemon overload gracefully (timeout + retry) — **[STILL-OPEN]**
- [ ] Circuit breaker: >5s unresponsive → cached context — **[STILL-OPEN]**
- [ ] Health check on startup — **[STILL-OPEN]**
- [ ] Test: full 15-stage pipeline on large repo, MCP stays connected — **[STILL-OPEN]**

### 5.8 Content & Marketing Alignment — **REFRAMED**
Original framing assumed path weights were marketed-but-unshipped. Opposite is true: they're shipped but have no dashboard UI. Revised items:
- [x] "Path weights" marketed & backend-implemented — **[FIXED]** (see §1.5; `index.py:1088-1114`)
- [ ] **NEW:** Dashboard Knowledge Graph UI for writing `path_weights` — **[STILL-OPEN]** Current path to set weights is JSON edit or API; no UI sliders/panel. Either add a small UI or document the API-only configuration in user docs.
- [x] "No LLM required" — Fast Sync skips stages 2-3 gracefully — **[FIXED]** (`pipeline/workers.py:351, 414` return `{"skipped": True, "reason": "no_llm"}`)
- [ ] "Works offline" — verify zero network calls in default configuration — **[NEEDS-VERIFICATION]** (structural phase is offline; full trace is offline; LLM stages are opt-in)
- [x] Intent classification marketing claim — **[FIXED]** 7-intent classifier shipped (see Phase 110)
- [ ] Update any stale marketing copy found during audit — **[STILL-OPEN]**

## 6. Links to Prior Work

| Phase | What it built | Status | Gap this phase addresses |
|---|---|---|---|
| 78 | MCP Server Stability Research | Research complete; no resilience code | §5.7 (0/4) |
| 90 | Haley Diagnostic Report | **2/21 now closed** (hub_files field + URL); 19 remain | §5.5 |
| 97 | Pricing/Tier Update | **Live** (`project_helpers.py:165-260`) | §5.6 — upgrade prompts + LicenseStatusCard verification |
| 98 | Dashboard Polling | F-11 mitigated; **17 pollers remain**; no SSE hook | §5.4 |
| 99 | Content | Status unclear | §5.8 (reframed — dashboard UI for path_weights) |
| 100 | NVIDIA Research | Validates direction | — |
| 101 | Dev-Only Architecture | **Worse than reported** — runtime-toggleable + unguarded admin routes | §5.0 + §5.3 |
| 102 | Prep & Rename | Status unclear | — |

## 7. Success Criteria

1. **Golden path works end-to-end:** fresh install -> add project -> fast sync -> MCP query -> useful result, all within 15 minutes
2. **API surface is consistent:** 100% envelope format, 100% field name consistency
3. **Dev code doesn't ship to users:** zero debug endpoints, zero DevToolbar, zero console.log
4. **Dashboard is SSE-driven:** steady-state connections <= 3
5. **Free tier enforced:** project limits, upgrade prompts, archive/purge all working
6. **Marketing claims verified:** every feature claimed on codrag.io is implemented and working
