# 04 — Candidate Findings (UNVERIFIED)

**These are hypotheses, not findings.** Each was surfaced while verifying file
paths on 2026-06-16; none has been adversarially confirmed. They are the deep
phases' starting backlog. Every one needs: (1) confirm the code path is reachable,
(2) build a concrete exploit/PoC or prove it can't be triggered, (3) assign real
severity. **Do not report any of these as a vulnerability until verified.**

Severity below is *severity-if-confirmed*, and every one is conditioned on the
threat model (Decision D-3: is the daemon ever non-loopback?).

---

### C-1 — Daemon HTTP auth is OFF by default
- **Evidence:** `server.py:246-262` `verify_ipc_token` enforces only if
  `PREP_DAEMON_TOKEN` is set; grep finds **no code in `src/prep` that generates
  it**. `/health` and `/events` bypass even when set.
- **Hypothesis:** out of the box, the entire HTTP API (search, context, file read,
  build, config, license) is unauthenticated, protected solely by the `127.0.0.1`
  bind. Any local process — or any website via DNS-rebinding / a browser if CORS
  slips — could drive the daemon.
- **Severity if confirmed:** HIGH (loopback) → CRITICAL (if ever exposed).
  `security_health.py` Check 8 already self-flags this, which is corroboration.
- **Verify (Phase 1):** Does any launcher (CLI `serve`, Tauri, installer, docker
  entrypoint) set `PREP_DAEMON_TOKEN`? Can a browser reach the API cross-origin
  given the real CORS config? Is DNS-rebinding to `127.0.0.1` viable?

### C-2 — `/license/dev-override` is unauthenticated and ungated
- **Evidence:** `api/routers/license.py:502-584` — no `PREP_DEV_MODE` guard;
  writes a real `~/.runprep/license.json` for any tier **and sets
  `os.environ['PREP_DEV_MODE']='1'` process-wide**, which then leaves the unsigned
  plain-JSON / tier-name license shortcuts enabled for the daemon's lifetime
  (`license.py:147-166`).
- **Hypothesis:** if the HTTP API is reachable (see C-1), one unauthenticated POST
  permanently downgrades the whole daemon into dev-mode and self-grants enterprise.
- **Severity if confirmed:** HIGH (privilege escalation / license bypass; this is
  the unresolved core of CRIT-1 in a new guise).
- **Verify (Phase 1/2):** Is the route present in the shipped build? Should it be
  compiled out, or require `PREP_DEV_MODE` already true at launch?

### C-3 — `is_safe_url` SSRF bypass gaps
- **Evidence:** `api/routers/llm.py` — provider in `{ollama, lm-studio}`
  short-circuits to `True` (`~:178-179`) before private-IP checks; a DNS
  resolution failure falls through to **allow** (`~:190-191`).
- **Hypothesis:** an attacker who can set `provider=ollama` with an arbitrary URL,
  or supply a host that fails resolution at check-time, may reach internal services
  despite the guard. (Note: `169.254.*` / `metadata.google.internal` are blocked
  first regardless.)
- **Severity if confirmed:** MEDIUM (SSRF, mitigated by C-1's token when set).
- **Verify (Phase 3):** Can `provider` be attacker-set on the proxy routes? Is the
  fail-open on `gaierror` reachable (DNS-rebinding/timeouts)?

### C-4 — Audit log persists details without redaction
- **Evidence:** `core/audit_log.py:148-187` `record()` stores `**details`
  verbatim via `json.dumps(details, default=str)`; it records endpoint URLs.
- **Hypothesis:** currently safe for LLM calls (only `prompt_chars` is logged), but
  it's a latent secret-leak channel — any future caller passing a key/credential in
  `details`, or a provider whose endpoint URL embeds a key, lands plaintext in the
  audit SQLite, which is readable from the admin panel.
- **Severity if confirmed:** MEDIUM (defense-in-depth / future-proofing).
- **Verify (Phase 4):** Enumerate every `audit_log.record(...)` caller; check for
  any sensitive kwargs or credential-bearing URLs reaching the DB.

### C-5 — MCP HTTP transport has no token, only an Origin check
- **Evidence:** `mcp/transport.py:121` `TrustedOriginMiddleware` checks only the
  `Origin` header and allows any localhost origin **and null/absent Origin**; no
  `PREP_DAEMON_TOKEN`.
- **Hypothesis:** the MCP HTTP transport (a separate uvicorn server) is reachable
  by any local client or any tool that omits an Origin header. `SECURITY.md`
  explicitly names "escalation via the MCP surface" as high-severity.
- **Severity if confirmed:** MEDIUM–HIGH (the MCP surface is a named crown-jewel).
- **Verify (Phase 1):** Default transport (stdio vs http)? When http, what port/bind?
  Can a non-browser client with no Origin reach tool dispatch?

### C-6 — git argument-injection residual (no `--` separator)
- **Evidence:** `agents/shared/git_client.py:21-55` — argv-form subprocess (no
  shell injection) but no `--` before user-influenced branch/path values.
- **Hypothesis:** a branch name or path beginning with `-` could be parsed as a git
  option (argument injection), unlike HIGH-1 which fixed the clone path specifically.
- **Severity if confirmed:** LOW–MEDIUM (depends on whether branch/path are
  attacker-influenced).
- **Verify (Phase 5):** Trace the provenance of `branch_name`/paths into
  `git_client`; are any user/config-controlled?

### C-7 — Default license public key is a placeholder
- **Evidence:** `core/licensing.py:22` `DEFAULT_PUBLIC_KEY_HEX` is a documented
  dev/placeholder key (overridable via `PREP_LICENSE_PUBLIC_KEY`).
- **Hypothesis:** if a shipped build doesn't override it, the Ed25519 verification
  (CRIT-1's fix) validates against a key whose private half is public/known →
  forgeable licenses.
- **Severity if confirmed:** HIGH (defeats the CRIT-1 remediation).
- **Verify (Phase 2):** Does the build/packaging inject a production public key?
  Where? Is there a test asserting the placeholder is not shipped?

---

## Also flag (from prep role-view, not yet examined)

- **`core/team_config.py`** — the validating loader for the attacker-controllable
  `team_config.json`. It's the trust boundary for CRIT-2/HIGH-2/MED-1. Audit its
  validation completeness in Phase 3 (does *every* field that drives an outbound
  call or a file path get validated, not just the endpoint?).
- **`tauri.conf.json`** — desktop CSP / auto-updater config; relevant if Phase 7
  (frontend) covers the Tauri shell.

---

## How to verify (the discipline for deep phases)

For each candidate, the deep phase produces a verdict record:
`{id, reachable: bool, poc_or_proof, real_severity, status: confirmed|refuted|partial}`.
Use the adversarial pattern: at least 2–3 independent skeptics try to **refute**
each candidate (build the case that it's *not* exploitable) before it's promoted to
a finding. Refuted candidates stay in this doc marked `refuted` with the reasoning —
they are not deleted, so the next audit doesn't re-chase them.
