# Security Audit → IT Panel Features Plan
*Created: March 9, 2026*
*Cross-references: SECURITY_AUDIT.md, ENTERPRISE_ADMIN_DESIGN.md, security_health.py*

---

## 1. Current Security Health Checks (Built in `security_health.py`)

These 7 checks already run and surface in the Security tab of the Enterprise Admin panel:

| # | Check | What It Detects | Source |
|---|-------|----------------|--------|
| 1 | License Verification | Invalid/expired/unsigned license | CRIT-1 |
| 2 | S3 Endpoint Security | Non-HTTPS, SSRF targets | CRIT-2 |
| 3 | Secrets & Credentials | .secrets file permission too open (not 0600) | HIGH-2 |
| 4 | Index Integrity | Missing content_hash, embedding_hash in manifest | MED-3 |
| 5 | DLP Compliance | Data policy config presence | EA-F |
| 6 | Config Drift | Invisible Unicode in team_config.json | MED-4 variant |
| 7 | Network Security | Proxy config, CA bundle | General |

---

## 2. NEW Security Checks to Add (From Security Audit)

These are security audit findings that **should become IT-visible health checks** but are NOT currently surfaced:

### Check 8: Daemon Authentication Posture
**Source:** FULL-4 (rate limiting), general security
**What IT cares about:** Is the CoDRAG daemon exposed to unauthenticated access?
**Check logic:**
- Is `CODRAG_DAEMON_TOKEN` set? → PASS
- Not set + binding to localhost only? → WARN ("No auth, but localhost only")
- Not set + binding to 0.0.0.0? → FAIL ("Daemon exposed without auth!")
**Why:** If an enterprise deploys CoDRAG on a shared server or the daemon binds to a non-loopback address, unauthenticated access = data leakage.

### Check 9: CORS Configuration
**Source:** FULL-1
**What IT cares about:** Can any website make requests to the CoDRAG daemon?
**Check logic:**
- CORS restricted to localhost/tauri → PASS
- `CODRAG_CORS_ALLOW_ALL=1` set → FAIL ("CORS wide open — any website can access CoDRAG")
**Why:** A malicious website visited by a developer could exfiltrate project data via CORS if unrestricted.

### Check 10: Dev Mode Detection
**Source:** CRIT-1 (CODRAG_DEV_MODE bypass)
**What IT cares about:** Is someone running with security overrides?
**Check logic:**
- `CODRAG_DEV_MODE=1` not set → PASS
- `CODRAG_DEV_MODE=1` is set → WARN ("Dev mode active — tier override enabled, reduced security")
- `CODRAG_TIER` override active → FAIL ("License tier being overridden via environment variable")
**Why:** Dev mode disables license verification. IT needs to know if anyone on the team is running with overrides.

### Check 11: Content Sanitization Active
**Source:** MED-4 (context injection)
**What IT cares about:** Is CoDRAG protecting LLM output from injection attacks?
**Check logic:**
- `sanitize_output()` import succeeds and is callable → PASS
- Import fails or content_sanitizer.py missing → WARN ("Content sanitization not available")
**Why:** Without sanitization, malicious repo content could inject instructions into LLM context windows.

### Check 12: API Key Hygiene
**Source:** FULL-3 (Google key in URL params)
**What IT cares about:** Are API keys being exposed in transit?
**Check logic:**
- Scan configured endpoints for providers that use URL-param auth (Google Gemini) → WARN with guidance
- All endpoints use header-based auth (OpenAI, Anthropic, Azure) → PASS
**Why:** URL-parameter API keys appear in HTTP logs, proxy logs, CDN logs. Enterprise security teams audit this.

### Check 13: MCP Rate Limit Health
**Source:** FULL-4 + EA-B12
**What IT cares about:** Is rate limiting protecting the daemon from abuse?
**Check logic:**
- MCP rate limiting is active → PASS (show current rate)
- Rate limit has been hit recently → WARN ("Rate limit triggered — possible abuse or runaway automation")
**Why:** If the MCP rate limit is being hit, it could indicate a misconfigured agent loop or abuse.

---

## 3. IT Security Panel Layout

### Option A: Expand Existing Security Tab (Recommended)

Keep the Security tab in the Enterprise Admin panel but expand it with the new checks (8-13). Group into categories:

```
Security & Compliance Tab:
├── Security Health Score: 11/13 checks passing
│
├── 🟢 Infrastructure Security
│   ├── ✅ Daemon Authentication (token set)
│   ├── ✅ CORS Restricted (localhost only)
│   └── ✅ Network Security (HTTPS proxy)
│
├── 🟡 License & Compliance
│   ├── ✅ License Verified (Ed25519 signature)
│   ├── ⚠️ Dev Mode Active (CODRAG_DEV_MODE=1)
│   └── ✅ DLP Policy Configured
│
├── 🟢 Data Protection
│   ├── ✅ Content Sanitization Active
│   ├── ✅ S3 Endpoint (HTTPS)
│   ├── ✅ Index Integrity (hash verified)
│   └── ⚠️ API Key Exposure (Google uses URL params)
│
├── 🟢 Runtime Protection
│   ├── ✅ MCP Rate Limiting (120/60s)
│   ├── ✅ Secrets File Permissions (0600)
│   └── ✅ Config Drift (no injection detected)
│
├── Recent Security Events (from audit_log)
│   ├── 2026-03-09 14:32 — MCP tool call: codrag_search
│   ├── 2026-03-09 14:30 — Admin policy changed by admin
│   └── ... (last 20 events)
│
└── [Export Security Report] [Export Audit Log]
```

### Option B: Separate Security Panel

Register a new `security-dashboard` panel in panelRegistry. This dedicates more screen space but fragments the admin experience.

**Recommendation: Option A** — keep it in the existing Security tab but expand the check count from 7 to 13 and group into categories.

---

## 4. Security Features for Non-Admin Users

Some security information should be visible to ALL users, not just admins:

| Feature | Where to Show | What User Sees |
|---------|--------------|---------------|
| **License status** | Settings → License tab | Tier, expiry, signature status |
| **Dev mode warning** | Settings → Developer tab | Yellow banner when active |
| **Content sanitization** | N/A (invisible to users) | Just works in the background |
| **CORS warning** | Settings → Developer tab (advanced) | Warning if CORS_ALLOW_ALL=1 |
| **API key exposure** | Endpoint Manager | Info tooltip: "Google uses URL-param auth (visible in logs)" |

---

## 5. Mapping: Security Audit → Implementation Tasks

| Audit ID | Finding | Current Status | IT Panel Action | Priority |
|----------|---------|---------------|-----------------|----------|
| CRIT-1 | License no crypto | ✅ Ed25519 built | Check 1 (exists) | Done |
| CRIT-2 | S3 SSRF | ✅ SSRF prevention built | Check 2 (exists) | Done |
| HIGH-1 | Git clone URL injection | ✅ Fixed (-- separator) | No panel action | Done |
| HIGH-2 | Secrets permissions | ✅ Check built | Check 3 (exists) | Done |
| HIGH-3 | API key in logs | ✅ Dead code removed | No panel action | Done |
| HIGH-4 | S3 prefix traversal | ✅ Fixed | No panel action | Done |
| HIGH-5 | Zip bomb | ✅ Fixed (10GB limit) | No panel action | Done |
| MED-1 | Polling interval | ✅ Fixed (5-min minimum) | No panel action | Done |
| MED-2 | GH Actions logs model | Unfixed | Docs recommendation | Low |
| MED-3 | Index hash verification | ✅ Fixed + Check 4 | Check 4 (exists) | Done |
| MED-4 | Context injection | ✅ Sanitizer built | **NEW Check 11** | Medium |
| FULL-1 | CORS wildcard | ✅ Fixed | **NEW Check 9** | High |
| FULL-2 | LLM proxy SSRF | ✅ Fixed | No panel action | Done |
| FULL-3 | Google key in URL | Can't fix (Google's API) | **NEW Check 12** | Medium |
| FULL-4 | No rate limiting | ✅ MCP rate limit built | **NEW Check 13** | Medium |
| — | Daemon auth | Exists (IPC token) | **NEW Check 8** | High |
| — | Dev mode detection | Exists (CODRAG_DEV_MODE) | **NEW Check 10** | High |

---

## 6. Implementation Order

```
Step 1: Add 6 new security health checks to security_health.py
  - Check 8: Daemon auth posture
  - Check 9: CORS configuration
  - Check 10: Dev mode detection
  - Check 11: Content sanitization active
  - Check 12: API key hygiene
  - Check 13: MCP rate limit health

Step 2: Update run_security_checks() total from 7 to 13

Step 3: Group checks into categories in the API response
  - infrastructure: [8, 9, 7]
  - license_compliance: [1, 10, 5]
  - data_protection: [11, 2, 4, 12]
  - runtime: [13, 3, 6]

Step 4: Update EnterpriseAdminPanel Security tab to show grouped checks

Step 5: Add API key exposure tooltip to EndpointManager for Google provider

Step 6: Test all 13 checks pass on a clean install
```
