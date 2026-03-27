# Phase 57: Goalposts — Pruned Scope & MCP Integration Plan

> This document consolidates the R&D findings into a clear, pruned implementation plan.
> Deferred items are explicitly called out. The MCP tool design is the primary focus.

---

## 1. Scope Pruning: What Ships Now vs. Later

### ✅ Ships Now (V1 Core)

| Item | Status | Notes |
|------|--------|-------|
| Backend: `goalposts_models.py` | ✅ Done | Data models + persistence |
| Backend: `goalposts_planner.py` | ✅ Done | LLM planning engine (current prompt) |
| Backend: `goalposts.py` API router | ✅ Done | 5 REST endpoints |
| Frontend: TypeScript types | ✅ Done | In `types.ts` |
| Frontend: API client methods | ✅ Done | In `client.ts` |
| Frontend: `useGoalpostsSystem.ts` hook | ✅ Done | Dashboard hook with polling |
| **MCP: `codrag_goalposts` tool** | 🔲 Next | Read-only tool for AI assistants |
| **Dashboard: `GoalpostsPanel.tsx`** | 🔲 Next | Simple panel in ModularDashboard |

### 🔜 Deferred to V2 (after V1 validates the concept)

| Item | Why Deferred |
|------|-------------|
| Multi-perspective prompt (architect/designer/SRE) | Needs V1 usage data to validate ROI |
| Module summaries + coupling hotspots in prompt | Adds complexity; see if Atlas alone suffices |
| `situation_assessment` / `unlocks` / `perspective` fields | Over-engineering before user feedback |
| Planning signals pre-analyzer | Wait for V1 prompt quality feedback |
| Module health scoring | Depends on planning signals |
| Spaghetti-informed effort estimates | Depends on spaghetti availability |

### 🔮 Future (V3+)

| Item | Dependency |
|------|-----------|
| Intent-aware Atlas generation | Needs Atlas generator changes |
| Cross-session memory (`codrag_observe`) | After decision patterns emerge |
| GitHub Issues export | After MCP tool validates the workflow |

---

## 2. How Goalposts Fits Developer Workflows

### The Key Insight

Goalposts is NOT a project management tool. It's a **planning context provider** that surfaces through the tools developers already use:

```
┌─────────────────────────────────────────────────┐
│    Developer's Existing Workflow                 │
│                                                  │
│  IDE ──→ AI Assistant ──→ MCP ──→ CoDRAG        │
│  (Cursor, VSCode,        (codrag_goalposts)      │
│   Claude Code,                                   │
│   Gemini CLI)                                    │
│                                                  │
│  Dashboard ──→ GoalpostsPanel (visual overview)  │
│                                                  │
│  CLI ──→ codrag goalposts (terminal summary)     │
└─────────────────────────────────────────────────┘
```

### Workflow Integration Points

| Surface | How Goalposts Appears | User Action |
|---------|----------------------|-------------|
| **MCP tool** | AI agent calls `codrag_goalposts` → gets approved milestones as context | Agent plans work aligned with goalposts |
| **Dashboard** | GoalpostsPanel shows proposals, questions, intent editor | Review, approve, dismiss, answer questions |
| **CLI** | `codrag goalposts` prints summary | Quick terminal overview |
| **AI agent rules** | `.codrag/AGENTS.md` mentions goalposts availability | Agent knows to check goalposts before planning |

### Why MCP is the Primary Integration Surface

1. **AI assistants are the new IDE**: Cursor, Claude Code, Gemini CLI, Copilot ALL consume MCP tools
2. **Read-only is perfect**: Goalposts proposals are *context* for AI planning, not write operations
3. **Mirrors `codrag_audit`**: Proven pattern — AI calls audit before refactoring, will call goalposts before planning
4. **Zero install**: Works immediately for anyone using CoDRAG MCP — no GitHub integration needed

---

## 3. MCP Tool Design: `codrag_goalposts`

### Tool Definition

```json
{
  "name": "codrag_goalposts",
  "description": "View project goalposts — AI-generated milestones based on codebase analysis, audit findings, and product intent. Returns approved milestones to guide your planning. Use action='view' (default) to see current goalposts. Use action='detail' with a proposal_id to get task-level detail.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "default": "view",
        "enum": ["view", "detail"],
        "description": "Operation: 'view' (default) to list all goalposts, 'detail' to get tasks for a specific goalpost."
      },
      "proposal_id": {
        "type": "string",
        "description": "(detail) ID of a specific goalpost to get task-level detail."
      },
      "filter": {
        "type": "string",
        "enum": ["all", "approved", "proposed"],
        "default": "approved",
        "description": "(view) Filter goalposts: 'approved' (default) for user-approved only, 'proposed' for unreviewed, 'all' for everything."
      },
      "project_id": {
        "type": "string",
        "description": "CoDRAG project ID. Auto-detected from workspace root if omitted."
      }
    }
  }
}
```

### Action: `view` (default)

Returns a summary of all goalposts. This is what an AI agent calls at the start of a planning session to align its work with the user's approved direction.

**Example `_to_markdown` output:**

```markdown
## Goalposts (3 approved, 2 proposed)

Product Intent: Build a privacy-first SaaS analytics dashboard

### Approved Milestones
- **[P0 · architecture] Add authentication layer**
  Rationale: No auth exists; required before multi-tenant support
  Tasks: 3 (2 small, 1 medium)

- **[P1 · tech_debt] Extract shared validation logic**
  Rationale: Duplicate validation in 4 API routers creates drift risk
  Tasks: 2 (2 small)

- **[P1 · feature] Add usage analytics endpoint**
  Rationale: Core product value requires metrics collection
  Tasks: 4 (1 small, 2 medium, 1 large)

### Proposed (awaiting review)
- **[P2 · security] Implement rate limiting**
- **[P3 · research] Evaluate event sourcing for audit trail**

Use `codrag_goalposts action='detail' proposal_id='...'` for task breakdown.
```

### Action: `detail`

Returns the task breakdown for a specific goalpost — file paths, effort estimates, and descriptions. This is what an AI agent calls when it's about to implement a specific milestone.

**Example `_to_markdown` output:**

```markdown
## Goalpost: Add authentication layer [P0 · architecture · approved]

Rationale: No auth exists; required before multi-tenant support

### Tasks
1. **Create auth middleware** [medium]
   Files: `src/codrag/api/middleware/auth.py`, `src/codrag/server.py`

2. **Add JWT token validation** [small]
   Files: `src/codrag/core/auth.py`

3. **Wire auth into existing routes** [small]
   Files: `src/codrag/api/routers/projects/build.py`, `src/codrag/api/routers/audit.py`
```

---

## 4. Design Decisions

### Why only 2 actions (not 4 like `codrag_audit`)?

The audit tool has `scan`, `refactor`, `verify`, `report` because the audit workflow is a multi-step loop. Goalposts is simpler:
- **View**: What should I work on? (AI calls this)
- **Detail**: Tell me more about this milestone (AI calls this before implementing)

Generation and approval happen through the **dashboard** and **REST API**, not through MCP. The MCP tool is read-only — it's a context provider, not a workflow driver.

### Why `filter: approved` as default?

When an AI agent asks "what should I work on?", only user-approved milestones should guide its planning. Showing proposed milestones would let the AI act on unreviewed suggestions, which breaks the human-in-the-loop principle.

### Why no `generate` action in MCP?

Generation is expensive (LLM call) and takes 10-30s. MCP tools should return fast. Generation is triggered through:
- Dashboard "Generate" button
- REST `POST /goalposts/generate` endpoint
- Future: CLI `codrag goalposts --generate`

---

## 5. Implementation Plan (V1 Remaining)

### Step 1: MCP Tool (server.py)

Add `tool_goalposts_view` and `tool_goalposts_detail` methods to `CodragMCPServer`. Add `codrag_goalposts` to the TOOLS list and dispatch in `handle_tools_call`.

#### [MODIFY] [server.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/mcp/server.py)
- Add tool methods: `tool_goalposts_view()`, `tool_goalposts_detail()`
- Add to TOOLS list
- Add dispatch in `handle_tools_call`
- Update `instructions` string to mention goalposts

### Step 2: Dashboard Panel

Create a simple `GoalpostsPanel.tsx` and wire into `useDashboardPanels.tsx`.

#### [NEW] GoalpostsPanel.tsx
- Intent editor (textarea)
- Generate button
- Proposal cards (approve/dismiss)
- Question cards (answer input)

#### [MODIFY] useDashboardPanels.tsx
- Add goalposts panel registration

### Step 3: AGENTS.md Update

Update the CoDRAG-managed `.codrag/AGENTS.md` to mention `codrag_goalposts`.

---

## 6. Verification Plan

### Automated
```bash
# Python imports + data model check
python -c "from codrag.core.goalposts_planner import GoalpostsPlanner; print('OK')"

# MCP tool handler check (after implementation)
python -c "from codrag.mcp.server import CodragMCPServer; print('OK')"
```

### Manual
1. Open dashboard → GoalpostsPanel visible in panel list
2. Set product intent → saved and displayed
3. Generate goalposts → proposals appear after LLM call
4. Approve/dismiss proposals → state persists
5. AI assistant calls `codrag_goalposts` → returns approved milestones
