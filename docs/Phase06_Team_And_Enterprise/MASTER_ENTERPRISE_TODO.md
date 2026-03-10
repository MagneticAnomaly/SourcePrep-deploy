# Master Enterprise TODO — All Work Items
*Created: March 9, 2026*
*This is the single authoritative checklist for all enterprise, security, and licensing work.*

---

## Priority Key
- **P0** — Ship blocker (can't launch without it)
- **P1** — Required for first enterprise customer
- **P2** — 3-6 month roadmap
- **P3** — 6-12 month roadmap

---

## SPRINT 1: Security Health Panel Expansion
*Expand security_health.py from 7 to 13 checks and group them in the IT panel.*

- [x] **SEC-8** Add daemon auth posture check (is CODRAG_DAEMON_TOKEN set? binding address?) — P1 ✅
- [x] **SEC-9** Add CORS configuration check (restricted vs CODRAG_CORS_ALLOW_ALL=1) — P1 ✅
- [x] **SEC-10** Add dev mode detection check (CODRAG_DEV_MODE=1, CODRAG_TIER override) — P1 ✅
- [x] **SEC-11** Add content sanitization active check (sanitize_output callable) — P1 ✅
- [x] **SEC-12** Add API key hygiene check (Google URL-param auth warning) — P2 ✅
- [x] **SEC-13** Add MCP rate limit health check (rate status, recent 429s) — P2 ✅
- [x] **SEC-GRP** Group checks into categories in API response (infrastructure, license, data, runtime) — P1 ✅
- [x] **SEC-UI** Update EnterpriseAdminPanel Security tab to show grouped/categorized checks — P1 ✅
- [x] **SEC-TIP** Add API key exposure tooltip to EndpointManager for Google provider — P2 ✅
- [ ] **SEC-TEST** Test all 13 checks pass on clean install — P1

### Also Completed (Security Pipeline Protection)
- [x] **CORE-1** Wire `sanitize_llm_input()` into `llm_client.py generate()` — ALL 8 pipeline stages now protected ✅
- [x] **CORE-2** Wire `validate_llm_output()` into ALL 6 provider return paths ✅
- [x] **CORE-3** Add NFKC normalization to `content_sanitizer.py` (EchoLeak CVE-2025-32711 defense) ✅
- [x] **CORE-4** Add `sanitize_output()` function for MCP context assembly path ✅
- [x] **CORE-5** Add well-known secret detection patterns (AWS, GitHub, Slack, OpenAI, Google, JWT, private keys) ✅
- [x] **CORE-6** Add `detect_secrets()` function for IT visibility (Check 14 future) ✅

## SPRINT 2: LemonSqueezy License Integration
*The revenue path. Without this, we can't charge money.*

- [x] **LS-1** Rewrite `POST /license/activate` to call LS API — ✅ Built (`lemon_squeezy.py` + `license.py`)
- [x] **LS-2** Periodic re-validation (7-day LS `validate` call) — ✅ Built (`/license/validate` + App.tsx hourly check)
- [x] **LS-3** 30-day offline grace period — ✅ Built (grace period logic in validate endpoint)
- [x] **LS-4** License recovery flow — ✅ Built (`POST /license/recover` endpoint redirects to web flow)
- [x] **LS-5** Deactivation endpoint (frees LS activation slot) — ✅ Built
- [ ] **LS-6** `api.codrag.io` relay service (serverless: LS webhook → Ed25519 license) — P0 (**Eric: see FOR_ERIC_TODO.md**)
- [ ] **LS-7** Ed25519 keypair generation — P0 (**Eric: see FOR_ERIC_TODO.md LS-10**)
- [ ] **LS-8** Activation limits per LS product — P0 (**Eric: see FOR_ERIC_TODO.md LS-02 to LS-04**)

## SPRINT 3: Seat Management (Team/Enterprise)
*Required when first team customer signs up.*

- [x] **SEAT-1** Seat count tracking — ✅ Built (`GET /license/seats`)
- [x] **SEAT-2** Seat management UI — ✅ Built (Enterprise Admin → Usage tab, active machines list)
- [x] **SEAT-3** Seat overflow handling — ✅ Built (amber warning + purchase link)
- [x] **SEAT-4** Admin seat provisioning (generate per-user keys from admin panel) — P2 ✅
- [x] **SEAT-5** Onboarding flow (new team member receives key → activates → joins seat pool) — P2 ✅
- [x] **SEAT-6** Offboarding flow (admin deactivates seat → next validation downgrades to FREE) — P2 ✅

## SPRINT 4: AI Gateway Enhancements
*Versatile access controls for IT admins who want flexible policies.*

- [x] **GW-1** Per-user local model override — ✅ Built (`allow_any_local_model` in ModelPolicy + enforcement bypass)
- [x] **GW-2** IT-managed API key injection — ✅ Built (`allow_user_api_keys` + masked UI)
- [x] **GW-3** Per-slot policy (different provider/model restrictions per model slot) — P2 ✅
- [x] **GW-4** Per-user cost limits (individual monthly budget caps) — P2 ✅
- [x] **GW-7** Policy change audit trail — ✅ Built (`_save_llm_config` logs to audit)
- [x] **GW-8** Read-only AI Gateway — ✅ Built (`canAddEndpoints`, `canEditApiKeys` gates)

### Also Completed (Pipeline Security)
- [x] **DLP-1** Enterprise DLP secret redaction wired into `llm_client.py generate()` chokepoint ✅
- [x] **AUDIT-1** LLM call audit trail — every call logs provider/model/endpoint/prompt_chars ✅

## SPRINT 5: Security Audit Fixes (Remaining)
*Items from SECURITY_AUDIT.md not yet fixed.*

- [x] **CRIT-1** License Ed25519 verification — ✅ Built (feature_gate.py + licensing.py)
- [x] **CRIT-2** S3 SSRF prevention — ✅ Built (remote_sync.py + llm.py is_safe_url)
- [x] **HIGH-1** Git clone URL injection — ✅ Fixed (-- separator)
- [x] **HIGH-2** Secrets file permissions — ✅ Built (remote_sync.py _check_secrets_permissions)
- [x] **HIGH-3** API key logged — ✅ Fixed (dead code removed)
- [x] **HIGH-4** S3 prefix path traversal — ✅ Fixed
- [x] **HIGH-5** Zip bomb DoS — ✅ Fixed (10 GB limit)
- [x] **MED-1** Polling interval minimum — ✅ Fixed (5 min)
- [ ] **MED-2** GitHub Actions logs model info — P3 (add --quiet flag to CLI)
- [x] **MED-3** Content hash verification — ✅ Fixed
- [x] **MED-4** Context injection — ✅ Content sanitizer built + wired
- [x] **FULL-1** CORS restricted — ✅ Fixed
- [x] **FULL-2** SSRF on LLM proxy — ✅ Fixed (is_safe_url enhanced)
- [ ] **FULL-3** Google API key in URL — Can't fix (Google's API design). Document for enterprise. — P2

## SPRINT 6: Authentication & Identity
*Enterprise maturity features.*

- [ ] **AUTH-1** SSO/SAML integration (Okta, Azure AD) — P3
- [ ] **AUTH-2** SCIM provisioning (auto-create/delete seats from IdP) — P3
- [ ] **AUTH-3** Expanded RBAC (viewer / developer / admin / super-admin) — P2
- [ ] **AUTH-4** Multi-org support (single license managing multiple teams) — P3

## SPRINT 7: Compliance & Documentation
*Enterprise sales enablement.*

- [ ] **COMP-1** SOC 2 Type II readiness documentation — P2
- [ ] **COMP-2** GDPR data export endpoint ("download my data") — P3
- [ ] **COMP-3** Data residency controls (S3 region restrictions in admin policy) — P3
- [x] **COMP-4** Immutable audit log with export — ✅ Built (audit_log.py)
- [x] **COMP-5** Security health dashboard — ✅ Built (security_health.py + Security tab)
- [ ] **COMP-6** Penetration test readiness — P3

## SPRINT 8: Deployment & Distribution
*Enterprise distribution features.*

- [ ] **DEPLOY-1** MDM distribution (Jamf/Intune silent install flags) — P2
- [ ] **DEPLOY-2** Pre-configured installer (bake team_config.json into installer) — P2
- [ ] **DEPLOY-4** Version pinning (IT can block auto-update until approved) — P2
- [ ] **DEPLOY-5** AWS Bedrock provider (SigV4 auth via boto3) — P2

## ALREADY BUILT (This Session — March 9, 2026)

### Backend
- [x] `team_config.py`: AdminPolicy schema (7 dataclasses) + 5 enforcement utilities
- [x] `settings.py`: 9 enterprise API endpoints (admin-policy, audit-log, security-health, batch-estimate, admin actions)
- [x] `remote_sync.py`: SSRF prevention + secrets permission check
- [x] `cli.py`: Secret deprecation warnings for CLI flags
- [x] `index.py` + `layered_index.py`: Content sanitizer wiring in get_context()
- [x] `mcp/server.py`: Audit logging + rate limiting (120 calls/60s)
- [x] `llm_client.py`: Azure OpenAI generation + is_available
- [x] `llm.py`: Google model metadata (context window, cost tier) in proxy_models
- [x] `batch_profiles.py`: Azure OpenAI batch profile entries

### Frontend
- [x] `types.ts`: AdminPolicy types (7 interfaces) + azure-openai provider
- [x] `useAdminPolicy.ts`: React hook with 5-min cache (new file)
- [x] `AdminSection.tsx`: Orange-bordered admin component (new file)
- [x] `client.ts` + `mock.ts`: getAdminPolicy + getBatchEstimate methods
- [x] `EndpointManager.tsx`: Admin policy integration + URL autofill + azure-openai + Wand2 autofill button
- [x] `AIModelsSettings.tsx`: adminPolicy prop + batchEstimate display + modelDetails pass-through
- [x] `ModelCard.tsx`: Rich model metadata (context window + cost tier with · bullet separators)
- [x] `EnterpriseAdminPanel.tsx`: Policy tab with orange AdminSection borders (provider, model, DLP, budget)
- [x] `useLLMConfig.ts`: modelDetails state + handleClearTestResult (user-applied)
- [x] `useDashboardPanels.tsx`: modelDetails + handleClearTestResult wiring (user-applied)
- [x] `App.tsx`: modelDetails + batchEstimate + handleClearTestResult wiring (user-applied)
- [x] `index.ts`: Exports for AdminSection, useAdminPolicy, 7 AdminPolicy types

### Tests
- [x] `test_admin_policy.py`: ~35 tests (parsing, enforcement, provider/model filtering)

### Documentation
- [x] `COMPREHENSIVE_LOST_WORK_AND_MEMORIES.md`: Full filesystem-verified audit of lost work
- [x] `ENTERPRISE_FEATURES_PLAN.md`: 6-section plan (licensing, gateway, auth, compliance, deployment)
- [x] `SECURITY_TO_IT_PANEL_PLAN.md`: Security audit → IT panel mapping (13 checks plan)
- [x] `TODO.md`: Updated with enterprise roadmap + session work log

---

## Quick Stats (Updated March 10, 2026)

| Category | Total | Done | Remaining |
|----------|-------|------|-----------|
| Security Health Panel | 10 | **10** | 0 |
| LemonSqueezy Integration | 8 | **5** | 3 (Eric tasks) |
| Seat Management | 6 | **6** | 0 |
| AI Gateway Enhancements | 6 | **6** | 0 |
| Security Audit Fixes | 15 | **13** | 2 |
| Pipeline Security (NEW) | 8 | **8** | 0 |
| Auth & Identity | 4 | 0 | 4 |
| Compliance & Documentation | 6 | 2 | 4 |
| Deployment & Distribution | 4 | 0 | 4 |
| **TOTAL** | **67** | **50** | **17** |

### Priority Breakdown of Remaining

| Priority | Count | Description |
|----------|-------|-------------|
| **P0** | 3 | Ship blockers (Eric: LS products, Ed25519, webhook) |
| **P1** | 1 | License recovery flow (LS-4) |
| **P2** | 8 | 3-6 month roadmap |
| **P3** | 9 | 6-12 month roadmap |
