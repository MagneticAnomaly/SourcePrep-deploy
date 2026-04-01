# HR Agent — Integration Reference

> **Phase 67 Research** | Date: 2026-04-01
> How the HR Adapter connects to existing CoDRAG infrastructure and Paperclip's API.

---

## 1. CoDRAG Internal Integration Points

### 1.1 Epistemic Data Access

The HR Adapter reads from CoDRAG's indexed data. All data access is **read-only** — the HR Adapter never modifies the graph.

| Data Source | How Accessed | What It Provides |
|------------|-------------|-----------------|
| Epistemic entries | `trace_store.get_entries()` | `architecture_layer`, `domain_tags`, `epistemic_confidence` per file |
| Module clusters | `cluster_manifest.json` | Module groupings with aggregated domain tags, architecture layers, summaries |
| Graph centrality | `routing.py` / trace edges | `in_degree` per file (hub detection) |
| Atlas | `atlas_manifest.json` | Global codebase overview |
| Sub-Atlases | `atlas_role_*.md` | Pre-generated role-specific overviews |
| Role definitions | `roles_manifest.json` | Existing RoleVector profiles (Phase 64) |

### 1.2 Role Projection Engine (Phase 64)

The HR Adapter uses the same scoring engine as `codrag_search(role=...)`:

```python
# From src/codrag/core/role_projection.py (or equivalent)
from codrag.core.role_projection import compute_role_relevance, resolve_role_vector

# Score all files for a given role
role_vector = resolve_role_vector("cto", project_id)
scored_files = [
    (path, compute_role_relevance(path, epistemic, in_degree, total_files, role_vector))
    for path, epistemic in entries.items()
]
scored_files.sort(key=lambda x: x[1], reverse=True)
```

### 1.3 Auto-Populate API (Phase 67)

For file scope recommendations:

```python
# Reuse the auto-populate endpoint logic
from codrag.api.routers.scope import auto_populate_scope

recommended_paths = await auto_populate_scope(
    project_id=project_id,
    agent_role="cto",
)
```

### 1.4 LLM Client

All LLM reasoning uses the existing `LLMClient`:

```python
from codrag.core.llm_client import LLMClient, _parse_json_response

# Uses the project's configured Thinking LLM for role inference
# Uses the Instruct LLM for prose generation (AGENTS.md text)
```

---

## 2. Paperclip API Integration

### 2.1 API Surface (From Research)

Based on the DebateHaus bootstrap-agents.sh precedent and Paperclip's REST API:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/companies` | GET | List companies (get company ID) |
| `GET /api/companies/:id/agents` | GET | List all agents for a company |
| `POST /api/companies/:id/agents` | POST | Create a new agent |
| `PATCH /api/agents/:id` | PATCH | Update an agent (adapterConfig, prompt) |
| `GET /api/companies/:id/issues` | GET | List tasks/issues |

### 2.2 Agent Creation Payload

From the DebateHaus bootstrap script, the agent creation payload structure is:

```json
{
  "name": "CTO",
  "role": "cto",
  "title": "Chief Technology Officer",
  "capabilities": "Architecture, engineering, React Native, Node.js",
  "reportsTo": "<parent_agent_id>",
  "adapterType": "claude_local",
  "adapterConfig": {
    "cwd": "/path/to/project",
    "model": "claude-sonnet-4-20250514",
    "promptTemplate": "<AGENTS.md + SOUL.md concatenated>",
    "env": {
      "CODRAG_PROJECT_ID": "<project_uuid>"
    }
  }
}
```

### 2.3 Instruction Sync

From the sync-instructions.sh pattern, Paperclip stores agent instructions at:
```
~/.paperclip/instances/default/companies/<company_id>/agents/<agent_id>/instructions/
  ├── AGENTS.md
  ├── SOUL.md
  └── KNOWLEDGE.md
```

The HR Adapter can sync either via:
1. **File copy** (direct to filesystem, like sync-instructions.sh)
2. **API PATCH** (update promptTemplate via REST, like bootstrap-agents.sh)

---

## 3. CoDRAG API Exposure (New Endpoints)

The HR Adapter should be exposed via CoDRAG's FastAPI server:

### 3.1 Generate Workforce
```
POST /projects/{project_id}/hr/generate
Body: {
  "business_goal": "Optional description of the business",
  "budget_monthly_usd": 1500,       // Optional budget constraint
  "max_agents": 8,                    // Optional role count limit
  "adapter_type": "claude_local",     // Default adapter for Paperclip
  "model": "claude-sonnet-4-20250514" // Default model
}
Response: {
  "roles": [
    {
      "name": "CTO",
      "slug": "cto",
      "title": "Chief Technology Officer",
      "reports_to": "CEO",
      "agents_md": "...",
      "soul_md": "...",
      "knowledge_md": "...",
      "role_vector": { ... },
      "recommended_files": ["src/...", ...],
      "fitness_score": 0.92
    },
    ...
  ],
  "org_chart": { ... },
  "model_latency_ms": 12400
}
```

### 3.2 Audit Roles
```
POST /projects/{project_id}/hr/audit
Body: {
  "agents_dir": "./agents/",           // Path to agent files
  "paperclip_url": "http://localhost:3100",  // Optional: fetch from Paperclip
  "company_id": "uuid"                 // Optional: Paperclip company
}
Response: {
  "overall_health": 0.78,
  "roles": [
    {
      "name": "CTO",
      "fitness_score": 0.85,
      "status": "healthy",
      "recommendations": []
    },
    {
      "name": "UX Designer",
      "fitness_score": 0.52,
      "status": "significant_drift",
      "recommendations": [
        {
          "type": "scope_update",
          "description": "New design system modules detected; update Knowledge Sources"
        }
      ]
    }
  ],
  "orphaned_domains": ["payments", "analytics"],
  "proposed_new_roles": [
    {
      "title": "Payments Engineer",
      "reason": "3 payment-domain modules have no agent coverage"
    }
  ]
}
```

### 3.3 Sync to Paperclip
```
POST /projects/{project_id}/hr/sync
Body: {
  "paperclip_url": "http://localhost:3100",
  "company_id": "uuid",
  "agents_dir": "./agents/",
  "mode": "update"  // "create" | "update" | "dry-run"
}
Response: {
  "synced": 6,
  "created": 0,
  "updated": 6,
  "errors": []
}
```

---

## 4. Dashboard UI Integration

### 4.1 HR Panel (New Dashboard Section)

A new section in the CoDRAG Dashboard for workforce management:

| UI Element | Purpose |
|-----------|---------|
| **"Generate Workforce" button** | Triggers role generation from codebase analysis |
| **Agent roster table** | Shows all roles with fitness scores, last audit date |
| **Drift indicator** | Per-role health badge (🟢🟡🟠🔴) |
| **Audit button** | Runs drift analysis and displays report |
| **Sync button** | Pushes changes to connected Paperclip instance |
| **Role detail drawer** | View/edit AGENTS.md, SOUL.md, Knowledge Scope for each role |

### 4.2 Integration with Existing Agent Scope UI

The HR Adapter's role generation feeds directly into the existing AgentKnowledgeTree:
- Generated roles appear in the Role Selector dropdown
- Auto-populated file scopes pre-fill the FolderTree checkboxes
- The "Auto-Populate ✨" button can run HR Adapter's scope recommendation

---

## 5. Existing DebateHaus Patterns to Reuse

### 5.1 From `bootstrap-agents.sh`
- Agent definition array format: `FOLDER|ROLE|TITLE|REPORTS_TO|CAPABILITIES`
- JSON payload construction with jq
- Sequential agent creation with agent ID tracking for org chart wiring
- Dry-run mode for preview

### 5.2 From `sync-instructions.sh`
- Agent folder → Paperclip agent ID mapping
- File copy pattern (AGENTS.md + SOUL.md + KNOWLEDGE.md)
- Cleanup of deprecated files

### 5.3 From Agent File Format
- AGENTS.md: Priorities, Role-Specific Behavior, Knowledge Sources
- SOUL.md: Identity, Values, Behavioral Guardrails, Communication Style
- Three-file convention: AGENTS.md (what to do) + SOUL.md (who to be) + KNOWLEDGE.md (what to know)

---

## 6. Implementation Priority

Given this is a low-frequency operation (weekly or manual), the implementation order should be:

| Phase | Capability | Complexity | Value |
|-------|-----------|-----------|-------|
| **1** | CLI `codrag hr audit` — drift detection for existing agents | Medium | High — validates the concept |
| **2** | CLI `codrag hr generate` — role generation from codebase | High | High — the wow factor |
| **3** | CLI `codrag hr adopt` — enhance existing Paperclip agents | Medium | Medium — bridges existing users |
| **4** | CLI `codrag hr sync` — push to Paperclip API | Low | Medium — automation convenience |
| **5** | Dashboard UI — HR panel with visual management | High | High — enterprise feel |
| **6** | Webhook/cron — automatic periodic audits | Low | Low — nice-to-have |
