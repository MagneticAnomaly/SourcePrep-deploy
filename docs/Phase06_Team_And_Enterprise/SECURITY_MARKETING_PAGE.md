# Security Marketing Page — Content Draft

*Status: Draft for codrag.io/security*
*Created: Mar 9, 2026*
*Ref: ENTERPRISE_ADMIN_DESIGN.md §17, existing security page at `websites/apps/marketing/src/app/security/page.tsx`*

---

## Purpose

The existing `/security` page covers Local-First Architecture, Telemetry, Network, Embedding, Licensing, Bug Reports, and Privacy. It's well-designed but needs updates to cover:

1. **LLM-specific security** — how we protect code sent to LLMs
2. **Supply chain security** — tools we use in CI/CD
3. **OWASP alignment** — standards compliance
4. **Enterprise security features** — what Team/Enterprise tiers add
5. **Homepage security card** — a single card on the main marketing page

## What to Disclose Publicly vs. Keep Internal

| Disclose (builds trust) | Keep internal |
|---|---|
| Security philosophy (local-first, no phone-home) | Specific vulnerability details until patched |
| Tool names (Trivy, Gitleaks, LLM Guard) | Ed25519 key infrastructure details |
| OWASP alignment | Specific regex patterns for secret detection |
| Data flow diagrams | Internal architecture attack surface details |
| Vulnerability reporting process | Security audit findings in detail |
| Encryption standards (Ed25519, TLS 1.2+) | Exact file paths of security-sensitive code |

**Disclosing tools is NOT a security flaw.** It's standard practice. GitLab publishes their entire security toolchain. Cloudflare publishes their DDoS architecture. 1Password publishes their crypto whitepaper. Transparency builds trust. Obscurity doesn't provide security.

---

## New Sections to Add to /security Page

### Section: LLM Security (insert after "Flexible Embedding")

**Sidebar nav label:** `LLM Security`

**Content:**

```
Section 04A. LLM Security

"CoDRAG sends code to LLMs for semantic enrichment. Here's how we 
protect your source code during that process."

┌─────────────────────────────────────────────────────────┐
│  DATA FLOW — What Happens When CoDRAG Talks to an LLM  │
│                                                         │
│  Your Code  ──→  [Input Sanitization]  ──→  LLM API    │
│                   • Strip invisible Unicode             │
│                   • Detect prompt injection patterns     │
│                   • Exclude sensitive files (.env, keys) │
│                   • Redact inline secrets                │
│                                                         │
│  LLM Response ──→ [Output Validation]  ──→  Index      │
│                   • Detect anomalous patterns            │
│                   • Reject unexpected instructions       │
│                   • Sanitize before storage              │
└─────────────────────────────────────────────────────────┘

Assertion: CoDRAG aligns with the OWASP Top 10 for LLM Applications 
(2025). We specifically mitigate:

  LLM01 Prompt Injection    — Input sanitization + output validation
  LLM02 Sensitive Disclosure — File exclusion + secret redaction
  LLM08 Vector Weaknesses   — Index integrity verification + isolation
  LLM10 Unbounded Consumption — Token budget controls (Team+)

LLM processing is always YOUR choice:
  • Local models (Ollama, LM Studio) — code never leaves your machine
  • Cloud APIs — you provide your own keys (BYOK), we never proxy
  • No LLM at all — structural graph works without any LLM

Tools we use:
  • LLM Guard by ProtectAI — input/output scanning for PII and 
    prompt injection
  • Content hash verification — detect tampered indexes
```

### Section: Supply Chain Security (update existing "Releases" section)

**Sidebar nav label:** `Supply Chain`

**Content:**

```
Section 06. Supply Chain Security (updated)

All installers are code-signed and include SHA-256 checksums.

Our CI/CD pipeline runs automated security scanning on every build:

┌──────────────┬────────────────────────────────────────┐
│ Tool         │ What It Checks                         │
├──────────────┼────────────────────────────────────────┤
│ Trivy        │ CVEs in Docker images, Python & Node   │
│              │ dependencies, container misconfigs      │
│ Gitleaks     │ Secrets accidentally committed to code  │
│ Code Signing │ macOS notarization, Windows EV cert     │
│ SBOM         │ Software Bill of Materials for audit    │
└──────────────┴────────────────────────────────────────┘

Docker images for Team Sync (codrag-headless) are:
  • Built in CI with reproducible builds
  • Scanned for vulnerabilities before publish
  • Signed with Sigstore/Cosign (Enterprise)
  • Available with SHA-256 checksums
```

### Section: Enterprise Security (new, after Supply Chain)

**Sidebar nav label:** `Enterprise`

**Content:**

```
Section 06A. Enterprise Security

For teams and enterprises, CoDRAG adds IT-managed security controls:

TEAM TIER:
  ✓ Provider allowlists — IT controls which LLM providers are available
  ✓ Locked endpoints — pre-configured, tamper-proof API connections
  ✓ Model restrictions — allowlist/blocklist by model name
  ✓ DLP file exclusion — prevent sensitive files from reaching LLMs
  ✓ S3 endpoint allowlist — trusted sync destinations only
  ✓ Enforcement modes — "suggest" (advisory) or "enforce" (mandatory)

ENTERPRISE TIER:
  ✓ Security Health Dashboard — aggregate security posture score
  ✓ Security Event Log — filterable audit trail
  ✓ Seat management — machine tracking, revocation
  ✓ Budget controls — token and cost limits per user/project
  ✓ Compliance export — PDF/JSON security reports
  ✓ Admin actions — quarantine projects, block endpoints
  ✓ MDM/GPO support — IT-pushed configuration
  ✓ Corporate proxy + custom CA certificates
  ✓ SSO/SAML integration (roadmap)

All admin-level controls are visually distinguished with an orange 
accent border in the dashboard, so users always know which settings 
are organization-managed.
```

---

## Homepage Security Card

A single card in the features section of the main marketing page (`/`).

**Card content:**

```
🔒 Security-First Architecture

Your code stays on your machine. CoDRAG runs locally with 
zero telemetry, offline licensing, and no cloud dependencies.

When you choose to use cloud LLMs, we protect your code with 
input sanitization, secret redaction, and OWASP-aligned guardrails.

Enterprise teams get IT-managed provider controls, DLP policies, 
and a security health dashboard.

[Learn more → /security]
```

**Visual:** Shield icon with a subtle gradient. Keep it clean — one card among the feature grid, not overly prominent but clearly present.

---

## Implementation Notes

### Changes to existing security page (`security/page.tsx`):

1. **Add to sidebar nav:** `LLM Security`, `Supply Chain` (rename from Releases), `Enterprise`
2. **Insert Section 04A** (LLM Security) between "Flexible Embedding" and "Offline Verification"
3. **Update Section 06** (Supply Chain) with Trivy/Gitleaks/SBOM table
4. **Insert Section 06A** (Enterprise Security) after Supply Chain
5. **Update `LAST_AUDIT` date** from 2026-02-01 to current

### Changes to homepage (`page.tsx`):

1. **Add security card** to the feature grid (wherever features are displayed)
2. Card links to `/security`

### What NOT to change:

- The existing privacy policy sections (08-10) are accurate, keep them
- The bug report section (07) is excellent, keep it
- The vulnerability reporting callout is good, keep it
- Don't add specific CVE numbers or audit finding IDs to the public page

---

## Tone Guide

The existing security page has a great "terminal/systems" aesthetic (monospace labels, numbered sections, code-block styling). New sections should match this tone:

- **Confident, not defensive.** "Here's how we protect you" not "we're sorry about security risks."
- **Specific, not vague.** Name the tools (Trivy, LLM Guard). Show the data flow. List the OWASP numbers.
- **Transparent, not exhaustive.** Show enough to build trust. Don't publish your full threat model.
- **Respectful of developers.** These are technical people. Don't condescend. Show architecture.
