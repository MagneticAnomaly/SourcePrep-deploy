# Phase 65 — Pushing Tasks to Paperclip: CoDRAG as Intelligence Source

> **Status:** ✅ Implemented  
> **Depends On:** Phase 57 (ActionItem model), Phase 59 (Roadmap/TODOs), Phase 62 (Universal Adapter Architecture), Phase 63 (Opportunities), Phase 66 (Pi Agent)  
> **Date:** 2026-03-31

### Implementation Files

| File | Purpose |
|------|---------|
| `src/codrag/adapters/__init__.py` | Package init |
| `src/codrag/adapters/pm_models.py` | Universal PM data models (PMIssue, PMProject, PMGoal, PushResult, PMPushConfig) |
| `src/codrag/adapters/pm_adapter.py` | Abstract PMAdapter base class (universal interface) |
| `src/codrag/adapters/paperclip_adapter.py` | Paperclip REST API implementation |
| `src/codrag/adapters/push_engine.py` | PushEngine orchestrator + factory |
| `src/codrag/core/audit/consolidator.py` | Anti-clutter consolidation engine (3 strategies) |
| `src/codrag/api/routers/pm_push.py` | 6 API endpoints for push, config, health, history |
| `src/codrag/core/audit/action_item.py` | Added `codrag_address()` + `to_pm_export()` |
| `src/codrag/api/routers/opportunities.py` | Added `/context` CoDRAG address resolution endpoint |
| `src/codrag/services/pi_agent.py` | Added `_try_auto_push()` for Watchdog auto-push |

---

## 1. The Concept

CoDRAG already **discovers** actionable intelligence from codebases — audit findings, TODOs, roadmap nodes, architectural issues, refactoring targets. Today this intelligence lives inside CoDRAG's dashboard and MCP tools, but it's not connected to where work actually gets managed.

**Paperclip** is an agent-orchestrated project management system where AI agents are "hired" to work on goals and issues. The missing link: **CoDRAG should push its discovered intelligence into Paperclip as structured projects, goals, and issues** — and Paperclip should be able to trace every item back to its **CoDRAG source address** to verify currency and gather deeper context.

### The Mental Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    CoDRAG (Intelligence Layer)                    │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Audit Scanner │  │ TODO Scanner │  │ Roadmap Miner        │   │
│  │ (11 analyzers)│  │ (rg/python)  │  │ (graph+keywords)     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                  │                      │               │
│         ▼                  ▼                      ▼               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │               ActionItem (Unified Model)                  │    │
│  │  id: HEALTH-a7b9 | TODO-c3d4 | ROAD-e5f6                │    │
│  │  title, priority, category, affected_files, tasks...      │    │
│  │  + mcp_command() for deep context retrieval               │    │
│  └────────────────────────┬─────────────────────────────────┘    │
│                            │                                      │
│                            ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │          Paperclip Push Adapter (NEW — Phase 65)          │    │
│  │                                                            │    │
│  │  Groups ActionItems into → Paperclip Projects              │    │
│  │  Maps P0/P1 to → Goals                                     │    │
│  │  Maps P2/P3 to → Issues                                    │    │
│  │  Attaches CoDRAG Address → source_ref for traceability     │    │
│  └────────────────────────┬─────────────────────────────────┘    │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │
                     HTTP POST (Paperclip API)
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                    Paperclip (PM Layer)                          │
│                                                                  │
│  ┌────────────┐   ┌────────────────┐   ┌────────────────────┐  │
│  │  Projects   │   │     Goals      │   │      Issues        │  │
│  │  (grouped   │   │  (P0/P1 items  │   │  (P2/P3 items      │  │
│  │   by module │   │   with agent   │   │   backlog for      │  │
│  │   or domain)│   │   assignment)  │   │   future sprints)  │  │
│  └─────┬──────┘   └────────┬───────┘   └────────┬───────────┘  │
│        │                    │                     │              │
│        │              codrag_address               │              │
│        │              ═══════════                  │              │
│        │    "codrag://project_id/HEALTH-a7b9"      │              │
│        │    Can call back to CoDRAG for:           │              │
│        │    • Current status (still active?)       │              │
│        │    • Deeper context (impact analysis)     │              │
│        │    • Related files and dependencies       │              │
│        └───────────────────┼───────────────────────┘              │
│                            │                                      │
│                     Paperclip Agents                              │
│                     (claude-local, etc.)                          │
│                     Can use codrag MCP tools                      │
│                     to work on assigned issues                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. What CoDRAG Already Discovers (The Raw Material)

CoDRAG has **5 discovery engines** that produce structured, addressable intelligence:

| Source | What It Finds | Data Model | Address Format |
|--------|---------------|------------|----------------|
| **Audit Scanner** (11 analyzers) | Circular deps, large files, naming violations, coverage gaps | `ActionItem` (HEALTH-xxxx) | `codrag://pid/HEALTH-xxxx` |
| **Spaghetti Scorer** | Files with high refactoring urgency | `ActionItem` (SPAG-xxxx) | `codrag://pid/SPAG-xxxx` |
| **TODO Scanner** | `TODO`, `FIXME`, `HACK`, `BUG` annotations in code | `RoadmapNode` → `ActionItem` (TODO-xxxx) | `codrag://pid/TODO-xxxx` |
| **Roadmap Miner** | Planning keywords in docs, orphan modules, hotspots | `RoadmapNode` → `ActionItem` (ROAD-xxxx) | `codrag://pid/ROAD-xxxx` |
| **Advisor** (LLM-powered) | Forward-looking proposals, architectural suggestions | `ActionItem` (ADV-xxxx) | `codrag://pid/ADV-xxxx` |

### 2.1 The ActionItem Model (Already Universal)

The `ActionItem` dataclass ([action_item.py](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/audit/action_item.py)) is already designed for external consumption:

```python
ActionItem:
  id: "HEALTH-a7b9"           # Stable, deterministic hash
  title: "Circular dependency between auth and user modules"
  description: "..."
  category: "architecture"    # architecture, security, feature, tech_debt, quality, ...
  severity: "warning"         # critical, warning, info, suggestion
  priority: "P1"              # P0-P3
  effort: "medium"            # small, medium, large
  source: "health"            # health, advisor, spaghetti, todo_scanner, roadmap
  affected_files: ["src/auth/login.py", "src/user/models.py"]
  suggested_action: "Break the circular import by extracting shared types"
  tasks: [SubTask(...), ...]   # Concrete sub-steps
  state: "active"              # active, dismissed
  mcp_command(): str           # Ready-to-paste CoDRAG command for deep context
```

Already has export methods:
- `to_export_json()` — clean JSON for Paperclip/PM tools
- `to_sarif_result()` — GitHub Code Scanning
- `to_csv_row()` — Linear/Jira import
- `to_ai_prompt()` — paste into any coding agent

### 2.2 The CoDRAG Address (The Key Innovation)

Every item already has a **deterministic, stable ID** (hash of source + analyzer + title + files). We formalize this as a **CoDRAG Address**:

```
codrag://1d6f0b35-45cb/HEALTH-a7b9
         ──────────────  ──────────
         project_id       item_id
```

This address is:
- **Stable** across scans (same problem → same hash)
- **Resolvable** — Paperclip agents can call CoDRAG to check if the item is still active
- **Deep-linkable** — Point back to exact files, impact analysis, related findings

---

## 3. The CoDRAG → Paperclip Mapping

### 3.1 Hierarchy Mapping

CoDRAG's flat list of ActionItems needs to be structured into Paperclip's project hierarchy:

```
CoDRAG ActionItems          →    Paperclip Structure
════════════════════              ════════════════════

ActionItem.category              →    Project
  "architecture"                 →    "Architecture Health"
  "security"                     →    "Security Remediation"
  "tech_debt"                    →    "Tech Debt Cleanup"
  "quality" + "naming"           →    "Code Quality"
  "feature"                      →    "Feature Development"
  "testing" + "coverage"         →    "Test Coverage"

ActionItem.priority              →    Item Type
  P0 (critical)                  →    Goal (agent-assigned, urgent)
  P1 (warning)                   →    Goal (agent-assigned, high priority)
  P2 (info)                      →    Issue (backlog)
  P3 (suggestion)                →    Issue (low priority / nice-to-have)

ActionItem.tasks[]               →    Sub-issues / checklist items
```

### 3.2 Enrichment: What CoDRAG Adds Beyond Raw Findings

When pushing to Paperclip, CoDRAG doesn't just shove raw ActionItems — it enriches them:

| Enrichment | Source | Value |
|-----------|--------|-------|
| **Impact radius** | `codrag_impact(file_path)` | "Changing this file affects 12 dependents" |
| **Module context** | `codrag(role="engineer")` | "This belongs to the Pipeline Orchestration Engine" |
| **Related findings** | Opportunity graph | "5 other findings share the same root cause" |
| **CoDRAG command** | `mcp_command()` | Ready-to-paste command for the agent working the issue |
| **Effort estimate** | ActionItem.effort | small/medium/large → story points ↔ Paperclip estimate |
| **File list** | ActionItem.affected_files | Exact scope of work |

### 3.3 The Sync Model: Push, Don't Poll

CoDRAG is the **source of truth** for codebase intelligence. Paperclip is the **source of truth** for work management. The sync is one-way push with back-reference:

```
CoDRAG discovers finding  →  Push to Paperclip as issue
CoDRAG finding resolved   →  Push status update to Paperclip
Paperclip agent working   →  Agent calls CoDRAG MCP for context
Paperclip agent done       →  Agent runs codrag_audit(verify) to confirm fix
```

**CoDRAG does NOT pull from Paperclip.** It doesn't care what Paperclip does with the issues. It just keeps discovering and pushing new intelligence.

---

## 4. Architecture: The Paperclip Push Adapter

### 4.1 Where It Lives

Following the Hybrid MCP Architecture, the Paperclip adapter is a workflow integration module. This logic operates within (or parallel to) our lightweight `@codrag/paperclip-plugin` to automate project management:

```
CoDRAG Core
  │
  ├── MCP Server ✅ (Primary tool provider for AI agents)
  ├── CLI Adapter ✅ (codrag advise --format json)
  ├── HTTP Adapter ✅ (/opportunities/export)
  ├── SARIF Adapter ✅ (GitHub Code Scanning)
  ├── AGENTS.md Adapter ✅ (auto-refresh)
  ├── A2A Adapter 🔜 (agent discovery)
  └── Paperclip Workflow Sync 🆕 (Phase 65 Push Logic)
```

### 4.2 New Components

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `src/codrag/adapters/paperclip_push.py` | Core push logic: ActionItem → Paperclip API | ~250 |
| `src/codrag/adapters/paperclip_models.py` | Paperclip data models (Project, Goal, Issue) | ~100 |
| `src/codrag/adapters/paperclip_grouper.py` | Groups ActionItems into Paperclip projects by category/module | ~150 |
| `src/codrag/api/routers/paperclip.py` | HTTP endpoints for manual/auto push | ~80 |
| Config in settings_store | Paperclip URL, API key, auto-push settings | ~20 lines |

### 4.3 The Grouper: Turning Flat Items into Projects

The smartest part of this adapter. CoDRAG has module-level intelligence — it knows which files belong to which subsystem. The grouper uses this to create meaningful Paperclip projects:

```python
# src/codrag/adapters/paperclip_grouper.py (conceptual)

class PaperclipGrouper:
    """Groups ActionItems into Paperclip project/goal/issue hierarchy.
    
    Strategy 1 (Default): Group by category
      → 1 Paperclip project per ActionItem.category
      → P0/P1 items become Goals
      → P2/P3 items become Issues
    
    Strategy 2 (Module-aware): Group by CoDRAG module
      → 1 Paperclip project per CoDRAG module/segment
      → All findings for "Pipeline Engine" go into one project
      → Requires atlas data (module membership per file)
    
    Strategy 3 (Root-cause): Group by shared affected files
      → Items sharing the same root files get grouped together
      → Reduces duplicate work (don't fix the same file 5 times)
    """
    
    def group_by_category(self, items: List[ActionItem]) -> Dict[str, PaperclipProject]:
        """Simple: group by ActionItem.category → Paperclip project."""
        projects = {}
        for item in items:
            project_name = CATEGORY_TO_PROJECT.get(item.category, "Miscellaneous")
            if project_name not in projects:
                projects[project_name] = PaperclipProject(name=project_name)
            
            if item.priority in ("P0", "P1"):
                projects[project_name].goals.append(
                    PaperclipGoal.from_action_item(item)
                )
            else:
                projects[project_name].issues.append(
                    PaperclipIssue.from_action_item(item)
                )
        return projects
    
    def group_by_module(
        self, 
        items: List[ActionItem], 
        modules: List[ModuleEntry],
    ) -> Dict[str, PaperclipProject]:
        """Smart: use CoDRAG module membership to group related findings."""
        # Build file → module index
        file_to_module = {}
        for mod in modules:
            for f in mod.files:
                file_to_module[f] = mod.name
        
        # Assign each item to its primary module
        projects = {}
        for item in items:
            module = self._resolve_module(item.affected_files, file_to_module)
            if module not in projects:
                projects[module] = PaperclipProject(name=module)
            # ... same goal/issue split as above
```

### 4.4 The Push Engine

```python
# src/codrag/adapters/paperclip_push.py (conceptual)

class PaperclipPushEngine:
    """Pushes CoDRAG intelligence to Paperclip's API.
    
    Modes:
    - Manual: User clicks "Push to Paperclip" in dashboard
    - Auto (Pi): After Pi Watchdog scan, auto-push new findings
    - Scheduled: Nightly sync of all active opportunities
    """
    
    def __init__(self, config: PaperclipConfig):
        self.base_url = config.url        # e.g., "http://localhost:3000"
        self.company_id = config.company   # Paperclip company slug
        self.api_key = config.api_key      # Optional auth
        self.grouper = PaperclipGrouper()
    
    async def push_opportunities(
        self,
        items: List[ActionItem],
        project_id: str,
        *,
        strategy: str = "category",   # "category" | "module" | "root_cause"
        dry_run: bool = False,
    ) -> PushResult:
        """Push ActionItems to Paperclip as projects/goals/issues."""
        
        # Step 1: Group items
        if strategy == "module":
            projects = self.grouper.group_by_module(items, self._load_modules())
        else:
            projects = self.grouper.group_by_category(items)
        
        if dry_run:
            return PushResult(projects=projects, pushed=False)
        
        # Step 2: Push each project
        results = []
        for name, project in projects.items():
            # Create or update Paperclip project
            paperclip_project = await self._ensure_project(name)
            
            # Push goals (P0/P1)
            for goal in project.goals:
                result = await self._push_goal(paperclip_project.id, goal)
                results.append(result)
            
            # Push issues (P2/P3)
            for issue in project.issues:
                result = await self._push_issue(paperclip_project.id, issue)
                results.append(result)
        
        return PushResult(projects=projects, pushed=True, details=results)
    
    async def _push_goal(self, project_id: str, goal: PaperclipGoal) -> dict:
        """Create a Paperclip goal with CoDRAG address metadata."""
        payload = {
            "title": goal.title,
            "description": goal.description,
            "priority": goal.priority,
            "metadata": {
                "codrag_address": goal.codrag_address,
                "codrag_command": goal.mcp_command,
                "affected_files": goal.affected_files,
                "effort": goal.effort,
                "category": goal.category,
                "source": goal.source,
            }
        }
        return await self._post(f"/api/goals", payload)
```

---

## 5. The CoDRAG Address Protocol

### 5.1 Address Format

```
codrag://<project_id>/<item_id>
codrag://<project_id>/<item_id>?context=impact     # request impact analysis
codrag://<project_id>/<item_id>?context=full        # full code context
codrag://<project_id>/scan?category=architecture    # query all findings
```

### 5.2 Resolution: How Paperclip Uses CoDRAG Addresses

When a Paperclip agent picks up an issue with a CoDRAG address, it can:

```python
# Paperclip agent workflow (conceptual):

# 1. Check if the issue is still valid
result = codrag_audit(action="scan")
still_active = any(f.id == "HEALTH-a7b9" for f in result.findings)

# 2. Get deep context for the issue
context = codrag_audit(action="refactor", finding_ids=["HEALTH-a7b9"])
# → Returns: affected files with code snippets, dependencies, impact

# 3. Understand blast radius
impact = codrag_impact(file_path="src/auth/login.py", direction="dependents")
# → Returns: what breaks if this file changes

# 4. After fixing, verify the fix
verify = codrag_audit(action="verify", analyzers=["circular_deps"])
# → Returns: updated findings (should show HEALTH-a7b9 resolved)
```

### 5.3 CoDRAG Address as HTTP Endpoint

The CoDRAG daemon can resolve addresses via its existing HTTP API:

```
GET /projects/{project_id}/opportunities?id=HEALTH-a7b9
  → Returns the ActionItem JSON if still active, or 404 if resolved

GET /projects/{project_id}/opportunities/HEALTH-a7b9/context
  → Returns: affected files, code context, impact analysis
  → This is the "deep look" endpoint for Paperclip agents
```

---

## 6. Integration with Pi Agent (Phase 66)

Pi's **Watchdog scenario** already runs after every pipeline rebuild. The natural extension:

```
Pipeline completes
  → Pi Watchdog scans for delta (new/resolved findings)
  → Pi pushes NEW findings to Paperclip as issues
  → Pi marks RESOLVED findings in Paperclip as closed
  → Paperclip agents pick up new issues automatically
```

### 6.1 Pi as the Push Trigger

```python
# Addition to pi_agent.py Watchdog scenario:

def _run_watchdog(self):
    """Scenario A: Watchdog with Paperclip push."""
    # ... existing delta computation ...
    
    if delta["new"]:
        # Push new findings to Paperclip
        from codrag.adapters.paperclip_push import PaperclipPushEngine
        engine = PaperclipPushEngine(self._paperclip_config)
        await engine.push_new_findings(delta["new"], self.project_id)
    
    if delta["resolved"]:
        # Close resolved items in Paperclip
        await engine.close_resolved(delta["resolved"], self.project_id)
```

### 6.2 Pi Dispatcher → Paperclip Triage

The **Dispatcher scenario** groups findings by root cause. After grouping:

```
Pi Dispatcher runs
  → Groups 50 findings into 8 root-cause clusters
  → Pushes each cluster as a Paperclip Goal (with all sub-items as issues)
  → Assigns based on category: architecture → "Architect" agent, 
                                security → "Security" agent, etc.
```

---

## 7. What We Don't Build (Scope Boundaries)

| We Build | We Don't Build |
|----------|----------------|
| Push adapter (CoDRAG → Paperclip) | Pull adapter (Paperclip → CoDRAG) |
| CoDRAG address resolution | Paperclip's internal task management |
| Grouping logic (category/module) | Agent assignment logic (Paperclip owns this) |
| Delta sync (new/resolved) | Bi-directional state sync |
| Dry-run preview | Complex conflict resolution |
| HTTP API endpoints | Paperclip UI modifications |

**CoDRAG stays a knowledge provider.** It discovers, groups, pushes. Paperclip manages, assigns, tracks.

---

## 8. Configuration

### 8.1 Settings Store

```json
{
  "paperclip": {
    "enabled": false,
    "url": "http://localhost:3000",
    "company_id": "my-company",
    "api_key": "",
    "auto_push": false,
    "push_strategy": "category",
    "min_priority": "P2",
    "exclude_categories": [],
    "push_on_watchdog": false
  }
}
```

### 8.2 Dashboard UI (AI Gateway Extension)

The Paperclip configuration would live in the AI Gateway panel:

- **Enable/disable** Paperclip integration
- **URL + Company** configuration
- **Push strategy** selector (Category / Module / Root-cause)
- **Priority filter** (only push P0-P1? or include P2?)
- **Auto-push toggle** (Pi pushes after each scan)
- **Manual push button** ("Push to Paperclip now")
- **Last push status** indicator

---

## 9. Implementation Phases

### Phase A: Core Adapter (2-3 days)
- [ ] Create `paperclip_models.py` — Paperclip data models
- [ ] Create `paperclip_grouper.py` — Category-based grouping
- [ ] Create `paperclip_push.py` — Push engine with dry-run support
- [ ] Add `paperclip` config to settings_store
- [ ] Add `GET/POST /paperclip/push` API endpoints

**Exit criteria:** Can manually push opportunities to Paperclip via `POST /paperclip/push`.

### Phase B: CoDRAG Address Resolution (1-2 days)
- [ ] Formalize CoDRAG address format in ActionItem
- [ ] Add `/opportunities/{item_id}/context` endpoint
- [ ] Document address protocol for Paperclip agent consumption

**Exit criteria:** Paperclip agent can resolve a CoDRAG address to get current status + context.

### Phase C: Pi Integration (1-2 days)
- [ ] Add `push_on_watchdog` support to Pi Watchdog scenario
- [ ] Add delta-push logic (new findings → Paperclip issues, resolved → close)
- [ ] Add Dispatcher → Paperclip cluster push

**Exit criteria:** New findings automatically appear in Paperclip after pipeline rebuild.

### Phase D: Dashboard UI (2-3 days)
- [ ] Paperclip config section in AI Gateway panel
- [ ] Manual push button with dry-run preview
- [ ] Push history log
- [ ] Module-aware grouping strategy (requires atlas data)

**Exit criteria:** User can configure and trigger Paperclip push from dashboard.

---

## 10. The Elegance: Why the Hybrid Architecture Works

### 10.1 CoDRAG Stays Pure via MCP

CoDRAG doesn't become a project management tool. It stays a **knowledge provider**. The Paperclip adapter is just another export format — like SARIF is an export for GitHub, the Paperclip push is an export for Paperclip. Same `ActionItem` model, different serialization.

### 10.2 CoDRAG Addresses Enable Self-Healing

Because every Paperclip issue carries a `codrag_address`, Paperclip agents can:
- Verify the issue still exists before starting work
- Get fresh context at work-time (not stale push-time data)
- Confirm the fix by re-running the specific analyzer
- Discover related issues that share the same root cause

### 10.3 The Grouper Is the Intelligence

The raw list of 50-200 ActionItems is overwhelming for a PM board. The Grouper transforms flat findings into a meaningful project hierarchy. The module-aware strategy is particularly powerful: it creates one project per CoDRAG module, so "Pipeline Engine" gets one board with all its issues, and "UI Library" gets another. This mirrors how teams actually organize work.

### 10.4 No Paperclip Lock-In

The adapter speaks HTTP. If Paperclip is replaced by Linear, Jira, or GitHub Projects, we swap the HTTP calls. The grouping logic and CoDRAG address protocol are adapter-agnostic.

---

## 11. Open Questions

> [!IMPORTANT]
> **Q1: Paperclip API contract.** What are Paperclip's actual API endpoints for creating projects, goals, and issues? We need to inspect the Paperclip codebase to confirm the data model.

> [!IMPORTANT]
> **Q2: Auto-push cadence.** Should Pi auto-push on every Watchdog scan (every pipeline rebuild) or on a schedule (daily)? Too frequent → noisy Paperclip boards. Too infrequent → stale data.

> [!NOTE]
> **Q3: Deduplication.** When CoDRAG pushes the same finding twice (same ID, updated description), should it create a new Paperclip issue or update the existing one? This requires Paperclip to support `codrag_address` as a unique external key.

> [!NOTE]
> **Q4: Agent context delivery.** When a Paperclip agent picks up a CoDRAG-originated issue, should the issue body include the full context, or should the agent call `codrag_audit(action="refactor")` at work-time for fresh context?

---

## Cross-References

| Document | Relationship |
|----------|-------------|
| [Phase 57B: ActionItem Model](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/audit/action_item.py) | The core data model pushed to Paperclip |
| [Phase 59: Roadmap & TODO](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/todo_scanner.py) | Discovery engine for in-code TODOs |
| [Phase 59D: Roadmap Miner](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/roadmap_miner.py) | Discovery engine for planning-intent keywords |
| [Phase 62 Doc 10: Universal Adapter](../Phase62_Pi-research/10_Universal_Adapter_Architecture.md) | Hexagonal architecture for adapters |
| [Phase 63: Opportunities](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/audit/opportunity_manager.py) | Aggregator that feeds this push adapter |
| [Phase 66: Pi Agent](../Phase66_Pi-Agent/README.md) | Auto-trigger for push on Watchdog scans |
| [Paperclip Integration Research](../Phase62_Pi-research/Paperclip%20+%20Sequential%20Thinking%20MCP%20+%20Superpowers%20Integration.md) | How Paperclip works with Claude agents |
