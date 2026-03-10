# Comprehensive Lost Work & Memory Audit
*(Generated March 9, 2026 — Verified against live filesystem)*

This is the master reference for all work that was built, lost, and needs to be rebuilt.
Every item has been verified against the actual codebase on disk. Use this document to
resume the Enterprise Admin rebuild in any future session.

---

# STATUS LEGEND

| Symbol | Meaning |
|--------|---------|
| ✅ | **Present on disk** — code exists and is functional |
| ❌ | **MISSING** — file or feature does not exist, must be rebuilt |
| ⚠️ | **Partial** — file exists but the enterprise feature was stripped/never wired |

---

# SECTION A: Enterprise Admin Core Modules

## A1. New Python Modules (Created from Scratch)

These files were entirely new — created during the enterprise session.

| File | Status | Lines | Description |
|------|--------|-------|-------------|
| `src/codrag/core/content_sanitizer.py` | ✅ | ~320 | Code fence sanitization, invisible Unicode stripping, LLM I/O validation, DLP enforcement (`is_file_blocked_by_dlp`, `check_dlp_before_llm_call`, `redact_secrets_in_content`) |
| `src/codrag/core/audit_log.py` | ✅ | ~389 | Append-only SQLite audit log. Functions: `record()`, `query()`, `count()`, `purge()`, `export()`. Has `SECURITY_EVENT_TYPES` filter set. 22+ event types. |
| `src/codrag/core/security_health.py` | ✅ | ~269 | 7 security checks: license validity, S3 endpoint HTTPS, credentials file permissions, index integrity (embedding hash), DLP compliance, config drift detection, network security. Aggregate scoring. |
| `src/codrag/core/cost_estimation.py` | ✅ | ~181 | Cost estimation engine mapping token counts to dollar estimates based on model pricing tables. |
| `src/codrag/core/budget_enforcement.py` | ✅ | ~218 | Budget enforcement checking token/cost limits from `admin_policy.budgets` section. Pauses pipeline if exceeded. |
| `src/codrag/core/licensing.py` | ✅ | exists | Contains `verify_license_key()` with Ed25519 signature verification. |

## A2. Modified Python Modules — Enterprise Features

These are existing files that had enterprise features added. Some survived, some were lost.

### `src/codrag/core/feature_gate.py` — ✅ INTACT
All enterprise licensing features are present:
- **EA-A6**: Ed25519 license signature verification via `verify_license_key()` import
- **EA-A7**: `expires_at` validation via `_is_license_expired()` / `_parse_expires_at()`
- **EA-A8**: `CODRAG_DEV_MODE=1` required alongside `CODRAG_TIER` for dev override
- `signature_verified` field on `License` dataclass

### `src/codrag/core/team_config.py` — ❌ ADMIN POLICY MISSING
The file exists but **none of the AdminPolicy code is present**:
- ❌ `AdminPolicy` dataclass (was 7 nested dataclasses: `ProviderPolicy`, `ModelPolicy`, `DataPolicy`, `SyncPolicy`, `NetworkPolicy`, `BudgetPolicy`, `AdminPolicyConfig`)
- ❌ `parse_admin_policy()` function
- ❌ `is_provider_allowed(provider, policy)` utility
- ❌ `is_model_allowed(model, policy)` utility
- ❌ `filter_models_by_policy(models, policy)` utility
- ❌ `check_policy_violation(action, policy)` utility

**What needs to be rebuilt:**
```python
# 7 dataclasses:
@dataclass
class ProviderPolicy:
    allowed_providers: list           # e.g. ["ollama", "openai"]
    blocked_providers: list           # explicit blocklist
    allow_local_providers: bool       # always allow ollama/lm-studio
    locked_endpoints: list            # IT-configured endpoints users can't edit

@dataclass
class ModelPolicy:
    allowed_models: list              # allowlist (empty = all allowed)
    blocked_models: list              # blocklist patterns
    require_approved_models: bool     # if True, only allowlisted models work

@dataclass
class DataPolicy:
    never_send_globs: list            # file patterns that must never go to cloud LLMs
    redact_patterns: list             # regex patterns to strip from LLM content
    block_unapproved_cloud: bool      # block sending data to non-approved cloud providers
    allowed_destinations: list        # approved cloud providers for data

@dataclass
class SyncPolicy:
    require_s3_https: bool
    allowed_s3_endpoints: list

@dataclass
class NetworkPolicy:
    block_metadata_endpoints: bool    # block 169.254.169.254
    allowed_ports: list               # for local providers

@dataclass
class BudgetPolicy:
    monthly_token_limit: int
    monthly_cost_limit_usd: float
    alert_threshold_percent: float    # e.g. 0.8 = alert at 80%

@dataclass
class AdminPolicy:
    provider: ProviderPolicy
    model: ModelPolicy
    data: DataPolicy
    sync: SyncPolicy
    network: NetworkPolicy
    budgets: BudgetPolicy
    enforcement_mode: str             # "suggest" or "enforce"
```

### `src/codrag/services/remote_sync.py` — ⚠️ PARTIAL
- ✅ `MIN_POLL_INTERVAL_MINUTES` enforcement (restored by user)
- ❌ SSRF prevention for S3 endpoints (was checking for private IPs, metadata endpoints)
- ❌ `.codrag/.secrets` file permission/ownership check (was verifying file mode 0o600)

**What needs to be rebuilt:**
- `_validate_s3_endpoint(url)` — blocks private IPs, metadata endpoints, non-HTTPS
- `_check_secrets_permissions(path)` — verifies file mode is 0o600, warns if too permissive

### `src/codrag/cli.py` — ❌ SECRET DEPRECATION MISSING
- ❌ No CLI deprecation warnings for passing secrets via command-line flags
- Should warn: "Passing S3 credentials via CLI flags is deprecated. Use environment variables instead."

### `src/codrag/core/index.py` — ❌ SANITIZER WIRING MISSING
- ❌ No `content_sanitizer` import or calls in `get_context()` or `get_context_structured()`
- Was: calling `sanitize_output()` on assembled context before returning to MCP/API

### `src/codrag/core/layered_index.py` — ❌ SANITIZER WIRING MISSING
- ❌ No `content_sanitizer` calls in `get_context()`
- Same pattern as `index.py` — sanitize before return

### `src/codrag/api/routers/mcp/server.py` — ❌ AUDIT LOGGING MISSING
- ❌ No audit log recording on MCP tool calls
- ❌ No rate limiting (was: 120 calls per 60 seconds per client)
- Was: wrapping each MCP tool handler to log event type, arguments, caller, and enforce rate limit

### `src/codrag/api/routers/settings.py` — ❌ ALL ENTERPRISE ENDPOINTS MISSING
None of these endpoints exist:
- ❌ `GET /settings/admin-policy` — returns parsed AdminPolicy from team_config
- ❌ `GET /admin/audit-log` — query audit log with pagination, date range, event type filters
- ❌ `GET /admin/audit-log/export` — export as JSON or CSV
- ❌ `GET /admin/security-health` — run 7 security checks, return aggregate score
- ❌ `GET /admin/security-report` — export full security report
- ❌ `POST /admin/actions/quarantine-project` — quarantine a project
- ❌ `POST /admin/actions/block-endpoint` — block an endpoint
- ❌ `POST /admin/actions/approve-config` — approve config changes

### `src/codrag/api/routers/llm.py` — ⚠️ PARTIAL
- ✅ SSRF protection with `is_safe_url()` including metadata endpoint blocking (restored by user)
- ✅ Google Gemini proxy/test/model listing (restored by user)
- ❌ Azure OpenAI generation endpoint (was: separate handler for azure-openai provider)
- ❌ Azure OpenAI model listing via deployment API
- ❌ Model allowlist filtering via AdminPolicy (was: filtering proxy_models results through `filter_models_by_policy`)

### `src/codrag/core/llm_client.py` — ⚠️ PARTIAL
- ✅ `CloudRateLimitError` exception class (restored by user)
- ✅ `_generate_lmstudio()` native SSE method (restored by user)
- ✅ `debug_mode` verbose logging (restored by user)
- ✅ LM Studio `unload` via `lmstudio_unload()` (restored by user)
- ❌ Azure OpenAI `_generate()` path (was: api-key header, deployment-based URL, streaming)
- ❌ Azure OpenAI `is_available()` check

### `src/codrag/core/batch_profiles.py` — ⚠️ PARTIAL
- ✅ Has GPT via "openai-compatible" comment mentioning Azure
- ❌ No dedicated `azure-openai` provider batch profile entries (was: 4-5 entries for azure deployment names)

---

# SECTION B: Frontend — Missing Enterprise Features

## B1. Files That Need to Be Created (Don't Exist on Disk)

| File | Status | Description |
|------|--------|-------------|
| `packages/ui/src/hooks/useAdminPolicy.ts` | ❌ MISSING | React hook: fetches `/settings/admin-policy`, caches result, returns `{ policy, loading, error }`. ~60 lines. |
| `packages/ui/src/components/primitives/AdminSection.tsx` | ❌ MISSING | Orange-bordered section wrapper for admin-only UI. `border-l-4 border-l-amber-500`. Shows "ADMIN" badge and enforcement mode (suggest/enforce). ~74 lines. |

**`useAdminPolicy.ts` spec:**
```typescript
// Fetches admin policy from backend, caches for 5 minutes
// Returns { policy: AdminPolicy | null, loading: boolean, error: string | null, refresh: () => void }
// Used by EndpointManager, AIModelsSettings, EnterpriseAdminPanel
```

**`AdminSection.tsx` spec:**
```typescript
// Props: { title, children, enforcementMode?: 'suggest' | 'enforce', className? }
// Renders: orange left border, "ADMIN" badge, orange background tint
// When enforcementMode='enforce': shows lock icon + "Enforced by IT" label
// When enforcementMode='suggest': shows info icon + "Suggested by IT" label
```

## B2. Existing Files Missing Enterprise Features

### `packages/ui/src/types.ts` — ❌ ADMIN POLICY TYPES MISSING
- ✅ `UserRole` type exists (`'user' | 'admin'`)
- ✅ `LLMProvider` includes `'google'`
- ✅ `concurrency?: number` on `LLMSlotConfig` and `LLMAssignmentBlock`
- ✅ `developer_debug_mode?: boolean` on config type
- ❌ No `AdminPolicy` TypeScript interface (was ~80 lines matching the Python dataclasses)
- ❌ No `ProviderPolicy`, `ModelPolicy`, `DataPolicy`, `SyncPolicy`, `NetworkPolicy`, `BudgetPolicy` types
- ❌ No `signature_verified` field on `LicenseStatus` type
- ❌ No `azure-openai` in `LLMProvider` union type

### `packages/ui/src/api/client.ts` — ❌ ADMIN POLICY CLIENT MISSING
- ✅ `destroyAtlas`, `destroyGroupReasoning`, `destroyDeepEnrichment` methods (restored by user)
- ❌ No `getAdminPolicy()` method
- ❌ No Azure OpenAI support in endpoint methods

### `packages/ui/src/api/mock.ts` — ❌ ADMIN POLICY MOCK MISSING
- ✅ `destroyAtlas`, `destroyGroupReasoning`, `destroyDeepEnrichment` mocks (restored by user)
- ❌ No `getAdminPolicy()` mock (was: returning a default empty AdminPolicy)

### `packages/ui/src/components/llm/EndpointManager.tsx` — ❌ ADMIN POLICY FEATURES MISSING
- ✅ Google provider added with hint URL (restored by user)
- ✅ `providerNeedsApiKey` includes google (restored by user)
- ❌ No `adminPolicy` prop
- ❌ No provider filtering by `allowed_providers` allowlist
- ❌ No `allow_local_providers` escape hatch
- ❌ No locked endpoint rendering (was: lock icon, non-editable rows, "Configured by IT" label)
- ❌ No `allow_user_endpoints` gate on the "Add Endpoint" button
- ❌ No `azure-openai` in provider options

### `packages/ui/src/components/llm/AIModelsSettings.tsx` — ⚠️ PARTIAL
- ✅ Per-model concurrency handlers (restored by user)
- ✅ Updated recommended models (restored by user)
- ✅ Global concurrency buttons removed (restored by user)
- ❌ No `adminPolicy` prop or admin policy summary banner
- ❌ No orange-bordered admin policy section showing active restrictions

### `packages/ui/src/index.ts` — ⚠️ PARTIAL
- ✅ `UserRole` export
- ✅ `Toggle`, `SlidingSwitch2`, `SlidingSwitch3` exports
- ✅ `EnterpriseAdminPanel` export
- ❌ No `AdminSection` export
- ❌ No `useAdminPolicy` export

### `packages/ui/src/components/enterprise/EnterpriseAdminPanel.tsx` — ✅ INTACT
Full 4-tab system is present: Fleet, Sync, Usage, Security. KPI cards, security health display,
token usage summary, sync fleet status, audit log export. ~450 lines.

---

# SECTION C: Tests

| Test File | Status | Count | Description |
|-----------|--------|-------|-------------|
| `tests/test_content_sanitizer.py` | ✅ | 73+ | Code fence, Unicode, LLM validation, DLP, SSRF tests |
| `tests/test_audit_log.py` | ✅ | 22+ | Record, query, count, purge, export tests |
| `tests/test_admin_policy.py` | ❌ MISSING | was 59 | AdminPolicy parsing, enforcement, provider/model filtering. Only `.pyc` exists in `__pycache__`. |

**`test_admin_policy.py` was testing:**
- Parsing `admin_policy` section from team_config JSON
- `is_provider_allowed()` with various combinations
- `is_model_allowed()` with allowlist/blocklist
- `filter_models_by_policy()` output
- `check_policy_violation()` for suggest vs enforce modes
- Edge cases: empty policy, missing fields, invalid values

---

# SECTION D: Restored Features (User-Applied, Verified Present)

These features were manually restored by the user and are verified present on disk:

### D1. LLM Client & Providers
- ✅ `CloudRateLimitError` exception in `llm_client.py`
- ✅ `_generate_lmstudio()` with native SSE parsing (`message.delta`, `reasoning.delta`, `chat.end`)
- ✅ `debug_mode` verbose logging (prompts + timings to stdout)
- ✅ LM Studio model unload via `lmstudio_unload()`
- ✅ `_is_cloud_model()` helper
- ✅ Google Gemini in `llm.py`: proxy_models, test_endpoint, ensure_model_ready
- ✅ SSRF protection in `is_safe_url()`: metadata endpoint blocking, private IP blocking, allowed local ports

### D2. Pipeline & Orchestrator
- ✅ `_maybe_retrigger_deepening()` in `orchestrator.py` (settled_ratio < 0.70 → 30s retrigger)
- ✅ `_backup_files_if_debug()` and `_selective_delete()` in `enrichment.py`
- ✅ `DELETE /projects/{id}/atlas/destroy` endpoint
- ✅ `DELETE /projects/{id}/group-reasoning/destroy` endpoint
- ✅ `DELETE /projects/{id}/deep-enrichment/destroy` endpoint
- ✅ `developer_debug_mode` injection in `server.py`
- ✅ Catch-all file preservation in `index.py` (replaces fragile whitelist)

### D3. UI Restored
- ✅ `GraphEnrichmentPipeline.tsx`: rerun visualization, stale/done percent, paused state, queued state
- ✅ `SettingsDrawer.tsx`: Debug Tools (Verbose Telemetry toggle), Selective Reset (Atlas/GroupReasoning/DeepEnrichment), Role Override dropdown
- ✅ `AIModelsSettings.tsx`: per-model concurrency handlers, updated model recommendations, global concurrency removed
- ✅ `EndpointManager.tsx`: Google provider, Anthropic hint URL
- ✅ `types.ts`: `UserRole`, `concurrency` on slots, `google` provider, `developer_debug_mode`

### D4. Concurrency Architecture
- ✅ Backend: `PipelineScheduler` in `scheduler.py`, `QUEUED` state in `state_machine.py`
- ✅ Frontend: Per-model concurrency (1/2) on Small/Large/Code cards + assignment blocks
- ✅ Documentation: `GPU_VRAM_MODEL_REFERENCE.md` updated with per-model rationale

---

# SECTION E: Architecture Decisions to Remember

These are key design decisions made during the enterprise session that must be followed during rebuild:

1. **Admin policy lives in `team_config.json`** under the `admin_policy` key
2. **Enforcement modes**: `suggest` (log violation but allow) vs `enforce` (block action)
3. **Local providers (ollama, lm-studio) always allowed** unless `allow_local_providers: false`
4. **DLP `never_send_globs`** uses `PurePath.match()` (not `fnmatch`)
5. **DLP `redact_patterns`** uses Python `re` regex
6. **Audit log**: Separate SQLite DB file, append-only, `SECURITY_EVENT_TYPES` filter set
7. **Security health**: 7 checks → aggregate score (0-7), status: healthy/warnings/critical
8. **Orange admin borders**: `border-l-4 border-l-amber-500` visual treatment for admin sections
9. **License path**: `~/.codrag/license.json` (offline Ed25519 signed token)
10. **Secrets path**: `.codrag/.secrets` (must be mode 0o600)
11. **Team config path**: `.codrag/team_config.json`
12. **MCP rate limit**: 120 calls per 60 seconds per client
13. **Budget enforcement reads from**: `admin_policy.budgets` section in team_config
14. **Azure OpenAI uses**: deployment-based URLs + `api-key` header (not Bearer token)
15. **Content sanitizer wiring**: Called in `get_context()` and `get_context_structured()` before returning

---

# SECTION F: Rebuild Priority Order

| Priority | Task | Scope | Depends On |
|----------|------|-------|------------|
| **1** | `team_config.py` AdminPolicy schema + enforcement | Backend | Nothing |
| **2** | `settings.py` enterprise API endpoints | Backend | Task 1 |
| **3** | `types.ts` AdminPolicy TypeScript types | Frontend | Task 1 |
| **4** | `useAdminPolicy.ts` hook | Frontend | Tasks 2, 3 |
| **5** | `AdminSection.tsx` component | Frontend | Nothing |
| **6** | `client.ts` + `mock.ts` getAdminPolicy | Frontend | Tasks 2, 3 |
| **7** | `EndpointManager.tsx` admin policy integration | Frontend | Tasks 3, 4, 6 |
| **8** | `AIModelsSettings.tsx` admin policy banner | Frontend | Tasks 3, 4 |
| **9** | `remote_sync.py` SSRF + secrets checks | Backend | Nothing |
| **10** | `cli.py` secret deprecation warnings | Backend | Nothing |
| **11** | `index.py` + `layered_index.py` sanitizer wiring | Backend | Nothing |
| **12** | `mcp/server.py` audit logging + rate limiting | Backend | Task 1 (audit_log) |
| **13** | `llm.py` + `llm_client.py` Azure OpenAI | Backend | Nothing |
| **14** | `batch_profiles.py` Azure entries | Backend | Task 13 |
| **15** | `test_admin_policy.py` (59 tests) | Tests | Task 1 |
| **16** | `index.ts` exports for AdminSection, useAdminPolicy | Frontend | Tasks 4, 5 |
| **17** | Full test suite run + tsc verification | QA | All above |

---

# SECTION G: Sprint Completion Status (EA Ticket Tracking)

| Sprint | Area | Status | Notes |
|--------|------|--------|-------|
| **EA-A** | Licensing | 3/11 done | A6 (signature), A7 (expiry), A8 (DEV_MODE) — rest needs api.codrag.io |
| **EA-B** | Security Hardening | 4/12 done | B1/B3 (SSRF/permissions) ❌, B4 (CLI warnings) ❌, B5 (sanitizer wiring) ❌, B12 (MCP audit) ❌ |
| **EA-C** | AI Gateway Policy | 0/11 ❌ | All admin policy features stripped — team_config, types, settings, endpoint filtering |
| **EA-D** | Seat Management | 0/? | Blocked on api.codrag.io |
| **EA-E** | Azure OpenAI | 0/6 ❌ | All Azure features stripped from llm.py, llm_client.py, batch_profiles.py |
| **EA-F** | DLP | 6/6 ✅ | content_sanitizer.py intact with all DLP functions |
| **EA-G** | AWS Bedrock | 0/? | Deferred (low priority) |
| **EA-H** | Audit Log | 1/8 ⚠️ | audit_log.py exists but API endpoints stripped from settings.py |
| **EA-I** | Security Panel | 1/15 ⚠️ | security_health.py exists but API endpoints stripped from settings.py |

---

# SECTION H: File-Level Quick Reference

### Files to CREATE (don't exist):
```
packages/ui/src/hooks/useAdminPolicy.ts          (~60 lines)
packages/ui/src/components/primitives/AdminSection.tsx  (~74 lines)
tests/test_admin_policy.py                        (~59 tests)
```

### Files to MODIFY (add missing enterprise features):
```
src/codrag/core/team_config.py          — Add AdminPolicy schema + enforcement
src/codrag/services/remote_sync.py      — Add SSRF + secrets permission checks
src/codrag/cli.py                       — Add secret deprecation warnings
src/codrag/core/index.py                — Wire content_sanitizer into get_context
src/codrag/core/layered_index.py        — Wire content_sanitizer into get_context
src/codrag/api/routers/mcp/server.py    — Add audit logging + rate limiting
src/codrag/api/routers/settings.py      — Add 8 enterprise API endpoints
src/codrag/api/routers/llm.py           — Add Azure OpenAI + model allowlist
src/codrag/core/llm_client.py           — Add Azure OpenAI generation
src/codrag/core/batch_profiles.py       — Add Azure batch profile entries
packages/ui/src/types.ts                — Add AdminPolicy types
packages/ui/src/api/client.ts           — Add getAdminPolicy method
packages/ui/src/api/mock.ts             — Add getAdminPolicy mock
packages/ui/src/components/llm/EndpointManager.tsx  — Add admin policy integration
packages/ui/src/components/llm/AIModelsSettings.tsx — Add admin policy banner
packages/ui/src/index.ts                — Add AdminSection + useAdminPolicy exports
```

### Files that are FINE (no changes needed):
```
src/codrag/core/feature_gate.py         — ✅ EA-A6/A7/A8 intact
src/codrag/core/content_sanitizer.py    — ✅ All DLP functions intact
src/codrag/core/audit_log.py            — ✅ Full audit log module
src/codrag/core/security_health.py      — ✅ All 7 checks
src/codrag/core/cost_estimation.py      — ✅ Cost engine
src/codrag/core/budget_enforcement.py   — ✅ Budget enforcement
src/codrag/core/licensing.py            — ✅ Ed25519 verification
tests/test_content_sanitizer.py         — ✅ 73+ tests
tests/test_audit_log.py                 — ✅ 22+ tests
packages/ui/src/components/enterprise/EnterpriseAdminPanel.tsx — ✅ Full 4-tab panel
```
