# Acquisition and Partnerships

## Purpose
Prep’s stated ambition is to become an essential companion to Cursor/Windsurf/Copilot workflows and potentially be acquired by one of these companies.

This doc clarifies:
- what “acquisition-ready” means for Prep
- what partnership surfaces exist today (MCP, plugins, distribution)
- what product choices increase acquisition attractiveness without derailing MVP

## What acquisition targets tend to buy
Likely acquirers in this space want one or more of:
- differentiated technology (retrieval/trace/agent workflows)
- distribution and user adoption momentum
- strategic positioning (local-first, enterprise-friendly)
- integration surface that reduces friction to embed the product

## Prep positioning that is acquisition-friendly

### 1) “Context engine” vs “another IDE”
The most plausible positioning:
- Prep is not competing as a full IDE.
- Prep is a local-first context/index daemon that integrates into IDE assistants.

This matches the architectural decision:
- MCP as primary IDE integration
  - `docs/DECISIONS.md` (ADR-010)

### 2) Local-first + enterprise constraints as a moat
A large portion of enterprise demand is constrained by:
- privacy concerns
- network restrictions
- procurement and security requirements

Competitor signals show enterprise buyers expect:
- SSO/SCIM
- audit logs
- admin controls

Example (Cursor Enterprise lists audit logs + SCIM + granular admin/model controls):
- https://cursor.com/pricing

Prep’s “local-first by default” stance can become a durable differentiation if paired with:
- safe defaults
- clear data-handling guarantees

### 3) Hybrid index mode increases compatibility
Hybrid (standalone + embedded) lets Prep serve:
- solo devs (standalone, clean repos)
- teams (embedded, repeatable onboarding)

Reference:
- `docs/DECISIONS.md` (ADR-003)

### 4) Business Model as a Trust Asset
Prep's "Perpetual License" model builds deep trust with developers who are fatigued by subscriptions.
- This creates a loyal, high-intent user base.
- An acquirer could easily transition this base to a subscription or keep the license model as a "Pro" wedge.

## Partnership surfaces

### MCP
MCP is the primary partnership surface because:
- it is cross-vendor
- it works with Windsurf/Cursor (per project docs)

Reference:
- `docs/DECISIONS.md` (ADR-010)

Partnership-style outcomes:
- “Verified tool” in MCP directories
- shared workflows / examples
- co-marketing via docs and templates

### Optional: IDE-specific plugins (post-MVP)
- VS Code extension (wrap MCP or direct API)
- JetBrains plugin

Reference:
- ADR-010 “Future” notes.

## Strategic Valuation Scenarios

Acquisition value is driven by **Strategic Value** (Moat) rather than just revenue multiples.

### Year 1: The "Strategic Acqui-hire" / IP Buy ($5M–$15M)
- **Target:** Windsurf (Codeium) or Sourcegraph.
- **Driver:** Trace Index IP (local graph structure) + Talent.
- **Value:** Making their agent (Cascade/Cody) 30% more accurate than Cursor.

### Year 2: The "Workflow Standard" Exit ($30M–$70M)
- **Target:** Anthropic (Claude Code) or Atlassian.
- **Driver:** Becoming the standard "Local Context Layer" that solves enterprise security hurdles for cloud LLMs.
- **Value:** 15x-25x revenue multiple on ~$3M ARR.

### Year 3: The "Enterprise Gateway" Exit ($150M–$400M+)
- **Target:** Microsoft (GitHub), Google (Cloud/IDX), Apple.
- **Driver:** Infrastructure Category dominance. Prep as the "Security Layer" for AI in regulated industries.
- **Value:** Protecting the dominance of Copilot/Gemini in the enterprise.

## Valuation Multipliers

1.  **"Stickiness" (Usage Addiction):** Users who index 3+ repos and use the app 4+ hours/day.
2.  **Privacy/Security IP:** High-quality RAG on encrypted local indexes that *never* touch a server.
3.  **MCP Dominance:** Being the backend for 80% of "best" MCP-compatible tools.

## Emerging Tech Moats (To Watch & Build)

To maintain acquisition attractiveness, Prep must lead in "Plumbing":

1.  **Small Language Models (SLMs) for Local Re-ranking:** (e.g., Phi-4, Llama 3.2) Re-rank chunks locally to beat cloud RAG quality at zero cost.
2.  **GraphRAG (Structural Trace):** Moving beyond chunks to understanding relationships (Functions, Classes, Imports) across multi-repo setups.
3.  **Context Compression:** (e.g., LLMLingua) Pruning context to save tokens and improve agent focus.
4.  **LSP Deep Integration:** Using Tree-sitter/LSP for real-time semantic freshness (rename variable = instant update).
5.  **Multi-Modal Context:** Indexing architecture diagrams/PDFs to guide agent "High Level" understanding.

## What to optimize for (as a solo dev)

### 1) Integration simplicity
Acquirers value products that are easy to embed.

Concretely:
- stable HTTP API
- stable MCP tool schemas
- stable on-disk formats

### 2) A crisp, narrow wedge
Your wedge should be obvious:
- “Your local codebase context engine that works with your AI IDE.”

Avoid:
- becoming a general-purpose agent platform
- building a full IDE

### 3) Evidence of differentiation
You’ll likely need at least one “hard” differentiator beyond baseline vector search:
- Trace index (graph structure) integrated into retrieval

This is already in the technical landscape:
- `../Phase00_Initial-Concept/COMPETITORS_AND_CUTTING_EDGE.md`

## Risks
- Chasing partnerships too early can distract from shipping a high-quality core loop.
- Adding cloud prematurely can violate local-first trust and add operational burden.

## Suggested “acquisition readiness” milestones
- MVP ships with:
  - local-first daemon
  - dashboard
  - MCP integration
  - stable storage and project registry
- Post-MVP adds:
  - team onboarding (embedded mode) and a safe network mode baseline
  - enterprise governance features (SSO/SCIM/audit) only when justified

## Open questions
- Which vendor ecosystem is the best initial amplifier (Cursor vs Windsurf vs Copilot)?
- Do we aim for “works everywhere” via MCP first, or do one deep integration?
- What would a Cursor/Windsurf acquisition care about most: tech moat vs distribution?
