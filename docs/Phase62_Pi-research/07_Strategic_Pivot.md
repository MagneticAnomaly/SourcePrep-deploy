# Phase 62 — Strategic Pivot: Knowledge Provider, Not Project Manager

> **Research Document 7 of 7** | Phase 62: Strategic Direction
> Date: 2026-03-30

---

## 1. The Insight

> *"I think we may not need to finish building the roadmap or goalposts, but instead simply build these items as epistemology or proactive thinking to enhance tools like Paperclip — that way we own the knowledge and knowledge gathering and then users can choose their own method of project management."*

This is a **fundamental strategic pivot** that aligns CoDRAG more cleanly with its Layer 1 identity. Let's examine what it means.

---

## 2. What CoDRAG Currently Builds (and Shouldn't)

### 2.1 The Roadmap (Phase 59) — Project Management Features

| Feature | What It Does | Layer |
|---|---|---|
| 9-tier timeline | Visual sprint-like kanban | 🟥 Layer 3-4 (PM) |
| North Star Goalposts | Strategic goal anchoring | 🟥 Layer 3-4 (PM) |
| Tier promotion | Drag-to-reorder, state machine | 🟥 Layer 3-4 (PM) |
| D3.js timeline visualization | Gantt-chart-like view | 🟥 Layer 3-4 (PM) |
| GitHub Issues sync | Bidirectional issue tracking | 🟥 Layer 3-4 (PM) |
| Sprint mapping | Map tiers to iterations | 🟥 Layer 3-4 (PM) |
| Fork visualization | Decision tree UI | 🟥 Layer 3-4 (PM) |

**These are project management features.** They compete directly with:
- 🏢 Paperclip (goal → task hierarchy with heartbeat scheduling)
- 📊 Linear (issues, sprints, roadmaps)
- 📋 Jira (epics, stories, sprints)
- 📌 GitHub Projects (kanban, roadmap views)
- 🗺️ Asana (portfolios, timelines)

CoDRAG will never build a better project manager than any of these. **This is not where CoDRAG wins.**

### 2.2 What CoDRAG DOES Build Well (and Should Keep)

| Feature | What It Does | Layer |
|---|---|---|
| ActionItem model | Structured knowledge output | ✅ Layer 1 (Intelligence) |
| Health Scanner | Detect code issues automatically | ✅ Layer 1 (Intelligence) |
| Advisor Proposals | LLM-generated improvement suggestions | ✅ Layer 1 (Intelligence) |
| Spaghetti Scorer | Identify refactoring urgency | ✅ Layer 1 (Intelligence) |
| TODO/FIXME Scanner | Surface tech debt from code | ✅ Layer 1 (Intelligence) |
| Product Intent | Anchor analysis to user's vision | ✅ Layer 1 (Intelligence) |
| `codrag_audit` MCP tool | Export findings to any agent | ✅ Layer 1 (Intelligence) |

> [!IMPORTANT]
> **The ActionItem model (`action_item.py`) is already the right abstraction.** It produces structured knowledge with: title, description, category, severity, priority, effort, affected_files, suggested_action, sub-tasks, evidence. This is *exactly* what project management tools consume.

---

## 3. The Pivot: From "Plan Manager" to "Opportunity Engine"

### Current Architecture (Building PM Features)

```
CoDRAG generates knowledge
  → CoDRAG stores it in its own Roadmap tier system
    → CoDRAG displays it in its own Timeline UI
      → User manages it inside CoDRAG's dashboard
        → CoDRAG tries to execute via "Execute with LLM"
```

**Problems:**
- Duplicates Paperclip/Linear/Jira functionality
- Locks knowledge into CoDRAG's proprietary UI
- Forces users to adopt CoDRAG's project management model
- Building PM features is a never-ending rabbit hole

### Proposed Architecture (Knowledge Provider)

```
CoDRAG generates knowledge (ActionItems, Proposals, Findings)
  → CoDRAG exposes it via universal interfaces
    ├→ MCP tool: codrag_audit action="advise"     (any MCP agent)
    ├→ CLI: codrag advise --format json             (any terminal agent)
    ├→ HTTP API: POST /projects/{id}/advise         (any integration)
    └→ AGENTS.md: auto-written opportunity summary  (passive, all agents)
  → User's chosen system manages it
    ├→ Paperclip picks it up as agent goals
    ├→ Claude Code reads it and proposes implementation
    ├→ Pi reads it via skill and acts on it
    ├→ User manually imports into Linear/Jira/GitHub Issues
    └→ Automation middleware (n8n, Zapier) pushes to PM tool
```

**Benefits:**
- CoDRAG stays at Layer 1 (its strength)
- Users choose their own PM workflow
- Knowledge output is composable and portable
- No PM feature maintenance burden
- Works with tools that don't exist yet

---

## 4. What This Means for Existing Features

### 4.1 Keep & Enhance

| Feature | Current Status | Action |
|---|---|---|
| **ActionItem model** | ✅ Shipped | **Enhance**: Add `export_format` field for structured JSON/SARIF output |
| **Health Scanner** | ✅ Shipped | **Keep**: This is pure code intelligence |
| **Advisor Proposals** | ✅ Shipped | **Reframe**: These are "opportunities," not "roadmap items" |
| **Spaghetti Scorer** | ✅ Shipped | **Keep**: This is pure code intelligence |
| **`codrag_audit`** | ✅ Shipped | **Enhance**: Better structured output for external tool consumption |
| **Product Intent** | ✅ Shipped | **Keep**: Anchors analysis to user's vision |
| **Observations** | ✅ Shipped | **Keep**: Cross-session memory is pure intelligence |

### 4.2 Simplify (Remove PM Features)

| Feature | Current Status | Action |
|---|---|---|
| **9-tier Roadmap** | 📋 Planned (Phase 59) | **Don't build** — this is Paperclip/Linear territory |
| **D3.js Timeline UI** | 📋 Planned | **Don't build** — UI lock-in |
| **GitHub Issues sync** | 📋 Planned | **Don't build** — middleware (n8n/Zapier) does this better |
| **Sprint mapping** | 📋 Planned | **Don't build** — PM tool feature |
| **Fork visualization** | 📋 Planned | **Don't build** — decision records are better as text |
| **North Star Goalposts** | ✅ Partly shipped | **Simplify** → Keep as "Product Intent" (text field) |
| **Tier promotion logic** | 📋 Planned | **Don't build** — state machine unnecessary for knowledge output |
| **Execute with LLM** | 📋 Planned | **Don't build** — let the agent (Claude Code/Pi) handle execution |

### 4.3 The Dashboard's New Role

Instead of a roadmap timeline, the CoDRAG dashboard becomes a **knowledge explorer**:

```
┌─────────────────────────────────────────────────────────────┐
│  CoDRAG Dashboard                                            │
├────────────┬──────────────┬────────────┬────────────────────┤
│  Overview  │  Search      │  Advisor   │  Settings          │
│  (Atlas)   │  (Code)      │  (NEW)     │                    │
├────────────┴──────────────┴────────────┴────────────────────┤
│                                                              │
│  ┌─ Advisor Panel ─────────────────────────────────────────┐ │
│  │                                                          │ │
│  │  Opportunities (23 found)          [Refresh] [Export]    │ │
│  │                                                          │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │ 🔴 P0: Circular dependency in auth module           │ │ │
│  │  │ 3 files • architecture • effort: medium              │ │ │
│  │  │ [Copy for AI] [Export JSON] [Dismiss]                │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │                                                          │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │ 🟡 P1: Missing error handling in API routes          │ │ │
│  │  │ 7 files • quality • effort: small                    │ │ │
│  │  │ [Copy for AI] [Export JSON] [Dismiss]                │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │                                                          │ │
│  │  [Export All as JSON] [Copy All for AI] [Push to API]   │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Key change:** No tiers, no drag-and-drop, no state machine. Just:
1. **View** opportunities (sorted by priority/severity)
2. **Copy for AI** (paste into Claude Code/Cursor/Antigravity/Pi session)
3. **Export** (JSON for Paperclip, CSV for Jira, SARIF for GitHub)
4. **Dismiss** (not relevant to current goals)

---

## 5. Where Pi and Claude Code Boundaries Are

> *"This is where I get confused because where does Pi end and Claude Code begin."*

The confusion is valid because **Pi and Claude Code are at the same layer** (Layer 3). They're both execution harnesses. Here's the clarity:

```
                    ┌─────────────────────┐
 "What should I     │  CoDRAG (Layer 1)   │   "Here are 23 opportunities
  work on?"         │  Knowledge Engine    │    ranked by priority"
                    └────────┬────────────┘
                             │
                    Structured ActionItems
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                   │
    ┌─────┴──────┐    ┌─────┴──────┐    ┌──────┴─────┐
    │Claude Code │    │    Pi      │    │  Paperclip │
    │(Layer 3)   │    │(Layer 3)   │    │(Layer 4)   │
    │            │    │            │    │            │
    │ Takes one  │    │ Takes one  │    │ Takes many │
    │ ActionItem │    │ ActionItem │    │ ActionItems│
    │ and does   │    │ and does   │    │ and assigns│
    │ the work   │    │ the work   │    │ to agents  │
    └────────────┘    └────────────┘    └────────────┘
```

### The Distinction

| Aspect | Claude Code | Pi | When to use |
|---|---|---|---|
| **Session model** | Persistent, sub-agents | One-shot or persistent | Claude Code for complex, Pi for simple/custom |
| **MCP support** | ✅ Native | ❌ CLI only | Claude Code for MCP-heavy stacks |
| **Model choice** | Claude only | Any provider | Pi when you need Ollama/other models |
| **Permission model** | Smart auto-mode | YOLO or DIY | Claude Code in production, Pi in dev |
| **Context control** | Automated (opaque) | Manual (transparent) | Pi when context matters, Claude Code for convenience |
| **Extension model** | Plugins + MCP | TypeScript extensions | Both are extensible, different ecosystems |

### Who Orchestrates Whom?

```
No orchestrator:        User → Claude Code → CoDRAG (via MCP)
                        User → Pi → CoDRAG (via CLI)

With Paperclip:         Paperclip → Claude Code → CoDRAG (via MCP)
                                                       ↑
                                    Pi is NOT here — Paperclip uses Claude Code

With Pi as orchestrator: User → Pi (SDK mode) → Claude Code subprocess
                                              → CoDRAG (via CLI)
```

**Bottom line:** In the Paperclip stack, Pi doesn't appear. Pi is an *alternative* to Claude Code, not a companion. A user either uses Claude Code *or* Pi as their agent, rarely both simultaneously.

---

## 6. Do We Need GitHub Integration?

> *"I also question if we need GitHub integrations and maybe we just need to be able to interface with existing management workflows and not try to build them in."*

### The Answer: No. CoDRAG Should NOT Build GitHub Integration.

**Why not:**

| Argument | Detail |
|---|---|
| **Maintenance burden** | GitHub API changes, OAuth flows, rate limiting, webhooks — all PM infrastructure |
| **Better alternatives exist** | n8n, Zapier, Unito, Exalate — all handle GitHub ↔ PM sync as their core business |
| **Agent-native approach** | Claude Code already has native GitHub access. Pi can `git` and `gh`. Why duplicate? |
| **Lock-in risk** | Building GitHub sync locks CoDRAG to GitHub. What about GitLab? Bitbucket? |
| **Scope creep** | GitHub sync leads to "also sync to Linear/Jira/Asana" which is infinite work |

### What CoDRAG SHOULD Do Instead

**Export structured data formats** that any tool can consume:

```bash
# Export opportunities as JSON (feed to Paperclip API, n8n, etc.)
codrag advise --format json > opportunities.json

# Export as SARIF (GitHub Code Scanning natively ingests this)
codrag advise --format sarif > codrag-findings.sarif

# Export as CSV (import to Linear, Jira, Sheets)
codrag advise --format csv > opportunities.csv

# Export as Markdown (paste into GitHub Issue, CLAUDE.md, etc.)
codrag advise --format md > opportunities.md
```

**The SARIF format is especially powerful**:
- GitHub Code Scanning displays SARIF results natively in the Security tab
- No GitHub API integration needed — just commit the SARIF file or upload via CI
- Industry standard (Microsoft-defined, adopted by GitHub, CodeQL, Snyk, etc.)

---

## 7. The "Opportunity Engine" MCP Surface

### Current MCP: `codrag_audit`

The existing `codrag_audit` tool already does most of this:
- `action="scan"` → run health checks
- `action="advise"` → get forward-looking proposals
- `action="refactor"` → get code context for specific findings

### Enhanced MCP: `codrag_opportunities`

Rename/extend to make the "knowledge provider" role explicit:

```
codrag_opportunities:
  action: "discover"    → Run all scanners, return structured opportunities
  action: "detail"      → Get deep context for a specific opportunity
  action: "export"      → Export in a specific format (json, sarif, csv, md)
  
  Filters:
    category: architecture | security | quality | tech_debt | feature
    min_priority: P0 | P1 | P2 | P3
    min_severity: critical | warning | info | suggestion
```

This makes CoDRAG's value proposition crystal clear:
> *"CoDRAG discovers opportunities. You choose how to manage them."*

---

## 8. What We Save By NOT Building

### Dev Time Saved

| Dropped Feature | Estimated Effort |
|---|---|
| D3.js Timeline UI (9-tier) | 2-3 weeks |
| Roadmap state machine | 1 week |
| GitHub Issues sync | 1-2 weeks |
| Sprint mapping logic | 1 week |
| Fork visualization | 1-2 weeks |
| Tier promotion triggers | 1 week |
| North Star management UI | 1 week |
| **Total saved** | **8-12 weeks** |

### What We Build Instead

| New Feature | Estimated Effort |
|---|---|
| `--format json/sarif/csv/md` CLI export | 2-3 days |
| Simplified Advisor panel (no tiers) | 1 week |
| SARIF output integration | 2-3 days |
| Documentation: config profiles & export guides | 2-3 days |
| Pi skill file + CLI wrappers | 1-2 days |
| **Total new work** | **~2-3 weeks** |

**Net savings: 6-9 weeks of engineering time** redirected to improving intelligence quality.

---

## 9. Revised CoDRAG Identity

### Before (Confused)

> *"CoDRAG: Local-first code intelligence + project management + roadmap planning + GitHub integration + execution engine"*

### After (Clear)

> *"CoDRAG: The codebase intelligence engine. We map your code's structure, find opportunities for improvement, and make that knowledge available to any tool you already use."*

### The Product Hierarchy

```
What CoDRAG IS:
  ├── Structural code intelligence (the graph)
  ├── Semantic code search (embeddings + LOD)
  ├── Opportunity discovery (audit + advisor)
  ├── Cross-session memory (observations)
  └── Knowledge export (MCP, CLI, HTTP, AGENTS.md)

What CoDRAG is NOT:
  ├── A project manager (use Paperclip, Linear, Jira)
  ├── A coding agent (use Claude Code, Pi, Cursor)
  ├── A CI/CD pipeline (use GitHub Actions)
  ├── A code review tool (use CodeRabbit, Reviewbot)
  └── A sprint planner (use your existing PM workflow)
```

---

## 10. Decision Summary

| Question | Decision | Rationale |
|---|---|---|
| Finish Roadmap (Phase 59)? | **No** — simplify to Advisor panel | PM features belong at Layer 3-4 |
| Finish Goalposts? | **Simplify** — keep as Product Intent text | North Stars are PM concepts |
| Build GitHub integration? | **No** — export SARIF/JSON instead | Middleware handles sync better |
| Build Pi-specific features? | **Low priority** — build universal CLI export first | Agent-agnostic > agent-specific |
| Build "Execute with LLM"? | **No** — let agents handle execution | CoDRAG provides knowledge, not action |
| What to build instead? | **Export formats** (JSON, SARIF, CSV, MD) + simplified Advisor panel | Maximizes reach, minimizes maintenance |

---

## 11. Next Steps

1. **Formalize** this strategic direction as the Phase 62 outcome
2. **Simplify** the existing Advisor/Goalposts panel — remove tier complexity
3. **Add export formats** to `codrag advise` (JSON, SARIF, CSV, Markdown)
4. **Document** configuration profiles (from [06_Ecosystem_And_Configurations.md](./06_Ecosystem_And_Configurations.md))
5. **Sunset** Phase 59 Roadmap R&D — mark as superseded by this strategic pivot
6. **Create** Pi skill file + universal CLI wrappers (low effort, high reach)

---

*This document represents a strategic inflection point for CoDRAG. It should be reviewed and approved before any further Roadmap/Goalposts development.*
