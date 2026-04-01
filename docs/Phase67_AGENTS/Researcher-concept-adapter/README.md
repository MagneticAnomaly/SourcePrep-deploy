# Phase 67: Unified Agent Adapter Architecture

> **Phase 67** | Date: 2026-04-01
> This directory contains the design and implementation plans for CoDRAG's autonomous agent system — three co-owned agents that bridge CoDRAG's codebase intelligence (the brain) with Paperclip's project management (the office), executed via pluggable orchestration adapters.

---

## Overview

Phase 67 delivers **three autonomous agent personas** that share a single underlying architecture:

| Agent | UI Name | Role | What It Does |
|-------|---------|------|-------------|
| **Staffing Agent** | 👔 Staffing Agent | Role Architect | Generates, audits, and evolves Paperclip agent role definitions using CoDRAG's epistemic knowledge graph |
| **Researcher Agent** | 🔬 Researcher Agent | Proactive Technical PM | Mines CoDRAG audit findings, researches solutions, and pushes structured project plans into Paperclip |
| **Digital Custodian** | 🧹 Digital Custodian | Codebase Janitor | Identifies dead code, orphaned files, and stale artifacts; executes cleanup in its own git branch with a full archive |

### The "Co-Owned" Identity Model

All three agents are **co-owned** by CoDRAG and Paperclip:

- **CoDRAG is the brain.** It provides the epistemic knowledge graph, audit findings, impact analysis, and module structure that power each agent's reasoning. The agents run within CoDRAG's daemon or as external scripts consuming CoDRAG's MCP server.

- **Paperclip is the office.** All agents project their identity into Paperclip's UI. The Staffing Agent appears as the workforce manager who creates and adjusts other agents. The Researcher appears as a technical PM who authors projects and tasks. The Digital Custodian appears as the maintenance lead who creates cleanup reports. To Paperclip users, these look like regular employees — they show up in org charts, author projects, and have activity histories.

- **The orchestration engine is pluggable.** Each agent can be executed via three different adapters:
  1. **Native Paperclip** — Runs inside the CoDRAG daemon as a daemon thread (like Pi Agent). Direct Python imports, lowest latency, zero external dependencies.
  2. **LangGraph** — Runs as an external Python script with a `StateGraph` for explicit state-machine semantics. Best for the LangChain ecosystem and users who want inspectable, replayable agent loops.
  3. **CrewAI** — Runs as an external Python script with a multi-agent `Crew`. Best for the CrewAI community and use cases that benefit from role/goal/backstory-style agent definitions.

### Why Three Adapters?

This pluggability is the marketing strategy. By building adapters for LangGraph and CrewAI alongside native Paperclip support, CoDRAG gains **three distinct marketing channels**:

| Platform | Target Audience | CoDRAG Value Prop |
|----------|----------------|-------------------|
| **Paperclip** | Paperclip users wanting smarter agent provisioning | CoDRAG = the brain that makes Paperclip agents useful |
| **LangGraph** | LangChain ecosystem (~500K devs) | CoDRAG = the codebase memory LangGraph agents have been missing |
| **CrewAI** | CrewAI community (~200K installs) | CoDRAG = the knowledge base that makes role/goal/backstory actually grounded |

CoDRAG, Paperclip, LangGraph, and CrewAI are not competitors — they occupy three different layers of the agent stack (knowledge → orchestration → workplace). See [02_LangGraph_CrewAI.md](./02_LangGraph_CrewAI.md) for the detailed competitive analysis and integration blueprints.

---

## Architecture at a Glance

```
┌─────────────────┐        ┌────────────────────────────┐        ┌─────────────────┐
│     CoDRAG      │        │     Agent Adapters          │        │   Paperclip     │
│  (The Brain)    │        │                             │        │  (The Office)   │
│                 │        │  ┌── Native (daemon) ──┐    │        │                 │
│ - Audit Engine  │◄──────►│  │  Staffing Agent     │    │───────►│ Agent Roster    │
│ - Impact Graph  │        │  │  Researcher Agent   │    │        │ Projects/Tasks  │
│ - Module Atlas  │        │  │  Digital Custodian   │    │        │ Cleanup Reports │
│ - RoleVectors   │        │  └─────────────────────┘    │        │                 │
│ - Observations  │        │                             │        │                 │
│                 │        │  ┌── LangGraph ─────────┐   │        │                 │
│                 │◄──MCP──│  │  StateGraph adapters  │   │─REST──►│                 │
│                 │        │  └─────────────────────┘   │        │                 │
│                 │        │                             │        │                 │
│                 │        │  ┌── CrewAI ─────────────┐  │        │                 │
│                 │◄──MCP──│  │  Multi-agent crews     │  │─REST──►│                 │
│                 │        │  └─────────────────────┘  │        │                 │
└─────────────────┘        └────────────────────────────┘        └─────────────────┘
```

All adapters consume the same `AgentCore` interface, which wraps CoDRAG's internal APIs and Phase 65's Paperclip Push Engine. The orchestration framework decides *how* the agent thinks; `AgentCore` decides *what data is available*.

---

## The Three Agents

### 1. The Staffing Agent (formerly "HR Agent")

**In the code:** `src/codrag/agents/hr/`
**In the UI:** "👔 Staffing Agent"
**In Paperclip:** Appears as the "Staffing Manager" employee

The Staffing Agent generates, audits, and evolves the Paperclip agent workforce. It reads CoDRAG's codebase atlas to understand what roles are needed, then generates complete agent instruction files (AGENTS.md, SOUL.md, KNOWLEDGE.md) for each role.

**Capabilities:**
- **Generate** (3 modes: list, auto, auto+list) — Creates new agent roles based on codebase structure
- **Adopt** — Imports existing Paperclip agents and enriches them with CoDRAG intelligence
- **Audit** — Detects role drift (agents whose file scopes no longer match the codebase)
- **Sync** — Pushes updated role definitions to Paperclip

**Full architecture:** See [HR-concept-adapter/](../HR-concept-adapter/) (Docs 01–07)

### 2. The Researcher Agent

**In the code:** `src/codrag/agents/researcher/`
**In the UI:** "🔬 Researcher Agent"
**In Paperclip:** Appears as the "Technical Researcher" employee

The Researcher Agent proactively mines CoDRAG's audit findings, researches solutions (optionally using web search), and pushes structured project plans into Paperclip.

**Capabilities:**
- **Tech Debt Prospector** — Finds spaghetti code hotspots, traces blast radius via `codrag_impact`, creates "Tech Debt Cleanup" projects
- **Security & Dependency Analyst** — Identifies out-of-date dependencies, researches migration steps, pushes P1 Goals
- **Bug Bounty Hunter** — Clusters scattered TODOs/FIXMEs by module, estimates effort, curates "Quick Win" backlogs

**Research loop:** Pipeline completes → Pi Watchdog delta → Researcher selects top 3 topics → LLM synthesizes solutions → Push to Paperclip → Cooldown

### 3. The Digital Custodian

**In the code:** `src/codrag/agents/custodian/`
**In the UI:** "🧹 Digital Custodian"
**In Paperclip:** Appears as the "Maintenance Lead" employee

The Digital Custodian manages the physical state of the codebase — cleaning up dead code, deleting orphaned files, and archiving deprecated modules. Unlike the other two agents, the Custodian **writes to the codebase** in its own git branch.

**Capabilities:**
- **Dead code detection** — Identifies files/functions with zero dependents via the trace graph
- **Orphan file cleanup** — Flags files that nothing imports and that import nothing
- **Stale TODO removal** — Cleans up TODOs that have been resolved but not removed
- **Deprecated module archival** — Moves entire deprecated modules to a long-lived archive branch

**Safety:** Dry-run by default, archive-first (nothing deleted without backup), never auto-merges, impact verification on every candidate, max 20 files per cleanup PR.

**Full architecture:** See [03_Digital_Custodian.md](./03_Digital_Custodian.md)

---

## Dashboard UI: Agent Operations

All agents are managed from the **"Agent Operations"** panel in the CoDRAG dashboard. This panel uses a two-level UI pattern identical to the AI Gateway:

- **Level 1 (Modular Panel):** Compact status cards for all 3 system agents + badge row for managed Paperclip employees
- **Level 2 (Detail Overlay):** Full-screen overlay with tabs: [System Agents] and [Managed Employees]

**LLM model assignment** for agents lives in the **AI Gateway Details → Assigned tab** (not in Agent Operations). This keeps all LLM configuration in one place and avoids duplication.

---

## Documents in This Directory

| Document | Purpose |
|----------|---------|
| [README.md](./README.md) | This file — overview of the unified agent architecture |
| [implementation_plan.md](./implementation_plan.md) | Comprehensive implementation plan with code samples, wireframes, and phased schedule |
| [02_LangGraph_CrewAI.md](./02_LangGraph_CrewAI.md) | Detailed LangGraph and CrewAI integration blueprint, competitive analysis, and marketing strategy |
| [03_Digital_Custodian.md](./03_Digital_Custodian.md) | Digital Custodian concept: git branch strategy, safety guardrails, archive manifest design |
| [04_Architecture_Audit.md](./04_Architecture_Audit.md) | Infrastructure alignment audit: 12 reuse opportunities, dependency direction rules, scalability analysis, module placement decisions |

## Related Documents

| Document | Relationship |
|----------|-------------|
| [HR-concept-adapter/](../HR-concept-adapter/) | Staffing Agent concept: Docs 01–07 covering landscape research, architecture, integration, orchestrators, edge cases, context pipeline, and primary-vs-agent alignment |
| [Phase 65: Pushing to Paperclip](../../Phase65_PushingTasksToPaperclip/README.md) | PushEngine and PMAdapter that all agents use to push to Paperclip |
| [Phase 66: Pi Agent](../../Phase66_Pi-Agent/README.md) | Pi daemon thread architecture and 7 scenarios — the Researcher and Custodian hook into the Pi Watchdog loop |
