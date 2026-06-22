# Phase 146 — Security Audit — STATUS LEDGER

> **This is the living progress document.** Update it as work proceeds.
> It is the single source of truth for what is verified, what is pending, and
> who owns it. Every other doc in this phase is a snapshot; this one is state.

**Last updated:** 2026-06-22
**Phase state:** ⏸ **Finance/legal track PAUSED pending Phase 142 (OSS-First) landing.** Continuing on non-finance security phases.
**🔴 TOP FINDING (held as Phase 142 input):** license system is cryptographically void — shipped signing key is the all-zeros-seed/RFC-8032 test vector; forgery PROVEN. Launch-blocker for paid tiers. See `PHASE2_LICENSE.md`.
**Decisions set (2026-06-22):** D-1 = one-phase-at-a-time · D-2 = product + deploy, defer websites · D-3 = loopback-primary + analyze exposed case

---

## ⏸ PAUSED TRACK — finance / legal (Phase 142 dependency)

**Why:** Phase 142 (OSS-First open-core split) is reworking the license + feature-gate
and what ships paid vs. free. It is **design-only, not yet implemented/merged**
(`docs/Phase142_OSS-First/`, no branch, no impl commits as of 2026-06-22). Auditing
this code further now = auditing soon-to-be-rewritten code. **Resume after Phase 142
lands and merges.**

**Paused:**
- Phase 2 follow-through (further license/feature-gate/crypto deep-dive)
- Phase 3's **S3 / team-sync** portion (CRIT-2, HIGH-2, MED-3 — team-sync is the Pro/open-core monetization layer being restructured)
- Future payments + legal phases (`websites/apps/payments`, `docs/Phase144_LegalPreLaunch`)

**NOT paused (continue):** Phase 4 (LLM injection), Phase 5 (file/path), Phase 6 (Rust),
Phase 8 (tooling/hardening), and Phase 3's **LLM-proxy SSRF** sub-part (C-3, `api/routers/llm.py`)
— all ship in the OSS core and are independent of tiering.

### Feed-forward → Phase 142 (do NOT lose these; they are 142 requirements)
The Phase 2 findings are precisely what 142's "secret audit" + "apply license" work must satisfy:
1. **Generate a real production keypair; never ship a test/placeholder key.** Current `licensing.py:22` ships the all-zeros-seed/RFC-8032 key → licenses forgeable (PROVEN).
2. **Actually implement the `PREP_LICENSE_PUBLIC_KEY` (or build-constant) read** — today it's comment-only.
3. **Reject unsigned `license.json`** — today `get_license()` warns-but-accepts (second forgery path).
4. **Remove/relocate the committed private key** in `scripts/generate_license.py:33` before the repo goes public (Apache 2.0).
5. **Architecture note for open-core:** client-side license gating in the *public* core is inherently bypassable — real entitlement enforcement for Pro/team features must live **server-side** (hosted indexes / team backend), not in the local feature-gate.
6. Carry the lower-severity P2-LIC/P2-FIX items (machine binding, LS signed-entitlement, store/product pinning, replay protection, `.sourceprep`/`.runprep` path mismatch) into the new license design.

---

## Phase progression

| Sub-phase | Description | State | Model / driver | Output |
|-----------|-------------|-------|----------------|--------|
| 0 | Initial orientation (lightweight) | ❌ **SUPERSEDED** (fabricated; see README Errata) | Haiku 4.5 | git `0aa18e0e` (removed) |
| 0.5 | Ground-truth verification + scaffold rebuild | ✅ **DONE** 2026-06-16 | Opus 4.8 + 6-agent workflow | this directory |
| 1 | Auth & Daemon Boundary deep dive | 🔎 REVIEWED 2026-06-22 (code-level; refute panel pending) | Opus 4.8 | `PHASE1_AUTH_BOUNDARY.md` |
| 2 | License & Feature-Gate deep dive | ✅ findings recorded · ⏸ **follow-through PAUSED** (Phase 142) | Opus 4.8 + 46-agent workflow | `PHASE2_LICENSE.md` |
| 3 | Outbound / SSRF / Team-Sync deep dive | ⏸ S3/team-sync PAUSED (142); 🟢 LLM-proxy SSRF (C-3) movable | TBD | — |
| 4 | LLM Injection & Data-Exposure deep dive | 🟢 **READY (recommended next)** | TBD | — |
| 5 | File / Path / Process surface deep dive | 🟢 ready | TBD | — |
| 6 | Rust engine deep dive | 🟢 ready | TBD | — |
| 7 | Frontend / webview deep dive | 🟡 ready minus payments/license UI | TBD | — |
| 8 | Tooling & process hardening | 🟢 ready (overlaps 142 SECURITY.md/CI/secret-audit) | TBD | — |

See `05_DEEP_DIVE_PLAN.md` for what each sub-phase covers.

---

## Prior-finding ledger (from Phase 06 audit, current state verified 2026-06-16)

Legend: ✅ fixed in code · 🟡 partially addressed / residual · 🔴 open · ⚪ deferred-by-design · ❓ needs deep re-verification

| ID | Title | Real location | Phase06 status | Current state | Re-verify? |
|----|-------|---------------|----------------|---------------|-----------|
| CRIT-1 | License has no crypto verification | `core/licensing.py:22`, `core/feature_gate.py:218-254` | Needs Design | 🔴 **CONFIRMED CRITICAL (launch-blocker)** — shipped key = all-zeros-seed/RFC-8032 test vector; `PREP_LICENSE_PUBLIC_KEY` override is comment-only; unsigned licenses accepted. **Forgery proven.** | ✅ Phase 2 done |
| CRIT-2 | SSRF via attacker-controlled S3 endpoint | `services/remote_sync.py:71,211` | Needs Design | ✅ `_validate_s3_endpoint` blocks metadata/private IPs | ❓ Phase 3 (rebinding/redirects) |
| HIGH-1 | Git clone URL injection | `services/headless_runner.py:485` | Fixed | ✅ `--` separator | low |
| HIGH-2 | Secrets file no permission check | `services/remote_sync.py:102-131` | Needs Design | 🟡 warns if group/world-readable; Windows behavior open | ❓ Phase 3 |
| HIGH-3 | API key logged in `_verify_license` | `services/headless_runner.py` | Fixed | ✅ dead method deleted (grep-confirmed) | done |
| HIGH-4 | S3 prefix path traversal | `services/s3_storage.py:163-170` | Fixed | ✅ `_s3_key` rejects `..`/leading `/` | done |
| HIGH-5 | Zip bomb DoS | `services/s3_storage.py:292-307` | Fixed | ✅ 10 GB cap + zip-slip guard | done |
| MED-1 | Polling interval no minimum | `services/remote_sync.py:52` | Fixed | ✅ 5-min min | low |
| MED-2 | GH Actions logs model name | `public/sourceprep-deploy/github-actions/prep-sync.yml:48` | rec only | 🔴 open (low) | Phase 8 |
| MED-3 | No integrity check on downloaded index | `services/s3_storage.py:316-329` | Fixed | 🟡 hash compared but only **warns** on mismatch, does not abort | ❓ Phase 3 |
| MED-4 | Context injection via document content | `core/layered_index.py:217` | Needs Design | 🟡 defensive marker present, code fences not escaped | ❓ Phase 4 |
| FULL-1 | CORS `*` + credentials | `server.py:227-243` | Fixed | ✅ loopback/tauri allowlist (escape hatch `PREP_CORS_ALLOW_ALL`) | low |
| FULL-2 | LLM proxy SSRF | `api/routers/llm.py:159` | Fixed | 🟡 `is_safe_url` exists; has bypass gaps → see C-3 | ❓ Phase 3 |
| FULL-3 | Google key in URL query param | `core/llm_client.py:591` | rec only | ⚪ Google API design; doc-for-enterprise | low |
| FULL-4 | No API rate limiting | `server.py` (global) | Deferred | ⚪ deferred to future Prep Manager | Phase 1 (note) |
| FULL-5 | git log subprocess | `core/inferred_edges.py:852` | No action | ✅ bounded, 30s timeout, argv form | done |

Full detail + notes in `02_PRIOR_FINDINGS_LEDGER.md`.

---

## Candidate findings backlog (NEW, unverified — for deep phases)

These were surfaced by the 2026-06-16 verification pass and are **not** in the
Phase 06 audit. They are hypotheses with evidence pointers, not confirmed vulns.

| # | Candidate | Evidence | Owner phase | State |
|---|-----------|----------|-------------|-------|
| C-1 | Daemon HTTP auth off by default | `server.py:246-262` | Phase 1 | 🟡 **PARTIAL/reframed** — desktop sets a random token (`main.rs:58,111`); no shipped non-loopback exposure (cloud=`sync-headless`). Real issue = no guardrail vs manual `--host 0.0.0.0`. MEDIUM footgun |
| C-2 | `/license/dev-override` ungated → self-grant enterprise + `PREP_DEV_MODE=1` | `api/routers/license.py:502-584` | Phase 1→2 | 🟡 **reframed (P2-SEC-2)** — endpoint ungated server-side (bounded: token/loopback/CSRF); **dashboard dropdown IS dev-build-gated** so prod UI can't reach it |
| C-3 | `is_safe_url` bypasses: ollama/lm-studio short-circuit; DNS failure → allow | `api/routers/llm.py:178-191` | Phase 3 | ⏳ to verify |
| C-4 | `audit_log.record` stores `**details` verbatim, no redaction | `core/audit_log.py:148-187` | Phase 4 | ⏳ to verify |
| C-5 | MCP HTTP transport: Origin-only, no token | `mcp/transport.py:121` | Phase 1 | 🟡 **CONFIRMED, low likelihood** — http transport is opt-in (default `stdio`, `cli.py:725`). MEDIUM |
| C-6 | git argument injection residual (no `--` separator) | `agents/shared/git_client.py:21-55` | Phase 5 | ⏳ to verify |
| C-7 | Default license public key is a placeholder/dev key | `core/licensing.py:22` | Phase 2 | 🔴 **CONFIRMED CRITICAL** — folded into CRIT-1 headline; forgery proven |
| **F1-NEW-1** | MCP `is_local` Origin check prefix-bypassable (`http://localhost.evil.com`) | `mcp/transport.py:136` | Phase 1 | 🟡 **bug confirmed, exploit refuted (0/2)** — real defect, fix cheap + regression test; mitigations incidental (P2-SEC-3) |

**Phase 2 new findings** (detail in `PHASE2_LICENSE.md`): P2-SEC-1 license file perms (`chmod 0600`) · P2-LIC-1 no machine binding · P2-LIC-2 LS activation unsigned/trusted · P2-LIC-3 no store/product pinning · P2-LIC-4 no replay protection · P2-LIC-5 crypto-missing skip · P2-FIX-1 `.sourceprep`/`.runprep` read-write path mismatch · P2-FIX-2 committed (non-matching) private key in `scripts/generate_license.py:33`.

Phase 1 detail: `PHASE1_AUTH_BOUNDARY.md` · Phase 2 detail: `PHASE2_LICENSE.md`.

Full detail in `04_CANDIDATE_FINDINGS.md`.

**Also flagged (from `prep()` Security-Engineer role-view, 2026-06-16):**
`core/team_config.py` (validating loader for attacker-controlled `team_config.json`
— the trust boundary for CRIT-2/HIGH-2/MED-1) and a second prior-audit doc
`docs/Phase06_Team_And_Enterprise/TEAM_ENTERPRISE_CODE_AUDIT.md` to read in the
deep phases.

---

## Tooling gaps (for hardening phase)

**Active (CI `.github/workflows/security-audit.yml`):** pip-audit · npm audit · cargo audit.
**Absent:** bandit · ruff `S` rules · semgrep-scan · CodeQL · gitleaks/trufflehog ·
Dependabot · DAST/Trivy/OSV · cargo-deny · license/SBOM gate · root pre-commit config ·
`tests/test_security_health.py` (the 16-check engine has no unit test).

Full detail in `03_TOOLING_BASELINE.md`.

---

## Decisions (RESOLVED 2026-06-22)

| # | Decision | Resolution | Basis |
|---|----------|------------|-------|
| D-1 | Orchestration | ✅ **one phase at a time**, review between | findings are dependency-linked; provenance wants review |
| D-2 | Scope | ✅ **product + `public/sourceprep-deploy/`**; defer `websites/` (payments gets its own later phase) | deploy is small/high-signal + owns MED-2/LOW-3 |
| D-3 | Threat model | ✅ **loopback-primary + exposed-case as first-class scenario** | code review: no shipped non-loopback exposure; desktop even sets a token; manual `--host 0.0.0.0` is the footgun |

---

## Dogfooding log (this phase is also a product test — CLAUDE.md)

| Date | Tool | Result | Action |
|------|------|--------|--------|
| 2026-06-16 | `prep()` role=security | ✅ role-view surfaced the right files (team_config.py, remote_sync.py, audit_log.py) + a prior-audit doc | use role-view for code orientation |
| 2026-06-16 | `prep_search` "team_config.json validation" | ❌ returned Phase 136 dogfood README (planning-doc bias, top score 0.51); missed `team_config.py` | known `project_search_docs_bias`; prefer role-view + grep for code |
| 2026-06-16 | `prep_search` "is_safe_url…" (LOCATE) | ❌ "No symbols found" for a function that exists at `llm.py:159` | LOCATE on descriptive phrase fails; product finding to log via prep_observe |
| 2026-06-16 | `prep_audit antibodies` | ⚪ none exist (no constraint concepts) | opportunity: seed security-constraint concepts (Phase 8) |
| 2026-06-16 | `prep_impact server.py` | ✅ 30 dependents (hub confirmed); note: server.py not a trace-graph node, import-edges still resolved | single auth chokepoint = good for audit, bad for defense-in-depth |
| 2026-06-22 | `prep()` (Phase 1 resume) | ❌ daemon down ("Cannot connect to :8400") — fell back to grep/read for the whole phase | restart-before-use; product can't help when daemon is down (expected, but worth noting for headless/CI audits) |

## Changelog

- **2026-06-22 (pause)** — Per user: license + feature-gate are being reworked by
  Phase 142 (OSS-First, design-only/unmerged). **Finance/legal security track paused**
  (Phase 2 follow-through, Phase 3 S3/team-sync, payments, legal) until 142 lands.
  Phase 2 findings preserved as feed-forward requirements for 142's license-application
  + secret-audit. Non-finance phases (4/5/6/8 + C-3 LLM-proxy SSRF) continue.
- **2026-06-22 (Phase 2)** — License & Feature-Gate done via 46-agent workflow
  (Map→Probe→Refute) + lead re-verification. **Proven:** offline license forgery —
  shipped Ed25519 public key is the all-zeros-seed/RFC-8032 test vector,
  `PREP_LICENSE_PUBLIC_KEY` override is comment-only, and unsigned `license.json`
  is accepted. CRIT-1/C-7 → CONFIRMED CRITICAL launch-blocker. Refute panel made a
  key category correction (most license findings are revenue/DRM integrity, not
  CIA-security) and reframed C-2 (UI is dev-gated) + bounded F1-NEW-1. 8 new
  findings logged (P2-SEC-1..3, P2-LIC-1..5, P2-FIX-1..4).
- **2026-06-22** — D-1/D-2/D-3 resolved. Phase 1 (Auth & Daemon Boundary) reviewed
  at code level (`PHASE1_AUTH_BOUNDARY.md`). C-1 reframed (MEDIUM footgun, not
  critical — desktop sets a token, no shipped non-loopback exposure); C-2 confirmed
  (ungated dev-override wired to dashboard UI); C-5 confirmed but low-likelihood
  (http transport opt-in); new finding F1-NEW-1 (MCP `is_local` prefix bypass).
  Refute panel still pending. prep daemon was down → grep/read fallback.
- **2026-06-16** — Phase 0.5 complete. Removed fabricated `Phase_SecurityAuditPrep/`;
  rebuilt as verified `Phase146_SecurityAudit/`. Ledger seeded from Phase 06 audit
  + verification pass. 7 candidate findings logged. Deep-dive plan (8 workstreams +
  per-phase orchestration) written. prep reconnected mid-phase; role-view used to
  enrich plan, search misses logged above.
