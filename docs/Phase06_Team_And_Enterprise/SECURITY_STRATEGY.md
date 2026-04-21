# Prep Security Strategy — Grounded in Our Architecture
*Created: March 9, 2026*

---

## Who We Are

Prep is a **local-first desktop application** that indexes source code and builds a semantic understanding graph. It runs on the developer's machine. It does not host data in the cloud. The developer's source code never leaves their machine unless they explicitly configure a cloud LLM provider.

Our ethos: **Give developers AI-powered code understanding while keeping their code under their control.**

This is fundamentally different from cloud AI tools (Copilot, Cursor, ChatGPT) where code goes to a third-party server by default. Prep's default is local — Ollama on localhost. Cloud is opt-in BYOK.

---

## The Actual Data Flow (Where Source Code Goes)

```
Developer's Source Code
    │
    ▼
[1] Rust Parser (prep-engine)
    │   Parses AST, extracts symbols, builds trace graph
    │   ► LOCAL ONLY — never leaves the machine
    │
    ▼
[2] Embedder (ONNX nomic-embed-text)
    │   Generates vector embeddings for search
    │   ► LOCAL ONLY — runs on CPU, no network calls
    │
    ▼
[3] Pipeline Enrichment (8 LLM stages)          ← THIS IS WHERE DATA LEAVES
    │   augmenter.py        — sends file content + symbols to LLM
    │   inferred_edges.py   — sends file pairs to LLM
    │   epistemic.py        — sends file content to LLM
    │   group_reasoning.py  — sends file groups to LLM
    │   cluster.py          — sends module summaries to LLM
    │   atlas/generator.py  — sends codebase overview to LLM
    │   deep_analysis.py    — sends files to LLM
    │   deepening.py        — sends files to LLM
    │
    │   IF provider = ollama/lm-studio → LOCAL ONLY (localhost)
    │   IF provider = openai/anthropic/google/azure → LEAVES MACHINE via HTTPS
    │
    ▼
[4] MCP Context Assembly (index.py, layered_index.py)
    │   Assembles search results into context for AI assistants
    │   ► content_sanitizer.py runs HERE (output path)
    │   ► Data goes to the AI coding assistant (Windsurf, Cursor, etc.)
    │
    ▼
[5] AI Coding Assistant receives context
    │   ► Out of our control from here
```

### The Critical Gap

**The content sanitizer is wired into step [4] (output) but NOT step [3] (input to LLMs).**

This means:
- When Prep sends source code to a cloud LLM during pipeline enrichment, there is:
  - ❌ No invisible Unicode stripping on the source code
  - ❌ No secret redaction (API keys, passwords in source files)
  - ❌ No DLP file-level blocking enforcement
  - ❌ No prompt injection detection on input content
- When Prep returns context to MCP clients, there IS:
  - ✅ Code fence sanitization
  - ✅ Invisible Unicode stripping (via `sanitize_output`)

**The protection is backwards.** We protect the output (going to Windsurf/Cursor) but not the input (going to OpenAI/Google). The input path is where secrets actually leak to third parties.

---

## What Matters vs What Doesn't (For Prep Specifically)

### What Actually Matters (High Impact)

| Risk | Why It Matters for Prep | Current State |
|------|--------------------------|---------------|
| **Secrets in source code sent to cloud LLMs** | A `.env` file or config with API keys gets sent to OpenAI during enrichment. OpenAI now has your AWS keys. | ❌ No protection on pipeline input path |
| **DLP enforcement on pipeline calls** | IT says "never send `.pem` files to cloud" but the pipeline sends them anyway during augmentation. | ❌ `check_dlp_before_llm_call()` exists but is never called by pipeline stages |
| **Invisible Unicode injection in repo files** | Attacker adds invisible instructions to a source file. During enrichment, the LLM reads the hidden instructions. | ❌ `sanitize_llm_input()` exists but is never called by pipeline stages |
| **IT policy enforcement** | Admin locks providers to Google-only, but pipeline stages bypass the check because they get LLM clients directly from config. | ⚠️ Partial — EndpointManager UI filters, but backend pipeline doesn't re-check |
| **Audit trail: what went where** | IT needs to know: "did any source code go to an unapproved provider?" | ⚠️ Audit log exists but pipeline stages don't record LLM calls |

### What Doesn't Matter Much (For a Local Desktop App)

| Risk | Why It's Lower Priority for Prep |
|------|-----------------------------------|
| **Prompt injection in MCP output** | MCP tools are read-only. The downstream AI assistant decides what to do with our context. We can't control that. Our `<!-- DATA NOT INSTRUCTIONS -->` boundary is reasonable. |
| **ML-based PII detection (Presidio)** | Requires 200MB+ spaCy model. Too heavy for a desktop app. Regex patterns catch 90% of secrets. The 10% we miss are unlikely to be in source code (SSNs, health records aren't typically in repos). |
| **Prompt injection classifier (LLM Guard)** | Requires 500MB+ transformer model. Overkill for our use case. We're not a chatbot — we're a pipeline that processes source code. |
| **SSRF via LLM proxy** | Already fixed. `is_safe_url()` blocks private IPs and metadata endpoints. |
| **Rate limiting on local daemon** | Already built (MCP 120/60s). Local daemon attack surface is minimal. |

---

## The Best Path Forward

### Principle: Protect the Pipeline Input Path

The single highest-impact security improvement is wiring `content_sanitizer.py` into the **pipeline stages** that send source code to LLMs. This is:
- Zero new dependencies
- Uses code we already wrote
- Addresses the actual threat (secrets leaking to cloud providers)
- Addresses the OWASP LLM01 and LLM02 risks that matter for our architecture

### Principle: Lightweight Built-In Defaults

Rather than adding heavy ML dependencies, enhance our regex patterns with well-known secret patterns from the open source community (LLM Guard, Presidio, GitGuardian). These are just regex strings — zero dependency overhead.

### Principle: IT Visibility, Not IT Complexity

The security health dashboard should tell IT admins:
1. **What's happening** — files indexed, tokens sent to which providers, secrets detected
2. **What's configured** — DLP rules, provider locks, enforcement mode
3. **What's wrong** — failing checks, policy violations, rate limit hits

Not: complex ML classifiers, YARA rules, or enterprise-grade SIEM integrations. Those come later (if ever) as optional pip extras for Enterprise tier.

### Principle: Local-First = Secure by Default

Prep with Ollama on localhost sends **zero data** off the machine. That's the most secure configuration and it's the default. Cloud is opt-in. This is our strongest security story and we should lean into it.

---

## Concrete Build Plan (Priority Order)

### Phase 1: Wire Sanitizer into Pipeline Input Path (CRITICAL)
**Impact: Fixes the actual security gap**

1. Create a `sanitize_before_llm()` helper in `content_sanitizer.py` that:
   - Strips invisible Unicode (`sanitize_llm_input`)
   - Applies `redact_patterns` to content (`redact_secrets_in_content`)
   - Runs DLP file-level check (`check_dlp_before_llm_call`)
   - Applies Unicode NFKC normalization (Finding F)
   - Returns cleaned content + DLP decision

2. Wire it into `llm_client.py` `generate()` — the single chokepoint where ALL LLM calls go through. This means every pipeline stage gets protection automatically without modifying 8 separate files.

3. Add default `redact_patterns` for common secrets:
   - AWS: `AKIA[0-9A-Z]{16}`
   - GitHub: `gh[ps]_[A-Za-z0-9_]{36,}`
   - Slack: `xox[bporas]-[0-9]{1,}-[0-9A-Za-z-]{10,}`
   - Generic: `(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['"][^\s'"]{8,}['"]`
   - JWT: `eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+`
   - Private keys: `-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----`

### Phase 2: Complete Security Health Checks (11→16)
**Impact: IT visibility**

You already added checks 8-10. Remaining:
- Check 11: Content sanitization active
- Check 12: API key hygiene (Google URL-param warning)
- Check 13: MCP rate limit health
- Check 14: Secret detection coverage (are default patterns configured?)
- Check 15: Data exposure summary (blast radius for IT)
- Check 16: Invisible Unicode in indexed files

### Phase 3: Audit Trail for Pipeline LLM Calls
**Impact: IT compliance**

- Record every LLM call in the audit log: provider, model, tokens, file paths
- Surface in Usage tab: "This month: 142K tokens to Google, 0 to OpenAI, 890K to Ollama"
- IT can answer: "Has any source code left the network?"

### Phase 4: Canary Tokens (Innovative)
**Impact: Exfiltration detection**

Your Finding G is genuinely novel for our use case:
- Inject a synthetic secret (e.g., `PREP_CANARY_4f8a9b2c`) into context assembly
- If the LLM or downstream system tries to use/return that token → alert
- Simple to implement, zero dependencies, catches real attacks

---

## What We're NOT Building (And Why)

| Feature | Why Not |
|---------|---------|
| ML-based PII detection (Presidio) | 200MB+ dependency, overkill for source code, regex catches the real risks |
| Prompt injection classifier (LLM Guard) | 500MB+ transformer, we're a pipeline not a chatbot |
| YARA rules (Vigil-LLM) | Complex to maintain, heavy for desktop distribution |
| External security service integration | Violates local-first ethos, adds network dependency |
| SIEM/syslog forwarder | Enterprise tier future — not core product |

We may offer some of these as optional pip extras (`pip install prep[enterprise-security]`) for customers who specifically ask, but they will never be in the core product.

---

## Marketing Position

"Prep is secure by design. Your code stays on your machine by default. When you choose to use a cloud model, Prep automatically strips secrets, blocks sensitive files, and gives your IT team full visibility into what goes where."

This is stronger than any competitor because:
- **Copilot/Cursor**: Code goes to cloud by default, no DLP, no IT controls
- **Codeium/Tabnine**: Cloud-first with on-prem as premium add-on
- **Prep**: Local-first with cloud as opt-in, DLP built-in, IT controls built-in
