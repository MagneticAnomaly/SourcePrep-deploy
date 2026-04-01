# HR Agent — Context Delivery Pipeline & KNOWLEDGE.md Design

> **Phase 67 Research** | Date: 2026-04-01
> How KNOWLEDGE.md, MCP tools, embeddings, role atlases, and knowledge scopes work together to deliver optimal context to agents. The complete context pipeline from CoDRAG's epistemic graph to an agent's working memory.

---

## 1. The Problem: What Does an Agent Actually Need?

An agent running as a Paperclip worker needs **three layers of context** to do good work:

| Layer | What It Is | When It's Needed | How It Changes |
|-------|-----------|-------------------|----------------|
| **Static Identity** | Who am I, what do I do, what are my guardrails | Every heartbeat cycle | Rarely (only when role drifts) |
| **Structural Orientation** | What does this codebase look like at a high level | Every heartbeat cycle | After pipeline rebuilds |
| **Dynamic Working Context** | Specific files, symbols, and relationships relevant to my current task | Per-task, mid-execution | Every few seconds during work |

The question is: **which CoDRAG mechanism delivers each layer?**

---

## 2. Current Context Delivery Mechanisms (Inventory)

CoDRAG already has multiple context delivery channels. They were built independently. The HR Adapter needs to orchestrate them into a coherent pipeline.

### 2.1 AGENTS.md (Static, Injected at Startup)

```markdown
# CTO — Chief Technology Officer

You are the CTO of [Project]...

## Priorities
1. ...

## Knowledge Sources
- src/codrag/core/ — Core engine logic
- ...
```

**Delivered via:** Paperclip's `promptTemplate` field (concatenated into the system prompt).
**Frequency:** Once per agent creation (refreshed on `codrag hr sync`).
**Content:** Behavioral instructions, priorities, relationships.
**Cost:** ~1000-2000 tokens.

### 2.2 SOUL.md (Static, Injected at Startup)

Identity, values, guardrails, communication style.
**Same delivery mechanism as AGENTS.md** — concatenated into promptTemplate.
**Cost:** ~500-800 tokens.

### 2.3 Role Atlas (Semi-Static, Cached)

```
codrag(role="cto") → GET /projects/{id}/atlas?role=cto → atlas_roles/cto.txt
```

**What it returns:** A role-filtered structural overview of the codebase. Module summaries, hub files, architecture layers — all weighted by the CTO's RoleVector.

**Delivered via:** MCP tool call response (appended to context by the AI).
**Frequency:** Once per session (cached until pipeline rebuilds).
**Content:** 1500-3000 chars of structural orientation.
**Cost:** ~800-1200 tokens.

### 2.4 Semantic Search (Dynamic, Per-Query)

```
codrag_search(query="authentication flow", role="cto")
```

**What it returns:** Relevant code chunks from embeddings, expanded via trace edges, filtered by the role's knowledge scope.

**Delivered via:** MCP tool call response.
**Frequency:** Multiple times per task.
**Content:** Up to `max_chars` (default 12,000) of code context.
**Cost:** ~3000-6000 tokens per call.

### 2.5 Impact Analysis (Dynamic, Per-File)

```
codrag_impact(file_path="src/auth/login.py")
```

**What it returns:** Blast radius — what depends on this file, what breaks if it changes.

**Delivered via:** MCP tool call response.
**Frequency:** Before making code changes.
**Content:** Dependency tree summary.
**Cost:** ~500-1500 tokens per call.

### 2.6 Knowledge Scope / Agent File Tree (Configuration)

Dashboard UI: checkboxes on folders/files that define which files this role can search.

**What it does:** Filters the embedding search to only return results within the role's scope.
**Delivered via:** Backend filter on the vector search query (not visible to the agent).
**Frequency:** Read at every `codrag_search` call.
**Content:** Not sent to agent — it's a backend filter.
**Effect:** Prevents a UX Designer from getting results about infrastructure code.

### 2.7 Auto-Populate (One-Shot Configuration)

```
POST /projects/{pid}/scope/agents/{agent_role}/auto-populate
```

**What it does:** Uses the Thinking LLM to vet the Top-100 files and select the optimal scope for a given role.
**Delivered via:** Sets the knowledge scope checkboxes (2.6 above).
**Frequency:** Once per role setup (re-run on demand).
**Content:** A list of file paths — not context directly.

### 2.8 Observations (Persistent Cross-Session Memory)

```
codrag_observe(action="save", content="The auth module uses JWT with RSA keys")
codrag_observe(action="get", query="auth")
```

**What it does:** Stores/retrieves facts the agent discovered in previous sessions.
**Delivered via:** MCP tool call response.
**Frequency:** Save during work, retrieve at session start.
**Content:** Short factual statements (~200 chars each).

---

## 3. The Redundancy Problem

Right now, several mechanisms overlap:

| Content | AGENTS.md | Role Atlas | codrag_search | Knowledge Scope |
|---------|-----------|------------|---------------|-----------------|
| Module overview | ❌ | ✅ | ❌ | ❌ |
| Key files list | ⚠️ (Knowledge Sources) | ✅ (hub files) | ❌ | ✅ (configuration) |
| Code context | ❌ | ❌ | ✅ | ❌ |
| Role identity | ✅ | ❌ | ❌ | ❌ |
| Search scope | ❌ | ❌ | ❌ | ✅ |

The **Knowledge Sources** section in AGENTS.md and the **Knowledge Scope** file tree overlap but serve different purposes:
- AGENTS.md's Knowledge Sources = a human-readable list of reference docs (for the agent to know about)
- Knowledge Scope = a machine-readable filter (for the backend to restrict search results)

KNOWLEDGE.md needs to bridge this gap.

---

## 4. KNOWLEDGE.md — The Integration Layer

**KNOWLEDGE.md is the CoDRAG-specific context injection document.** It tells the agent:
1. **How to access CoDRAG** (which tools to call, with what parameters)
2. **What the codebase looks like right now** (snapshot of role atlas at generation time)
3. **Where to focus** (files auto-populated as high-relevance for this role)

It is NOT a replacement for AGENTS.md (identity) or SOUL.md (values). It is the **knowledge glue**.

### 4.1 KNOWLEDGE.md Structure

```markdown
# CTO Knowledge — CoDRAG Context

## How to Use CoDRAG

You have access to CoDRAG, an epistemic code intelligence system. 
Use these tools during every task:

### Before Starting Work
Call `codrag(role="cto")` for a role-filtered codebase overview.
This gives you module structure, hub files, and architectural patterns
weighted for your technical leadership role.

### When Searching for Code
Call `codrag_search(query="<what you need>", role="cto")`.
Your searches are automatically scoped to files relevant to your role.
{scope_count} files are in your knowledge scope.

### Before Making Changes
Call `codrag_impact(file_path="<file>")` to understand what depends
on the file you're changing. Never modify a hub file without checking
impact first.

### Cross-Session Memory
Call `codrag_observe(action="save", content="<fact>")` to remember 
important discoveries for future sessions.
Call `codrag_observe(action="get")` at the start of each session to
recall previous findings.

---

## Architecture Snapshot

{role_atlas_content}

---

## Key Files for Your Role

The following files are most relevant to your responsibilities.
They were selected by CoDRAG's epistemic analysis based on 
architecture layer weights, domain tag affinity, and graph centrality.

### High Relevance (score > 0.8)
- `src/codrag/core/atlas/generator.py` — Atlas generation engine (0.95)
- `src/codrag/mcp/server.py` — MCP server, primary API surface (0.92)
- `src/codrag/services/pipeline/orchestrator.py` — Pipeline orchestration (0.91)

### Medium Relevance (score 0.6-0.8)
- `src/codrag/api/routers/projects/` — REST API layer (0.74)
- `src/codrag/core/llm_client.py` — LLM client infrastructure (0.72)

### Reference (score 0.4-0.6)
- `docs/Phase64_prep-for-agents+paperclip/` — Architecture decisions (0.55)
- `packages/ui/src/components/` — Dashboard components (0.48)

---

## Domain Focus

Based on epistemic analysis, your primary domains are:
- **architecture** (12 modules, 47 files)
- **api** (3 modules, 23 files)
- **pipeline** (2 modules, 18 files)
- **infrastructure** (4 modules, 15 files)

---

## CoDRAG Project Configuration

- **Project ID:** `{project_id}`
- **Last Pipeline Build:** `{last_build_timestamp}`
- **Epistemic Confidence:** `{avg_confidence}` avg across {file_count} files
- **Your Knowledge Scope:** {scope_file_count} files selected
```

### 4.2 What KNOWLEDGE.md Does NOT Contain

| Excluded Content | Reason |
|-----------------|--------|
| Actual code | That's what `codrag_search` is for (dynamic, on-demand) |
| Full file contents | Token budget — KNOWLEDGE.md should be <3000 tokens |
| Embeddings | Embeddings are backend-only; agents use semantic search |
| Raw graph data | The role atlas is the pre-digested version |
| Other roles' scopes | Each agent sees only their own knowledge |

---

## 5. The Complete Context Pipeline

Here's how all the pieces work together, in sequence:

```
AGENT STARTUP / HEARTBEAT CYCLE
│
├─ 1. STATIC INJECTION (Paperclip promptTemplate)
│   ├── AGENTS.md (1000-2000 tokens) — Who am I, what do I do
│   ├── SOUL.md (500-800 tokens) — How I think and communicate
│   └── KNOWLEDGE.md (800-1500 tokens) — How to use CoDRAG + structural snapshot
│       Total static budget: ~2300-4300 tokens
│
├─ 2. AMBIENT CONTEXT (Agent's first tool call)
│   └── codrag(role="cto") → Role Atlas (800-1200 tokens)
│       ◄── Backed by: cached atlas_roles/cto.txt
│       ◄── Scoring: RoleVector × epistemic metadata × graph centrality
│       ◄── Freshness: Regenerated when pipeline rebuilds
│
├─ 3. MEMORY RECALL (Agent's second tool call)
│   └── codrag_observe(action="get") → Previous observations (200-800 tokens)
│       ◄── Backed by: observation store (JSON)
│       ◄── Staleness: Flagged when linked files change
│
├─ 4. TASK-SPECIFIC CONTEXT (During task execution)
│   ├── codrag_search(query="...", role="cto") → Code chunks (3000-6000 tokens)
│   │   ◄── Backed by: embedding store (vector search)
│   │   ◄── Filtered by: Knowledge Scope (dashboard checkboxes)
│   │   ◄── Expanded by: trace edges (structural neighbors)
│   │   ◄── Role-scoped: Only files in this role's scope are returned
│   │
│   ├── codrag_impact(file_path="...") → Blast radius (500-1500 tokens)
│   │   ◄── Backed by: trace graph (edges + in-degree)
│   │
│   └── codrag_observe(action="save", ...) → Persist discoveries
│       ◄── Written to: observation store for future sessions
│
└─ 5. POST-TASK (Agent completes heartbeat)
    └── Results → Paperclip task queue → Next agent
```

### Token Budget Summary

| Phase | Source | Tokens | When |
|-------|--------|--------|------|
| Startup | AGENTS.md + SOUL.md + KNOWLEDGE.md | ~3000 | Every cycle |
| Ambient | Role Atlas (codrag) | ~1000 | First call |
| Memory | Observations | ~500 | First call |
| Search | Per codrag_search call | ~4500 | Per task |
| Impact | Per codrag_impact call | ~1000 | Before changes |
| **Total per task** | | **~10,000** | Typical |

This fits well within modern context windows (128K-1M) while delivering comprehensive, role-appropriate context.

---

## 6. The Embedding Question: Do We Expose Embeddings?

**No. Agents never see raw embeddings.**

Here's why:

### What Embeddings Are (Backend Internals)
- CoDRAG builds a vector index of code chunks using `sentence-transformers` (or similar)
- Each chunk is embedded into a ~384-768 dimensional vector
- `codrag_search` performs cosine similarity search on these vectors
- The results are returned as **text** (code content), not vectors

### What Agents See
```
Agent calls: codrag_search(query="authentication flow", role="cto")
             ↓
Backend:     1. Embed the query → vector
             2. Search vector index → top-k similar chunks
             3. Filter by Knowledge Scope (only files in CTO's scope)
             4. Expand via trace edges (structural neighbors)
             5. Apply role-based re-ranking (RoleVector scoring)
             6. Compress to max_chars budget
             7. Return text content
             ↑
Agent gets:  Formatted code chunks with file paths and summaries
```

**Why not expose embeddings?**
1. Agents don't have vector math capabilities — they work with text
2. Embeddings would waste enormous token budget (~768 floats × 4 chars each × N chunks = thousands of wasted tokens)
3. The search quality is better server-side where we can apply trace expansion and role filtering
4. Embedding model details are an implementation detail the agent shouldn't know about

**What we DO expose through KNOWLEDGE.md:**
- The fact that semantic search exists ("Call `codrag_search`")
- The scope of search ("Your searches are automatically scoped to {N} files")
- The quality signal ("CoDRAG has epistemic confidence of {X} across {Y} files")

---

## 7. Knowledge Scope + Auto-Populate + KNOWLEDGE.md Integration

These three features form a tight loop:

```
                    ┌─────────────────────────────────────┐
                    │         HR Adapter generates          │
                    │         a new CTO role                │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼───────────────────────┐
              │                    │                        │
              ▼                    ▼                        ▼
     ┌────────────────┐   ┌───────────────┐   ┌────────────────────┐
     │  AGENTS.md     │   │  SOUL.md      │   │  Auto-Populate     │
     │  generated     │   │  generated    │   │  (backend call)    │
     └────────────────┘   └───────────────┘   └──────────┬─────────┘
                                                          │
                                                          ▼
                                              ┌────────────────────┐
                                              │  Knowledge Scope   │
                                              │  (file checkboxes  │
                                              │   set in dashboard)│
                                              └──────────┬─────────┘
                                                          │
                                                          ▼
                                              ┌────────────────────┐
                                              │  KNOWLEDGE.md      │
                                              │  generated from:   │
                                              │  - Role Atlas      │
                                              │  - Scope file list │
                                              │  - Domain analysis │
                                              │  - CoDRAG tool     │
                                              │    instructions    │
                                              └────────────────────┘
```

### The Loop:

1. **HR Adapter generates a role** (AGENTS.md + SOUL.md)
2. **Auto-Populate runs** → selects optimal file paths for this role
3. **Knowledge Scope is set** → those paths become the search filter
4. **KNOWLEDGE.md is generated** → includes:
   - The file list (human-readable, with relevance scores)
   - The role atlas snapshot (structural overview)
   - CoDRAG tool usage instructions
   - Domain focus areas
5. **All three files are bundled** → pushed to Paperclip

When the codebase changes:

6. **Pipeline rebuilds** → role atlases regenerate
7. **Drift detection runs** → checks if knowledge scope is still optimal
8. **If drift detected** → re-run auto-populate, regenerate KNOWLEDGE.md
9. **Sync to Paperclip** → agent gets updated context next heartbeat

---

## 8. Optimization Strategies

### 8.1 Token Efficiency

| Strategy | Implementation |
|----------|---------------|
| **Static context compression** | KNOWLEDGE.md uses bullet points, not prose. ~800 tokens for the structural snapshot. |
| **Lazy ambient loading** | KNOWLEDGE.md tells the agent to call `codrag(role=X)` for live data, rather than packing everything statically. |
| **Scope-filtered search** | Knowledge Scope prevents wasting search budget on irrelevant files. |
| **Role atlas caching** | Pre-generated at pipeline build time → instant response. |
| **Observation dedup** | Stale observations are flagged, saving retrieval budget. |

### 8.2 Freshness-vs-Cost Tradeoffs

| Context Source | Freshness | Cost | Strategy |
|---------------|-----------|------|----------|
| KNOWLEDGE.md | Stale until `codrag hr sync` | Free (pre-generated) | Regenerate on drift detection |
| Role Atlas | Stale until pipeline rebuild | Free (cached) | Auto-refreshed by pipeline |
| codrag_search | Live | ~0.01-0.05 per call (LLM tokens) | Agent calls on-demand |
| codrag_impact | Live | ~0.01 per call | Agent calls before changes |
| Observations | Live writes, stale flags | Free (local JSON) | Always available |

### 8.3 Preventing Context Thrashing

**Problem:** An agent might call `codrag(role=X)` + `codrag_search(role=X)` every heartbeat, wasting tokens on the same structural overview.

**Solution in KNOWLEDGE.md:**
```markdown
## Context Optimization Rules
- Call `codrag(role="cto")` ONCE at the start of each session, not per task
- Call `codrag_search` with specific queries, not generic ones
- The structural overview in the Architecture Snapshot below is current as of {timestamp}
  — only call codrag() again if you suspect major changes
```

### 8.4 Cross-Agent Context Isolation

Each agent's KNOWLEDGE.md uses their specific role slug. This ensures:
- `codrag(role="cto")` returns CTO-weighted atlas (infrastructure heavy)
- `codrag(role="ux_designer")` returns UX-weighted atlas (presentation heavy)
- `codrag_search(role="cto")` searches only within CTO's knowledge scope
- `codrag_search(role="ux_designer")` searches only within UX's knowledge scope

Agents CANNOT see each other's knowledge scopes. The isolation is enforced at the backend, not by trust in the agent's instructions.

---

## 9. Summary: The Three Files, Clarified

| File | Purpose | Contains | Changes When | Token Cost |
|------|---------|----------|-------------|------------|
| **AGENTS.md** | Identity + Behavior | Role description, priorities, guardrails, org chart relationships | Role drifts or responsibilities change | ~1500 |
| **SOUL.md** | Personality + Values | Who the agent "is", communication style, decision-making principles | Rarely (cultural/brand changes) | ~600 |
| **KNOWLEDGE.md** | CoDRAG Integration | Tool instructions, architecture snapshot, key file list, domain focus, scope metadata | Pipeline rebuilds, scope changes, drift detection | ~1200 |

**Total static injection per agent: ~3300 tokens** — leaving 96%+ of context window for actual work.
