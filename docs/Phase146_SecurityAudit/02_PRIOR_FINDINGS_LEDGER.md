# 02 — Prior Findings Ledger

**Source of truth:** `docs/Phase06_Team_And_Enterprise/SECURITY_AUDIT.md` (Mar 9, 2026),
a two-part audit (Team/Enterprise deep audit + Full-Codebase audit). A companion
doc `docs/Phase06_Team_And_Enterprise/TEAM_ENTERPRISE_CODE_AUDIT.md` also exists
and should be read in full during the deep phases. There is also an earlier
`docs/Phase36_SecurityAudit/COMPREHENSIVE_AUDIT_PLAN.md` (Feb 21, 2026) — see
"Caveats" below.

**Current-state column verified:** 2026-06-16 by the `security-scaffold-verify`
pass (double-sourced where the file-locator and adversarial-reviewer agents
agreed). Anything not re-read against live code is marked ❓.

Legend: ✅ fixed · 🟡 partial/residual · 🔴 open · ⚪ deferred-by-design · ❓ re-verify

---

## Critical

### CRIT-1 — License system has no cryptographic verification 🟡
- **Real location:** `src/prep/core/feature_gate.py` (the gate), `src/prep/core/licensing.py` (the verifier), `src/prep/core/lemon_squeezy.py` (online), `src/prep/api/routers/license.py` (the API).
- **Phase06 status:** "Needs Design" — called a ship-blocker for paid tiers. CVSS estimate 8.0.
- **What it was:** any user could write `~/.runprep/license.json` with `{"tier":"enterprise"}` or set `PREP_TIER=enterprise` and unlock all paid features; the docstring claimed an "Ed25519 signed token" but no signature was checked.
- **Current code state:** `feature_gate.py:196-257` now imports `prep.core.licensing.verify_license_key`, tracks a `signature_verified` flag, logs "License signature verified successfully," and fails closed on a bad signature. **So the core gap is addressed** — but two residuals remain (see C-2, C-7): the **default public key is a placeholder/dev key** (`licensing.py:22`), and `/license/dev-override` flips `PREP_DEV_MODE=1` process-wide, re-enabling the unsigned plain-JSON/tier-name shortcuts (`license.py:147-166`).
- **Deep-phase question (Phase 2):** Does the *shipped build* embed a real production public key (override via `PREP_LICENSE_PUBLIC_KEY`)? Is unsigned-license behaviour reject vs. warn-and-allow? Can `dev-override` be reached in a packaged build?

### CRIT-2 — S3 endpoint URL is attacker-controlled (SSRF via team_config.json) ✅(guarded)
- **Real location:** `src/prep/services/remote_sync.py:211` (use), `:71` (`_validate_s3_endpoint`). Config loaded by `src/prep/core/team_config.py`.
- **Phase06 status:** "Needs Design." CVSS estimate 7.5.
- **What it was:** `s3_endpoint` in `.runprep/team_config.json` (committed to git) could point a teammate's daemon at `http://169.254.169.254/...` and the daemon would send S3 creds there.
- **Current code state:** `_validate_s3_endpoint` (`remote_sync.py:71`, "EA-B1: SSRF prevention") blocks `169.254.169.254` / `metadata.google.internal`, resolves the host and rejects private/loopback/link-local/reserved IPs, and requires HTTPS (except localhost). **The metadata-server claim is no longer reachable.**
- **Deep-phase question (Phase 3):** DNS-rebinding (TOCTOU between validate and use)? HTTP→internal redirects followed? Does `team_config.py` validation cover every field that feeds an outbound call? Is endpoint-change warned to the user?

---

## High

### HIGH-1 — Git clone URL injection ✅
- **Location:** `src/prep/services/headless_runner.py:485-503`.
- **Phase06:** "✅ Fixed — added `--` separator to git clone." List-form subprocess already prevented shell injection; the `--` stops a `--upload-pack=...` style flag-injection.
- **Re-verify:** low — confirm `--` is present before the URL arg.

### HIGH-2 — Secrets file has no permission check 🟡
- **Location:** `src/prep/services/remote_sync.py:102-131` (`_check_secrets_permissions`).
- **Phase06:** "Needs Design" (Windows vs Unix behaviour).
- **Current:** warns if `.sourceprep/.secrets` is group/world-readable (Unix). The plaintext S3 creds still sit in JSON.
- **Deep-phase question (Phase 3):** warn vs. refuse-to-load? Windows ACL handling? Should creds be env-only?

### HIGH-3 — API key logged in `_verify_license` ✅
- **Location:** `src/prep/services/headless_runner.py` (was line 458).
- **Phase06:** "✅ Fixed — deleted dead `_verify_license()` method." grep confirms the method is gone.
- **Re-verify:** done.

### HIGH-4 — S3 config prefix path traversal ✅
- **Location:** `src/prep/services/s3_storage.py:163-170` (`_s3_key`).
- **Phase06:** "✅ Fixed — added prefix traversal validation." `_s3_key` rejects `..` segments and leading `/`, so one team can't read/overwrite another team's prefix in a shared bucket.
- **Re-verify:** done.

### HIGH-5 — Zip bomb denial of service ✅
- **Location:** `src/prep/services/s3_storage.py:292-307`.
- **Phase06:** "✅ Fixed — 10 GB uncompressed limit." Before `extractall`, sums `zf.infolist()` uncompressed sizes and rejects > `MAX_UNCOMPRESSED_BYTES` (10 GB); also a zip-slip guard rejects members escaping the temp dir.
- **Re-verify:** done. (Note the *content-hash* check on the same download only **warns** — see MED-3.)

---

## Medium

| ID | Title | Location | Phase06 | Current | Re-verify |
|----|-------|----------|---------|---------|-----------|
| MED-1 | Polling interval has no minimum | `remote_sync.py:52` | ✅ Fixed (5-min min) | enforced | low |
| MED-2 | GH Actions logs model provider/name | `public/sourceprep-deploy/github-actions/prep-sync.yml:48` | rec only (no fix) | 🔴 open (info-disclosure, low) | Phase 8 |
| MED-3 | No content integrity check on downloaded index | `s3_storage.py:268-329` | ✅ Fixed (hash verify) | 🟡 hash compared but **only logs a warning on mismatch — does not abort extraction** | ❓ Phase 3 |
| MED-4 | Context injection via document content | `core/layered_index.py:217` | "Needs Design" | 🟡 defensive marker present; triple-backtick code fences not escaped, so a malicious file could break out of the data block | ❓ Phase 4 |

---

## Low / Full-codebase

| ID | Title | Location | Phase06 | Current |
|----|-------|----------|---------|---------|
| FULL-1 | CORS `*` + `allow_credentials=True` | `server.py:227-243` | ✅ Fixed | loopback/tauri allowlist; `PREP_CORS_ALLOW_ALL=1` dev escape hatch |
| FULL-2 | LLM proxy endpoints are SSRF vectors | `api/routers/llm.py:159` | ✅ Fixed | `is_safe_url` blocks metadata/private IPs — **but has bypass gaps** (→ C-3) |
| FULL-3 | Google API key as URL query param | `core/llm_client.py:591` | rec only | ⚪ Google's API design; document for enterprise |
| FULL-4 | No API rate limiting | `server.py` (global) | Deferred | ⚪ deferred to future Prep Manager; IPC token deemed sufficient for local daemon |
| FULL-5 | git log subprocess in inferred edges | `core/inferred_edges.py:852` | no action | ✅ bounded (≤500 commits, 30s timeout, argv form) |
| LOW-1 | Dead `_verify_license` method | `headless_runner.py` | same as HIGH-3 | ✅ removed |
| LOW-2 | S3 client cached forever | `s3_storage.py:131` | observation | ⚪ reliability (STS rotation), not a vuln |
| LOW-3 | Dockerfile installs Ollama via piped curl | `public/sourceprep-deploy/Dockerfile.gpu:33` | rec only | 🔴 supply-chain (pin+checksum) — Phase 8 |

Also referenced from a previous audit (no file refs in the Phase06 doc, marked fixed):
non-root Docker user, Modal webhook auth, redundant soft license gate removed,
entrypoint fails loudly on Ollama timeout, model defaults updated.

---

## Caveats on the prior docs

- **All "Fixed" statuses in the prior docs are self-asserted by those docs.**
  The current-state column here re-verified the *high-impact* ones against live
  code (CRIT-1, CRIT-2, HIGH-5, FULL-1/2) but not every Medium/Low. Treat ❓ rows
  as "claimed fixed, not independently re-confirmed."
- **Phase36 (Feb 2026) is stale.** It uses the old `CoDRAG`/`codrag` package
  names and old paths (`codrag/core/index.py`, `codrag-engine/src/lib.rs`); the
  current tree is `src/prep/` + `engine/crates/`. Its "AUDITED & FIXED" claims
  cannot be assumed valid against today's code. It also **deferred `npm audit`
  and `cargo audit` to CI** — those are now wired (see `03_TOOLING_BASELINE.md`).
- **More security docs exist** under `Phase06_Team_And_Enterprise/`
  (`SECURITY_DESIGN_DECISIONS.md`, `SECURITY_STRATEGY.md`,
  `SECURITY_TIER_ASSIGNMENT.md`, `TEAM_ENTERPRISE_CODE_AUDIT.md`,
  `SECURITY_TO_IT_PANEL_PLAN.md`) and `Phase129_DevLeakAudit/`. The deep phases
  should read these before declaring any area covered.
