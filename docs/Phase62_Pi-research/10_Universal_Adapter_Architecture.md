# Phase 62 — Universal Adapter Architecture: Academic Foundations

> **Research Document 10 of 10** | Phase 62: CS Research & Protocol Stack for Universal Compatibility
> Date: 2026-03-30

---

## 1. Purpose

This document surveys current computer science research, industry standards, and architectural patterns to ensure CoDRAG's "knowledge provider" pivot is built on the strongest possible foundation — one that maximizes compatibility with ANY agent, orchestrator, or PM tool, present or future.

---

## 2. The Protocol Stack (2026 Industry Consensus)

The AI agent ecosystem has converged on a **layered protocol architecture**. This is no longer theoretical — it's being standardized:

```
┌──────────────────────────────────────────────────────────────────────┐
│                     The Agentic Protocol Stack                       │
│                                                                       │
│  Layer 4: A2A (Agent-to-Agent Protocol)                              │
│  ─────────────────────────────────────                               │
│  • Google-originated, now Linux Foundation governance                │
│  • Agent Cards for capability discovery (/.well-known/agent.json)    │
│  • JSON-RPC 2.0 over HTTPS + SSE                                    │
│  • Task lifecycle: submitted → working → input-required → completed  │
│  • Purpose: Agent-to-agent coordination and task delegation          │
│                                                                       │
│  Layer 3: MCP (Model Context Protocol)                               │
│  ─────────────────────────────────────                               │
│  • Anthropic-originated, broadly adopted                             │
│  • Tools, Resources, Prompts exposed via JSON-RPC                    │
│  • Purpose: Agent-to-tool/data connections                           │
│  • CoDRAG already implements this ✅                                  │
│                                                                       │
│  Layer 2: AGENTS.md / Skill Files                                    │
│  ─────────────────────────────────                                   │
│  • Informal but widely adopted convention                            │
│  • Static capability description (read at session start)             │
│  • Purpose: Ambient context injection                                │
│  • CoDRAG already implements this ✅                                  │
│                                                                       │
│  Layer 1: CLI / HTTP API                                             │
│  ─────────────────────────────────                                   │
│  • Universal substrate — any language, any runtime                   │
│  • stdout/stderr + exit codes                                        │
│  • Purpose: Direct tool invocation                                   │
│  • CoDRAG already implements this ✅                                  │
│                                                                       │
│  Layer 0: Export Formats (SARIF, OCSF, JSON, CSV)                    │
│  ─────────────────────────────────────────────────                   │
│  • Standards bodies: OASIS (SARIF), AWS/Splunk (OCSF)               │
│  • Purpose: Static data interchange (file-based)                     │
│  • CoDRAG needs to implement this ⚠️                                 │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Insight

> CoDRAG already covers Layers 1-3. The two gaps are **A2A (Layer 4)** and **Export Formats (Layer 0)**. Filling these makes CoDRAG compatible with essentially every tool in the ecosystem.

---

## 3. A2A: The Missing Protocol (and Why CoDRAG Should Implement It)

### 3.1 What A2A Means for CoDRAG

A2A enables **any agent** (Pi, Claude Code, Devin, custom agents) to *discover* CoDRAG and *request analysis tasks* from it, without hardcoded integration. This is the difference between:

**Without A2A:**
```
Paperclip → (custom adapter) → Pi → (custom script) → CoDRAG CLI
  Each integration is bespoke. N tools × M agents = N×M adapters.
```

**With A2A:**
```
Any Agent → (A2A protocol) → CoDRAG Agent Card → (task request) → CoDRAG → (result)
  One interface. N tools can discover and use CoDRAG automatically.
```

### 3.2 CoDRAG's Agent Card

The A2A protocol defines a machine-readable "Agent Card" at `/.well-known/agent.json`:

```json
{
  "name": "CoDRAG",
  "description": "Codebase intelligence engine. Discovers structural patterns, architectural issues, opportunities, and provides context-aware code analysis.",
  "url": "http://localhost:8400",
  "version": "2026.1",
  "provider": {
    "organization": "CoDRAG",
    "url": "https://codrag.dev"
  },
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "authentication": {
    "schemes": ["none"]
  },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain", "application/json"],
  "skills": [
    {
      "id": "codebase-context",
      "name": "Codebase Context Assembly",
      "description": "Assembles focused, compressed context for a code query using semantic search, structural trace expansion, and LOD compression.",
      "tags": ["code", "search", "context", "RAG"],
      "examples": [
        "Assemble context about the authentication module",
        "Find all files that depend on utils.py"
      ]
    },
    {
      "id": "opportunity-discovery",
      "name": "Opportunity Discovery",
      "description": "Scans the codebase for architectural issues, tech debt, security concerns, and improvement opportunities. Returns structured ActionItems.",
      "tags": ["audit", "health", "tech-debt", "opportunities"],
      "examples": [
        "Find all opportunities for improvement in this codebase",
        "What are the critical architectural issues?"
      ]
    },
    {
      "id": "impact-analysis",
      "name": "Impact Analysis",
      "description": "Analyzes what connects to a file or symbol — dependencies, dependents, or both. Use before making changes to understand blast radius.",
      "tags": ["dependencies", "impact", "blast-radius"],
      "examples": [
        "What breaks if I change auth/login.py?",
        "What does the router module depend on?"
      ]
    },
    {
      "id": "structural-overview",
      "name": "Structural Overview",
      "description": "Returns module structure, hub files, focus areas, and architectural patterns. The starting point for understanding any codebase.",
      "tags": ["architecture", "modules", "structure"],
      "examples": [
        "Give me an overview of this codebase",
        "What are the hub files?"
      ]
    }
  ]
}
```

### 3.3 What This Enables

With an Agent Card, CoDRAG becomes **discoverable by any A2A-compliant agent**:

```
Paperclip Agent "Code Analyst"
  → Discovers CoDRAG via A2A Agent Card
  → Sends task: "Find all critical architectural issues in project X"
  → CoDRAG processes (using its existing audit pipeline)
  → Returns structured ActionItems as A2A artifacts
  → Paperclip routes findings to Claude Code or Pi agents

No custom adapter needed. Paperclip just speaks A2A.
```

### 3.4 Implementation Effort

CoDRAG's daemon already runs an HTTP server at `localhost:8400`. Adding A2A support means:

1. Serve `/.well-known/agent.json` (Agent Card) — static JSON file
2. Add JSON-RPC 2.0 endpoint for task handling — ~200 lines
3. Map incoming A2A tasks to existing pipeline functions — wiring
4. Return results as A2A artifacts — serialization

**Estimated effort: 3-5 days**. This is shockingly cheap for the interoperability it unlocks.

---

## 4. Hexagonal Architecture: The "Ports and Adapters" Pattern

### 4.1 What CoDRAG Already Is (Without Knowing It)

CoDRAG's architecture naturally follows Cockburn's Hexagonal Architecture:

```
                             ┌─────────────────────┐
                             │                     │
                  ┌──────────┤    CoDRAG Core      ├──────────┐
                  │          │    (The Hexagon)     │          │
                  │          │                     │          │
                  │          │  • Code Graph       │          │
                  │          │  • Audit Pipeline    │          │
                  │          │  • ActionItem Model  │          │
                  │          │  • Search Engine     │          │
                  │          │  • Context Assembler │          │
                  │          │                     │          │
                  │          └─────────────────────┘          │
                  │                                            │
     ╔════════════╧═══╗                            ╔═══════════╧════════╗
     ║ DRIVING PORTS   ║                            ║ DRIVEN PORTS       ║
     ║ (Who calls us)  ║                            ║ (What we call)     ║
     ╠════════════════╣                            ╠═══════════════════╣
     ║                 ║                            ║                    ║
     ║ Port: MCP       ║ ← Already built           ║ Port: LLM Provider ║
     ║  Adapter: MCP   ║                            ║  Adapter: Ollama   ║
     ║  Server         ║                            ║  Adapter: Cloud API║
     ║                 ║                            ║                    ║
     ║ Port: CLI       ║ ← Already built           ║ Port: File System  ║
     ║  Adapter: argparse                           ║  Adapter: OS       ║
     ║                 ║                            ║                    ║
     ║ Port: HTTP API  ║ ← Already built           ║ Port: Embedding    ║
     ║  Adapter: Flask ║                            ║  Adapter: HF/Ollama║
     ║                 ║                            ║                    ║
     ║ Port: A2A       ║ ← NEW (to build)          ║ Port: Graph Store  ║
     ║  Adapter: JSON- ║                            ║  Adapter: NetworkX ║
     ║  RPC 2.0        ║                            ║                    ║
     ║                 ║                            ║                    ║
     ║ Port: Export    ║ ← NEW (to build)          ║                    ║
     ║  Adapter: SARIF ║                            ║                    ║
     ║  Adapter: JSON  ║                            ║                    ║
     ║  Adapter: CSV   ║                            ║                    ║
     ╚════════════════╝                            ╚═══════════════════╝
```

### 4.2 The Architectural Principle

> **CoDRAG's core intelligence (the hexagon) should be completely independent of how it's consumed.**

The same `ActionItem` model gets exported through:
- **MCP** → `codrag_audit(action="advise")` returns ActionItems as tool output
- **CLI** → `codrag advise --format json` prints ActionItems to stdout
- **HTTP** → `GET /projects/{id}/opportunities` returns ActionItems as JSON
- **A2A** → Task completion returns ActionItems as A2A artifacts
- **SARIF** → ActionItems mapped to SARIF results (for GitHub)
- **CSV** → ActionItems as spreadsheet rows (for PM import)
- **AGENTS.md** → ActionItems summarized in markdown (for ambient context)

**7 adapters, 1 core model.** This is the power of Hexagonal Architecture.

---

## 5. Academic Research: Multi-Agent Code Intelligence

### 5.1 Graph-Based Code Understanding (2024-2025 Trend)

Academic research has shifted from flat text embeddings to **graph-based code representations**:

| Paper/Framework | Contribution | CoDRAG Alignment |
|---|---|---|
| **ALMAS** (2025, arXiv) | End-to-end multi-agent SDLC with dynamic summarization | CoDRAG's LOD compression = dynamic summarization |
| **CodeAgent** (2024-25) | Multi-agent collaborative code review with QA supervision | CoDRAG provides the structural context for such agents |
| **KARMA** (2025, NeurIPS) | Multi-agent knowledge graph enrichment and verification | CoDRAG's enrichment pipeline does exactly this |
| **RTADev** (2025, ACL) | Intention-aligned multi-agent consensus for structural completeness | CoDRAG's product intent + advisor = intention alignment |
| **MAKGED** (2025) | Multi-agent KG error detection via subgraph embeddings | CoDRAG's spaghetti scorer detects structural anomalies similarly |

### 5.2 Key Research Insights for CoDRAG

1. **Specialization wins over generalism**: The best multi-agent systems use *specialized* agents, not one monolithic agent. CoDRAG IS a specialized agent — it should excel at intelligence, not try to also be an executor.

2. **Graph-based RAG outperforms flat RAG**: CoDRAG's structural trace expansion (walking the dependency graph to assemble context) aligns with state-of-the-art "GraphRAG" research. This is a genuine competitive advantage.

3. **Consensus mechanisms improve quality**: Multiple agents analyzing code from different perspectives (readability, security, performance) and scoring findings reduces hallucinations. CoDRAG's multi-scanner approach (health, spaghetti, advisor) is a form of this.

4. **Knowledge export must be structured**: All research frameworks output structured findings (JSON, graph triples, annotated ASTs) — not prose. CoDRAG's ActionItem model is the right abstraction.

---

## 6. Export Format Standards

### 6.1 SARIF (Static Analysis Results Interchange Format)

**The most important standard for CoDRAG to adopt.** SARIF is:
- OASIS-governed (industry standard body)
- Natively consumed by GitHub Code Scanning
- Understood by VS Code, IntelliJ, Azure DevOps
- Version 2.1.0 is current

**ActionItem → SARIF mapping:**

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [{
    "tool": {
      "driver": {
        "name": "CoDRAG",
        "version": "2026.1",
        "informationUri": "https://codrag.dev",
        "rules": [{
          "id": "ARCH-001",
          "name": "CircularDependency",
          "shortDescription": { "text": "Circular dependency detected" },
          "helpUri": "https://codrag.dev/rules/ARCH-001",
          "properties": { "tags": ["architecture", "maintainability"] }
        }]
      }
    },
    "results": [{
      "ruleId": "ARCH-001",
      "level": "warning",
      "message": { "text": "Circular dependency between auth module and user module" },
      "locations": [{
        "physicalLocation": {
          "artifactLocation": { "uri": "src/auth/login.py" },
          "region": { "startLine": 42 }
        }
      }],
      "properties": {
        "codrag_action_item_id": "HEALTH-a7b9",
        "effort": "medium",
        "category": "architecture"
      }
    }]
  }]
}
```

### 6.2 OCSF (Open Cybersecurity Schema Framework)

For security-focused findings. CoDRAG's security audit findings should also support OCSF export for integration with security dashboards (Amazon Security Lake, Splunk).

### 6.3 Recommendation

| Format | When to Use | Priority |
|---|---|---|
| **JSON** | Default export, API responses, Paperclip integration | P0 |
| **SARIF** | GitHub Code Scanning, IDE integration, CI/CD gates | P0 |
| **Markdown** | AGENTS.md injection, documentation, human review | P1 |
| **CSV** | PM tool import (Linear, Jira), spreadsheet analysis | P2 |
| **OCSF** | Security dashboard integration (future) | P3 |

---

## 7. Universal Compatibility Matrix

With all protocols and formats implemented, CoDRAG becomes universally compatible:

```
                                  CoDRAG
                                  (Core)
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
               ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
               │   MCP   │    │  A2A    │    │  CLI    │
               │  Server │    │  Agent  │    │  Tool   │
               └────┬────┘    └────┬────┘    └────┬────┘
                    │               │               │
           ┌───────┼───────┐  ┌────┼────┐    ┌────┼────────┐
           │       │       │  │    │    │    │    │        │
         Claude  Cursor  Anti │   Any   │  Shell Pi     n8n
         Code           grav │   A2A   │  scripts      Zapier
                        ity  │  Agent   │
                             │         │
                          Paperclip  Custom
                          Devin     Agents
                          CrewAI

                    ┌───────────────┼───────────────┐
                    │               │               │
               ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
               │  SARIF  │    │  JSON   │    │   CSV   │
               │ Export  │    │ Export  │    │ Export  │
               └────┬────┘    └────┬────┘    └────┬────┘
                    │               │               │
                 GitHub         Paperclip        Linear
                 VS Code        Any tool         Jira
                 Azure          Custom           Sheets
                 DevOps         scripts
```

### Compatibility Count

| Protocol/Format | Compatible Tools |
|---|---|
| MCP | Claude Code, Cursor, Antigravity, VS Code, Zed, any MCP client |
| A2A | Paperclip, CrewAI, LangGraph, Google ADK, any A2A agent |
| CLI | Pi, Aider, Cline, shell scripts, cron jobs, n8n, Zapier |
| SARIF | GitHub, GitLab, VS Code, IntelliJ, Azure DevOps, CodeQL |
| JSON | Everything |
| CSV | Linear, Jira, Notion, Sheets, Excel |
| AGENTS.md | Claude Code, Windsurf, Pi, Aider, any agent that reads project files |

**Total unique tool reach: 30+** from 7 interfaces. No custom adapter needed for any of them.

---

## 8. Revised Architecture: The "Protocol Hexagon"

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                       │
│                    CoDRAG: The Protocol Hexagon                       │
│                                                                       │
│                         ┌─────────────┐                              │
│                    A2A  │             │  MCP                         │
│                ┌────────┤   ActionItem ├────────┐                    │
│                │        │    Model     │        │                    │
│                │        │             │        │                    │
│           SARIF│        │  • id       │        │CLI                 │
│                │        │  • title    │        │                    │
│                │        │  • category │        │                    │
│                │        │  • priority │        │                    │
│                │        │  • effort   │        │                    │
│                │        │  • files    │        │                    │
│                │        │  • subtasks │        │                    │
│                ├────────┤  • source   ├────────┤                    │
│                │        │             │        │                    │
│           JSON │        │  (stable,   │        │HTTP                │
│                │        │   universal)│        │                    │
│                │        │             │        │                    │
│                │        └─────────────┘        │                    │
│                │               │               │                    │
│                └───────────────┼───────────────┘                    │
│                           CSV  │  AGENTS.md                         │
│                                │                                     │
│                                                                       │
│  All adapters serialize the SAME ActionItem through different        │
│  protocols. The core never changes. New adapters are additive.       │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Design Opportunities Identified

### 9.1 A2A Agent Card (Highest Impact, Lowest Cost)

**Impact:** Makes CoDRAG discoverable by ANY A2A-compliant orchestrator (Paperclip, CrewAI, LangGraph, Google ADK).
**Cost:** 3-5 days. It's a JSON file + a thin JSON-RPC handler.
**Why now:** A2A adoption is accelerating (50+ enterprise partners, Linux Foundation governance). Being early is a competitive advantage.

### 9.2 SARIF Export (Highest Reach, Already Standardized)

**Impact:** GitHub Code Scanning shows CoDRAG findings natively in the Security tab. Zero GitHub API integration needed.
**Cost:** 2-3 days. Map ActionItem fields to SARIF result fields.
**Why now:** Every team uses GitHub. This is the fastest path to mass visibility.

### 9.3 Dual-Protocol Server (MCP + A2A)

CoDRAG's daemon can serve **both** MCP and A2A simultaneously — different endpoints, same core. This is architecturally clean and recommended by protocol experts:

```
localhost:8400/          → HTTP API (existing)
localhost:8400/mcp       → MCP Server (existing)
localhost:8400/.well-known/agent.json  → A2A Agent Card (NEW)
localhost:8400/a2a       → A2A task handler (NEW)
```

### 9.4 Headless AGENTS.md Auto-Refresh

**Impact:** Zero-config agent compatibility. Any agent that reads `.agents/AGENTS.md` gets current CoDRAG findings without any protocol setup.
**Cost:** 1-2 days. Write markdown summary of top ActionItems into AGENTS.md.
**Why now:** This is the "it just works" path for users who don't want to configure protocols.

---

## 10. Summary: What Makes CoDRAG Universally Compatible

| Principle | How CoDRAG Implements It |
|---|---|
| **Hexagonal Architecture** | Core (ActionItem) is protocol-independent. Adapters handle serialization. |
| **Protocol Layering** | CLI → AGENTS.md → MCP → A2A. Users choose their preferred layer. |
| **Standard Formats** | SARIF, OCSF, JSON, CSV. Never a proprietary format. |
| **Agent-Agnosticism** | CoDRAG doesn't know or care which agent consumes its output. |
| **Progressive Disclosure** | Simple CLI for basic users. MCP for IDE users. A2A for orchestrator users. |
| **Composability** | Any tool can combine CoDRAG's output with any other tool's output. No lock-in. |

---

## References

### Standards & Specifications
1. **A2A Protocol** — Google/Linux Foundation, 2025. [a2a-protocol.org](https://a2a-protocol.org)
2. **SARIF 2.1.0** — OASIS, 2023. [docs.oasis-open.org/sarif](https://docs.oasis-open.org/sarif)
3. **MCP** — Anthropic, 2024. [modelcontextprotocol.io](https://modelcontextprotocol.io)
4. **OCSF** — AWS/Splunk, 2023. [ocsf.io](https://ocsf.io)
5. **AGENTS.md** — Community convention, 2024-2025.

### Academic Papers
6. **ALMAS** — "Autonomous LLM-based Multi-Agent Software Engineering" (arXiv, 2025)
7. **CodeAgent** — "Multi-Agent Collaborative Code Review" (Semantic Scholar, 2024-25)
8. **KARMA** — "Multi-Agent KG Enrichment" (NeurIPS 2025)
9. **RTADev** — "Intention-Aligned Multi-Agent Consensus" (ACL 2025)
10. **MAKGED** — "Multi-Agent KG Error Detection" (ResearchGate, 2025)

### Architecture
11. Cockburn, A. — "Hexagonal Architecture (Ports and Adapters)" (2005)
12. Evans, E. — "Domain-Driven Design" (2003)

---

*This completes the Phase 62 research series. The next step is the implementation plan.*
