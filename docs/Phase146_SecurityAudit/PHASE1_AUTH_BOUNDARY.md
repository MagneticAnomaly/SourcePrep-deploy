# Phase 1 — Auth & Daemon Boundary — Findings

**Date:** 2026-06-22
**Method:** source review (prep daemon was down → grep/read, the documented floor). Every claim cites `file:line` that was read directly.
**Verification level:** single-reviewer, code-level. Reachability/mitigation reasoning applied inline as the refutation lens. A formal independent refute panel (per `05_DEEP_DIVE_PLAN.md`) is NOT yet run — flagged where it would change a verdict.

## Decisions recorded (set 2026-06-22)
- **D-1 = one phase at a time**, reviewer drives, human reviews between phases.
- **D-2 = product code + `public/sourceprep-deploy/`**; `websites/` deferred (payments/license flows there get their own later phase).
- **D-3 = loopback-primary + exposed-case as a first-class scenario.** Evidence below shows no shipped path exposes the daemon non-loopback; the manual-exposure footgun is analyzed but not treated as critical-by-default.

---

## Verdict summary

| ID | Candidate | Verdict | Severity (under D-3) | Reachability |
|----|-----------|---------|----------------------|--------------|
| C-1 | Daemon HTTP auth off by default | **PARTIAL / reframed** | MEDIUM (footgun) | token-less only on bare `prep serve`; desktop sets a token |
| C-2 | `/license/dev-override` ungated | **CONFIRMED (code-level)** | HIGH if shipped to prod UI (open Q) | behind global IPC token; wired to dashboard UI |
| C-5 | MCP HTTP transport no token | **CONFIRMED, low likelihood** | MEDIUM (opt-in `--transport http`) | only when http transport chosen |
| F1-NEW-1 | MCP `is_local` Origin prefix bypass | **CONFIRMED (new)** | MEDIUM | only in http transport mode |
| FULL-1 | CORS `*`+creds | **RE-CONFIRMED sound** | LOW (residual) | browser-only enforcement |

---

## C-1 — Daemon HTTP auth is off by default → **reframed to a footgun, not critical-by-default**

**Evidence (all read):**
- `verify_ipc_token` (`server.py:246-262`) enforces only if `PREP_DAEMON_TOKEN` is set; `/health` + `/events` always bypass.
- The env var is **read** in 4 places but **set in exactly one**: the Tauri desktop shell generates a random token (`dashboard/src-tauri/src/main.rs:58` `Uuid::new_v4()`) and injects it (`main.rs:111`). → **the packaged desktop product authenticates.**
- Every `--host` defaults to `127.0.0.1` (`server.py:1312`, all `cli.py` serve-family commands). **No `0.0.0.0` anywhere** in `src/`, `public/`, `scripts/`.
- No shipped artifact starts the server non-loopback: all containers run `sync-headless` (batch), not `serve` — `Dockerfile.cpu:56`, `Dockerfile.gpu:72`, `aws/ecs-task-definition.json:16` (no `portMappings`), `modal/modal_adapter.py:64`, `runpod/runpod_handler.py:29`.
- Mitigating control exists: `security_health.py:252` (Check 8) **fails** if bound non-localhost without a token, warns if no token on localhost.

**Accurate finding:** the bare `prep serve` CLI runs unauthenticated, and **nothing prevents/warns a user who manually sets `--host 0.0.0.0`** (the flag is on every command) from exposing a fully unauthenticated API. DNS-rebinding can drive state-changing POSTs against the token-less loopback daemon (browser can't *read* the response cross-origin, but the request still executes server-side; the Bearer token — not a cookie — is what actually stops this, and it's absent on the CLI path).

**Recommendation (for the fix phase):** when `--host` is non-loopback and no `PREP_DAEMON_TOKEN`, refuse to start (or auto-generate + print one); consider a default-on token for `serve` too.

## C-2 — `/license/dev-override` is ungated and self-grants enterprise → **CONFIRMED**

**Evidence (`api/routers/license.py:502-584`, read):**
- Plain `@router.post("/license/dev-override")`, **no `PREP_DEV_MODE`/auth gate** in the handler.
- Accepts `tier` up to `"enterprise"` (allowed set line 519); writes a real `license.json` with `valid:True, seats:999` (lines 566-575) and **backs up the user's real license** to `license.json.real`.
- Sets `os.environ["PREP_DEV_MODE"]="1"` and `PREP_TIER=tier` **process-wide** (lines 579-580) — persists for the daemon's lifetime, re-enabling unsigned/plain-JSON license shortcuts elsewhere (ties to CRIT-1 / C-7).
- **It's a live UI feature, not dead code:** `packages/ui/src/api/client.ts:684` calls it; `dashboard/src/hooks/useLicenseSystem.ts` drives a tier dropdown off it.

**Reachability:** behind the same global IPC token as every route — so on the token-less CLI it's unauthenticated; in the desktop app it requires the token, *but the dashboard holds the token and exposes a button*. Net: any desktop user who can open the dashboard can self-grant enterprise.

**Open question (→ Phase 2):** is the tier dropdown gated to dev/internal builds in the UI, or shipped to end users? That decides whether this is HIGH (prod license bypass) or contained (dev-only tool). The *route* has no gate regardless.

**Recommendation:** gate the route on `PREP_DEV_MODE` being set at launch (or compile it out of production builds); never mutate `os.environ` from an HTTP handler.

## C-5 — MCP HTTP transport has no token → **CONFIRMED, low likelihood**

**Evidence (`mcp/transport.py:121-168`, read):** `TrustedOriginMiddleware` checks only the `Origin` header; **no `PREP_DAEMON_TOKEN` check** in `run_http`. No-Origin requests (curl/native) are allowed by design (line 129). Default transport is `stdio` (`cli.py:725`); http is opt-in (`--transport http`, default host 127.0.0.1, port 8401). MCP tools are read-mostly (info disclosure of indexed code) plus the hidden `prep_build`.

**Severity:** MEDIUM, conditioned on the user choosing http transport. `SECURITY.md` names "escalation via the MCP surface" as high-severity, so even read access to indexed code matters.

## F1-NEW-1 — MCP `is_local` Origin check is prefix-match-bypassable → **CONFIRMED (new this phase)**

**Evidence (`mcp/transport.py:136`):** `origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")`. A browser origin `http://localhost.evil.com` (attacker-registered) **passes** this check → reaches the MCP HTTP transport with no token (C-5). Contrast the daemon's CORS regex `^https?://(localhost|127\.0\.0\.1)(:\d+)?$` (`server.py:238`), which is anchored and **not** bypassable — so the daemon got Origin validation right and the MCP transport got it wrong. **Recommendation:** reuse the anchored regex; drop the `startswith` check.

## FULL-1 (CORS) — **RE-CONFIRMED sound for cross-site; residual noted**

**Evidence (`server.py:227-243`):** default uses the anchored regex above + `allow_credentials=True`; no subdomain bypass (`localhost.evil.com` fails the anchor). Residuals: (1) **any** local web app (`http://localhost:<port>`) is an allowed credentialed origin; (2) CORS is browser-enforced only — it does not stop curl/local-process/DNS-rebind requests, which is why C-1's token (absent on CLI) is the real control.

---

## Remaining for Phase 1 (optional, before closing)
- Formal independent refute panel on C-2 and F1-NEW-1 (needs Workflow opt-in).
- Confirm whether the dashboard tier-dropdown is build-gated (the C-2 severity hinge) — borders on Phase 2.

## Next: Phase 2 — License & Feature-Gate (CRIT-1, C-7, and the C-2 prod-exposure question).
