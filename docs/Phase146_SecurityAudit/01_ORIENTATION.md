# 01 — Orientation: Verified Architecture & Attack Surface

**Verified:** 2026-06-16 (by `security-scaffold-verify` workflow, reading actual source)
All paths below were confirmed to exist on disk.

---

## What SourcePrep is (for threat-modelling)

A **local-first** codebase-intelligence daemon. It indexes a user's source
code, builds a semantic + structural graph, and serves bounded context to AI
agents over MCP. Security-relevant properties:

- It **reads local source code** — so the crown jewels are *the indexed code
  itself* and *the credentials it holds* (LLM API keys, S3 sync creds).
- It makes **outbound network calls** — to LLM providers (cloud or local) and,
  in Team mode, to an S3-compatible endpoint. These are the SSRF/exfil surface.
- It runs a **FastAPI daemon**, default-bound to `127.0.0.1:8400`, that the
  dashboard, the MCP server, and the CLI all talk to.

`SECURITY.md` (repo root) names the three high-severity classes officially:
**exfiltration of indexed code, daemon authentication bypass, and privilege
escalation via the MCP surface.** The audit should weight toward those.

---

## Trust boundaries

```
        ┌─────────────────────────────────────────────────────────────┐
        │ Local machine (default trust: 127.0.0.1 loopback only)       │
        │                                                              │
  CLI ──┤  ┌────────────┐   HTTP :8400   ┌──────────────────────────┐  │
        │  │ dashboard  │───────────────▶│ FastAPI daemon           │  │
 MCP ───┤  │ (React)    │   (CORS:       │ (server.py)              │  │
client  │  └────────────┘    loopback)   │  · verify_ipc_token MW   │  │
        │  ┌────────────┐                │    (OPT-IN, see C-1)     │  │──┐ outbound
        │  │ MCP server │── httpx ──────▶│  · 25+ routers, no       │  │  │ LLM / S3 / PM
        │  │ (proxy)    │                │    per-route authz       │  │  ▼
        │  └────────────┘                └───────────┬──────────────┘  │ ┌───────────┐
        │   MCP HTTP transport: Origin-              │ ingests          │ │ cloud LLM │
        │   header-only, no token (C-5)              ▼                  │ │ S3 bucket │
        │                              file watcher / S3 pull / archive │ │ Paperclip │
        └─────────────────────────────────────────────────────────────┘ └───────────┘
```

The **critical assumption** is the loopback bind. If the daemon is ever exposed
on a routable interface (container, `--host 0.0.0.0`, port-forward), the
opt-in-and-usually-unset IPC token (C-1) means the entire API is open. Decision
D-3 in `STATUS.md` turns on this.

---

## Attack surface inventory (verified)

### 1. HTTP API — `src/prep/server.py`, routers in `src/prep/api/routers/`

**Auth:** single global middleware `verify_ipc_token` (`server.py:246-262`).
- Enforces **only if** `PREP_DAEMON_TOKEN` is set in the environment. The daemon
  **never generates this token** anywhere in `src/prep` — so it ships auth-OFF
  by default and relies on the loopback bind. (→ candidate **C-1**.)
- When set: `Authorization: Bearer <token>`, constant-time `hmac.compare_digest`.
- `/health` and `/events` bypass the token even when set (`server.py:249`).
- **No per-router or per-route authorization.** All 25+ routers mounted plain
  (`server.py:819-842`). "Roles" in this product are atlas-projection personas,
  not access control.

**Highest-risk routes (verified):**

| Route | File | Why it matters |
|-------|------|----------------|
| `POST /license/dev-override` | `api/routers/license.py:502` | **Not** gated by `PREP_DEV_MODE`; writes a real `~/.runprep/license.json` for any tier and sets `PREP_DEV_MODE=1` process-wide → privilege escalation (**C-2**) |
| `POST /license/activate` | `api/routers/license.py` | Online LemonSqueezy / Ed25519 offline / dev base64 paths |
| `POST /api/llm/proxy/{models,test,test-model}` | `api/routers/llm.py:159` | Server-side fetch of user-supplied URL+key → SSRF, guarded by `is_safe_url` (gaps → **C-3**) |
| `GET /projects/{id}/file?path=` | `api/routers/projects/files.py:27-143` | File-content read — **defended** (reject `..`/abs, `relative_to(repo_root)`, glob policy, size cap) |
| `POST /projects` | `api/routers/projects/crud.py` | Registers an arbitrary on-disk path as a project, triggers background scan of that tree |
| `PUT /global/config` | `api/routers/system.py` | Merge-writes LLM endpoint URLs / api_keys / S3 config (drives later outbound calls) |
| `POST /projects/{id}/pm/push` | `api/routers/pm_push.py` | Outbound to configured Paperclip URL+api_key |
| `POST /projects/{id}/build`, `/pipeline/*` | `api/routers/build.py`, `pipeline.py` | Trigger index builds / LLM-spending enrichment runs |

Large routers only partially line-audited (enumerated, high-risk handlers read):
`llm.py` (72KB), `pipeline.py` (67KB), `enrichment.py` (69KB), `search.py` (57KB),
`settings.py` (31KB), `roadmap.py` (38KB). Full handler audit is deep-phase work.

### 2. MCP surface — `src/prep/mcp/server.py`, `src/prep/mcp_tools.py`

Tools: `prep`, `prep_search`, `prep_impact`, `prep_audit`, `prep_observe`,
`prep_concepts` (+ dev-only `prep_context` alias, + hidden `prep_build` dispatch
alias at `mcp/server.py:4470`). The MCP server is mostly a proxy to the daemon
over httpx. Its **HTTP transport** (`mcp/transport.py`) has its own
`TrustedOriginMiddleware` that checks **only the `Origin` header** (allows any
localhost origin and null/absent Origin) — **no token** (→ candidate **C-5**).
`SECURITY.md` explicitly names the MCP surface as a high-severity escalation
class, so this transport deserves Phase 1 scrutiny.

### 3. CLI — `src/prep/cli.py`

~40 commands. Security-relevant: `serve` (default `--host 127.0.0.1`),
`add`/`remove`/`delete`/`prune`/`reset` (project + on-disk state),
`mcp` (stdio/http transport), `sync-headless`, `research-push`, `custodian-push`.

### 4. Data-ingest entry points (external/attacker-influenceable data)

| Entry point | File | Notes |
|-------------|------|-------|
| File watcher | `core/watcher.py:23,125` | watchdog Observer, recursive, triggers delta builds on file change in a registered tree |
| Remote (S3) sync pull | `services/remote_sync.py:234` | Polls S3-compatible endpoint; endpoint **SSRF-validated** at `:71`; creds from env or `.sourceprep/.secrets` |
| Archive extraction | `services/s3_storage.py:307` | The **only** decompression in the codebase; zip-bomb (10 GB) + zip-slip guarded at `:292-306` |
| Outbound LLM/PM calls | `api/routers/llm.py`, `pm_push.py` | SSRF sinks reachable from HTTP API |
| SSE streams | `system.py:138` (`/events`), `mcp/transport.py` (`/sse`) | auth-exempt |
| Settings store | `PUT /global/config`, settings router | persists endpoint URLs/keys that drive the above |

There is **no generic "upload an archive" import** — "project import" means
registering an existing on-disk repo path (`crud.py`), not uploading a zip.

---

## Verified defensive posture (the good news)

These are real, working defenses confirmed by reading the code — credit where due:

- **No deserialization sinks:** no `pickle.load`, no `yaml.unsafe_load`, no
  `eval`/`exec` on user input; all `np.load` use `allow_pickle=False`.
- **No shell injection:** every `subprocess.run` uses argv list form, no
  `shell=True` anywhere.
- **Path traversal defended** on the file-read API (`files.py:38-103`,
  layered `relative_to` + glob policy + size cap) and `/system/swarm-events`.
- **SSRF guard** on S3 endpoints (`remote_sync.py:71`) blocks cloud-metadata
  IPs, private ranges, and non-HTTPS.
- **Archive extraction bounded** — zip-bomb + zip-slip guards before `extractall`.
- **LLM input sanitization on every call** — `sanitize_llm_input`
  (`llm_client.py:692`) strips invisible-unicode / homoglyph injection
  (EchoLeak CVE-2025-32711, Rules-File-Backdoor class); optional DLP secret
  redaction when an admin policy is loaded.
- **Audit log avoids prompt text** — LLM-call records log `prompt_chars`
  (a length), not the prompt content (`llm_client.py:734-747`).

The audit's job is to find the **gaps in and around** these defenses (the
candidate findings), not to re-discover that the baseline is decent — the
prior audit already established that and it still holds.

---

## What a deep phase should NOT waste time on

Per the verified ledger, these are settled: HIGH-1, HIGH-3, HIGH-4, HIGH-5,
FULL-1, FULL-5, and the absence of deserialization/shell-injection/eval sinks.
Confirm-and-move-on, don't re-investigate from scratch.
