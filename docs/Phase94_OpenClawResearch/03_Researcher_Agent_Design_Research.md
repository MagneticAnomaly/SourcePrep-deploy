# Phase 94 — CoDRAG as Research Context Provider

**Date:** 2026-04-09
**Status:** Design research — no implementation
**Prerequisite:** Phase 94 docs 01 (OpenClaw research) and 02 (minimal integration path)

---

## 1. The Reframe

The question is NOT "how does CoDRAG run a researcher agent?"

The question IS "when an external tool (Paperclip, OpenClaw, a human with a UI) decides to research something about a codebase, what does CoDRAG need to provide so that research is well-informed?"

CoDRAG is Layer 1. It doesn't decide what to research, when, or what to do with findings. It provides the structural context that makes research productive.

```
WHO DECIDES          WHO EXECUTES           WHO PROVIDES CONTEXT
─────────            ────────────           ────────────────────
Paperclip            OpenClaw               CoDRAG
(governance,         (web access,           (codebase structure,
 task routing,        scheduling,            dependencies,
 human review)        messaging)             impact analysis)
```

---

## 2. What a Researcher Needs from CoDRAG

When Paperclip dispatches an OpenClaw agent (or a human opens a UI) to research something like "what changed in FastAPI 0.115 and does it affect us?", the researcher needs:

### 2.1 Dependency Context

**"What external packages does this codebase use and where?"**

| Question | CoDRAG Tool | Current Status |
|----------|-------------|----------------|
| Which external packages are imported? | `codrag_search(query="fastapi", intent="trace")` | Works today — finds import chains |
| Which files use a specific external API? | `codrag_search(query="on_event lifecycle")` | Works today — semantic search |
| What depends on files that import X? | `codrag_impact(file_path="src/codrag/server.py")` | Works today — blast radius |
| What's the overall dependency footprint? | `codrag()` | Partial — hub files listed, but no structured external dep manifest |

**Gap:** CoDRAG doesn't expose a clean "here are your external dependencies and where they're used" view. The data exists in the trace graph (import edges), but there's no tool query that returns a dependency-centric view.

### 2.2 Architectural Context

**"Would this external change conflict with our design decisions?"**

| Question | CoDRAG Tool | Current Status |
|----------|-------------|----------------|
| What are our architecture concepts? | `codrag_concepts(action="get", category="architecture")` | Works today |
| Are there constraints relevant to X? | `codrag_concepts(action="get", query="lifecycle management")` | Works today |
| What immune system rules apply? | `codrag_audit(action="antibodies")` | Works today |

**Gap:** None. Concepts and antibodies already serve this purpose.

### 2.3 Impact Assessment

**"If this external change breaks something, how bad is it?"**

| Question | CoDRAG Tool | Current Status |
|----------|-------------|----------------|
| What files are affected? | `codrag_impact(file_path="...", direction="dependents")` | Works today |
| Is the affected file a hub? | `codrag()` — hub files section | Works today |
| How many modules are touched? | `codrag_impact` + `codrag()` module map | Works today (manual cross-reference) |

**Gap:** No single query that says "if this external package's API changes, here's your exposure." The researcher has to chain `codrag_search` (find usage) → `codrag_impact` (find dependents) manually. This works but could be smoother.

### 2.4 Historical Context

**"Have we dealt with this kind of change before?"**

| Question | CoDRAG Tool | Current Status |
|----------|-------------|----------------|
| Any observations about this dependency? | `codrag_observe(action="get", query="fastapi migration")` | Works today |
| Past research on this topic? | `codrag_observe(action="get", category="pattern")` | Works today |

**Gap:** None, if prior observations were saved. The observation store is the memory layer.

---

## 3. The Real Gaps

Inverting the perspective — CoDRAG as context provider rather than agent — reveals that the gaps are smaller and more focused than the previous doc suggested:

### Gap 1: External Dependency View

**What's missing:** A query like `codrag_search(query="external dependencies", intent="discover")` that returns a structured view:

```json
{
  "external_dependencies": [
    {
      "package": "fastapi",
      "version": "0.110.0",
      "import_count": 23,
      "importing_files": ["src/codrag/server.py", "src/codrag/api/..."],
      "hub_files_affected": ["server.py"],
      "modules_affected": ["Pipeline Orchestration Engine", "LLM Orchestration Engine"]
    }
  ]
}
```

**Where it comes from:** The trace graph already has import edges. `pyproject.toml` / `package.json` / `Cargo.toml` have version pins. The data exists — it just isn't assembled into a dependency-centric view.

**Effort:** This is a CoDRAG enhancement — a new query mode or a new tool parameter. Not an OpenClaw concern.

**Value:** High. Every researcher (human or agent) needs this as step 1.

### Gap 2: "Exposure Report" for a Package

**What's missing:** A compound query like `codrag_impact(package="fastapi")` that does the search → impact chain automatically:

1. Find all files importing `fastapi`
2. Run impact analysis on each
3. Aggregate into a single exposure report

**Where it comes from:** `codrag_search` + `codrag_impact` chained. Today the researcher has to do this manually in multiple calls.

**Effort:** Could be a convenience wrapper in the MCP tool layer, or just documented as a multi-step recipe for agent SOUL.md configs.

**Value:** Medium. It's a UX improvement for agent consumers, not new capability.

### Gap 3: Observation Provenance

**What's missing:** When a researcher (human or agent) saves a finding via `codrag_observe`, there's no structured metadata about source, confidence, or authorship. All observations look the same regardless of origin.

**Current schema:** `content` (string), `category` (enum), `file_path` (optional anchor)

**What's needed:** Optional fields like `source_url`, `author` (human vs. agent name), `confidence` (0-1). This lets downstream consumers (humans, Paperclip, UIs) filter and trust-score observations.

**Effort:** Minor schema extension to the observation store.

**Value:** Medium. Becomes important when multiple agents and humans are writing observations.

---

## 4. What CoDRAG Should Build (Knowledge Provider Enhancements)

These are CoDRAG-side improvements that make it a better context source for ANY researcher — OpenClaw, Paperclip agent, human with a dashboard, or future tools we haven't imagined:

### Priority 1: External Dependency View

Add a query mode to `codrag_search` or `codrag` that returns a structured dependency manifest cross-referenced with the trace graph.

**Why:** This is the single most useful piece of context for any external research task. "What do we depend on and where?" is always the first question.

**Serves:** OpenClaw agents, Paperclip agents, dashboard UI, CLI users.

### Priority 2: Multi-Step Recipe Documentation

Document the standard research query patterns as recipes in AGENTS.md / SOUL.md templates:

```
Recipe: "Check if dependency update affects us"
1. codrag_search(query="<package name>", intent="trace") → find usage
2. codrag_impact(file_path=<each result>) → find blast radius
3. codrag_concepts(query="<relevant domain>") → check constraints
4. codrag_observe(query="<package name>") → check prior findings
```

**Why:** Until Gap 2 (compound queries) is built, documenting the multi-step pattern lets agents and humans do it manually. Zero CoDRAG code changes.

**Serves:** All agent consumers. This goes in the OpenClaw SOUL.md, Paperclip agent configs, and AGENTS.md.

### Priority 3 (Future): Observation Provenance

Extend the observation schema with optional `source`, `author`, `confidence` fields. Non-breaking — existing observations work unchanged.

**Why:** Becomes important when the write path is used by multiple sources. Not urgent today.

**Serves:** Any system that reads observations and needs to assess trustworthiness.

---

## 5. What CoDRAG Should NOT Build

| Item | Why Not |
|------|---------|
| Research agent runtime | That's OpenClaw/Paperclip's job. CoDRAG is Layer 1. |
| Web browsing / URL fetching | Not CoDRAG's domain. Agent runtimes handle this. |
| Scheduling / cron triggers | Gateway/orchestrator concern. Not CoDRAG's domain. |
| Human review UI for findings | Paperclip or a dedicated UI handles governance. |
| Notification routing | OpenClaw has 24+ channels. CoDRAG doesn't need one. |
| Confidence scoring of external findings | The researcher (Paperclip/OpenClaw) scores its own findings. CoDRAG stores what it's told. |

---

## 6. Updated Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ GOVERNANCE (decides what, when, who reviews)                     │
│                                                                  │
│  Paperclip: "Research FastAPI 0.115 impact. Assign to OpenClaw. │
│              Route findings to #architecture for review."        │
│                                                                  │
│  Human: Reviews findings in Paperclip UI or chat thread.         │
│         Approves/rejects before action is taken.                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ dispatches task
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ EXECUTION (does the research)                                    │
│                                                                  │
│  OpenClaw agent:                                                 │
│    1. Calls CoDRAG for codebase context (MCP)                   │
│    2. Browses web for changelogs, CVEs, docs (web skills)       │
│    3. Cross-references external findings with CoDRAG results    │
│    4. Reports back to Paperclip / chat channel                  │
│                                                                  │
│  OR: Human developer doing manual research with CoDRAG CLI      │
│  OR: Future agent framework we haven't built for yet            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ queries for context
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ KNOWLEDGE (provides codebase intelligence)                       │
│                                                                  │
│  CoDRAG MCP:                                                    │
│    - codrag          → structural overview, modules, hubs       │
│    - codrag_search   → "where do we use <package API>?"         │
│    - codrag_impact   → "what breaks if <file> changes?"         │
│    - codrag_concepts → "what constraints apply here?"           │
│    - codrag_observe  → "what do we already know about this?"    │
│    - codrag_audit    → "what structural issues exist?"          │
│                                                                  │
│  NEW: External dependency view (Priority 1 enhancement)          │
│    - "What packages do we use, where, and how deeply?"          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. What This Means for OpenClaw Specifically

OpenClaw doesn't get special treatment. It's one of several possible execution runtimes that consume CoDRAG via MCP. The integration from doc 02 (Minimal Integration Path) is complete and correct:

1. Connect to CoDRAG MCP via stdio (works today)
2. SOUL.md constrains agent behavior (doc 02, section 4)
3. Recipes tell the agent how to chain CoDRAG queries for research tasks (this doc, section 4)

The only OpenClaw-specific artifact is the SOUL.md template, which is documentation, not code.

---

## 8. Next Steps

| Step | Owner | Effort |
|------|-------|--------|
| Write multi-step research recipes into AGENTS.md generation | CoDRAG | ~1 day |
| Design external dependency view query | CoDRAG | ~2 days design |
| Build external dependency view | CoDRAG | ~3-5 days |
| Test OpenClaw agent with recipes (manual, one dependency) | Integration | ~1 day |
| Observation provenance schema extension | CoDRAG (future) | ~1-2 days |

All steps improve CoDRAG for every consumer, not just OpenClaw. That's the point.
