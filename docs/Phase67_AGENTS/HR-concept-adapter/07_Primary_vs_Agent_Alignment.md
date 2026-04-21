# HR Agent — Architecture Alignment Audit: Primary vs. Agent Use Cases

> **Phase 67 Research** | Date: 2026-04-01
> Ensuring the HR Agent subsystem strengthens — not compromises — Prep's primary purpose as a universal MCP context server for AI IDEs and CLI assistants.

---

## 1. Prep's Identity Hierarchy

Prep serves two audiences in this priority order:

```
PRIORITY 1 (Primary):  AI IDE / CLI User
                        Human developer using Cursor, Claude Code, Windsurf, 
                        Antigravity, or any MCP-capable AI assistant.
                        They want better code context. Period.

PRIORITY 2 (Agent):    Autonomous Agent Worker
                        Paperclip/CrewAI/AutoGen agent running as a 
                        persistent, role-specific AI worker.
                        They want role-scoped, persistent context.
```

Everything we build for agents must **flow downhill to the primary use case**. If a feature only helps agents, it's a lower priority. If a feature helps agents AND IDE users, it's an accelerator.

---

## 2. Audit: Does the HR Agent Planning Affect the Primary Use Case?

### 2.1 Code Changes That Touch the Primary User Path

| HR Feature | Touches Primary? | Impact | Verdict |
|-----------|-----------------|--------|---------|
| `RoleSpec` dataclass | ❌ New module, no existing code modified | None | ✅ Safe |
| Paperclip adapter | ❌ New module, no existing code modified | None | ✅ Safe |
| `prep hr` CLI commands | ❌ New subcommand group, existing CLI untouched | None | ✅ Safe |
| Dashboard HR panel | ❌ New panel, existing panels untouched | None | ✅ Safe |
| Epistemic readiness scoring | ⚠️ Reads from `trace_epistemic.jsonl`, same files as MCP tools | **Read-only**. No writes, no locks. | ✅ Safe |
| KNOWLEDGE.md generation | ❌ New file generation, no existing paths | None | ✅ Safe |
| Auto-Populate | ⚠️ Uses the same embedding store + Thinking LLM | Read-only on embeddings. LLM call is a new scope. | ✅ Safe |
| Role Atlas caching | ✅ **Already exists** from Phase 64 | We're just consuming it, not changing it | ✅ Existing |
| `role` param on `prep`/`prep_search` | ✅ **Already exists** in Phase 67 | Already shipped. HR reads these results. | ✅ Existing |

**Verdict: The HR Agent subsystem is architecturally isolated.** It lives in a new `src/prep/services/hr_adapter/` module, new CLI subcommands, new API endpoints, and a new dashboard panel. It **reads** from existing Prep data stores (embeddings, epistemic, atlas) but **never writes** to them.

### 2.2 No Shared Mutable State

```
┌──────────────────────────────────────────────┐
│                  Prep Core                  │
│                                               │
│  Pipeline ──► trace_nodes.jsonl               │
│           ──► trace_edges.jsonl               │    READ ONLY
│           ──► trace_epistemic.jsonl ◄──────── HR Adapter
│           ──► embedding_store      ◄──────── HR Adapter
│           ──► atlas.json           ◄──────── HR Adapter
│           ──► atlas_roles/*.txt    ◄──────── HR Adapter
│                                               │
│  MCP Server ──► context endpoint              │
│             ──► search endpoint               │
│             ──► impact endpoint               │
│                                               │
└──────────────────────────────────────────────┘
                      │
                      │ READ ONLY
                      ▼
┌──────────────────────────────────────────────┐
│              HR Adapter (NEW)                 │
│                                               │
│  WRITES ONLY TO:                              │
│  ──► agents/{role}/AGENTS.md                  │
│  ──► agents/{role}/SOUL.md                    │
│  ──► agents/{role}/KNOWLEDGE.md               │
│  ──► .runprep/hr_roster.json                   │
│  ──► Paperclip API (external)                 │
│                                               │
└──────────────────────────────────────────────┘
```

**The HR Adapter is a pure consumer of Prep's knowledge.** It adds no load, no locks, no mutations to the primary pipeline.

---

## 3. Opportunities: Where Agent Work Improves the Primary Use Case

This is where it gets interesting. Several features we're building for agents are **just as valuable** for a developer in Cursor.

### 3.1 The `role` Parameter → Persona-Based Context for IDE Users

**What we built for agents:**
```
prep(role="cto")           → CTO-weighted atlas
prep_search(role="cto")    → Search scoped to CTO's files
```

**What this gives IDE users FOR FREE:**
```
prep(role="security")      → Security-focused atlas for a security review
prep(role="intern")        → Simplified high-level view for onboarding
prep_search(role="design") → Only UI/component files when working on design
```

A developer working in Cursor can type `role="security"` even though they're not a Paperclip agent. The role parameter is already universal — it was designed this way in Phase 64.

**Opportunity:** The HR Adapter's role discovery system (analyzing what roles a codebase needs) could **suggest roles** to IDE users via the dashboard. "Based on your codebase, these context scopes might be useful: `security`, `devops`, `frontend`."

### 3.2 Epistemic Readiness Score → Codebase Health for Everyone

**What we built for agents:**
```python
def compute_hr_readiness(project_id) -> HRReadiness:
    checks = {
        "pipeline_complete": ...,
        "minimum_files": ...,
        "has_modules": ...,
        "has_domain_tags": ...,
        ...
    }
```

**What this gives IDE users:** A **"codebase intelligence readiness"** indicator on the dashboard. "Prep is 85% ready to give you great context. Run the deep enrichment pipeline to improve." This helps everyday users understand whether Prep has enough data to be useful, not just HR agents.

**Opportunity:** Surface the readiness score in the main dashboard panel, not just the HR panel.

### 3.3 Auto-Populate → Context Scope Suggestions for Everyone

**What we built for agents:**
The Auto-Populate endpoint uses the Thinking LLM to select optimal files for a given role.

**What this gives IDE users:** A **"Focus Scope"** feature. "I'm working on authentication. Show me the most relevant files for auth work." Instead of the user manually checking boxes in the knowledge tree, Prep auto-selects based on a natural-language description.

**Opportunity:** Abstract auto-populate into a general "scope suggestion" feature:
```
# Agent use case (existing plan)
POST /projects/{pid}/scope/agents/cto/auto-populate

# IDE user case (new, powered by same engine)
POST /projects/{pid}/scope/suggest?focus="authentication"
POST /projects/{pid}/scope/suggest?focus="frontend redesign"
```

### 3.4 Drift Detection → Staleness Alerts for Everyone

**What we built for agents:** Drift detection compares role fitness scores across pipeline builds. When fitness drops, the agent's instructions may be stale.

**What this gives IDE users:** **"Your context may be stale"** warnings. If the user has been using `prep(role="security")` for a week and the security module has changed significantly, Prep can proactively show a notification: "The security module has changed since your last audit — consider re-running `prep(role='security')` for updated context."

### 3.5 KNOWLEDGE.md → MCP Instructions for Any AI

**What we built for agents:** KNOWLEDGE.md teaches an agent how to call Prep's MCP tools effectively.

**What this gives IDE users:** The same best-practice instructions can be emitted as **`prep.md` rules files** (already a feature). The Prep rules file (.cursorrules or AGENTS.md equivalent) already injects MCP tool instructions into AI system prompts.

**Opportunity confirmation:** KNOWLEDGE.md's tool-usage instructions are a specialized version of what the rules file already does. They should share a common generation template.

---

## 4. What We Should NOT Do

### 4.1 Do NOT Add Agent-Only Parameters to Core Tools

❌ **Bad:** Adding `agent_id`, `org_chart`, or `workforce` parameters to `prep` or `prep_search`
✅ **Good:** The `role` parameter is already universal and sufficient

### 4.2 Do NOT Gate Core Features Behind Paperclip

❌ **Bad:** "You need Paperclip installed to use role-based context"
✅ **Good:** Role-based context works for everyone. Paperclip is just one orchestrator adapter.

### 4.3 Do NOT Pollute the MCP Tool List

❌ **Bad:** Adding `prep_hr_generate`, `prep_hr_audit` as MCP tools available to every IDE user
✅ **Good:** HR tools are CLI-only (`prep hr generate`) and API-only (`POST /hr/generate`). The 5 core MCP tools stay clean for IDE users.

**Exception:** Later, once the system is proven, we _may_ add a `prep_hr` MCP tool for autonomous agents to self-manage their org chart. But that's a Phase 68+ feature, not Phase 67.

### 4.4 Do NOT Increase MCP Response Latency

❌ **Bad:** Adding HR-related processing to the `prep()` or `prep_search()` hot path
✅ **Good:** HR operations (generate, audit, sync) are background operations triggered by the user or on a schedule. They never touch the MCP tool response path.

---

## 5. The Revised Context Pipeline (Both Use Cases Side-by-Side)

```
┌─────────────────────────────────────────────────────────────┐
│                     Prep Platform                          │
│                                                              │
│  ┌─────────────────────┐   ┌──────────────────────────┐     │
│  │   Pipeline Engine    │   │    Knowledge Stores       │     │
│  │   (11 stages)        │──►│  trace_epistemic.jsonl    │     │
│  │                      │   │  embedding_store          │     │
│  │                      │   │  atlas.json               │     │
│  │                      │   │  atlas_roles/*.txt        │     │
│  └─────────────────────┘   │  trace_modules.jsonl      │     │
│                             │  observations.json        │     │
│                             └──────────┬───────────────┘     │
│                                        │                     │
│                           ┌────────────┼──────────┐          │
│                           │            │          │          │
│                    ┌──────▼──────┐ ┌──▼────┐ ┌──▼──────┐   │
│                    │ MCP Server  │ │  API  │ │   CLI   │   │
│                    │ (5 tools)   │ │(REST) │ │         │   │
│                    └──────┬──────┘ └──┬────┘ └──┬──────┘   │
│                           │           │         │           │
└───────────────────────────┼───────────┼─────────┼───────────┘
                            │           │         │
              ┌─────────────┼───────────┼─────────┼────────┐
              │             │           │         │        │
      ┌───────▼───────┐ ┌──▼──────────▼──┐  ┌──▼──────────┐
      │ PRIMARY USER  │ │  DASHBOARD     │  │ HR ADAPTER  │
      │               │ │  (management)  │  │ (agents)    │
      │ Cursor        │ │                │  │             │
      │ Claude Code   │ │ ┌────────────┐ │  │ Generate    │
      │ Windsurf      │ │ │ Main Panel │ │  │ Audit       │
      │ Antigravity   │ │ │ Focus Area │ │  │ Sync        │
      │ Any MCP IDE   │ │ │ KnowScope │ │  │ Adopt       │
      │               │ │ └────────────┘ │  │             │
      │ Uses:         │ │ ┌────────────┐ │  │ Uses:       │
      │ prep()      │ │ │  HR Panel  │ │  │ Same data   │
      │ prep_search │ │ │  (NEW)     │ │  │ as primary  │
      │ prep_impact │ │ │ Agent list │ │  │ + writes:   │
      │ prep_audit  │ │ │ Drift view │ │  │ AGENTS.md   │
      │ prep_observe│ │ │ Sync btn   │ │  │ SOUL.md     │
      │               │ │ └────────────┘ │  │ KNOWLEDGE.md│
      │ Optional:     │ │                │  │ roster.json │
      │ role="X"      │ │                │  │             │
      └───────────────┘ └────────────────┘  └─────────────┘
```

### Key Insight: Same Data, Different Lenses

| Capability | Primary IDE User | Agent Worker |
|-----------|-----------------|--------------|
| Structural overview | `prep()` | `prep(role="cto")` |
| Code search | `prep_search(query="auth")` | `prep_search(query="auth", role="cto")` |
| Impact analysis | `prep_impact(file="...")` | `prep_impact(file="...")` |
| Session memory | `prep_observe(save/get)` | `prep_observe(save/get)` |
| Health audit | `prep_audit()` | `prep_audit()` |
| Context scoping | Optional. `role=` or focus areas in dashboard | KNOWLEDGE.md + Knowledge Scope tree |
| Role atlas | Optional. Any user can call `prep(role=X)` | System-generated per agent role |
| Orchestrator sync | N/A | Paperclip API / file sync |

**The 5 MCP tools are identical for both users.** The only difference is that agents have pre-configured `role` parameters and pre-selected knowledge scopes. Everything the HR Adapter does is configuration management on top of the same core infrastructure.

---

## 6. Opportunities to Improve the Primary Use Case from HR Work

### 6.1 Focus Scope Suggestions (New Feature, Primary User Benefit)

**Current state:** Users set "Focus Areas" in the dashboard by manually selecting files/folders.

**Opportunity:** The same auto-populate engine that selects files for agent roles can suggest focus areas for ad-hoc tasks:

```
# In the dashboard, when a user says "I'm working on the API layer":
POST /projects/{pid}/scope/suggest
{
  "focus_description": "I'm refactoring the API layer",
  "max_files": 30
}

# Returns:
{
  "recommended_focus_areas": ["src/prep/api/", "src/prep/mcp/"],
  "recommended_paths": ["src/prep/api/routers/projects/atlas_endpoints.py", ...],
  "confidence": 0.88
}
```

This gives IDE users the same "smart file selection" that agents get, without requiring any role definition.

### 6.2 Role Suggestions for IDE Users (Dashboard Feature)

**Current state:** Users must know about the `role=` parameter and manually type role names.

**Opportunity:** The dashboard could show **suggested roles** based on codebase analysis:
```
┌─────────────────────────────────────────────────┐
│  🔍 Context Scopes                               │
│                                                   │
│  Based on your codebase, try these scopes:        │
│                                                   │
│  prep(role="security")   — 23 relevant files    │
│  prep(role="frontend")   — 47 relevant files    │
│  prep(role="devops")     — 12 relevant files    │
│                                                   │
│  These filter your context to the most relevant    │
│  files for each focus area.                       │
└─────────────────────────────────────────────────┘
```

### 6.3 Context Budget Insights (Dashboard Feature)

**Current state:** Users don't see how many tokens their context uses or whether it's well-targeted.

**Opportunity:** Show a "Context Quality" indicator:
```
┌─────────────────────────────────────────────────┐
│  📊 Context Quality                              │
│                                                   │
│  Last prep() call: 4,200 chars (est. 1,050 tk) │
│  Coverage: 12 modules, 8 hub files                │
│  Epistemic confidence: 0.87 avg                   │
│                                                   │
│  💡 Tip: Use role="backend" to focus on the       │
│  67 backend files instead of all 1,143 files.     │
└─────────────────────────────────────────────────┘
```

---

## 7. Implementation Priority (Revised with Primary-First Ordering)

| Priority | Feature | Benefits Primary? | Benefits Agents? |
|----------|---------|-------------------|-------------------|
| **P0** | Core engine (readiness + generate) | ⚠️ Readiness score is universal | ✅ |
| **P0** | KNOWLEDGE.md generation | ⚠️ Template shares with rules files | ✅ |
| **P1** | Focus Scope Suggestions API | ✅ **Big win for IDE users** | ✅ (powers auto-populate) |
| **P1** | `prep hr generate` CLI | ❌ Agent-only | ✅ |
| **P1** | Paperclip adapter | ❌ Agent-only | ✅ |
| **P2** | Role suggestions in dashboard | ✅ Helps IDE users discover `role=` | ✅ |
| **P2** | Dashboard HR panel | ❌ Agent-only | ✅ |
| **P2** | Drift detection | ⚠️ Staleness alerts for everyone | ✅ |
| **P3** | Context quality dashboard widget | ✅ **Primary user value** | ✅ |
| **P3** | CrewAI/AutoGen adapters | ❌ Agent-only | ✅ (future) |

### The Key Takeaway

**Build the Focus Scope Suggestion engine FIRST as a general-purpose feature.** Then the HR Adapter's auto-populate is just a wrapper that passes a role description instead of a user's ad-hoc focus query. Same engine, two UIs.

---

## 8. Verified: MCP Tool Surface Remains Clean

The current 5 production MCP tools are:

| # | Tool | Primary? | Agent? | Changes Needed? |
|---|------|----------|--------|-----------------|
| 1 | `prep` | ✅ | ✅ (with role=) | ❌ None |
| 2 | `prep_search` | ✅ | ✅ (with role=) | ❌ None |
| 3 | `prep_impact` | ✅ | ✅ | ❌ None |
| 4 | `prep_audit` | ✅ | ✅ | ❌ None |
| 5 | `prep_observe` | ✅ | ✅ | ❌ None |

**Zero changes to the MCP tool surface.** The HR Adapter is a CLI + API + Dashboard feature that sits outside the MCP tool path entirely.

The `role` parameter on tools 1 and 2 is already deployed and working. It was designed universally from the start (Phase 64) — it serves IDE users wanting focused context just as well as it serves autonomous agents.
