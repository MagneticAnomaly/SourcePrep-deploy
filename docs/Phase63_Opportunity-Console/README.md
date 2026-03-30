# Phase 63 — Opportunity Console & Universal Adapter

> **Status:** In Progress
> **Start Date:** 2026-03-30
> **Research Foundation:** [Phase 62 Research](../Phase62_Pi-research/README.md) (10 documents)
> **Architecture Reference:** [10_Universal_Adapter_Architecture.md](../Phase62_Pi-research/10_Universal_Adapter_Architecture.md)

---

## Executive Summary

CoDRAG pivots from building project management features (Goalposts, Roadmap, GitHub sync) to becoming a **universal codebase intelligence provider**. The core product is the `ActionItem` — a structured finding that can be consumed by any agent, orchestrator, or PM tool through 7 standardized interfaces.

**What we're building:**
1. A unified "Opportunity Console" (dashboard panel) replacing 3 overlapping panels
2. Export formats: SARIF, JSON, CSV, Markdown for universal tool compatibility
3. A2A Agent Card for automatic discovery by orchestrators (Paperclip, CrewAI, etc.)
4. Headless AGENTS.md auto-refresh for zero-config agent compatibility
5. Advisor Model slot for dedicated opportunity analysis

**What we're sunsetting:**
- GoalpostsPanel (replaced by Opportunities)
- AdvisorPanel (merged into Opportunities)
- RoadmapPanel (removed — PM is the orchestrator's job)

---

## Architecture: The Protocol Hexagon

CoDRAG follows Hexagonal Architecture (Cockburn, 2005). The core intelligence is protocol-independent. Each consumer gets its own adapter — all serializing the same `ActionItem` model:

```
                              CoDRAG Core
                          ┌─────────────────┐
                     A2A  │                 │  MCP
                 ┌────────┤   ActionItem    ├────────┐
                 │        │    Model        │        │
                 │        │                 │        │
            SARIF│        │  • id           │        │CLI
                 │        │  • title        │        │
                 │        │  • category     │        │
                 │        │  • priority     │        │
                 │        │  • effort       │        │
                 │        │  • files        │        │
                 │        │  • subtasks     │        │
                 ├────────┤  • source       ├────────┤
                 │        │                 │        │
            JSON │        │  (stable,       │        │HTTP
                 │        │   universal)    │        │
                 │        │                 │        │
                 │        └─────────────────┘        │
                 │               │                   │
                 └───────────────┼───────────────────┘
                            CSV  │  AGENTS.md
```

**7 adapters, 1 core model. 30+ compatible tools. Zero custom integration.**

### Protocol Stack

| Layer | Protocol | Status | Compatible Tools |
|-------|----------|--------|-----------------|
| 4 | **A2A** (Agent-to-Agent) | 🆕 To Build | Paperclip, CrewAI, LangGraph, Google ADK |
| 3 | **MCP** (Model Context Protocol) | ✅ Built | Claude Code, Cursor, Antigravity, VS Code, Zed |
| 2 | **AGENTS.md** / Skill Files | ✅ Built | All agents that read project files |
| 1 | **CLI** / HTTP API | ✅ Built | Pi, Aider, Cline, shell scripts, n8n, Zapier |
| 0 | **Export Formats** (SARIF, JSON, CSV) | 🆕 To Build | GitHub, GitLab, Linear, Jira, VS Code, IntelliJ |

---

## Implementation Plan

### Phase 1: Backend — Unified Opportunity Pipeline

**Duration:** 3-4 days
**Dependencies:** None (greenfield)
**Goal:** All findings from all sources become native ActionItem objects with a unified query/export API.

---

#### 1.1 Simplify ActionItem State Model

**File:** `src/codrag/core/audit/action_item.py`

The current `ActionItem` supports states: `proposed`, `approved`, `dismissed`, `completed`. This was designed for a world where CoDRAG _managed_ the lifecycle. In the new model, CoDRAG only _discovers_ — the lifecycle is the PM tool's concern.

**Changes:**
```python
# Before:
VALID_STATES = frozenset({"proposed", "approved", "dismissed", "completed"})

# After:
VALID_STATES = frozenset({"active", "dismissed"})
```

- Add `source` field (enum): `health_scanner`, `spaghetti`, `advisor`, `todo_scanner`
- Add `dismissed_at: Optional[str]` timestamp
- Add method `to_sarif_result() -> dict` — maps to SARIF 2.1.0 result object
- Add method `to_csv_row() -> list` — flat row for CSV export
- Add method `to_export_json() -> dict` — clean JSON without internal fields
- Keep backward compatibility: `proposed` maps to `active`, `approved` maps to `active`

**Rationale:** CoDRAG tracks only two states because everything past "discovered" is the consuming tool's responsibility. Paperclip tracks `working`, `completed`, `blocked`. Linear tracks `in progress`, `done`. We don't duplicate their state machines.

---

#### 1.2 SARIF Exporter

**File:** `src/codrag/core/audit/sarif_exporter.py` (NEW)

SARIF (Static Analysis Results Interchange Format) is the OASIS standard for code findings. GitHub Code Scanning consumes it natively — upload a SARIF file and findings appear in the Security tab without any API integration.

**ActionItem → SARIF mapping:**

| ActionItem Field | SARIF Field | Notes |
|-----------------|-------------|-------|
| `id` | `results[].properties.codrag_id` | Custom property |
| `title` | `results[].message.text` | Primary display text |
| `category` | `results[].properties.tags` | Architecture, Quality, etc. |
| `priority` | `results[].level` | P0→error, P1→warning, P2→note |
| `files` | `results[].locations` | Physical locations in code |
| `source` | `results[].ruleId` prefix | HEALTH-xxx, SPAG-xxx, ADV-xxx |
| `effort` | `results[].properties.effort` | Custom property |
| `subtasks` | `results[].relatedLocations` | Sub-findings |

**Functions:**
```python
def action_items_to_sarif(items: List[ActionItem], tool_version: str) -> dict:
    """Convert ActionItems to SARIF 2.1.0 JSON."""

def write_sarif_file(items: List[ActionItem], output_path: Path) -> None:
    """Write SARIF to file."""

def validate_sarif(sarif_json: dict) -> bool:
    """Validate against SARIF 2.1.0 schema."""
```

---

#### 1.3 Opportunity Manager

**File:** `src/codrag/core/audit/opportunity_manager.py` (NEW)

The central orchestrator for all opportunity discovery. Aggregates findings from all scanners into a single stream.

**Class design:**
```python
class OpportunityManager:
    """Aggregates ActionItems from all analysis sources."""
    
    def refresh(self, project_id: str) -> List[ActionItem]:
        """Run all scanners and merge results.
        
        Sources (in priority order):
        1. Health Scanner — code health findings
        2. Spaghetti Scorer — refactoring urgency
        3. Advisor — LLM-generated proposals (if advisor model configured)
        4. TODO Scanner — in-code TODOs and FIXMEs
        
        Deduplication:
        - Hash-based on (title + affected_files) to prevent duplicates
        - Preserves dismiss state across refreshes
        """
    
    def get_opportunities(
        self,
        project_id: str,
        *,
        categories: Optional[List[str]] = None,
        min_priority: Optional[str] = None,  # "P0", "P1", "P2", "P3"
        sources: Optional[List[str]] = None,
        include_dismissed: bool = False,
    ) -> List[ActionItem]:
        """Query opportunities with filters."""
    
    def dismiss(self, project_id: str, item_id: str) -> None:
        """Mark an opportunity as dismissed."""
    
    def export(
        self,
        project_id: str,
        format: str,  # "json", "sarif", "csv", "md"
        **filters,
    ) -> Union[str, dict, bytes]:
        """Export opportunities in the specified format."""
    
    def get_summary(self, project_id: str) -> dict:
        """Return aggregate stats: total, by priority, by category, last refresh."""
```

**Storage:** Opportunities are persisted per-project in `{project_dir}/.codrag/opportunities.json`. A simple JSON file — no database needed.

---

#### 1.4 API Endpoints

**File:** `src/codrag/server.py` (MODIFY)

New endpoints under the existing Flask app:

```
GET  /projects/{id}/opportunities
     ?categories=architecture,quality
     &min_priority=P1
     &sources=health_scanner,spaghetti
     &include_dismissed=false
     → Returns: List[ActionItem] as JSON

POST /projects/{id}/opportunities/{item_id}/dismiss
     → Returns: {"dismissed": true}

GET  /projects/{id}/opportunities/export
     ?format=sarif|json|csv|md
     &min_priority=P1
     → Returns: SARIF JSON, JSON array, CSV text, or Markdown text

POST /projects/{id}/opportunities/refresh
     → Triggers re-scan from all sources
     → Returns: {"refreshed": true, "count": 23, "new": 5}

GET  /projects/{id}/opportunities/summary
     → Returns: {total, critical, warning, info, last_refresh, sources}
```

---

#### 1.5 CLI Commands

**File:** `src/codrag/cli.py` (MODIFY)

```bash
# List opportunities
codrag advise [--project PROJECT_ID] [--min-priority P1] [--format json|sarif|csv|md]

# Refresh (re-scan all sources)
codrag advise --refresh [--project PROJECT_ID]

# Export SARIF for GitHub
codrag advise --format sarif --output findings.sarif

# Quick summary
codrag advise --summary
```

---

### Phase 2: Frontend — Opportunities Panel

**Duration:** 5-7 days
**Dependencies:** Phase 1 (API endpoints)
**Goal:** Single panel replacing GoalpostsPanel + AdvisorPanel + RoadmapPanel.

---

#### 2.1 OpportunitiesPanel Component

**File:** `packages/ui/src/components/opportunities/OpportunitiesPanel.tsx` (NEW)

**Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│  ★ Opportunities                               [↻ Refresh]      │
│  ────────────────                                                │
│                                                                   │
│  ┌── Product Intent ──────────────────────────────────────────┐  │
│  │  [Editable text field, migrated from Goalposts]            │  │
│  │  Your product is a codebase intelligence engine that...    │  │
│  └──────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌── Summary ──────────────────────────────────────────────────┐│
│  │  23 total │ 3 🔴 critical │ 8 🟡 warning │ 12 🔵 info      ││
│  │  Last refreshed: 2 hours ago │ Model: kimi-2.5 k1:cloud     ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                   │
│  [All ▾] [Category ▾] [Source ▾] [Priority ▾]                   │
│                                                                   │
│  ┌── Opportunity Card ──────────────────────────────────────────┐│
│  │  🔴 P0  Circular dependency in auth module      HEALTH-a7b9 ││
│  │  3 files │ architecture │ effort: medium                      ││
│  │  ┌────────┐ ┌─────────┐ ┌────────────┐ ┌──────────┐        ││
│  │  │Copy ✨ │ │JSON     │ │MCP cmd     │ │Dismiss ✕ │        ││
│  │  └────────┘ └─────────┘ └────────────┘ └──────────┘        ││
│  │                                                               ││
│  │  ▸ Show details (expandable)                                  ││
│  │    Description text, sub-tasks, affected files list            ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                   │
│  (... more cards ...)                                             │
│                                                                   │
│  ┌── Export All ─────────────────────────────────────────────────┐│
│  │  [JSON] [SARIF] [CSV] [Markdown] [Copy All for AI ✨]        ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                   │
│  ┌── AI Questions ──────────────────────────────────────────────┐│
│  │  💬 "Should auth use JWT or session tokens?"                  ││
│  │  [Answer: ____________________________] [Submit]              ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

**Interactivity:**
- **Copy ✨** — Formats a rich prompt: title + description + affected files + sub-tasks + `codrag_audit(action="refactor", finding_ids=["ID"])` command. Ready to paste into any coding agent.
- **JSON** — Downloads single ActionItem as `.json` file
- **MCP cmd** — Copies the exact MCP tool call to clipboard
- **Dismiss ✕** — POST to dismiss endpoint, optimistic UI update, item fades out
- **Expand** — Shows full description, sub-tasks, file list with clickable paths
- **Refresh ↻** — Triggers backend re-scan, shows loading spinner, updates list via SSE
- **Export All** — Bulk download in chosen format
- **Copy All for AI** — Generates single paste-ready prompt with all undismissed items

---

#### 2.2 useOpportunitiesSystem Hook

**File:** `src/codrag/dashboard/src/hooks/useOpportunitiesSystem.ts` (NEW)

```typescript
interface UseOpportunitiesSystemReturn {
  // State
  opportunities: ActionItem[]
  summary: OpportunitySummary | null
  loading: boolean
  refreshing: boolean
  error: string | null
  
  // Product Intent (migrated from Goalposts)
  productIntent: string
  questions: Question[]
  
  // Filters
  filters: OpportunityFilters
  setFilters: (filters: OpportunityFilters) => void
  
  // Actions
  handleRefresh: () => Promise<void>
  handleDismiss: (itemId: string) => Promise<void>
  handleExport: (format: 'json' | 'sarif' | 'csv' | 'md') => Promise<void>
  handleCopyForAI: (itemId?: string) => void  // single or all
  handleCopyMCPCmd: (itemId: string) => void
  handleUpdateIntent: (intent: string) => Promise<void>
  handleAnswerQuestion: (qId: string, answer: string) => Promise<void>
}
```

---

#### 2.3 Panel Registration and Migration

**File:** `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` (MODIFY)

**Remove:**
- `goalposts` panel entry → replaced
- `advisor` panel entry → replaced
- `roadmap` panel entry → replaced
- `UseGoalpostsSystemReturn` import
- `UseRoadmapSystemReturn` import

**Add:**
- `opportunities` panel entry → new OpportunitiesPanel
- `UseOpportunitiesSystemReturn` import

**File:** `src/codrag/dashboard/src/App.tsx` (MODIFY)

**Remove:**
- `useGoalpostsSystem` import and invocation
- `useRoadmapSystem` import and invocation
- `goalposts` prop passing
- `roadmap` prop passing

**Add:**
- `useOpportunitiesSystem` import and invocation
- `opportunities` prop passing

---

### Phase 3: A2A Agent Card & Task Handler

**Duration:** 3-5 days
**Dependencies:** Phase 1 (opportunity pipeline for task routing)
**Goal:** Make CoDRAG discoverable and invokable by any A2A-compliant agent.

---

#### 3.1 Agent Card

**File:** `src/codrag/a2a/agent_card.json` (NEW)

Served at `http://localhost:8400/.well-known/agent.json`

This is the machine-readable "business card" that tells any A2A agent what CoDRAG can do:

```json
{
  "name": "CoDRAG",
  "description": "Codebase intelligence engine. Discovers structural patterns, architectural issues, and improvement opportunities.",
  "url": "http://localhost:8400",
  "version": "2026.1",
  "provider": {
    "organization": "CoDRAG",
    "url": "https://codrag.dev"
  },
  "capabilities": {
    "streaming": true,
    "pushNotifications": false
  },
  "authentication": { "schemes": ["none"] },
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain", "application/json"],
  "skills": [
    {
      "id": "codebase-context",
      "name": "Codebase Context Assembly",
      "description": "Assembles focused context for a code query using semantic search and structural expansion."
    },
    {
      "id": "opportunity-discovery",
      "name": "Opportunity Discovery",
      "description": "Scans codebase for issues and improvement opportunities. Returns structured ActionItems."
    },
    {
      "id": "impact-analysis",
      "name": "Impact Analysis",
      "description": "Analyzes dependencies and dependents of a file or symbol. Shows blast radius."
    },
    {
      "id": "structural-overview",
      "name": "Structural Overview",
      "description": "Returns module structure, hub files, and architectural patterns."
    }
  ]
}
```

---

#### 3.2 A2A Task Handler

**File:** `src/codrag/a2a/a2a_handler.py` (NEW)

JSON-RPC 2.0 handler that maps A2A task requests to existing CoDRAG pipeline functions:

```python
class A2AHandler:
    """Handles A2A protocol task requests."""
    
    SKILL_HANDLERS = {
        "codebase-context": "_handle_context",
        "opportunity-discovery": "_handle_opportunities",
        "impact-analysis": "_handle_impact",
        "structural-overview": "_handle_overview",
    }
    
    async def handle_task(self, task_request: dict) -> dict:
        """Process an A2A task request.
        
        Task lifecycle: submitted → working → completed/failed
        """
    
    async def _handle_context(self, params: dict) -> dict:
        """Maps to codrag_search internally."""
    
    async def _handle_opportunities(self, params: dict) -> dict:
        """Maps to OpportunityManager.refresh + export."""
    
    async def _handle_impact(self, params: dict) -> dict:
        """Maps to codrag_impact internally."""
    
    async def _handle_overview(self, params: dict) -> dict:
        """Maps to codrag (structural overview) internally."""
```

#### 3.3 Server Integration

**File:** `src/codrag/server.py` (MODIFY)

Add two endpoints:
- `GET /.well-known/agent.json` — serve the static Agent Card
- `POST /a2a` — JSON-RPC 2.0 endpoint for task handling

---

### Phase 4: Headless Mode — AGENTS.md Auto-Refresh

**Duration:** 2-3 days
**Dependencies:** Phase 1 (opportunity pipeline)
**Goal:** Zero-config agent compatibility. Any agent that reads AGENTS.md sees current findings.

---

#### 4.1 AGENTS.md Writer

**File:** `src/codrag/core/agents_md_writer.py` (NEW)

Writes a managed section into `.agents/AGENTS.md` with opportunity summaries:

```markdown
<!-- codrag-opportunities-start -->
## CoDRAG Opportunities

Last refreshed: 2026-03-30T17:00:00Z | 23 findings

### Critical (P0)
- **HEALTH-a7b9**: Circular dependency in auth module (3 files, effort: medium)
- **SPAG-d2e1**: God class in UserService.py (1 file, effort: large)

### Warnings (P1)
- **ADV-c3d4**: Missing error handling in API routes (7 files, effort: small)
- ...

To get full details: `codrag advise --format json`
To fix a finding: `codrag_audit(action="refactor", finding_ids=["HEALTH-a7b9"])`
<!-- codrag-opportunities-end -->
```

**Key behaviors:**
- Only writes within managed markers (preserves user content)
- Includes top 10 items by priority
- Shows counts and last refresh time
- Includes CLI commands for next steps
- Truncates gracefully if many items (links to full export)

---

#### 4.2 Auto-Refresh Integration

**File:** `src/codrag/core/watcher.py` (MODIFY)
- After pipeline completion → trigger opportunity refresh
- After opportunity refresh → update AGENTS.md

**File:** `src/codrag/core/scheduler.py` (MODIFY)
- Add idle-time opportunity refresh (when no pipelines running)
- Default interval: 4 hours (configurable)

**Config toggle:** `auto_refresh_agents_md: bool` (default: `true`)

---

### Phase 5: Advisor Model Slot

**Duration:** 2-3 days
**Dependencies:** Phase 1 (model awareness)
**Goal:** Explicit 5th model slot for opportunity analysis.

---

#### 5.1 LLM Config Changes

**Files:** `packages/ui` types + `AIModelsSettings` component

Add `advisor_model` to `LLMConfig`:
```typescript
interface LLMConfig {
  embedding: EmbeddingConfig
  small_model: ModelSlotConfig    // Fast Model
  large_model: ModelSlotConfig    // Thinking Model
  code_model: ModelSlotConfig     // Code Model
  advisor_model: ModelSlotConfig  // Advisor Model (NEW)
}
```

#### 5.2 Backend Wiring

**File:** `src/codrag/core/model_awareness.py` (MODIFY)
- Add `advisor` task to slot mapping
- Falls back to `large_model` if `advisor_model` not configured

**File:** `src/codrag/server.py` (MODIFY)
- Accept `advisor_model` in global config save/load

---

## Files Changed Summary

### New Files (8)
| File | Description |
|------|-------------|
| `src/codrag/core/audit/opportunity_manager.py` | Central opportunity aggregator |
| `src/codrag/core/audit/sarif_exporter.py` | SARIF 2.1.0 export |
| `src/codrag/core/agents_md_writer.py` | AGENTS.md auto-writer |
| `src/codrag/a2a/__init__.py` | A2A module init |
| `src/codrag/a2a/agent_card.json` | A2A Agent Card |
| `src/codrag/a2a/a2a_handler.py` | A2A task handler |
| `packages/ui/.../OpportunitiesPanel.tsx` | New dashboard panel |
| `src/codrag/dashboard/.../useOpportunitiesSystem.ts` | Dashboard hook |

### Modified Files (7)
| File | Change |
|------|--------|
| `src/codrag/core/audit/action_item.py` | Simplified state, export methods |
| `src/codrag/server.py` | New API endpoints, A2A mount |
| `src/codrag/cli.py` | Export format options |
| `src/codrag/core/watcher.py` | Auto-refresh trigger |
| `src/codrag/core/scheduler.py` | Idle-time refresh |
| `src/codrag/core/model_awareness.py` | Advisor slot |
| `src/codrag/dashboard/.../useDashboardPanels.tsx` | Panel swap |
| `src/codrag/dashboard/.../App.tsx` | Hook swap |

### Deprecated Files (marked, not deleted)
| File | Replacement |
|------|------------|
| `hooks/useGoalpostsSystem.ts` | `useOpportunitiesSystem.ts` |
| `hooks/useRoadmapSystem.ts` | `useOpportunitiesSystem.ts` |
| `GoalpostsPanel.tsx` | `OpportunitiesPanel.tsx` |
| `AdvisorPanel.tsx` | `OpportunitiesPanel.tsx` |
| `RoadmapPanel.tsx` | Removed (PM is orchestrator's job) |

---

## Timeline

```
Week 1: Phase 1 (Backend)
  Day 1-2: ActionItem simplification + SARIF exporter
  Day 3-4: OpportunityManager + API endpoints + CLI

Week 2: Phase 2 (Frontend) + Phase 3 (A2A)
  Day 5-7: OpportunitiesPanel + useOpportunitiesSystem
  Day 8-9: A2A Agent Card + handler
  Day 10: Panel migration in App.tsx + useDashboardPanels

Week 3: Phase 4 (Headless) + Phase 5 (Advisor) + Polish
  Day 11-12: AGENTS.md writer + auto-refresh
  Day 13-14: Advisor model slot + testing
  Day 15: Integration testing + documentation
```

**Critical path:** Phase 1 → Phase 2 (backend must exist before frontend)
**Parallel:** Phases 3-5 can run alongside Phase 2

---

## Verification Checklist

- [ ] `codrag advise --format json` outputs valid JSON array of ActionItems
- [ ] `codrag advise --format sarif` outputs valid SARIF 2.1.0
- [ ] SARIF upload to GitHub shows findings in Security tab
- [ ] `curl localhost:8400/.well-known/agent.json` returns valid Agent Card
- [ ] Dashboard Opportunities panel shows all findings
- [ ] "Copy for AI" generates well-formatted paste prompt
- [ ] Dismiss persists across page reload
- [ ] Export All downloads correct files
- [ ] AGENTS.md auto-updates after pipeline runs
- [ ] Product Intent and Questions migrated from Goalposts
- [ ] Old panels (Goalposts/Advisor/Roadmap) hidden from panel picker
