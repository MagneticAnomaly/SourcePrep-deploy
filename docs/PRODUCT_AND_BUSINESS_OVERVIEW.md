# Prep — Product and Business Overview

## Purpose
This document is a thorough, end-to-end overview of Prep as:
- a product memo for stakeholders evaluating the opportunity
- a clear, developer-facing explanation for prospective users

It covers:
- what Prep is and why it exists
- how it works (conceptual + architectural)
- key differentiators and design constraints
- pricing approach (not finalized)
- distribution plan (desktop app + enterprise considerations)
- go-to-market and roadmap

## One-line summary
Prep is a **local-first context engine for codebases**: it indexes your repos, provides **fast and verifiable retrieval**, and exposes that context to IDE agents (Cursor/Windsurf/Copilot workflows) via **MCP**, without requiring your code to be uploaded to a vendor cloud.

## The problem
Modern AI coding workflows have a predictable failure mode:

- **Context Assembly**: `prep` tool automatically pulls relevant code/docs into the LLM context window.
- **Manual context assembly does not scale**: developers paste files, guess what’s relevant, and fight hallucinations.
- **Cloud-first code indexing is not always acceptable**:
  - security and IP constraints
  - regulated environments
  - air-gapped workflows
  - personal preference for local ownership
- **Multi-repo reality**: real work spans multiple repos, forks, branches, and client codebases.
- **Trust breaks easily**:
  - “am I looking at the right repo?”
  - “is the index fresh?”
  - “where did this answer come from?”

The result is a workflow tax: AI assistants are powerful, but often unreliable and opaque in real production codebases.

## The product thesis
Prep is built around a single thesis:

> The next generation of developer productivity is not “a better LLM,” but a better **context system**.

AI tooling succeeds when it can:
- rapidly retrieve the right parts of the codebase
- keep results consistent with the developer’s reality (repo, branch, freshness)
- bound outputs so tools remain controllable
- cite sources so users can verify
- integrate into existing IDE agent loops

Prep is designed to be **a context layer** that complements (rather than replaces) Cursor/Windsurf/Copilot.

## What Prep is

### Core concept
Prep maintains one or more local indexes of codebases (projects). For a given question or task, it:
1. searches for relevant chunks/snippets
2. assembles a bounded context bundle
3. returns prompt-ready context with citations
4. optionally expands context using lightweight structural traces

### What Prep is not
- not a replacement IDE
- not a hosted “upload your repo” SaaS requirement
- not a generic “agent platform” competing with IDE vendors

## Who it’s for

### Primary users
- **Solo developers** who want local-first trust and fast context recall
- **Staff engineers / tech leads** who work across multiple repos and need verifiable answers
- **IDE agent users** who want reliable context retrieval via MCP tool calls
- **Security/ops-conscious developers** who can’t upload code to 3rd-party indexing services

### Secondary users (later)
- **Teams** who need repeatable onboarding and consistent indexing policy
- **Enterprise admins** who require governance (SSO/SCIM/audit) and controlled rollout

## The core user loop
Prep’s “core loop” is designed to be learnable in minutes:

1. **Add a project** (a repo / folder)
2. **Build an index** (full or incremental)
3. **Search** and inspect results (debuggable retrieval)
4. **Assemble context** (bounded, cited, ready for an LLM)
5. **Use inside an IDE agent** via MCP

This loop is intentionally separated from any particular LLM vendor.

## Key features (today and planned)

### 1) Multi-codebase registry
Prep is designed to manage many projects:
- a personal “registry” of repos
- per-project settings (include/exclude rules, modes)
- clear visibility into freshness and build history

This is a deliberate difference from “one-off RAG scripts.”

### 2) Index lifecycle management
- full builds
- incremental rebuilds
- file watcher / staleness indicators (planned)
- predictable failure recovery (planned)

The product goal is simple: you should always know whether your index is correct and current.

### 3) Search (inspectable retrieval)
Prep emphasizes retrieval that is:
- inspectable
- bounded
- debuggable

Instead of returning only an answer, Prep returns ranked results with file/line references and previews.

### 4) Context assembly (prompt-ready)
Prep can return a single assembled context bundle:
- bounded by `max_chars`
- optionally includes sources and/or relevance scores
- designed to be pasted into prompts or sent by an IDE agent

This is the product’s “atomic unit” for agent workflows.

### 5) Trace index (structural signals; optional)
Prep can supplement embeddings with lightweight structural understanding:
- symbols (functions/classes)
- import edges
- bounded neighborhood expansion

This is meant to answer questions like:
- “what calls this function?”
- “where is this defined?”
- “what are related modules?”

It is intentionally bounded (to preserve tool reliability).

### 6) MCP integration (primary integration surface)
Prep integrates via MCP so it can be invoked by IDE agents:
- Cursor
- Windsurf
- other MCP-compatible tooling

The design intent is for Prep to be callable as tools such as:
- `prep_status`
- `prep_build`
- `prep_search`
- `prep_context`
- `prep_trace`

MCP is the integration surface so Prep avoids writing and maintaining many IDE plugins.

### 7) Local-first embeddings + BYOK augmentation
Prep is designed to be useful at multiple “power levels”:
- works without LLMs (e.g., keyword search modes)
- improves retrieval via embeddings (e.g., `nomic-embed-text`)
- optionally augments summaries/explanations using a BYOK LLM provider

Practical implication:
- indexing and retrieval remain local-first
- if you choose BYOK augmentation, only the retrieved context is sent to your chosen provider

### 8) Desktop companion app (distribution)
Prep is intended to ship as:
- a desktop app (macOS/Windows) using Tauri
- a bundled sidecar backend (Python/FastAPI)

This choice is meant to reduce “dev tool friction”:
- no complex installs
- consistent lifecycle management
- a simple UI for trust + configuration

## Architecture (high level)

### System components
Prep is structured around:
- **Core engine** (project registry + index managers)
- **Local daemon** (FastAPI server)
- **Dashboard** (React UI)
- **MCP server** (stdio; proxies to daemon)
- **Desktop wrapper** (Tauri managing sidecar)

### Storage modes
Prep supports multiple indexing postures:

- **Standalone mode**: index stored in an application data directory
- **Embedded mode**: index stored in a repo-local folder (e.g. `.runprep/`), enabling git workflows (roadmap)

The goal is to support both:
- personal workflows across many repos
- team onboarding workflows where indexes can be shared/reproduced

### Bounded outputs are a design constraint
Tool reliability is a core product requirement:
- context assembly respects size budgets
- trace expansion respects node/edge caps
- errors are stable and actionable

This makes Prep a better fit for agentic workflows where runaway outputs cause failure.

## Competitive landscape (where Prep sits)

### The closest “big” competitors
- **Augment Code**: cloud-first indexing with strong context modeling
- **Sourcegraph Cody**: enterprise code search platform with AI assistant

Both are powerful, but structurally cloud-first.

### Prep differentiation
Prep’s differentiation is not “we are smarter.” It’s:
- **local-first by default**
- **fast and predictable** (local query latency)
- **works offline** (or with restricted network)
- **BYOK augmentation** (not locked to a single vendor)
- **multi-codebase + granular scoping** as a first-class design goal
- **MCP-native** to integrate into IDE agent loops

## Why local-first matters (beyond philosophy)
Local-first is not just branding; it affects outcomes:
- latency: local retrieval can be dramatically faster than remote API calls
- security: code doesn’t need to be uploaded to a vendor index
- autonomy: tool remains usable without vendor uptime dependency
- enterprise feasibility: supports restricted network environments

Prep treats these as product requirements.

## Business model overview

### Market category
Prep is positioned as a **developer productivity tool** and **context engine**.
It complements AI IDEs rather than competing head-on as a full IDE.

### Distribution strategy
- **Direct download** for initial releases (best for licensing + enterprise friendliness)
- App stores are an eventual option, not required for early viability

### Pricing (Finalized Strategy)
Prep uses a **"Software License"** model for individuals and a **"Seat-Based Subscription"** for teams.

**Philosophy:**
- **Local-First Trust:** Users own the software, not rent it.
- **BYOK Cost Savings:** We don't mark up tokens; users pay provider costs directly.

**The Tiers:**

1.  **Free Tier (The Hook):**
    - **$0**.
    - Limits: 2 active projects.
    - Features: Standard keyword/embedding search.
    - Purpose: Evaluation and hobbyist use.

2.  **Pro License (Personal/Professional):**
    - **$79** (One-time perpetual license).
    - **Founder's Edition:** **$49** for the first 500 users.
    - Features: Unlimited projects, **Trace Index** (structural signals), Full MCP suite.
    - Updates: Includes 1 year; optional ~$30/year renewal for updates (app keeps working if not renewed).

3.  **Team Tier (Indexed Harmony):**
    - **$12/seat/month** (billed annually).
    - Features: **Shared Index Configs** (standardized scoping), Centralized Policy, License Management.

4.  **Enterprise Tier:**
    - **Custom Pricing**.
    - Features: Air-gapped support, SSO/SCIM, Audit Logs, SLA.

See:
- `Phase10_Business_And_Competitive_Research/Pricing/PRICING_STRATEGY.md`

### What we charge for (value metrics)
To avoid “token pricing” (BYOK), pricing should align to value drivers:
- number of indexed codebases
- index size
- advanced scoping and policy controls
- team onboarding / shared configuration
- governance features (audit, SSO/SCIM)

## Go-to-market strategy (pragmatic)

### Bottom-up adoption
Initial adoption is expected to be developer-led:
- install, index a repo, connect MCP, feel the workflow improvement
- expand usage across multiple repos
- introduce to team

### Trust-led marketing
The core message is:
- your code stays yours
- you can verify what the tool retrieved
- it works with your existing AI IDE

### Early channels
- developer communities (Cursor/Windsurf power users)
- local-first / privacy-focused communities
- content demonstrating “agent workflows + bounded context + citations”

## Roadmap (high level)
The roadmap is organized as phases with a clear MVP target.

### MVP outcome
A stable desktop companion app that reliably supports:
- add/build/search/context
- a dashboard UI
- MCP integration
- optional trace index

### Post-MVP directions
- embedded mode and team onboarding workflows
- network/shared server mode (enterprise)
- stronger trace features
- better incremental indexing and branch-awareness
- optional context compression and summarization workflows

## Risks and mitigations

### Risk: being “a feature” in a larger IDE
Mitigation:
- focus on being the best local-first context engine
- integrate via MCP rather than competing as an IDE
- keep a clear API contract and stable tool surfaces

### Risk: retrieval quality vs cloud competitors
Mitigation:
- retrieval can be improved without cloud dependency (hybrid retrieval, re-ranking, trace expansion)
- focus on correctness and debuggability, not marketing claims

### Risk: distribution complexity (desktop + sidecar)
Mitigation:
- start with direct distribution
- prioritize stability and clear diagnostics
- keep the backend as a single daemon with clear health checks

## What success looks like
Success is not “the best model.” It’s:
- developers trust it
- developers keep it running in the background
- MCP tool calls become a default part of IDE workflows
- teams adopt it for onboarding and codebase comprehension

Concrete success signals:
- high repeat usage across multiple codebases
- low time-to-first-success (install → index → MCP query)
- low support burden due to predictable diagnostics

## Next steps
If you’re evaluating Prep as a user:
1. install
2. add a repo
3. build
4. connect via MCP
5. ask your IDE agent questions that require multi-file context

If you’re evaluating Prep as a stakeholder:
- confirm the product/market fit around local-first + context reliability
- validate willingness to pay for a perpetual license + updates model
- validate enterprise demand for governance without mandatory cloud
