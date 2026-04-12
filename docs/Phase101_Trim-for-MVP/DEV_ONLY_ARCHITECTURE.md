# Dev-Only Architecture & Dead Code Elimination Strategy (Phase 101)

**Last Audit:** April 2026
**Scope:** Full-stack — Tauri/Rust, Vite/React dashboard, Python daemon, MCP server

---

## Objective

Establish a strict separation between development and production across **every layer** of the CoDRAG desktop application. This is not just about the frontend or Tauri shell — the Python daemon API, the MCP server, the license system, and the build tooling all have dev-only code that must be gated or stripped before shipping to users.

**Non-goal:** The `websites/apps` marketing sites have their own dev/prod separation (Next.js handles this natively). This document focuses exclusively on the **core product** that ships as a Tauri `.dmg`/`.msi`.

---

## Full-Stack Audit Results

### Legend

| Status | Meaning |
|--------|---------|
| **MISSING** | No dev/prod separation exists; ships to prod as-is |
| **PARTIAL** | Some gating exists but is incomplete or inconsistent |
| **OK** | Properly gated behind dev-only checks |

---

## Layer 1: Python Daemon API (`src/codrag/api/routers/`)

The Python daemon runs as a sidecar process. It exposes HTTP endpoints consumed by the dashboard frontend and the MCP server. **The previous version of this document completely ignored this layer.**

### Finding 1.1: `POST /license/dev-override` endpoint — **MISSING**

`src/codrag/api/routers/license.py:502-584`

This endpoint writes a fake license file to disk with `activation_method: "dev_override"` and `seats: 999`. It sets `CODRAG_DEV_MODE=1` in the process environment. **It is unconditionally registered as a FastAPI route** — any user who discovers the endpoint can grant themselves an Enterprise license.

**Risk:** CRITICAL. A user running the daemon could `curl POST /license/dev-override` with `{"tier": "enterprise"}` and unlock all features permanently.

**Fix:** Gate this endpoint behind `CODRAG_DEV_MODE=1` being set *before* the daemon starts. The endpoint itself should refuse to execute if `CODRAG_DEV_MODE` was not already in the environment at startup:

```python
_STARTUP_DEV_MODE = os.environ.get("CODRAG_DEV_MODE", "").strip() == "1"

@router.post("/license/dev-override")
def set_dev_tier_override(req: DevTierOverrideRequest) -> Dict[str, Any]:
    if not _STARTUP_DEV_MODE:
        raise ApiException(status_code=403, code="FORBIDDEN",
            message="Dev override is only available when daemon is started with CODRAG_DEV_MODE=1")
    # ... existing logic ...
```

### Finding 1.2: License Activation Method 3 (dev shortcuts) — **PARTIAL**

`src/codrag/api/routers/license.py:147-166`

The `POST /license/activate` endpoint accepts plain tier names ("pro", "enterprise") or raw JSON as license keys — but only when `CODRAG_DEV_MODE=1` is set in the environment. This is **correctly gated** by env var, but the env var can be set at runtime by Finding 1.1 above.

**Fix:** Same as 1.1 — use `_STARTUP_DEV_MODE` captured at import time, not a runtime `os.environ.get()`.

### Finding 1.3: `CODRAG_DEV_MODE` env var propagation — **PARTIAL**

Files affected:
- `src/codrag/core/feature_gate.py:143-165` — `CODRAG_TIER` env override requires `CODRAG_DEV_MODE=1`
- `src/codrag/core/security_health.py:304-321` — Detects and warns about dev mode
- `src/codrag/mcp/mcp_tools.py:13` — `_DEV_MODE` flag controls extra MCP tool (`codrag_context` alias)

The `CODRAG_DEV_MODE` pattern is used consistently across 4 files as the single dev-mode gate for the Python backend. This is good. But the `/license/dev-override` endpoint can **set this at runtime**, creating a security hole.

**Fix:** All `CODRAG_DEV_MODE` checks should read from a frozen startup-time snapshot, not from `os.environ` at call time. Define once in a shared module:

```python
# src/codrag/core/dev_mode.py
import os
IS_DEV_MODE: bool = os.environ.get("CODRAG_DEV_MODE", "").strip() in ("1", "true", "yes")
```

Import `IS_DEV_MODE` everywhere instead of re-reading `os.environ`.

### Finding 1.4: No route-level middleware to block dev endpoints — **MISSING**

There is no FastAPI middleware or dependency that globally blocks dev-only routes. Every dev endpoint must individually check the dev flag. This is error-prone.

**Fix:** Create a FastAPI dependency:

```python
# src/codrag/api/deps.py
from codrag.core.dev_mode import IS_DEV_MODE
from fastapi import HTTPException

def require_dev_mode():
    if not IS_DEV_MODE:
        raise HTTPException(status_code=403, detail="Dev-only endpoint")
```

Then use it on dev routes:

```python
@router.post("/license/dev-override", dependencies=[Depends(require_dev_mode)])
def set_dev_tier_override(...):
    ...
```

---

## Layer 2: Dashboard Frontend (`src/codrag/dashboard/src/`)

### Finding 2.1: `import.meta.env.DEV` usage — **PARTIAL**

Only 2 uses in `src/App.tsx`:
- Line 308: `eventsUrl` — switches between `localhost:8400` and `api.baseUrl`
- Line 973: `SidebarPipelineQueue baseUrl` — same pattern

These are fine for primitive values. Rollup replaces `import.meta.env.DEV` with `false` in prod builds, and the dead branch is eliminated.

**No action needed** for these specific cases.

### Finding 2.2: `console.log` / `console.error` scattered throughout — **MISSING**

Found `console.*` calls in:
- `src/main.tsx:17,21` — `console.log('[Tauri] Daemon config:', config)` **leaks daemon URL and IPC token to browser console**
- `src/App.tsx:499,504,509` — `console.error('destroyAtlas failed', ...)` 
- `src/hooks/useTraceSystem.ts:538`
- `src/hooks/useRoadmapSystem.ts:127,263`
- `src/hooks/useOpportunitiesSystem.ts:125`
- `src/hooks/useLLMConfig.ts:136,148,223,240`
- `src/hooks/useProjectManager.ts:324`
- `src/components/UpdateBanner.tsx:42,83,113`

**Risk:** MEDIUM. `console.log` in `main.tsx` exposes the daemon IPC token to any user who opens the browser console. Other `console.error` calls are noisy but not a security risk.

**Fix:**
1. **Immediately:** Wrap `main.tsx:17` in `if (import.meta.env.DEV)` — this leaks the auth token.
2. **Systematically:** Create a tiny logger utility:

```typescript
// src/lib/logger.ts
export const log = {
  debug: (...args: any[]) => { if (import.meta.env.DEV) console.log(...args) },
  warn: (...args: any[]) => console.warn(...args),  // keep warnings in prod
  error: (...args: any[]) => console.error(...args), // keep errors in prod
}
```

Replace `console.log` calls with `log.debug`. Keep `console.error` for genuine error reporting.

### Finding 2.3: `destroyAtlas`, `destroyGroupReasoning`, `destroyDeepEnrichment` — **MISSING**

`src/App.tsx:497-509` — These callbacks call destructive API endpoints that wipe enrichment data. They are wired to the dashboard UI and available to all users.

**Decision needed:** Are these prod features (user wants to re-index) or dev-only (dangerous reset)? If dev-only, they need `import.meta.env.DEV` guards or a "danger zone" confirmation dialog in prod.

### Finding 2.4: No `src/config/env.ts` centralization — **MISSING**

The document proposed creating `src/config/env.ts` but it doesn't exist yet.

---

## Layer 3: Vite Build Configuration (`vite.config.ts`)

### Finding 3.1: Verbose proxy logging — **OK (dev-server only)**

`vite.config.ts:31-119` — Every proxy route has `console.log('[Vite Proxy] ...')` handlers. These run **only in the Vite dev server** (`npm run dev`), never in the production build. The `server:` block in `vite.config.ts` is completely ignored by `vite build`.

**No action needed.**

### Finding 3.2: No `build:` block in Vite config — **MISSING**

The `vite.config.ts` has no `build:` section at all. This means:
- No explicit minification settings
- No sourcemap configuration (Tauri should NOT ship sourcemaps)
- No chunk size warnings
- No explicit `esbuild.drop` for `console.log` stripping

**Fix:** Add a production build block:

```typescript
build: {
  // Don't ship sourcemaps in production Tauri builds
  sourcemap: !!process.env.TAURI_DEBUG,
  // Don't minify in debug builds for readability
  minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
  // Strip console.log and debugger statements in production
  esbuild: process.env.TAURI_DEBUG ? undefined : {
    drop: ['debugger'],
    pure: ['console.log', 'console.debug'],
  },
},
```

This uses Tauri's own `TAURI_DEBUG` env var (set by `tauri dev` and `tauri build --debug`) to control build behavior.

---

## Layer 4: Tauri / Rust Shell (`src-tauri/`)

### Finding 4.1: `main.rs` conditional compilation — **OK (already implemented)**

We already restructured `main.rs` with `#[cfg(debug_assertions)]` for:
- Dev-only commands (`trigger_mock_event`)
- DevTools window auto-open

### Finding 4.2: `Cargo.toml` does NOT include `devtools` feature — **OK**

`Cargo.toml` line 13: `tauri = { version = "1", features = ["shell-open", "http-all", "process-command-api", "updater"] }` — No `devtools` feature. Production builds will not include the web inspector.

### Finding 4.3: CSP allows `ws://localhost:*` and `http://localhost:*` — **PARTIAL**

`tauri.conf.json:61`:
```
connect-src 'self' http://127.0.0.1:8400 ws://127.0.0.1:8400 ws://localhost:* http://localhost:*
```

The wildcards `ws://localhost:*` and `http://localhost:*` are overly permissive. In production, the only connection needed is to the sidecar daemon on a specific port.

**Fix:** Tighten CSP for production. Ideally, use Tauri's capability to set different CSPs per build profile. At minimum, document that the wildcard must be replaced with the actual daemon port before release:
```
connect-src 'self' http://127.0.0.1:8400 ws://127.0.0.1:8400
```

### Finding 4.4: Updater endpoint points to GitHub — **OK but verify**

`tauri.conf.json:68`: Points to `https://github.com/MagneticAnomaly/CoDRAG-MCP/releases/latest/download/latest.json`. This is fine for production — it's the standard Tauri updater pattern.

### Finding 4.5: `println!` statements in Rust — **PARTIAL**

`main.rs` contains 7 `println!` / `eprintln!` statements for sidecar lifecycle logging (e.g., `"[Tauri] Killing sidecar process..."`). These go to stdout/stderr, which is invisible to users on macOS (stdout is piped to Console.app logs) but visible on Windows if launched from a terminal.

**Fix:** Low priority. These are informational, not a security risk. Optionally wrap in `#[cfg(debug_assertions)]` if we want a completely silent release build.

### Finding 4.6: No `[profile.release]` in `Cargo.toml` — **MISSING**

No release profile configuration for:
- Symbol stripping (`strip = true`)
- LTO (link-time optimization for smaller binary)
- Optimization level

**Fix:** Add to `Cargo.toml`:
```toml
[profile.release]
strip = true
lto = true
opt-level = "s"  # optimize for size
codegen-units = 1
```

---

## Layer 5: MCP Server (`src/codrag/mcp/`)

### Finding 5.1: `codrag_context` dev alias tool — **OK**

`mcp_tools.py:411-437` — The `codrag_context` tool alias is only appended to the `TOOLS` list when `_DEV_MODE` is true (read from `CODRAG_DEV_MODE` env at import time). Correctly gated.

### Finding 5.2: `logger.debug` calls throughout `server.py` — **OK**

38 `logger.debug(...)` calls in `server.py`. These use Python's standard logging — they only produce output if the logger is configured at DEBUG level. Production daemons should run at INFO or WARNING level.

**Fix:** Ensure the daemon's logging config defaults to `INFO` in production. This is a daemon startup config issue, not a code issue.

---

## Layer 6: The `CODRAG_DEV_MODE` Unification

This is the **biggest gap** the previous document missed. The Python backend already has a coherent dev-mode flag (`CODRAG_DEV_MODE`), but it's read inconsistently and can be set at runtime.

### Current State

| File | How it reads `CODRAG_DEV_MODE` | When |
|------|-------------------------------|------|
| `feature_gate.py:146` | `os.environ.get(...)` | Every `get_license()` call |
| `security_health.py:307` | `os.environ.get(...)` | Every health check |
| `mcp_tools.py:13` | `os.environ.get(...)` | Module import time (frozen) |
| `license.py:149` | `os.environ.get(...)` | Every activation request |
| `license.py:580` | `os.environ["CODRAG_DEV_MODE"] = "1"` | **SETS it at runtime** |

### The Problem

`license.py:580` can **escalate** dev mode at runtime via the `/license/dev-override` endpoint. Once set, every subsequent call to `feature_gate.get_license()` or `license.activate` sees dev mode as active.

### The Fix

1. Create `src/codrag/core/dev_mode.py` — single source of truth, frozen at startup
2. All consumers import from there instead of reading `os.environ`
3. `/license/dev-override` checks the frozen flag, never sets it

---

## Implementation Strategy: Zero-Disruption Transition

### Guiding Principle

**Active development must never break.** Every step below is designed so that:
1. The daemon starts and runs identically before and after the change.
2. The dashboard dev server (`npm run dev`) works without modification.
3. `CODRAG_DEV_MODE=1` (which we already use every day) continues to unlock all dev features.
4. No step requires coordinating changes across multiple layers simultaneously.

Each step is a single, testable commit. If any step breaks something, revert that one commit.

---

### Wave 1: Additive-Only (no behavior changes, safe to land anytime)

These create new files and infrastructure without touching any existing code. Zero risk of breaking anything.

**1a. Create `src/codrag/core/dev_mode.py`** (~2 min)

A one-line module that freezes the dev flag at import time:
```python
import os
IS_DEV_MODE: bool = os.environ.get("CODRAG_DEV_MODE", "").strip() in ("1", "true", "yes")
```

Nothing imports it yet. It just exists, ready to be wired in.

**1b. Create `src/codrag/api/deps.py`** (~2 min)

A FastAPI dependency for gating dev-only routes:
```python
from fastapi import HTTPException
from codrag.core.dev_mode import IS_DEV_MODE

def require_dev_mode():
    if not IS_DEV_MODE:
        raise HTTPException(status_code=403, detail="Dev-only endpoint. Start daemon with CODRAG_DEV_MODE=1")
```

Nothing uses it yet. Just scaffolding.

**1c. Create `src/codrag/dashboard/src/lib/logger.ts`** (~2 min)

A tiny logger that gates `console.log` behind `import.meta.env.DEV`:
```typescript
export const log = {
  debug: (...args: any[]) => { if (import.meta.env.DEV) console.log(...args) },
  warn: console.warn,
  error: console.error,
}
```

Nothing imports it yet.

**1d. Create `src/codrag/dashboard/src/config/env.ts`** (~2 min)
```typescript
export const IS_DEV = import.meta.env.DEV;
export const DAEMON_BASE = IS_DEV
  ? `http://${window.location.hostname}:8400`
  : '';
```

Nothing imports it yet.

**Checkpoint:** All 4 files exist. `pytest` passes. `npm run dev` works. Zero behavior change.

---

### Wave 2: Surgical Backend Fixes (one file at a time, each is a standalone commit)

Each change below touches exactly one file. Test after each. If you're in the middle of a feature sprint that touches one of these files, defer that specific step — the others are independent.

**2a. Wire `dev_mode.py` into `license.py`** (~5 min)

Replace the runtime `os.environ.get("CODRAG_DEV_MODE")` reads with the frozen import, and add the `require_dev_mode` dependency to the `/license/dev-override` route.

Key changes:
- `license.py:149` — `from codrag.core.dev_mode import IS_DEV_MODE` instead of `os.environ.get(...)`
- `license.py:502` — add `dependencies=[Depends(require_dev_mode)]`
- `license.py:580` — **delete** `os.environ["CODRAG_DEV_MODE"] = "1"` (the runtime escalation)
- `license.py:538` — **delete** `os.environ.pop("CODRAG_DEV_MODE", None)` (no longer needed)

**Transition safety:** If you currently start your daemon with `CODRAG_DEV_MODE=1` (which you do), nothing changes — the frozen flag sees it at startup and all dev features work. The only thing that stops working is the ability for `/license/dev-override` to *create* dev mode from a non-dev daemon. That's the security fix.

**2b. Wire `dev_mode.py` into `feature_gate.py`** (~3 min)

Replace `os.environ.get("CODRAG_DEV_MODE")` with the frozen import. The CODRAG_TIER override still works when `IS_DEV_MODE` is True.

**2c. Wire `dev_mode.py` into `security_health.py`** (~2 min)

Replace `os.environ.get("CODRAG_DEV_MODE")` with the frozen import.

**2d. Wire `dev_mode.py` into `mcp_tools.py`** (~2 min)

Replace the local `_DEV_MODE = _os.environ.get(...)` with `from codrag.core.dev_mode import IS_DEV_MODE`. Rename the local reference. This is cosmetic — `mcp_tools.py` already froze at import time, so behavior is identical.

**Checkpoint:** All Python dev-mode checks now read from a single frozen source. `CODRAG_DEV_MODE=1` works exactly as before. Without it, `/license/dev-override` returns 403. Run `pytest` to confirm.

---

### Wave 3: Frontend Safety Net (config changes only, no component refactors)

These are build-tool and bootstrap changes. They don't touch any React components or hooks, so they won't conflict with feature work happening in those files.

**3a. Fix `main.tsx` token leak** (~1 min)

One-line change: wrap the `console.log` in an `import.meta.env.DEV` check.

```typescript
// Before:
console.log('[Tauri] Daemon config:', config);
// After:
if (import.meta.env.DEV) console.log('[Tauri] Daemon config:', config);
```

This is the **highest-priority frontend fix** because it leaks the IPC auth token in production.

**3b. Add `build:` block to `vite.config.ts`** (~2 min)

Append to the existing config object (no existing keys are changed):

```typescript
build: {
  sourcemap: !!process.env.TAURI_DEBUG,
  minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
  esbuild: process.env.TAURI_DEBUG ? undefined : {
    drop: ['debugger'],
    pure: ['console.log', 'console.debug'],
  },
},
```

**Transition safety:** This only affects `vite build` (production). `npm run dev` is completely unaffected — the `build:` block is ignored during dev server mode. The `esbuild.pure` setting means that even if we never migrate `console.log` → `log.debug`, production builds will strip them anyway. This is a **safety net**, not a requirement.

**Checkpoint:** `npm run dev` still works. `npm run build` now strips console.log and sourcemaps. No component files touched.

---

### Wave 4: Rust/Tauri Config (only affects release builds)

These changes only matter when you run `tauri build`. They have zero effect on `tauri dev`.

**4a. Add `[profile.release]` to `Cargo.toml`** (~1 min)

Append at end of file:
```toml
[profile.release]
strip = true
lto = true
opt-level = "s"
codegen-units = 1
```

**Transition safety:** `cargo build` (debug) is completely unaffected. Only `cargo build --release` (which `tauri build` uses) changes — and it gets faster, smaller binaries.

**4b. Tighten CSP in `tauri.conf.json`** (~1 min, **defer until release**)

Remove `ws://localhost:*` and `http://localhost:*` wildcards. Replace with specific port.

**WARNING:** Do this LAST, right before cutting a release build. The wildcards are useful during development (hot-reload, Vite proxy). Tightening them early will cause `tauri dev` to break with CSP errors.

**Alternative:** Keep the loose CSP in the repo and tighten it only in CI/CD release pipeline via a `sed` command or a `tauri.conf.release.json` override.

**4c. Extract `dev_cmds.rs`** (~5 min, **defer until needed**)

Move `trigger_mock_event` into a separate `dev_cmds.rs` module gated by `#[cfg(debug_assertions)]`. Low priority — the existing inline `#[cfg(debug_assertions)]` in `main.rs` already works correctly. This is a cleanliness refactor, not a functional change. Do it when you're already touching `main.rs` for another reason.

---

### Wave 5: Gradual Console Migration (do opportunistically, never as a blocking task)

**5a. When you touch a hook file for any reason, migrate its `console.log` → `log.debug`**

This is NOT a dedicated task. It happens organically:
- Fixing a bug in `useRoadmapSystem.ts`? Replace its 2 `console.error` calls while you're in there.
- Adding a feature to `useLLMConfig.ts`? Replace its 4 `console.warn` calls.

The `vite.config.ts` `esbuild.pure` setting from Wave 3b is the safety net — even un-migrated `console.log` calls get stripped in production. So this wave is about code hygiene, not security.

---

### Timing Cheat Sheet

| Wave | When to do it | Risk | Touches active code? |
|------|--------------|------|---------------------|
| **1** | Anytime, right now | Zero | No — additive only |
| **2** | Next natural break from feature work | Low | Only `license.py`, `feature_gate.py`, `security_health.py`, `mcp_tools.py` — one at a time |
| **3a** | **ASAP** — security fix | Zero | One line in `main.tsx` |
| **3b** | Anytime | Zero | Only `vite.config.ts` build block |
| **4a** | Anytime | Zero | Only affects release builds |
| **4b** | **Right before first release build** | Medium | Can break `tauri dev` if done early |
| **4c** | When already in `main.rs` | Zero | Rust-only refactor |
| **5** | Ongoing, opportunistic | Zero | One file at a time, as you're already there |

### What NOT to do

- **Do NOT batch all these into one mega-commit.** That's how you get a broken dev environment for a day.
- **Do NOT tighten the CSP (4b) until you're cutting a release.** It will break hot-reload.
- **Do NOT refactor all console.log calls in one pass.** The Vite `esbuild.pure` setting is the real fix; the migration is just hygiene.
- **Do NOT create a `dev_cmds.rs` file until you have a second dev command to put in it.** One command inline with `#[cfg(debug_assertions)]` is fine.

---

### Verification (run after Wave 2 and Wave 3)

**Dev mode smoke test (should work exactly as before):**
```bash
CODRAG_DEV_MODE=1 python -m codrag.server
# /license/dev-override works
# codrag_context MCP tool appears
# CODRAG_TIER override works
```

**Security verification (the new behavior):**
```bash
python -m codrag.server  # no CODRAG_DEV_MODE
# /license/dev-override returns 403
# typing "enterprise" as a license key fails
# codrag_context MCP tool does NOT appear
```

**Production build smoke test (after Wave 3b + 4a):**
```bash
cd src/codrag/dashboard && npm run tauri build
# Verify no sourcemaps in dist/
# Verify no console.log in JS bundles (grep for '[Tauri]')
# Verify binary is stripped (nm -gU on macOS, or file size comparison)
```

---

## Summary of Gaps Found (vs. Previous Document Version)

| # | Gap | Severity | Previous Doc? |
|---|-----|----------|--------------|
| 1 | `/license/dev-override` endpoint is unconditionally registered | CRITICAL | No |
| 2 | `CODRAG_DEV_MODE` can be set at runtime via API call | CRITICAL | No |
| 3 | `main.tsx` logs IPC auth token to browser console | HIGH | No |
| 4 | No `build:` block in `vite.config.ts` (no sourcemap/minify/console stripping) | HIGH | No |
| 5 | No `[profile.release]` in `Cargo.toml` (no strip/LTO) | MEDIUM | Mentioned but no fix |
| 6 | CSP wildcards `ws://localhost:*` in `tauri.conf.json` | MEDIUM | No |
| 7 | Python daemon layer entirely missing from analysis | HIGH | No |
| 8 | MCP server dev tools analysis missing | MEDIUM | No |
| 9 | `console.log` scattered across 8+ frontend files | LOW | Mentioned but no audit |
| 10 | No centralized `dev_mode.py` for Python backend | MEDIUM | No |
| 11 | No FastAPI dependency for gating dev-only routes | MEDIUM | No |
| 12 | `destroyAtlas`/`destroyGroupReasoning`/`destroyDeepEnrichment` exposed without confirmation | LOW | No |

---

## Technical Debt / Blockers

- **Rust toolchain:** As of April 2026, `cargo build` in the Tauri project is blocked by `globset v0.4.18` requiring the unstable `edition2024` feature in Cargo 1.84.1. Must update Rust toolchain or pin dependency before Phase C can be verified.
- **Daemon logging level:** Need to confirm that the production daemon defaults to `INFO` level logging (not `DEBUG`). This is a startup config issue in `server.py`.

---

*This document is the authoritative blueprint for Phase 101 dev/prod separation. Phases A-D should be executed in order. Phase A is the security-critical path.*
