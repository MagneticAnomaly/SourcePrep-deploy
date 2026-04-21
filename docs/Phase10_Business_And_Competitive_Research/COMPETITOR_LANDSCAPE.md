# Competitor Landscape

## Purpose
This document captures a **business-focused** competitor landscape for Prep (pricing, packaging, distribution, enterprise posture). It is meant to complement the more **technical** landscape:
- `../Phase00_Initial-Concept/COMPETITORS_AND_CUTTING_EDGE.md`

## How to use
Use this document to inform:
- Packaging tiers (individual/team/enterprise)
- Pricing sanity checks
- Distribution (direct download vs app stores vs enterprise distribution)
- “Local-first” positioning and what customers will expect

## Market map (high-level)

> **Update Feb 2026**: A new wave of local-first context engines and agents (Vexp, Empirica, Serena, Grepai) has been analyzed in `COMPETITOR_LANDSCAPE_UPDATE_FEB2026.md`.

### AI IDEs / AI coding assistants (primary context)
- Cursor
- Windsurf
- GitHub Copilot
- Amazon Q Developer
- Google Gemini Code Assist
- Tabnine
- JetBrains AI

### Code search / code intelligence platforms
- Sourcegraph

### Local-first knowledge / memory companions (adjacent)
- Pieces for Developers
- Obsidian

### Developer tools with strong “individual → team → enterprise” licensing patterns (adjacent)
- Docker Desktop
- GitKraken (notably: on-prem license management options)

### “Agent platform” / workflow automation (adjacent)
- Continue

## Pricing snapshot (selected)
Pricing changes frequently; treat this as a **snapshot**.

| Product | Individual | Team | Enterprise | Notes / Source |
|---|---:|---:|---:|---|
| Cursor | Pro $20/mo | Teams $40/user/mo | Enterprise: custom | https://cursor.com/pricing |
| Windsurf | Pro $15/mo | Teams $30/user/mo | Enterprise: “Let’s talk” | https://windsurf.com/pricing |
| GitHub Copilot | Pro $10/mo | Business $19/user/mo | Enterprise $39/user/mo | https://github.com/features/copilot/plans + https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises |
| Amazon Q Developer | Pro $19/user/mo | N/A | N/A | https://aws.amazon.com/q/developer/pricing/ |
| Gemini Code Assist (Enterprise) | N/A | N/A | $45/user/mo (promo $19/user/mo on 1-year until Mar 31, 2025) | https://cloud.google.com/blog/products/application-development/introducing-gemini-code-assist-enterprise |
| Tabnine | Pro $12/user/mo (annual billing) | N/A | Enterprise $39/user/mo | https://www.tabnine.com/blog/key-takeaways-and-tabnine-faqs-from-nvidia-gtc/ |
| Pieces for Developers | Pro $18.99/mo (+ taxes) | N/A | N/A | https://pieces.app/features |
| Docker Desktop | Pro $9 | Team $15 | Business $24 | https://www.docker.com/pricing/ |
| Obsidian | App is free; Sync $5/user/mo (monthly) | N/A | N/A | https://obsidian.md/pricing |
| Sourcegraph (Code Search) | N/A | N/A | $49/user/monthy (as shown) | https://sourcegraph.com/pricing |
| Continue | Plans listed without public prices | N/A | “Company” tier | https://www.continue.dev/pricing |

## Competitor notes (what to copy vs what to avoid)

### Cursor
What they sell:
- AI-first IDE + agents + fast workflows.

Pricing/packaging signals:
- Individual tiers span from free to high-end ($200/mo), indicating:
  - willingness to pay exists for “power” tiers
  - pricing is a function of model usage / agent capacity
- Teams tier includes:
  - shared rules, admin controls, SSO, SCIM, audit logs (enterprise features show up quickly in the tier ladder)

Source:
- https://cursor.com/pricing

### Windsurf
What they sell:
- AI-first coding environment (Cascade) + model-provider flexibility.

Pricing/packaging signals:
- Clear ladder: Free → Pro ($15/mo) → Teams ($30/user/mo) → Enterprise.
- Emphasis on “model provider support” and enterprise deployment options.

Source:
- https://windsurf.com/pricing

### GitHub Copilot
What they sell:
- A cross-editor assistant embedded into the GitHub ecosystem.

Pricing/packaging signals:
- Strong separation between:
  - Individual plan ($10/mo)
  - Business ($19/user/mo)
  - Enterprise ($39/user/mo)
- Enterprise differentiation is framed as:
  - policy + management
  - customization / deeper org context
  - IP indemnity for organizations

Sources:
- https://github.com/features/copilot/plans
- https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises

### Amazon Q Developer
What they sell:
- “Developer assistant” anchored in AWS identity + admin controls.

Pricing/packaging signals:
- Pro pricing called out as $19/user/mo.
- Identity Center support and admin controls show up as key enterprise differentiators.

Source:
- https://aws.amazon.com/q/developer/pricing/

### Google Gemini Code Assist
What they sell:
- Code assist plus broader “across the cloud stack” assistance.

Pricing/packaging signals:
- Enterprise starts at $45/user/mo (with time-bound promotional pricing mentioned).
- Key enterprise messaging:
  - do not train on customer private data
  - code customization and repository indexing

Source:
- https://cloud.google.com/blog/products/application-development/introducing-gemini-code-assist-enterprise

### Tabnine
What they sell:
- “AI code assistant that you control”, with strong privacy/on-prem messaging.

Pricing/packaging signals:
- Free tier exists (local model for basic completion).
- Pro: $12/user/mo (annual billing) after trial.
- Enterprise: $39/user/mo and “deploy anywhere”.

Source:
- https://www.tabnine.com/blog/key-takeaways-and-tabnine-faqs-from-nvidia-gtc/

### Pieces for Developers
What they sell:
- Local-first memory + context across your whole workflow.

Pricing/packaging signals:
- Free plan exists.
- Pro: $18.99/mo (+ taxes).

Source:
- https://pieces.app/features

### Docker Desktop
Why it matters here:
- A canonical example of **free personal use** and paid tiers for professional/org use.

Pricing/packaging signals:
- Business tier includes SSO/SCIM + invoice purchasing.

Source:
- https://www.docker.com/pricing/

### Obsidian
Why it matters here:
- A canonical example of a **local-first** product with paid optional services.

Pricing/packaging signals:
- Keep core app free; charge for sync/publish.

Source:
- https://obsidian.md/pricing

### GitKraken (on-prem licensing pattern)
Why it matters here:
- “Serverless” or self-hosted license management patterns map closely to how a local-first enterprise tool may need to be licensed.

Source:
- https://www.gitkraken.com/git-client/on-premise-pricing

## Key patterns that impact Prep
- Most AI dev tools are priced per-user, per-month with a clear enterprise ladder.
- Enterprise tier differentiation commonly includes:
  - SSO (SAML/OIDC)
  - SCIM
  - audit logs
  - admin controls / governance
  - data retention / privacy guarantees
- Local-first products often monetize via:
  - paid sync/backup
  - team collaboration
  - enterprise deployment and support

## Direct competitors: Is anyone doing exactly what Prep does?

### Answer: No exact match exists

Prep's combination of features is unique:
- **Local-first** (indexes + queries stay on-device by default)
- **Multi-codebase** (registry of projects, not single-repo)
- **Granular scoping** (include/exclude patterns, embedded vs standalone modes)
- **MCP integration** (companion to Cursor/Windsurf, not a replacement IDE)
- **Desktop app packaging** (Tauri + sidecar, not pip install)

### OSS local code RAG tools (pip install style)

These are the "basic version for a single codebase" tools you found:

#### CodeRAG (GitHub: Neverdecel/CodeRAG)
- Single codebase indexing via FAISS + OpenAI embeddings.
- Streamlit UI.
- No multi-project registry, no scoping controls, no MCP, no desktop packaging.

Source:
- https://github.com/Neverdecel/CodeRAG

 #### ChunkHound
 ChunkHound is the closest OSS-style tool to Prep's core loop because it combines:
 - local indexing (`chunkhound index`)
 - incremental re-indexing (re-running only processes changed files)
 - `.gitignore` awareness
 - MCP integration (Claude Code / Cursor / Continue)
 
 Source:
 - https://chunkhound.github.io/quickstart/
 
 What they do well:
 - Simple CLI-first onboarding (Python toolchain).
 - Multiple embedding backends (VoyageAI / OpenAI / Ollama).
 - Optional "code research" workflows (`chunkhound research ...`) to generate higher-level reports.
 
 Differences vs Prep (our differentiation to keep sharpening):
 - **UI + inspectability:** Prep is dashboard-first, designed to make retrieval inspectable (citations, status, errors), not just "a CLI that works".
 - **Curated retrieval controls:** Prep's UI/CLI direction includes user-driven control over what data is retrieved and how it is assembled into bounded context.
 - **Freshness mechanisms:** Prep explicitly treats freshness/staleness as a first-class invariant (auto-rebuild loops, stale indicators, rebuild affordances). ChunkHound emphasizes incremental re-indexing, but not (from quickstart) a full freshness UX model.
 - **Multi-project registry:** Prep is built around multiple codebases and per-project configuration; ChunkHound's quickstart is oriented around a single project directory.
 - **Team posture:** Prep is planning embedded/team config and later enterprise posture; ChunkHound is primarily a developer tool surface.
 - **Config safety posture:** ChunkHound's manual config examples include an `api_key` field in `.chunkhound.json` (easy to accidentally commit). Prep should keep provider keys per-user/local and keep shared configs secret-free.

#### Similar OSS patterns
Many "local RAG for code" projects exist (LanceDB tutorials, txtai examples, etc.) but they share common limitations:
- Single repo focus.
- CLI or notebook-first, not a polished app.
- No persistent project registry.
- No MCP or IDE integration.
- No embedded mode for team portability.

**Prep differentiation**:
- Multi-codebase registry with per-project config.
- Embedded mode for Git-trackable indexes.
- MCP tools for IDE agent loops.
- Desktop app with sidecar lifecycle management.
- Bounded outputs and citation headers designed for AI assistant consumption.

### Commercial local-first competitors

#### Pieces for Developers
Closest in spirit to Prep's "local-first companion" positioning.

What they do:
- Local-first storage and memory across your workflow.
- AI copilot with long-term memory (9 months of context).
- Privacy-first: processed locally, encrypted, no mandatory cloud.
- IDE extensions (VS Code, JetBrains, etc.).

Source:
- https://pieces.app/features/long-term-memory/ai-memory-assistant

Differences from Prep:
- Pieces focuses on **workflow memory** (browsing, notes, snippets) more than **codebase indexing**.
- Pieces is broader (cross-app context); Prep is narrower (code search/context/trace).
- Pieces does not emphasize MCP as a primary integration surface.

**Implication**: Pieces is adjacent, not a direct competitor. Prep's codebase-specific depth + MCP integration is a differentiation.

## Cloud-based code context services

These are doing something **similar** to Prep but as **cloud services**, not local-first apps.

### Greptile
Cloud AI code review with full codebase context.

What they do:
- Builds a detailed graph of your codebase (cloud-hosted).
- PR review, chat, API access.
- Self-hosted option available.
- SOC2 compliant.

Pricing:
- $30/dev/month for code reviews.
- API pricing is per-request.
- Self-hosted available for enterprise.

Source:
- https://www.greptile.com

**Prep differentiation**:
- Greptile is cloud-first (even with self-host option); Prep is local-first by default.
- Greptile focuses on PR review; Prep focuses on context assembly for AI assistants.
- Greptile requires code to leave the device; Prep does not.

### Augment Code (Context Engine)
Enterprise AI coding platform with a proprietary "Context Engine".

What they do:
- Semantic indexing and mapping of codebases.
- Claims to handle enterprise monorepos (millions of lines).
- Tracks commit history, patterns, tribal knowledge.
- Positions context as the differentiator ("Every AI uses the same models. Context is the difference.").

Source:
- https://www.augmentcode.com/context-engine

**Prep differentiation**:
- Augment is enterprise SaaS; Prep is local-first.
- Augment bundles context into a full AI platform; Prep is a companion/tool.
- Augment's pricing is enterprise-focused; Prep targets individual → team → enterprise ladder.

### Sourcegraph Cody
Code intelligence + AI assistant with RAG-based context retrieval.

What they do:
- RAG for code context (retrieves relevant files/chunks at query time).
- Enterprise-scale (300k+ repos, 90GB+ monorepos).
- Remote repository awareness.

Source:
- https://sourcegraph.com/blog/how-cody-understands-your-codebase

Pricing:
- Enterprise: $49/user/month (Code Search).
- Cody has separate tiers.

**Prep differentiation**:
- Sourcegraph is a platform (search + Cody); Prep is a focused companion.
- Sourcegraph requires infrastructure; Prep runs locally.
- Sourcegraph's pricing is enterprise-first; Prep starts free/low-cost.

## Acquisition signals (Cursor, Windsurf, OpenAI)

Understanding what these companies acquire helps set expectations for Prep's positioning.

### Cursor (Anysphere) acquisitions

#### Supermaven (Nov 2024)
- AI coding assistant with low-latency autocomplete.
- Founded by Jacob Jackson (Tabnine co-founder).
- 35k+ developers, $12M raised.
- Acquired to improve Cursor's Tab AI model.

Source:
- https://techcrunch.com/2024/11/12/anysphere-acquires-supermaven-to-beef-up-cursor/

#### Graphite (Dec 2025)
- Code review startup (used by Shopify, Snowflake, Figma).
- $52M Series B, 20X revenue growth in 2024.
- Acquired to address "code review is now a bottleneck as writing code gets faster".

Source:
- https://fortune.com/2025/12/19/cursor-ai-coding-startup-graphite-competition-heats-up/

#### Growth by Design
- Tech recruiting strategy company (helped OpenAI recruit).
- Acquired for in-house recruiting.

Source:
- https://news.bloomberglaw.com/private-equity/ai-startup-cursor-buys-firm-that-helped-openai-recruit-talent

**Pattern**: Cursor acquires to fill gaps in the **end-to-end dev workflow** (autocomplete → code review → recruiting).

### OpenAI acquisition

#### Windsurf (Codeium) (~$3B, 2025)
- AI-assisted coding tool / IDE.
- OpenAI's largest acquisition to date.
- Competes with GitHub Copilot.

Source:
- https://www.reuters.com/business/openai-agrees-buy-windsurf-about-3-billion-bloomberg-news-reports-2025-05-06/

**Pattern**: OpenAI acquiring to **own the IDE layer** and compete with Microsoft/GitHub Copilot.

### What this means for Prep

Acquirers care about:
1. **Filling workflow gaps** (Cursor buys what accelerates the dev loop).
2. **Competitive positioning** (OpenAI buys to compete with Copilot).
3. **User base / traction** (Supermaven had 35k devs; Graphite had Shopify/Figma).
4. **Technical moat** (Supermaven's low-latency model; Greptile's codebase graph).

Prep's acquisition attractiveness would come from:
- **Local-first context engine** as a differentiated moat (not easily replicated by cloud-first players).
- **MCP integration** making it a natural complement to Cursor/Windsurf.
- **Enterprise-friendly posture** (privacy, offline, governance hooks).

## Implications for Prep (updated)

### Positioning
- Prep should avoid competing head-on as "another IDE"; instead position as:
  - a local-first context engine that works with existing IDE assistants via MCP.
- **Pricing Strategy: The "Context Drug" Ladder**:
  - **Free (The Hook):** 1-repo limit creates natural friction to upgrade once usage habits form.
  - **Starter (The Bridge):** $29/4-mo pass for freelancers/students who need >1 repo but aren't ready for $79.
  - **Pro (The Owner):** Perpetual License ("Pay once, own forever") disrupts the $20/mo subscription fatigue.
- "Enterprise" in this market implies identity + policy + audit even if the core app is local.

### Differentiation summary
| Dimension | Prep | OSS pip-install tools | Pieces | Greptile/Augment/Sourcegraph |
|-----------|--------|----------------------|--------|------------------------------|
| Local-first | Yes (default) | Yes | Yes | No (cloud or self-host) |
| Multi-codebase | Yes | No | Partial | Yes |
| Scoping controls | Yes | No | No | Partial |
| MCP integration | Yes | No | No | No |
| Desktop app | Yes (Tauri) | No | Yes | No |
| Enterprise tier | Roadmap | No | No | Yes |
| Trace/graph | **Pro Feature** | No | No | Yes (Greptile) |

### Strategic implications
- **No direct competitor** is doing local-first + multi-codebase + MCP + desktop app.
- **Pieces** is the closest in spirit but different in focus (memory vs codebase context).
- **Cloud services** (Greptile, Augment, Sourcegraph) are potential competitive threats if they add local modes, but their DNA is cloud-first.
- **Acquisition path**: Prep's best angle is as a **local-first context engine** that complements Cursor/Windsurf (filling the "local graph" gap) without requiring them to build local infrastructure.
