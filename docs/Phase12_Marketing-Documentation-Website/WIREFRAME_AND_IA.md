# Wireframe and Information Architecture (IA)

## Purpose
This document turns Phase 10/11 research into a concrete v0 website + docs wireframe that supports:
- A0-J1 (Evaluate Prep and decide to try it)
- A0-J2 (Download, upgrade, and recover)

Reference journeys and boundaries:
- `../WORKFLOW_RESEARCH.md`

## Design constraints
- The site must not imply cloud requirements.
- The site must not oversell enterprise features as MVP.
- The site must communicate the “trust invariants” (right project, fresh, verifiable) and bounded outputs.
- The site must be honest about platform constraints (macOS/Windows signing, app stores, sidecar).

## Primary CTA model (v0)
The site should have 2 primary paths:
- **Read docs** (for careful evaluators, security-conscious users)
- **Download** (once installers exist; until then, a waitlist/updates CTA)

Secondary CTAs:
- “How it works”
- “Security & Privacy”
- “Using Prep with Cursor/Windsurf via MCP”

## Website IA (v0 placeholder)

### `/` Home
Wireframe sections:
- Hero
  - One-sentence value prop
  - Subhead: local-first posture + IDE companion framing
  - CTAs:
    - Primary: “Read docs”
    - Secondary: “Get updates” or “Download” (depending on readiness)
- Social proof placeholder (not logos):
  - “Built for Cursor/Windsurf/Copilot workflows”
  - “Local-first by default”
- The loop (3–5 steps):
  - Add repo → Build → Search → Context (→ Trace, optional)
- What stays local
  - bullets: indexes, config, query history (if applicable)
  - explicit “no mandatory cloud”
- Integrations
  - MCP mention + link to docs
- Deployment reality (short)
  - macOS/Windows/linux desktop app
  - note about signed installers
- Footer
  - Links: Docs, Download, Security, Contact

### `/download`
States:
- v0 (pre-release):
  - “Not yet available” + link to GitHub releases (when available) + get updates.
- v1 (release):
  - macOS download button
  - Windows download button
  - checksums
  - “verify signature” guidance

Must support A0-J2:
- clear upgrade story (where to get new versions)
- recovery expectations (projects persist; rebuild if index format changes)

### `/pricing`
v0 launch:
- **Free Tier:** 2 projects, $0.
- **Pro License:** Unlimited, Trace Index.
  - **Founder's Edition:** $49 (Limited).
  - Standard: $79.
- **Team:** $12/seat/mo.
- **Enterprise:** Custom (Air-gapped).
- Message: "One-time payment for individuals. No token markup."

### `/security`
Sections:
- Local-first posture (what is on disk)
- Network behavior (binds to loopback by default)
- What we do/don’t collect
- Enterprise posture (roadmap): SSO/SCIM/audit are future

### `/contact`
- email
- GitHub
- optionally: “Enterprise interest” form (but do not imply enterprise availability)

## Website IA (v1 expanded)
- `/changelog`
- `/blog`
- `/workflows/*` (case studies)
- `/enterprise` (roadmap + posture + “talk to us”)

## Support IA (v0)
Hosted at `runprep.io/contact` (formerly `support.runprep.io`).

Primary entry options:
- Community Support (GitHub Discussions)
- Private Inquiries (Email support@runprep.io)
- Self-service links (Docs, Pricing, Privacy)

## Payments IA (v0)
Hosted at `payments.runprep.io`.

V0 payments surfaces:
- Purchase / checkout entry (redirect to hosted checkout)
- Success page (receipt + next steps)
- License recovery (resend key / receipt lookup)

## Docs IA (v0 scaffold)
Hosted at `docs.runprep.io`.

### Getting Started
- What is Prep?
- Installation
  - macOS
  - Windows
- Quickstart
  - Add project
  - Build index
  - Search
  - Generate context

### Concepts
- Local-first model
- Projects, indexes, and modes
  - standalone vs embedded
- Search vs Context vs Trace
- Bounded outputs and trust invariants

### Guides
- Indexing a repo (include/exclude)
- Using Prep with Cursor/Windsurf via MCP (Phase05 scaffold)
- “Why is it wrong?” (debugging stale/wrong results)

### Reference
- CLI reference (align with repo README)
- HTTP API reference (`../API.md`)

### Troubleshooting
- Ollama not running
- Build failures
- Performance tips

## Doc-to-site cross-links
- Home → “Local-first model” doc
- Home → “Quickstart” doc
- Download → Installation docs
- Security page → “Local-first model” doc + network mode boundary

## Research sources (inputs)
- Phase 10 market positioning:
  - `../Phase10_Business_And_Competitive_Research/COMPETITOR_LANDSCAPE.md`
  - `../Phase10_Business_And_Competitive_Research/BUSINESS_MODELS_AND_PRICING.md`
  - `../Phase10_Business_And_Competitive_Research/LOCAL_FIRST_ENTERPRISE_ECOSYSTEM.md`
- Phase 11 deployment constraints:
  - `../Phase11_Deployment/README.md`
  - `../Phase11_Deployment/MACOS_DISTRIBUTION.md`
  - `../Phase11_Deployment/WINDOWS_DISTRIBUTION.md`
