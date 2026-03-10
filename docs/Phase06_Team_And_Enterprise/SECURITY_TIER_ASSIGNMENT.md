# Security Feature Tier Assignment
*Created: March 9, 2026*

## Guiding Principles

1. **If it protects the individual developer's machine/data silently → Core (all tiers)**
2. **If it requires admin/IT configuration → Team/Enterprise**
3. **If it could degrade pipeline quality → Only when explicitly configured (admin policy)**
4. **If it's organizational visibility/compliance → Enterprise**

---

## CORE — All Tiers (Free, Pro, Team, Enterprise)

These run automatically, require no configuration, and never degrade quality.

| Feature | What It Does | Why Core |
|---------|-------------|----------|
| **Code fence sanitization** | Escapes ``` breakouts in MCP output | Prevents prompt injection for ALL users using MCP. Zero quality impact. |
| **Invisible Unicode stripping** | Removes zero-width chars from LLM input | Prevents "Rules File Backdoor" attack. Zero quality impact on real code. |
| **LLM output validation** | Logs suspicious patterns (observation-only) | Free security telemetry. Doesn't modify output. |
| **SSRF protection** | `is_safe_url()` blocks metadata endpoints, private IPs | Protects every user from malicious endpoint URLs. |
| **CORS restriction** | Localhost-only CORS by default | Protects every user's daemon from browser-based attacks. |
| **Git clone `--` separator** | Prevents flag injection in git clone | Protects headless runner users. |
| **Zip bomb protection** | 10GB limit on S3 index extraction | Protects team sync users from DoS. |
| **S3 prefix path traversal block** | Rejects `../` in S3 prefixes | Protects team sync users. |
| **Content hash verification** | Verifies downloaded index integrity | Protects team sync users. |
| **Polling interval minimum** | 5-minute floor on sync polling | Prevents accidental S3 bill bombs. |
| **Cloud rate limit detection** | `CloudRateLimitError` pauses pipeline on 429 | Protects BYOK users from runaway costs. |
| **MCP rate limiting** | 120 calls/60s | Protects every MCP user from runaway agents. |
| **OutputMonitor** | Detects repetition loops in LLM output, aborts | Saves tokens/money for all users. |
| **Unicode NFKC normalization** | Normalizes homoglyphs before LLM input | Prevents character substitution attacks (EchoLeak-style). |

**Total: 14 features. Zero configuration needed. Zero quality impact.**

---

## TEAM — Team Tier and Above

These are organizational features that require team_config.json and benefit multi-developer teams.

| Feature | What It Does | Why Team |
|---------|-------------|----------|
| **Admin policy schema** | `team_config.json` → provider/model/data policies | Only relevant for organizations managing multiple developers. |
| **Enforcement modes** | `suggest` vs `enforce` | Only meaningful when IT sets policy for a team. |
| **Provider allowlist/blocklist** | Hide providers from user dropdown | IT controlling which LLM providers devs can use. |
| **Model allowlist/blocklist** | Filter model dropdown | IT controlling which models devs can select. |
| **Locked endpoints** | IT-configured endpoints users can't edit | Pre-provisioned cloud endpoints with managed keys. |
| **`allow_user_endpoints` gate** | IT can prevent users from adding endpoints | Strict lockdown scenario. |
| **S3 endpoint allowlist** | `allowed_s3_endpoints` in team_config | Prevents S3 SSRF via malicious PRs (CRIT-2). |
| **Secrets file permission check** | Warns if `.secrets` isn't 0600 | Relevant for shared machines in team environments. |
| **Config drift detection** | Invisible Unicode in team_config.json | Protects the shared config file from injection. |
| **Team Sync** | S3-based index sharing | The core team feature. |
| **Security health checks 1-10** | IT-visible health dashboard | IT needs visibility into team security posture. |

**Total: 11 features. Require team_config.json or admin role.**

---

## ENTERPRISE — Enterprise Tier Only

These are compliance, advanced DLP, and organizational governance features.

| Feature | What It Does | Why Enterprise |
|---------|-------------|---------------|
| **Secret redaction** (`redact_patterns`) | Regex-based secret stripping from LLM input | **Quality impact** — removes content. Only appropriate when IT explicitly configures patterns. |
| **DLP file blocking** (`never_send_globs`) | Blocks files from ALL LLM calls | **Quality impact** — skips files. Only appropriate when IT defines sensitive file patterns. |
| **DLP provider blocking** (`block_unapproved_cloud`) | Blocks cloud providers not in approved list | **Quality impact** — may prevent enrichment entirely if only approved provider is down. |
| **Audit log** | Append-only SQLite event tracking | Compliance requirement for enterprise customers. |
| **Audit log export** (JSON/CSV) | SIEM integration | Enterprise compliance teams need this. |
| **Security report export** | Comprehensive security posture document | Enterprise procurement/compliance. |
| **Admin actions** (quarantine, block) | IT can quarantine projects, block endpoints | Organizational incident response. |
| **Budget enforcement** | Monthly token/cost limits | Organizational cost control. |
| **Seat management** | Track/manage license seats | Only relevant with per-seat licensing. |
| **Data exposure summary** | "Blast radius" — files indexed, tokens sent where | Enterprise risk assessment. |
| **Canary tokens** | Synthetic secrets in context to detect exfiltration | Advanced enterprise security feature. |
| **Secret detection coverage check** | Are redact_patterns configured? How many secrets found? | Only relevant when DLP is configured. |

**Total: 12 features. Require enterprise license + explicit admin configuration.**

---

## The Boundary Decision: Where to Wire Sanitizer in llm_client.py

Based on this analysis, here's exactly what should happen in `llm_client.py generate()`:

```python
def generate(self, prompt, ...):
    # CORE (always, all tiers):
    prompt = strip_invisible_unicode(prompt)        # Zero quality impact
    prompt = normalize_nfkc(prompt)                 # Zero quality impact
    if system:
        system = strip_invisible_unicode(system)
        system = normalize_nfkc(system)
    
    # TEAM/ENTERPRISE (only when admin_policy exists):
    if admin_policy:
        # Check DLP file blocking — Enterprise only
        if admin_policy.data.never_send_globs:
            allowed, reason = check_dlp_before_llm_call(...)
            if not allowed:
                return "", 0  # Skip this call
        
        # Redact secrets — Enterprise only
        if admin_policy.data.redact_patterns:
            prompt = redact_secrets_in_content(prompt, admin_policy.data.redact_patterns)
    
    # ... actual LLM call ...
    
    # CORE (always, all tiers):
    response, warnings = validate_llm_output(response)  # Observation only
    
    return response, tokens
```

The key: **core protections are invisible and always-on. Enterprise protections are admin-configured and quality-impacting by design (that's the tradeoff IT makes when they enable DLP).**

---

## Summary Table

| Tier | Features | Config Needed | Quality Impact |
|------|----------|--------------|----------------|
| **Core** | 14 transparent protections | None | Zero |
| **Team** | 11 policy/visibility features | `team_config.json` | None (policy is UI-level only) |
| **Enterprise** | 12 DLP/compliance features | Admin policy + enterprise license | **Possible** (intentional tradeoff by IT) |
