# HR Agent — Orchestrator Adapter Design

> **Phase 67 Research** | Date: 2026-04-01
> Universal adapter pattern for Paperclip (primary) with extensibility for CrewAI, AutoGen, and future orchestrators.

---

## 1. Design Principle: Adapter Pattern

The HR Agent generates **platform-neutral role definitions** internally, then uses **orchestrator-specific adapters** to emit the correct output format and make the correct API calls.

```
                     ┌──────────────────────┐
                     │   HR Engine Core     │
                     │                      │
                     │  Role Analysis       │
                     │  Drift Detection     │
                     │  Org Chart Reasoning │
                     │                      │
                     │  Output: RoleSpec[]  │
                     └──────────┬───────────┘
                                │
                   ┌────────────┼────────────────┐
                   │            │                 │
            ┌──────▼──────┐ ┌──▼──────────┐ ┌───▼──────────┐
            │  Paperclip  │ │  CrewAI     │ │  AutoGen     │
            │  Adapter    │ │  Adapter    │ │  Adapter     │
            │             │ │  (future)   │ │  (future)    │
            │  AGENTS.md  │ │  agents.yaml│ │  Python      │
            │  SOUL.md    │ │  tasks.yaml │ │  config      │
            │  REST API   │ │  crew.py    │ │  team.py     │
            └─────────────┘ └─────────────┘ └──────────────┘
```

---

## 2. Internal Role Specification (Platform-Neutral)

All adapters consume a common `RoleSpec`:

```python
@dataclass
class RoleSpec:
    """Platform-neutral agent role specification."""
    
    # Identity
    slug: str                          # "cto", "ux-designer", "qa-lead"
    title: str                         # "Chief Technology Officer"
    name: str                          # Display name for UI: "CTO"
    
    # Role Content
    role_description: str              # Full prose role description
    soul_description: str              # Identity, values, guardrails prose
    knowledge_context: str             # Prep-generated codebase context
    
    # Organization
    reports_to: Optional[str]          # Slug of manager role (None for top-level)
    manages: List[str]                 # Slugs of direct reports
    collaborates_with: List[str]       # Slugs of peer collaborators
    
    # Prep Integration
    role_vector: RoleVector            # Phase 64 weighted scoring profile
    recommended_files: List[str]       # Auto-populated file paths
    prep_role_slug: str              # For prep(role="<slug>") calls
    fitness_score: float               # 0.0-1.0 alignment score
    
    # Orchestrator Hints
    capabilities: List[str]            # ["architecture", "React Native", ...]
    heartbeat_interval_hours: int      # Suggested check-in frequency
    budget_monthly_usd: Optional[int]  # Suggested budget
    adapter_type: str                  # "claude_local", "http", "codex", etc.
    priority_level: int                # 0=P0 (hire first), 1=P1, etc.
    
    # Metadata
    generated_at: str                  # ISO timestamp
    generation_mode: str               # "auto", "list", "auto+list"
    epistemic_basis: Dict[str, Any]    # Summary of what data informed this role
```

---

## 3. Paperclip Adapter (Primary — Full Detail)

### 3.1 Output Format

The Paperclip adapter produces three files per role (matching the DebateHaus precedent) plus API payloads:

```
agents/
├── CEO/
│   ├── AGENTS.md          # Behavioral instructions
│   ├── SOUL.md            # Identity and values
│   └── KNOWLEDGE.md       # Prep context injection (optional)
├── CTO/
│   ├── AGENTS.md
│   ├── SOUL.md
│   └── KNOWLEDGE.md
└── _roster.json           # Machine-readable manifest
```

### 3.2 API Operations

| Operation | Paperclip Endpoint | Method | When Used |
|-----------|-------------------|--------|-----------|
| List agents | `GET /api/companies/:id/agents` | GET | Audit, Adopt |
| Create agent | `POST /api/companies/:id/agents` | POST | Generate |
| Update agent | `PATCH /api/agents/:id` | PATCH | Sync, Adopt |
| Delete agent | `DELETE /api/agents/:id` | DELETE | Elimination proposals (with Board approval) |
| List companies | `GET /api/companies` | GET | Connection setup |

### 3.3 Prompt Template Assembly

Paperclip's `claude_local` adapter takes a single `promptTemplate` field. The adapter concatenates:

```
promptTemplate = AGENTS.md + "\n\n---\n\n" + SOUL.md
```

With KNOWLEDGE.md injected as an env var or appended to AGENTS.md if present.

### 3.4 Configuration Payload

```json
{
  "name": "<slug>",
  "role": "<paperclip_role>",
  "title": "<title>",
  "capabilities": "<comma-separated>",
  "reportsTo": "<parent_agent_id>",
  "adapterType": "claude_local",
  "adapterConfig": {
    "cwd": "<project_root>",
    "model": "<user_selected_model>",
    "promptTemplate": "<AGENTS.md + SOUL.md>",
    "env": {
      "PREP_PROJECT_ID": "<project_uuid>"
    }
  }
}
```

### 3.5 Paperclip Role Mapping

| Prep Role Category | Paperclip `role` field |
|---------------------|----------------------|
| Executive (CEO, CTO, CMO) | `ceo`, `cto`, or `manager` |
| Management (VP Product, VP Content) | `manager` |
| Engineering (Lead Engineer, DevOps) | `engineer` |
| Design (UX, Design System) | `engineer` |
| Support (QA, Content Writer) | `engineer` |

### 3.6 Instruction Sync Paths

```
~/.paperclip/instances/default/companies/<company_id>/agents/<agent_id>/instructions/
  ├── AGENTS.md
  ├── SOUL.md
  └── KNOWLEDGE.md
```

The adapter supports both:
- **API sync**: PATCH promptTemplate (recommended for remote Paperclip)
- **File sync**: Direct file copy (for local Paperclip installations)

---

## 4. CrewAI Adapter (Future — Specification)

### 4.1 Output Format

```
config/
├── agents.yaml       # Role/Goal/Backstory per agent
├── tasks.yaml        # Task definitions linked to agents
└── crew.py           # Python crew configuration
```

### 4.2 YAML Mapping

```yaml
# agents.yaml (generated by HR Adapter)
cto:
  role: >
    Chief Technology Officer
  goal: >
    Own the entire technical architecture and be the principal engineer.
    Audit the codebase, architect the technical roadmap, and ship features.
  backstory: >
    You are the CTO of {company_name}. You report to the CEO.
    {soul_description}
  tools:
    - prep_search
    - prep_impact
  verbose: true
  allow_delegation: true
```

### 4.3 Prep Integration Injection

Instead of `prep(role="cto")` in AGENTS.md, the CrewAI adapter:
1. Adds `prep_search` and `prep_impact` as tools in the agent config
2. Injects role context into the `backstory` field
3. Uses CrewAI's Knowledge Base feature to point at Prep-curated files

---

## 5. AutoGen Adapter (Future — Specification)

### 5.1 Output Format

```python
# Generated team configuration
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import SelectorGroupChat

cto = AssistantAgent(
    name="CTO",
    model_client=model_client,
    system_message="""You are the CTO of {company_name}.
    {agents_md_content}
    ---
    {soul_md_content}"""
)
```

### 5.2 Team Pattern Mapping

| Prep Org Structure | AutoGen Pattern |
|---------------------|----------------|
| Hierarchical (CEO → CTO → QA) | `SelectorGroupChat` with CEO as selector |
| Flat (all peer collaborators) | `RoundRobinGroupChat` |
| Specialized handoffs | `Swarm` with handoff definitions |

---

## 6. Adapter Interface Contract

```python
class OrchestratorAdapter(ABC):
    """Base class for all orchestrator adapters."""
    
    @abstractmethod
    def emit_files(self, roles: List[RoleSpec], output_dir: Path) -> List[Path]:
        """Generate orchestrator-specific files on disk."""
        ...
    
    @abstractmethod
    def sync_to_platform(self, roles: List[RoleSpec], config: AdapterConfig) -> SyncResult:
        """Push roles to a running orchestrator instance."""
        ...
    
    @abstractmethod
    def fetch_existing_agents(self, config: AdapterConfig) -> List[RoleSpec]:
        """Read existing agents from a running orchestrator instance."""
        ...
    
    @abstractmethod
    def format_prep_injection(self, role: RoleSpec) -> str:
        """Generate platform-specific Prep integration instructions."""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter identifier (e.g., 'paperclip', 'crewai', 'autogen')."""
        ...

@dataclass
class AdapterConfig:
    """Connection configuration for an orchestrator instance."""
    platform: str                      # "paperclip", "crewai", "autogen"
    api_url: Optional[str]             # e.g., "http://localhost:3100/api"
    company_id: Optional[str]          # Paperclip company UUID
    project_cwd: str                   # Repo root path
    model: str                         # Default LLM model for agents
    adapter_type: str                  # "claude_local", "http", etc.

@dataclass
class SyncResult:
    created: int
    updated: int
    deleted: int
    errors: List[str]
    dry_run: bool
```

---

## 7. Implementation Priority

| Phase | Adapter | Status |
|-------|---------|--------|
| Now | Paperclip | Primary, full implementation |
| Later | CrewAI | Specification only, implement on demand |
| Later | AutoGen | Specification only, implement on demand |
| Later | Generic AGENTS.md | For non-orchestrated setups (just files) |

The adapter pattern ensures we can add new orchestrators without modifying the core HR engine. Each adapter is a single Python module (~100-300 lines) that implements the `OrchestratorAdapter` interface.
