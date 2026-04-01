# HR Agent Adapter — Landscape Research

> **Phase 67 Research** | Date: 2026-04-01
> Question: Does a codebase-aware agent role generator/manager already exist?

---

## 1. Research Verdict

**No existing tool does what we need.** There are three adjacent categories of tooling, but none combine codebase-aware epistemic knowledge with agent role lifecycle management. CoDRAG is uniquely positioned to fill this gap.

---

## 2. Adjacent Tooling Landscape

### 2.1 AGENTS.md Generators (Static, One-Shot)

| Tool | What It Does | Gap |
|------|-------------|-----|
| **agents-md-generator** (Smithery/Apify) | Scans a repo's README, package.json, and file tree to produce a generic `AGENTS.md` | **No epistemic knowledge.** Generates surface-level coding conventions, not role-specific intelligence. No ongoing management. No Paperclip awareness. |
| **CrewAI `agents.yaml`** generator | Creates role/goal/backstory YAML for CrewAI crews from prompts | **No codebase awareness.** Requires manual role definition. No graph data. No drift detection. |

**Key insight:** These tools produce a *starter file*. They don't:
- Understand the architecture at an epistemic level (module clusters, domain tags, architecture layers)
- Generate *role-specific* file scopes
- Monitor codebase evolution and recommend role updates
- Interface with Paperclip's API for lifecycle management

### 2.2 Agent Orchestration Platforms (Runtime, Not Generative)

| Tool | What It Does | Gap |
|------|-------------|-----|
| **Paperclip** | Org charts, heartbeats, budgets, adapters, task assignment for AI agents | **No codebase intelligence.** It's a runtime orchestrator. It doesn't know what the codebase *contains* or which files matter to which agent. Roles are manually written. |
| **CrewAI Enterprise (AMP)** | Visual agent builder, crew orchestration, knowledge bases | **No structural code intelligence.** Knowledge bases are document-level RAG, not graph-aware epistemic scoring. |
| **Microsoft AutoGen** | Multi-agent conversations, agent-to-agent collaboration | **Pure runtime.** No codebase intelligence whatsoever. |
| **LangGraph** | Stateful agent workflow graphs | **Workflow engine only.** No role generation or codebase awareness. |

### 2.3 Codebase Intelligence Systems (Knowledge, Not Role Management)

| Tool | What It Does | Gap |
|------|-------------|-----|
| **CoDRAG (us)** | Full epistemic knowledge graph with architecture layers, domain tags, module clustering, role projection vectors | **We have the knowledge but no HR layer.** We can score file relevance per role but don't generate/manage roles themselves. |
| **GitHub Copilot / Cursor context** | IDE-level code intelligence | **No multi-agent awareness.** Single-agent context, no role differentiation, no lifecycle management. |

---

## 3. What CoDRAG Already Has (Our Unfair Advantage)

CoDRAG's existing infrastructure provides 80% of what an HR Agent needs:

### 3.1 Per-File Epistemic Metadata
- **Architecture layers** (9 values): `presentation`, `business_logic`, `data`, `infrastructure`, etc.
- **Domain tags** (1-4 per file): Free-form LLM-generated tags like `"auth"`, `"ui"`, `"monetization"`
- **Epistemic confidence** (0.0-1.0): 6-component quality score
- **Module membership**: Clustered subsystems with aggregated metadata

### 3.2 Role Projection Engine (Phase 64)
- **RoleVector scoring**: Weighted composite of layer match (30%) + domain affinity (35%) + graph centrality (20%) + epistemic confidence (15%)
- **Predefined profiles**: CEO, CTO, Design Engineer, DevSecOps, Intern, etc.
- **LLM-driven role resolution**: For ambiguous roles, the Thinking LLM generates a RoleVector dynamically
- **Sub-Atlas generation**: Role-specific codebase overviews

### 3.3 Auto-Populate (Phase 67)
- **One-click file scope**: LLM vets Top-100 files for a given role and returns a curated file list
- **Backend API**: `POST /projects/{project_id}/scope/agents/{agent_role}/auto-populate`
- **Dashboard UI**: `AgentKnowledgeTree.tsx` with per-role file checkboxes

### 3.4 MCP Tool Surface
- `codrag(role="ceo")` — Role-filtered structural overview
- `codrag_search(query, role="ceo")` — Role-scoped semantic search
- `codrag_observe` — Cross-session memory per observation

---

## 4. The Gap: What We're Building

The missing piece is the **generative + management layer** — an "HR Agent" that:

| Capability | Status |
|-----------|--------|
| **Analyze codebase** to determine what roles are needed | 🟡 CoDRAG has the data, needs the reasoning |
| **Generate AGENTS.md + SOUL.md** for each role | 🔴 New |
| **Inject CoDRAG tool usage** into role files (`codrag(role="ceo")`) | 🔴 New |
| **Score role-to-code alignment** and detect drift | 🟡 RoleVector scoring exists, threshold logic needed |
| **Propose realignments** when code evolves | 🔴 New |
| **Interface with Paperclip API** to create/update agents | 🔴 New (but bootstrap-agents.sh is precedent) |
| **Accept existing Paperclip agents** and enhance them | 🔴 New |
| **Manage org chart relationships** between agents | 🔴 New |

---

## 5. Conclusion: Build Adapter, Not Build-From-Scratch

**CoDRAG should build an HR adapter that:**
1. Uses CoDRAG's epistemic knowledge to *generate* and *maintain* agent role definitions
2. Interfaces with Paperclip's REST API for agent lifecycle (create, update, propose changes)
3. Can also work as a standalone CLI tool for non-Paperclip users (generates AGENTS.md files)
4. Runs as a periodic analysis pass (weekly or on-demand) to detect role drift

**We are NOT rebuilding Paperclip.** We are the **knowledge engine** behind an HR function that Paperclip orchestrates.

The relationship is:
```
CoDRAG (epistemic knowledge) → HR Adapter (role reasoning) → Paperclip (runtime orchestration)
```
