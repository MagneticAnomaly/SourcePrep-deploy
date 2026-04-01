# Phase 67 — Unified Agent Adapter Implementation Plan

> **Status:** 📋 Planning
> **Depends On:** Phase 64 (RoleVector scoring), Phase 65 (Paperclip Push Adapter), Phase 66 (Pi Agent), Phase 67 prior HR research
> **Date:** 2026-04-01

---

## 1. Vision: Three Agents, One Architecture

Phase 67 delivers **three distinct autonomous agent concepts** that share a single underlying architecture within CoDRAG:

| Agent | Role | Metaphor | Primary Task |
|-------|------|----------|-------------|
| **HR Agent** | Role Architect | The HR Department | Generates, audits, and evolves Paperclip agent role definitions using CoDRAG's epistemic knowledge graph |
| **Researcher Agent** | Proactive Technical PM | The Company Researcher | Mines CoDRAG audit findings, researches solutions, and pushes structured project plans into Paperclip |
| **Digital Custodian** | Codebase Janitor | The Building Maintenance Crew | Identifies dead code, orphaned files, and stale artifacts; executes cleanup in its own git branch with a full archive |

All three agents are **co-owned** by CoDRAG and Paperclip:
- **CoDRAG is the brain.** It provides the epistemic knowledge graph, audit findings, impact analysis, and module structure that power all agents' reasoning.
- **Paperclip is the office.** All agents project their identity into Paperclip's UI. The HR Agent appears as the workforce manager. The Researcher appears as the technical PM. The Digital Custodian appears as the maintenance lead.
- **The orchestration engine is pluggable.** All agents can be executed via a native CoDRAG daemon thread (like Pi), a LangGraph StateGraph, or a CrewAI Crew. This pluggability is the entire marketing strategy.

### 1.1 Why This Is One Plan, Not Three

All three agents share:
1. **The same CoDRAG data sources** — epistemic entries, module clusters, audit findings, RoleVector scoring, observations
2. **The same Paperclip Push infrastructure** — Phase 65's `PushEngine`, `PMAdapter`, and `paperclip_adapter.py`
3. **The same orchestrator adapter pattern** — Phase 67 HR's `OrchestratorAdapter` ABC (Doc 04) defines the universal interface all agents use
4. **The same KNOWLEDGE.md delivery pipeline** — Doc 06's context injection system works identically for all
5. **The same dashboard integration point** — the "Agent Operations" panel houses all agents' UI
6. **The same git integration layer** — the Custodian's branch management can be reused by any agent that needs to make code changes

Building them separately would duplicate 60%+ of the infrastructure. Building them together means the core adapter engine is built once, and each agent is a specialized "persona" running on top of it.

---

## 2. Competitive Landscape: Is Paperclip a Competitor to CrewAI or LangGraph?

**No. They occupy three different layers of the agent stack:**

```
┌───────────────────────────────────────────────────────────────┐
│ Layer 3: Agent Workplace / PM Tool                            │
│                                                               │
│ ┌───────────┐                                                 │
│ │ Paperclip │ — Org charts, budgets, heartbeats, task boards  │
│ └───────────┘   The "office" where agents are "employed"      │
│                 Manages WHAT agents work on                    │
└───────────────────────────────────────────────────────────────┘
                              ▲
                              │ pushes tasks to
                              │
┌───────────────────────────────────────────────────────────────┐
│ Layer 2: Agent Orchestration / Reasoning Engine               │
│                                                               │
│ ┌───────────┐  ┌─────────┐  ┌────────────┐  ┌─────────────┐ │
│ │ LangGraph │  │ CrewAI  │  │ AutoGen    │  │ Pi (native) │ │
│ └───────────┘  └─────────┘  └────────────┘  └─────────────┘ │
│                                                               │
│ The "brain wiring" — HOW an agent thinks, loops, and decides  │
│ Manages the reasoning loop, tool-use cycles, reflection       │
└───────────────────────────────────────────────────────────────┘
                              ▲
                              │ pulls knowledge from
                              │
┌───────────────────────────────────────────────────────────────┐
│ Layer 1: Codebase Intelligence / Epistemic Engine             │
│                                                               │
│ ┌────────┐                                                    │
│ │ CoDRAG │ — Module clusters, domain tags, architecture       │
│ └────────┘   layers, impact graphs, audit findings            │
│              The "knowledge" — WHAT the agent knows about     │
└───────────────────────────────────────────────────────────────┘
```

**Key insight:** CoDRAG (Layer 1) and Paperclip (Layer 3) are not competitors to anything in Layer 2. LangGraph, CrewAI, and AutoGen are all potential **execution engines** that CoDRAG can power and Paperclip can manage. This makes all three layers complementary, not competitive.

### 2.1 The Marketing Trifecta

By building adapters for LangGraph and CrewAI alongside native Paperclip support, we get **three distinct marketing channels**:

| Platform | Blog Post Title | Target Audience | CoDRAG Value Prop |
|----------|----------------|-----------------|-------------------|
| **Paperclip** | "How CoDRAG's HR Agent Auto-Generates Your Agent Workforce" | Paperclip users wanting smarter agent provisioning | CoDRAG = the brain that makes Paperclip agents useful |
| **LangGraph** | "Building an Autonomous Tech Lead with CoDRAG + LangGraph" | LangChain ecosystem (~500K devs) | CoDRAG = the codebase memory LangGraph agents have been missing |
| **CrewAI** | "A Self-Healing Codebase: CrewAI Crews Powered by CoDRAG Intelligence" | CrewAI community (~200K installs) | CoDRAG = the knowledge base that makes role/goal/backstory actually grounded |

Each framework's community is incentivized to amplify projects that showcase their tools doing impressive things. CoDRAG solves the exact problem all three communities struggle with: **how do you give an autonomous agent real, structural codebase knowledge?**

---

## 3. Unified Architecture

### 3.1 The Shared Core

All three agents consume the same `AgentCore` — a shared Python module that wraps CoDRAG's internal APIs into a clean interface for any orchestration engine:

```
src/codrag/agents/
├── __init__.py
├── core.py                        # Shared AgentCore: CoDRAG data access + Paperclip push
├── hr/
│   ├── __init__.py
│   ├── engine.py                  # HR-specific logic: role generation, drift detection, org charts
│   ├── adapters/
│   │   ├── paperclip.py           # Paperclip-native HR execution (daemon thread)
│   │   ├── langgraph_adapter.py   # LangGraph StateGraph for HR workflow
│   │   └── crewai_adapter.py      # CrewAI Crew for HR workflow
│   └── prompts/
│       ├── generate_roles.txt
│       ├── generate_soul.txt
│       └── drift_analysis.txt
├── researcher/
│   ├── __init__.py
│   ├── engine.py                  # Researcher-specific logic: topic selection, plan formulation
│   ├── adapters/
│   │   ├── paperclip.py           # Paperclip-native researcher execution (daemon thread)
│   │   ├── langgraph_adapter.py   # LangGraph StateGraph for research workflow
│   │   └── crewai_adapter.py      # CrewAI Crew for research workflow
│   └── prompts/
│       ├── topic_selection.txt
│       ├── research_synthesis.txt
│       └── plan_formulation.txt
├── custodian/
│   ├── __init__.py
│   ├── engine.py                  # Custodian-specific: dead code detection, cleanup planning
│   ├── git_ops.py                 # Branch management, archive commits, PR creation
│   ├── adapters/
│   │   ├── paperclip.py           # Paperclip-native custodian execution
│   │   ├── langgraph_adapter.py   # LangGraph StateGraph for cleanup workflow
│   │   └── crewai_adapter.py      # CrewAI Crew for cleanup workflow
│   └── prompts/
│       ├── dead_code_analysis.txt
│       ├── cleanup_plan.txt
│       └── archive_summary.txt
└── shared/
    ├── paperclip_client.py        # Shared Paperclip REST client (reuses Phase 65 adapter)
    ├── codrag_data.py             # Shared CoDRAG data access (audit, atlas, impact)
    ├── git_client.py              # Shared git operations (branch, commit, diff)
    └── models.py                  # Shared data models (RoleSpec, ResearchTopic, CleanupPlan, etc.)
```

### 3.2 The AgentCore Interface

```python
class AgentCore:
    """Shared foundation for all CoDRAG-powered agents.
    
    Provides read-only access to CoDRAG's epistemic knowledge and
    write access to Paperclip's project management API.
    """
    
    # ── CoDRAG Read Access (Brain) ──
    def get_audit_findings(self) -> List[ActionItem]:
        """Pull the latest audit findings from CoDRAG's opportunity manager."""
    
    def get_module_structure(self) -> List[ModuleEntry]:
        """Get the current module cluster map with domain tags and layers."""
    
    def get_impact_radius(self, file_path: str) -> ImpactResult:
        """Trace what depends on a given file."""
    
    def get_atlas(self, role: Optional[str] = None) -> str:
        """Get a structural overview, optionally filtered by role."""
    
    def search_code(self, query: str, role: Optional[str] = None) -> str:
        """Semantic search with optional role scoping."""
    
    def get_role_vector(self, role_slug: str) -> RoleVector:
        """Get or generate a RoleVector for scoring file relevance."""
    
    def save_observation(self, content: str, file_path: Optional[str] = None):
        """Persist a cross-session observation."""
    
    # ── Paperclip Write Access (Office) ──
    def push_project(self, project: PMProject) -> PushResult:
        """Create or update a project in Paperclip."""
    
    def push_goal(self, project_id: str, goal: PMGoal) -> PushResult:
        """Create a goal (P0/P1 priority item) in Paperclip."""
    
    def push_issue(self, project_id: str, issue: PMIssue) -> PushResult:
        """Create an issue (P2/P3 backlog item) in Paperclip."""
    
    def create_agent(self, role_spec: RoleSpec) -> str:
        """Create a new Paperclip agent and return its ID."""
    
    def update_agent(self, agent_id: str, role_spec: RoleSpec) -> None:
        """Update an existing Paperclip agent's instructions."""
```

This interface is what every adapter — Paperclip-native, LangGraph, or CrewAI — consumes. The orchestration framework decides *how* to reason; `AgentCore` decides *what data is available*.

### 3.3 How Each Orchestrator Adapter Works

#### Native Paperclip Adapter (Daemon Thread)

Runs inside the CoDRAG daemon as a daemon thread, just like Pi Agent. Uses CoDRAG's internal Python imports directly (no MCP overhead). Best for production use — lowest latency, no external dependencies.

```python
# src/codrag/agents/hr/adapters/paperclip.py

class HRPaperclipAdapter:
    """Runs HR workflows as a daemon thread inside the CoDRAG server.
    
    Triggered by:
    - Manual CLI: `codrag hr generate`
    - Dashboard button: "Generate Workforce"
    - Post-pipeline hook: drift detection after rebuild
    """
    
    def __init__(self, core: AgentCore, llm_client: LLMClient):
        self.core = core
        self.llm = llm_client
    
    async def generate_workforce(self, mode: str, roles: List[str] = None) -> List[RoleSpec]:
        """The main HR generation loop."""
        # 1. Read codebase structure
        modules = self.core.get_module_structure()
        atlas = self.core.get_atlas()
        findings = self.core.get_audit_findings()
        
        # 2. LLM reasons about what roles are needed
        prompt = self._build_generation_prompt(modules, atlas, findings, mode, roles)
        response = await self.llm.generate(prompt, task="hr_generate")
        role_specs = self._parse_role_specs(response)
        
        # 3. For each role, generate AGENTS.md, SOUL.md, KNOWLEDGE.md
        for spec in role_specs:
            spec.agents_md = await self._generate_agents_md(spec)
            spec.soul_md = await self._generate_soul_md(spec)
            spec.knowledge_md = await self._generate_knowledge_md(spec)
            spec.recommended_files = await self.core.auto_populate(spec.slug)
        
        # 4. Push to Paperclip
        for spec in role_specs:
            agent_id = self.core.create_agent(spec)
            spec.paperclip_agent_id = agent_id
        
        return role_specs
```

#### LangGraph Adapter (External Script)

Runs as a standalone Python process. Connects to CoDRAG via its MCP server (or REST API). Best for showcasing CoDRAG integration with the LangChain ecosystem, and for users who prefer LangGraph's explicit state-machine semantics.

```python
# src/codrag/agents/researcher/adapters/langgraph_adapter.py

from langgraph.graph import StateGraph, END
from typing import TypedDict

class ResearchState(TypedDict):
    """State that flows through the LangGraph researcher."""
    findings: list           # Raw CoDRAG audit findings
    selected_topics: list    # Top N findings worth researching
    research_results: list   # LLM-synthesized research per topic
    paperclip_projects: list # Formatted Paperclip project payloads
    push_results: list       # API responses from Paperclip

def build_researcher_graph(core: AgentCore) -> StateGraph:
    """Build a LangGraph StateGraph for the Researcher Agent.
    
    Node A (Ingest):     Pull audit findings from CoDRAG
    Node B (Select):     LLM selects top 3 most impactful topics
    Node C (Research):   LLM researches solutions, optionally using web search
    Node D (Formulate):  Structure research into Paperclip project schemas
    Node E (Push):       POST to Paperclip via Phase 65 adapter
    """
    
    graph = StateGraph(ResearchState)
    
    # ── Node A: Ingest findings from CoDRAG ──
    def ingest(state: ResearchState) -> ResearchState:
        findings = core.get_audit_findings()
        modules = core.get_module_structure()
        # Enrich findings with impact radius
        for f in findings[:20]:  # Cap at 20 to avoid token explosion
            if f.affected_files:
                f.impact = core.get_impact_radius(f.affected_files[0])
        state["findings"] = findings
        return state
    
    # ── Node B: Select top topics ──
    def select_topics(state: ResearchState) -> ResearchState:
        # LLM reviews findings and picks the top 3 worth researching
        prompt = f"""You are a technical PM. Review these {len(state['findings'])} 
        codebase findings and select the top 3 that would most benefit from 
        deeper research and a structured implementation plan.
        
        Findings:
        {json.dumps([f.to_export_json() for f in state['findings'][:20]])}
        
        Return a JSON array of the 3 most impactful finding IDs with a 
        one-sentence rationale for each."""
        
        response = llm.invoke(prompt)
        state["selected_topics"] = parse_selected(response, state["findings"])
        return state
    
    # ── Node C: Research solutions ──
    def research(state: ResearchState) -> ResearchState:
        results = []
        for topic in state["selected_topics"]:
            # Get deep CoDRAG context for this topic
            context = core.search_code(topic.title)
            impact = core.get_impact_radius(topic.affected_files[0])
            
            prompt = f"""You are researching a solution for this codebase issue:
            
            Title: {topic.title}
            Description: {topic.description}
            Affected files: {topic.affected_files}
            Impact radius: {impact}
            Code context: {context}
            
            Produce a detailed implementation plan with:
            1. Root cause analysis
            2. Step-by-step fix procedure
            3. Estimated effort (small/medium/large)
            4. Risk assessment
            5. Testing strategy"""
            
            result = llm.invoke(prompt)
            results.append({"topic": topic, "plan": result})
        
        state["research_results"] = results
        return state
    
    # ── Node D: Formulate Paperclip projects ──
    def formulate(state: ResearchState) -> ResearchState:
        projects = []
        for r in state["research_results"]:
            project = PMProject(
                name=f"Research: {r['topic'].title}",
                description=r["plan"],
                source="researcher_agent",
                codrag_address=f"codrag://{core.project_id}/{r['topic'].id}",
            )
            projects.append(project)
        state["paperclip_projects"] = projects
        return state
    
    # ── Node E: Push to Paperclip ──
    def push(state: ResearchState) -> ResearchState:
        results = []
        for project in state["paperclip_projects"]:
            result = core.push_project(project)
            results.append(result)
        state["push_results"] = results
        return state
    
    # Wire the graph
    graph.add_node("ingest", ingest)
    graph.add_node("select_topics", select_topics)
    graph.add_node("research", research)
    graph.add_node("formulate", formulate)
    graph.add_node("push", push)
    
    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "select_topics")
    graph.add_edge("select_topics", "research")
    graph.add_edge("research", "formulate")
    graph.add_edge("formulate", "push")
    graph.add_edge("push", END)
    
    return graph.compile()
```

#### CrewAI Adapter (External Script)

Runs as a standalone Python process. Uses CrewAI's role/goal/backstory paradigm — which maps perfectly to what CoDRAG generates. Best for showcasing how CoDRAG's HR-generated role definitions can bootstrap an entire CrewAI crew.

```python
# src/codrag/agents/researcher/adapters/crewai_adapter.py

from crewai import Agent, Task, Crew, Process

def build_researcher_crew(core: AgentCore) -> Crew:
    """Build a CrewAI Crew for the Researcher Agent.
    
    Agent 1 (Codebase Analyst):   Reads CoDRAG audit data, selects topics
    Agent 2 (Solutions Architect): Researches solutions for selected topics
    Agent 3 (Technical PM):       Formats and pushes plans to Paperclip
    """
    
    # ── Agent 1: Codebase Analyst ──
    analyst = Agent(
        role="Codebase Health Analyst",
        goal="Identify the top 3 most impactful codebase issues worth fixing",
        backstory=f"""You have deep knowledge of this codebase's architecture. 
        The codebase has {len(core.get_module_structure())} modules. 
        You use CoDRAG's epistemic analysis to find issues that matter.
        
        Architecture overview:
        {core.get_atlas()[:2000]}""",
        tools=[codrag_search_tool, codrag_audit_tool, codrag_impact_tool],
        verbose=True,
    )
    
    # ── Agent 2: Solutions Architect ──
    architect = Agent(
        role="Solutions Architect",
        goal="Research and design implementation plans for codebase issues",
        backstory="""You are an expert software architect. Given a codebase 
        issue identified by the Analyst, you research best practices, 
        design a step-by-step fix, and estimate effort and risk.""",
        tools=[codrag_search_tool, web_search_tool],
        verbose=True,
    )
    
    # ── Agent 3: Technical PM ──
    pm = Agent(
        role="Technical Project Manager",
        goal="Structure research findings into actionable Paperclip projects",
        backstory="""You transform technical research into structured project 
        plans. You create projects with clear goals, subtasks, and 
        assignments that can be pushed to Paperclip's task board.""",
        tools=[paperclip_push_tool],
        verbose=True,
    )
    
    # ── Tasks ──
    analyze_task = Task(
        description="Pull the latest CoDRAG audit findings and select the top 3 most impactful issues.",
        expected_output="A JSON list of 3 findings with ID, title, affected files, and impact summary.",
        agent=analyst,
    )
    
    research_task = Task(
        description="For each of the top 3 issues, research a solution and create an implementation plan.",
        expected_output="3 implementation plans with root cause, fix steps, effort, and risk.",
        agent=architect,
        context=[analyze_task],
    )
    
    push_task = Task(
        description="Format each implementation plan as a Paperclip project and push via the API.",
        expected_output="Confirmation that 3 projects were created in Paperclip with task breakdowns.",
        agent=pm,
        context=[research_task],
    )
    
    return Crew(
        agents=[analyst, architect, pm],
        tasks=[analyze_task, research_task, push_task],
        process=Process.sequential,
        verbose=True,
    )
```

---

## 4. The HR Agent — Detailed Feature Breakdown

The HR Agent's features are fully documented in the [HR-concept-adapter](../HR-concept-adapter/) directory. This section maps those concepts to implementation files.

### 4.1 Core Capabilities (from Doc 02)

| Capability | Implementation File | Description |
|-----------|-------------------|-------------|
| **Generate** (3 modes: list, auto, auto+list) | `agents/hr/engine.py` | Analyzes codebase via epistemic data, infers roles, generates AGENTS.md + SOUL.md + KNOWLEDGE.md |
| **Adopt** (import existing agents) | `agents/hr/engine.py` | Parses existing Paperclip agents, enriches with CoDRAG intelligence, normalizes format |
| **Audit** (drift detection) | `agents/hr/engine.py` | Computes role fitness scores, detects domain drift, proposes realignments |
| **Sync** (push to Paperclip) | `agents/shared/paperclip_client.py` | Pushes AGENTS.md/SOUL.md/KNOWLEDGE.md to Paperclip via REST API or file copy |

### 4.2 Edge Cases (from Doc 05)

All edge cases documented in [05_Edge_Cases_and_Modes.md](../HR-concept-adapter/05_Edge_Cases_and_Modes.md) are handled by the `engine.py` logic:
- Insufficient codebase data → readiness score check + blocking
- Single-domain codebase → fewer, more generalist roles
- Massive monorepo → more specialized domain-owner roles  
- Re-generation → detect existing agents, offer Regenerate/Merge/Cancel
- Role elimination → NEVER auto-delete, propose for human approval

### 4.3 Context Pipeline (from Doc 06)

KNOWLEDGE.md generation follows the template in [06_Context_Pipeline_and_Knowledge.md](../HR-concept-adapter/06_Context_Pipeline_and_Knowledge.md):
- CoDRAG tool usage instructions (codrag, codrag_search, codrag_impact, codrag_observe)
- Architecture snapshot (role-filtered atlas)
- Key files list (from auto-populate, with relevance scores)
- Domain focus areas
- Project configuration metadata

---

## 5. The Researcher Agent — Detailed Feature Breakdown

### 5.1 Core Scenarios

| Scenario | Trigger | CoDRAG Data Used | Paperclip Output |
|----------|---------|-----------------|-----------------|
| **Tech Debt Prospector** | Pi Watchdog flags high-spaghetti module | `codrag_audit` findings, `codrag_impact` blast radius | "Tech Debt Cleanup" project with implementation plan |
| **Security & Dependency Analyst** | Scheduled poll of dependency files | `codrag_search` for usage patterns, web search for changelogs | P1 Goal: "Migrate library X" with migration steps |
| **Bug Bounty Hunter** | TODO Scanner produces 20+ items | TODO/FIXME `ActionItems`, module grouping | "Quick Win" issues in active sprint backlog |

### 5.2 The Research Loop

Unlike the HR Agent (which is primarily a one-shot generation + periodic audit), the Researcher Agent runs a **continuous loop**:

```
Pipeline completes
  │
  ├── Pi Watchdog runs (existing, ~10s)
  │     └── Delta: 5 new findings, 2 resolved
  │
  ├── Researcher Agent wakes up (NEW)
  │     ├── Step 1: Reads Watchdog delta + full findings list
  │     ├── Step 2: LLM selects top 3 topics worth researching
  │     ├── Step 3: For each topic:
  │     │     ├── Pull deep CoDRAG context (impact, code search)
  │     │     ├── (Optional) Web search for best practices
  │     │     └── Synthesize into implementation plan
  │     ├── Step 4: Format as Paperclip Projects/Goals/Issues
  │     └── Step 5: Push to Paperclip via Phase 65 adapter
  │
  └── Cooldown (configurable, default 1 hour)
```

### 5.3 Researcher Configuration

```json
{
  "agents": {
    "researcher": {
      "enabled": false,
      "adapter": "native",        // "native" | "langgraph" | "crewai"  
      "max_topics_per_run": 3,
      "min_finding_priority": "P2",
      "cooldown_seconds": 3600,
      "web_search_enabled": false,
      "auto_push": false,         // true = push to Paperclip automatically
      "dry_run": true             // true = generate but don't push
    }
  }
}
```

---

## 6. CLI and API Design

### 6.1 CLI Commands

```bash
# ── HR Agent ──
codrag hr generate --project <id> --mode auto          # Auto-generate workforce
codrag hr generate --project <id> --mode list --roles "CTO,QA Lead"
codrag hr generate --project <id> --mode auto+list --roles "Social Media"
codrag hr adopt --paperclip-url http://localhost:3100 --company <id>
codrag hr audit --project <id>                          # Drift detection
codrag hr audit --project <id> --dry-run                # Report only
codrag hr sync --paperclip-url http://localhost:3100 --company <id>

# ── Researcher Agent ──
codrag research run --project <id>                      # Run one research cycle
codrag research run --project <id> --adapter langgraph  # Use LangGraph adapter
codrag research run --project <id> --adapter crewai     # Use CrewAI adapter
codrag research run --project <id> --dry-run            # Generate plans, don't push
codrag research topics --project <id>                   # Show current top topics
```

### 6.2 REST API Endpoints

```
# ── HR Agent ──
POST   /projects/{pid}/hr/generate     # Generate workforce
POST   /projects/{pid}/hr/audit        # Run drift detection
POST   /projects/{pid}/hr/sync         # Push to Paperclip
GET    /projects/{pid}/hr/readiness    # Epistemic readiness score
GET    /projects/{pid}/hr/roster       # Current agent roster

# ── Researcher Agent ──
POST   /projects/{pid}/research/run    # Trigger one research cycle
GET    /projects/{pid}/research/topics # Current top research topics
GET    /projects/{pid}/research/history # History of pushed research
```

---

## 7. LLM Provider Strategy: How LangGraph & CrewAI Use Models

### 7.1 Are LangGraph and CrewAI Anthropic-only?

**No.** Both frameworks are multi-provider:

| Framework | Supported Providers | How It Connects |
|-----------|--------------------|-----------------|
| **LangGraph** | Anthropic, OpenAI, Google, Ollama, Azure, any LangChain-compatible | `ChatAnthropic`, `ChatOpenAI`, `ChatOllama`, etc. |
| **CrewAI** | Anthropic, OpenAI, Google, Ollama, Azure, LiteLLM proxy | `llm` param accepts any LiteLLM-compatible string |

Both can use **local models via Ollama** — the same Ollama endpoint CoDRAG's own `LLMClient` already talks to.

### 7.2 Can We Leverage the Existing AI Gateway Endpoint UI?

**Yes — and we should.** CoDRAG already has the AI Gateway panel where users configure model endpoints (Ollama URL, API keys, model assignments per task). We should:

1. **Add agent-specific model slots** to the existing AI Gateway Assigned Tab (just like Pi Agent already has scenario-level model assignment).
2. **The native Paperclip adapter** uses CoDRAG's `LLMClient` directly, which already reads from the AI Gateway configuration. Zero extra work.
3. **The LangGraph/CrewAI adapters** should read the same AI Gateway settings and construct their LLM client objects from those values:

```python
# In the LangGraph adapter:
from codrag.services.settings_store import settings

def _build_llm_from_gateway():
    """Construct a LangChain-compatible LLM from CoDRAG's AI Gateway config."""
    config = settings.get("pipeline_config") or {}
    provider = config.get("llm_provider", "ollama")
    model = config.get("agent_model", config.get("model_thinking", "claude-sonnet-4-20250514"))
    
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=config.get("anthropic_api_key"))
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, base_url=config.get("ollama_url", "http://localhost:11434"))
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=config.get("openai_api_key"))
```

This means users configure their models **once** in the AI Gateway, and all adapters (native, LangGraph, CrewAI) inherit those settings. No separate API key management.

---

## 8. The Digital Custodian Agent

### 8.1 Concept: The Codebase Janitor

The Digital Custodian is the third CoDRAG-native agent. While the HR Agent manages *people* and the Researcher manages *plans*, the Custodian manages the **physical state of the codebase** — cleaning up dead code, deleting orphaned files, reformatting inconsistencies, and archiving deprecated modules.

**Key differentiator:** Unlike the other two agents, the Digital Custodian **writes to the codebase**. It operates in its own git branch and maintains a full archive of everything it deletes.

### 8.2 Core Capabilities

| Capability | CoDRAG Data Source | Action |
|-----------|-------------------|--------|
| **Dead code detection** | `codrag_audit` (unused exports, orphan modules) | Identifies files/functions with zero dependents |
| **Orphan file cleanup** | Trace graph (nodes with in_degree=0 and out_degree=0) | Flags files that nothing imports and that import nothing |
| **Stale TODO removal** | TODO Scanner + `codrag_observe` staleness flags | Cleans up TODOs that have been resolved but not removed from code |
| **Deprecated module archival** | Module clusters + drift detection | Moves entire deprecated modules to an archive branch |
| **Consistent formatting** | Audit findings (naming conventions, style) | Bulk renames, import reordering, whitespace normalization |

### 8.3 Git Branch Strategy

The Custodian **never commits to main**. It operates on a dedicated branch:

```
main
  │
  ├── custodian/cleanup-2026-04-01    ← Custodian's working branch
  │     ├── commit: "Remove 3 orphaned test fixtures"
  │     ├── commit: "Archive deprecated auth_v1 module"
  │     └── commit: "Clean up 8 resolved TODOs"
  │
  └── custodian/archive               ← Long-lived archive branch
        ├── archived/auth_v1/          ← Full copy of deleted module
        ├── archived/legacy_api/       ← With README explaining why
        └── .custodian_manifest.json   ← Index of all archived items
```

**The archive branch** is the Custodian's long-term memory. Every file it deletes is first committed to the archive with a manifest entry explaining:
- What was deleted and why
- The CoDRAG address of the finding that triggered deletion
- A timestamp and the audit state at the time of deletion
- How to restore (cherry-pick hash)

### 8.4 Workflow

```
Pipeline completes
  │
  ├── Pi Watchdog → delta scan
  ├── Researcher → topic selection + research
  │
  └── Digital Custodian wakes up
        │
        ├── Step 1: Pull audit findings tagged "dead_code", "orphan", "deprecated"
        │
        ├── Step 2: For each candidate:
        │     ├── Run codrag_impact(file) → verify 0 dependents
        │     ├── LLM reviews: "Is this truly dead, or is it used dynamically?"
        │     └── Classify: SAFE_TO_DELETE | NEEDS_REVIEW | KEEP
        │
        ├── Step 3: Create git branch custodian/cleanup-{date}
        │     ├── Archive SAFE_TO_DELETE files to archive branch first
        │     ├── Delete from working branch
        │     └── Commit with CoDRAG address in message
        │
        ├── Step 4: Push to Paperclip as a "Cleanup Report" project
        │     ├── Goal: "Code cleanup: {date}" with summary
        │     └── Issues: one per deleted file/module for audit trail
        │
        └── Step 5: (Optional) Open a PR for human review
              └── PR description includes full archive manifest
```

### 8.5 Safety Guardrails

| Guardrail | Implementation |
|-----------|---------------|
| **Never auto-merge** | Custodian creates branches and PRs; a human merges |
| **Impact verification** | Every candidate is verified via `codrag_impact` before deletion |
| **Archive-first** | Nothing is deleted without first being archived |
| **Dry-run default** | `dry_run: true` by default in config — must be explicitly enabled |
| **Exclusion list** | Config allows paths to be excluded from custodian's scope |
| **Size cap** | Maximum files per cleanup run (default: 20) to keep PRs reviewable |

### 8.6 Configuration

```json
{
  "agents": {
    "custodian": {
      "enabled": false,
      "adapter": "native",
      "dry_run": true,
      "max_files_per_run": 20,
      "archive_branch": "custodian/archive",
      "auto_pr": false,
      "exclude_paths": ["docs/", "scripts/", ".github/"],
      "cooldown_seconds": 86400
    }
  }
}
```

### 8.7 CLI

```bash
codrag custodian run --project <id>                    # Run one cleanup cycle
codrag custodian run --project <id> --dry-run          # Preview only
codrag custodian run --project <id> --adapter langgraph
codrag custodian archive --project <id>                # View archive manifest
codrag custodian restore --project <id> --file <path>  # Restore from archive
```

---

## 9. Dashboard Architecture: "Agent Operations" Panel

### 9.1 Naming: Why Not "HR"?

Since there are no humans in this system, calling it "HR" is misleading. The panel manages **autonomous agent operations** — CoDRAG-controlled agents (the three above) and Paperclip-managed employees (the workforce the Staffing Agent generates).

**Proposed name: "Agent Operations"** (or "Agent Ops" in compact UI)

> **Naming note:** In the UI, the HR Agent is called the **"Staffing Agent"** to avoid human-resources connotations. Internally in code it remains `hr` for consistency with the existing docs.

### 9.2 The Two-Screen Architecture (Simplified)

Rather than duplicating endpoint/LLM configuration inside the Agent Operations panel, we keep a clean separation of concerns:

| Screen | Owns | Does NOT Own |
|--------|------|-------------|
| **Agent Operations** (new) | Agent status, config, actions, managed employees, activity logs | LLM model assignment |
| **AI Gateway Details** (existing) | Endpoints, model slots, API keys, **agent model assignment** | Agent operational config |

**Why this is simpler:**
1. The AI Gateway already has an "Assigned" tab where you map model slots to pipeline stages (Fast, Code, Deep) and Pi Agent scenarios. Adding agent model slots here is a natural extension — just 3 more rows in the same table.
2. The Agent Operations screen stays focused on *what agents do*, not *which LLM they use*. This mirrors how a project manager assigns work without managing the compute resources.
3. Users who don't use agents never see agent rows in the AI Gateway. Users who do use agents configure everything LLM-related in one place.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CoDRAG Dashboard                              │
│                                                                  │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │  AI Gateway      │  │  Agent Operations │  │  Audit        │  │
│  │  (Panel)         │  │  (Panel)          │  │  (Panel)      │  │
│  └────────┬────────┘  └────────┬─────────┘  └───────────────┘  │
│           │                     │                                │
│           ▼                     ▼                                │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐  │
│  │ AI Gateway Details  │  │ Agent Operations Details          │  │
│  │                     │  │                                    │  │
│  │ Tabs:               │  │ Tabs:                              │  │
│  │ [Endpoints]         │  │ [System Agents]                    │  │
│  │ [Assigned]          │  │ [Managed Employees]                │  │
│  │   ├─ Pipeline slots │  │                                    │  │
│  │   ├─ Pi Scenarios   │  │ (NO Endpoints tab —                │  │
│  │   └─ Agent Models◄──┼──┼── models configured here instead)  │  │
│  │ [Telemetry]         │  │                                    │  │
│  └─────────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 AI Gateway: New "Agent Models" Section in Assigned Tab

The AI Gateway's existing "Assigned" tab already groups model assignments into sections (Pipeline Stages, Pi Agent Scenarios). We add a third section:

```
┌──────────────────────────────────────────────────────────────┐
│  ← AI Gateway Details                                        │
│                                                              │
│  [Endpoints]  [Assigned]  [Telemetry]                        │
│                                                              │
│ ═══ Assigned tab ═══════════════════════════════════════════ │
│                                                              │
│  ── Pipeline Stages ──────────────────────────────────────── │
│  │ Fast (Stage 3)    │ qwen3:4b-instruct     │ [Change ▾] │ │
│  │ Code (Stage 2)    │ qwen3-coder:30b       │ [Change ▾] │ │
│  │ Deep (Stage 6-9)  │ deepseek-r1:32b       │ [Change ▾] │ │
│                                                              │
│  ── Pi Agent Scenarios ───────────────────────────────────── │
│  │ A: Watchdog       │ (no LLM)              │            │ │
│  │ B: Doctor         │ deepseek-r1:32b       │ [Change ▾] │ │
│  │ C: Geologist      │ deepseek-r1:32b       │ [Change ▾] │ │
│  │ ...               │ ...                    │            │ │
│                                                              │
│  ── Agent Operations Models ──────────────────────────── NEW │
│  │ 👔 Staffing Agent │ claude-sonnet-4        │ [Change ▾] │ │
│  │ 🔬 Researcher     │ claude-sonnet-4        │ [Change ▾] │ │
│  │ 🧹 Custodian      │ qwen3:8b              │ [Change ▾] │ │
│  │                    │                        │            │ │
│  │  ℹ️ These model assignments are used by all │            │ │
│  │  agent adapters (native, LangGraph, CrewAI) │            │ │
│  └────────────────────────────────────────────────────────── │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Implementation detail:** The agent model slots are stored in `pipeline_config` alongside the existing model keys:
```json
{
  "pipeline_config": {
    "model_fast": "qwen3:4b-instruct",
    "model_code": "qwen3-coder:30b",
    "model_thinking": "deepseek-r1:32b",
    "agent_model_staffing": "claude-sonnet-4-20250514",
    "agent_model_researcher": "claude-sonnet-4-20250514",
    "agent_model_custodian": "qwen3:8b"
  }
}
```

The `_build_llm_from_gateway()` bridge function reads these keys to construct LangChain/CrewAI LLM objects. The native adapter's `LLMClient` reads them directly.

### 9.4 Agent Operations: Level 1 — Modular Panel

The modular panel shows compact, high-level status. No LLM configuration here — just agent status and quick-glance metrics.

```
┌──────────────────────────────────────────────────────────────┐
│  🤖 Agent Operations                                  [⚙️]   │
│                                                              │
│  ┌── CoDRAG Agents (System) ─────────────────────────────┐  │
│  │                                                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │  │
│  │  │ 👔 Staffing │  │ 🔬 Research │  │ 🧹 Custodian  │  │  │
│  │  │  Agent      │  │  Agent      │  │  Agent        │  │  │
│  │  │             │  │             │  │               │  │  │
│  │  │ 6 roles     │  │ 3 topics    │  │ 12 candidates │  │  │
│  │  │ Health: 87% │  │ Last: 45m   │  │ Last: 2d ago  │  │  │
│  │  │ 🟢 Active   │  │ 🟢 Active   │  │ ⚪ Dry Run    │  │  │
│  │  └─────────────┘  └─────────────┘  └───────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── Managed Employees (Paperclip) ──────────────────────┐  │
│  │ CEO 🟢 │ CTO 🟢 │ CMO 🟡 │ VP Eng 🟢 │ UX 🟠 │ QA 🟢 │ │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [Open Agent Operations →]                                   │
└──────────────────────────────────────────────────────────────┘
```

### 9.5 Agent Operations: Level 2 — Detail Overlay

Two tabs only (no Endpoints tab — that lives in AI Gateway):

```
┌──────────────────────────────────────────────────────────────┐
│  ← Agent Operations                                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  [System Agents]  [Managed Employees]                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│ ═══ System Agents tab ═══════════════════════════════════   │
│                                                              │
│  ┌─── 👔 Staffing Agent ────────────────────────────────┐   │
│  │                                                       │   │
│  │  Status: 🟢 Active        Adapter: Native             │   │
│  │  Last Audit: 2h ago       Health: 87%                 │   │
│  │  Cooldown: 300s           Trigger: post-pipeline      │   │
│  │                                                       │   │
│  │  Model: claude-sonnet ← Configure in AI Gateway       │   │
│  │                                                       │   │
│  │  [Run Audit] [Generate Workforce] [Sync to Paperclip] │   │
│  │                                                       │   │
│  │  ── Recent Activity ──                                │   │
│  │  • 2h ago: Drift audit completed. 1 role drifted.     │   │
│  │  • 6h ago: Generated 6 roles for project CoDRAG.      │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─── 🔬 Researcher Agent ──────────────────────────────┐   │
│  │                                                       │   │
│  │  Status: 🟢 Active        Adapter: LangGraph          │   │
│  │  Last Run: 45m ago        Topics: 3                   │   │
│  │  Max Topics: 3            Auto Push: Off              │   │
│  │                                                       │   │
│  │  Model: claude-sonnet ← Configure in AI Gateway       │   │
│  │                                                       │   │
│  │  [Run Now] [View History] [Configure]                 │   │
│  │                                                       │   │
│  │  ── Latest Topics ──                                  │   │
│  │  📋 P1: Refactor circular deps (Pushed ✅)             │   │
│  │  📋 P1: Migrate Pydantic v1→v2 (Pushed ✅)             │   │
│  │  📋 P3: Clean 12 orphaned TODOs (Dry Run 🔍)          │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─── 🧹 Digital Custodian ─────────────────────────────┐   │
│  │                                                       │   │
│  │  Status: ⚪ Dry Run        Adapter: Native             │   │
│  │  Last Run: 2d ago         Candidates: 12              │   │
│  │  Branch: custodian/archive  Max Files: 20             │   │
│  │  Archive Size: 47 files     Auto PR: Off              │   │
│  │                                                       │   │
│  │  Model: qwen3:8b ← Configure in AI Gateway           │   │
│  │                                                       │   │
│  │  [Run Cleanup] [View Archive] [Configure]             │   │
│  │                                                       │   │
│  │  ── Last Cleanup Preview ──                           │   │
│  │  🗑️ test-fixtures/deprecated_auth.py (0 dependents)   │   │
│  │  🗑️ src/legacy/old_parser.py (0 dependents)           │   │
│  │  ⚠️ src/utils/helpers.py (1 dependent — needs review) │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│ ═══ Managed Employees tab ══════════════════════════════   │
│  (Same roster table as HR wireframe in Doc 05, with         │
│   per-agent detail drawers showing AGENTS.md, SOUL.md,      │
│   KNOWLEDGE.md, role vector bars, drift history)            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Key UX detail:** Each agent card shows the current model name with a "← Configure in AI Gateway" hint text. Clicking that text deep-links to the AI Gateway Details → Assigned tab → Agent Models section.

### 9.6 Component Reuse from AI Gateway

The detail overlay reuses these existing React components from the AI Gateway:

| AI Gateway Component | Agent Ops Reuse |
|---------------------|----------------|
| `DetailOverlay` container | Same outer shell, same open/close animation |
| `TabPanel` | Same tab switching (System Agents / Managed Employees) |
| `ConfigSection` | Same collapsible config blocks per agent |
| `StatusBadge` | Same 🟢🟡🟠🔴 badges for agent health |
| `ActivityLog` | Same format for recent activity feed |
| `ModelSlotRow` (new shared) | Same row component used in AI Gateway Assigned tab AND Agent Ops read-only display |

New components specific to Agent Operations:

| New Component | Purpose |
|--------------|--------|
| `AgentCard` | Compact status card (Level 1 panel) |
| `AgentDetailSection` | Expanded config + activity per agent (Level 2) |
| `RosterTable` | Managed employee table with fitness scores |
| `CleanupPreview` | Custodian's file deletion preview list |
| `ResearchTopicList` | Researcher's topic list with push status |
| `EmployeeBadges` | Compact role badges with health indicators (Level 1) |

---

## 10. Implementation Phases

### Phase A: Shared Foundation (3-4 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| A1 | Create `agents/` module structure | `src/codrag/agents/__init__.py` | Package scaffolding |
| A2 | Implement `AgentCore` | `agents/core.py` | Wraps existing CoDRAG data access + Phase 65 push engine |
| A3 | Create shared models | `agents/shared/models.py` | `RoleSpec`, `ResearchTopic`, `ResearchPlan`, `CleanupPlan` |
| A4 | Create Paperclip client wrapper | `agents/shared/paperclip_client.py` | Thin wrapper around Phase 65's `PaperclipAdapter` |
| A5 | Create CoDRAG data access | `agents/shared/codrag_data.py` | Clean interface over `run_audit()`, atlas, trace store |
| A6 | Create shared git client | `agents/shared/git_client.py` | Branch, commit, diff, archive ops for Custodian (and future agents) |

**Exit criteria:** `AgentCore` can pull audit findings and push a dummy project to Paperclip.

---

### Phase B: Staffing Agent Engine (4-5 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| B1 | Implement readiness scoring | `agents/hr/engine.py` | `compute_hr_readiness()` — checks pipeline, modules, tags |
| B2 | Implement role generation (3 modes) | `agents/hr/engine.py` | `list`, `auto`, `auto+list` as per Doc 05 |
| B3 | Implement AGENTS.md generation | `agents/hr/engine.py` + prompts | LLM-powered prose from RoleSpec |
| B4 | Implement SOUL.md generation | `agents/hr/engine.py` + prompts | Identity/values/guardrails from role type |
| B5 | Implement KNOWLEDGE.md generation | `agents/hr/engine.py` + prompts | Template from Doc 06 |
| B6 | Implement drift detection | `agents/hr/engine.py` | Role fitness scoring + threshold logic |
| B7 | Implement org chart generation | `agents/hr/engine.py` | Reports-to, manages, collaborates-with |
| B8 | Native Paperclip adapter | `agents/hr/adapters/paperclip.py` | Daemon thread, direct Python imports |

**Exit criteria:** `codrag hr generate --mode auto` produces a complete `agents/` directory with AGENTS.md + SOUL.md + KNOWLEDGE.md per role.

---

### Phase C: Researcher Agent Engine (3-4 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| C1 | Implement topic selection | `agents/researcher/engine.py` | LLM picks top N findings from audit |
| C2 | Implement research synthesis | `agents/researcher/engine.py` | LLM researches solutions per topic |
| C3 | Implement plan formulation | `agents/researcher/engine.py` | Structures research into PM project schema |
| C4 | Implement push packaging | `agents/researcher/engine.py` | Converts plans to Phase 65 `PMProject` |
| C5 | Native Paperclip adapter | `agents/researcher/adapters/paperclip.py` | Daemon thread, hooks into Pi Watchdog |
| C6 | Wire to Pi agent loop | `services/pi_agent.py` | New scenario "I: Researcher" after Watchdog |

**Exit criteria:** `codrag research run` produces 3 structured research plans and pushes them to Paperclip.

---

### Phase H: Digital Custodian Engine (3-4 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| H1 | Implement dead code detection | `agents/custodian/engine.py` | Query trace graph for zero-dependent nodes |
| H2 | Implement safety verification | `agents/custodian/engine.py` | LLM reviews each candidate: dynamic usage? reflection? |
| H3 | Implement git branch ops | `agents/custodian/git_ops.py` | Create cleanup branch, archive branch, commit + manifest |
| H4 | Implement archive manifest | `agents/custodian/engine.py` | `.custodian_manifest.json` with restore instructions |
| H5 | Implement cleanup push to Paperclip | `agents/custodian/engine.py` | Create "Cleanup Report" project with per-file issues |
| H6 | Native Paperclip adapter | `agents/custodian/adapters/paperclip.py` | Daemon thread, post-pipeline trigger |
| H7 | Wire to Pi agent loop | `services/pi_agent.py` | New scenario "J: Custodian" after Researcher |

**Exit criteria:** `codrag custodian run --dry-run` identifies dead code candidates and produces an archive plan without modifying git.

---

### Phase D: LangGraph Adapters (2-3 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| D1 | Install LangGraph dependency | `pyproject.toml` (optional extras) | `pip install codrag[langgraph]` |
| D2 | Build Staffing LangGraph adapter | `agents/hr/adapters/langgraph_adapter.py` | StateGraph: Analyze → Generate → Push |
| D3 | Build Researcher LangGraph adapter | `agents/researcher/adapters/langgraph_adapter.py` | StateGraph: Ingest → Select → Research → Push |
| D4 | Build Custodian LangGraph adapter | `agents/custodian/adapters/langgraph_adapter.py` | StateGraph: Scan → Verify → Archive → Push |
| D5 | LLM provider bridge | `agents/shared/llm_bridge.py` | Builds LangChain LLM from AI Gateway config |
| D6 | CLI integration | `cli.py` | `--adapter langgraph` flag |
| D7 | Write tutorial / blog draft | `docs/` | "CoDRAG + LangGraph: Building an Autonomous Tech Lead" |

**Exit criteria:** `codrag research run --adapter langgraph` executes the full LangGraph pipeline end-to-end.

---

### Phase E: CrewAI Adapters (2-3 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| E1 | Install CrewAI dependency | `pyproject.toml` (optional extras) | `pip install codrag[crewai]` |
| E2 | Build Staffing CrewAI adapter | `agents/hr/adapters/crewai_adapter.py` | 2-agent crew: Analyst + Generator |
| E3 | Build Researcher CrewAI adapter | `agents/researcher/adapters/crewai_adapter.py` | 3-agent crew: Analyst + Architect + PM |
| E4 | Build Custodian CrewAI adapter | `agents/custodian/adapters/crewai_adapter.py` | 2-agent crew: Analyzer + Janitor |
| E5 | CLI integration | `cli.py` | `--adapter crewai` flag |
| E6 | Write tutorial / blog draft | `docs/` | "CoDRAG + CrewAI: A Self-Healing Codebase" |

**Exit criteria:** `codrag research run --adapter crewai` executes the full CrewAI pipeline end-to-end.

---

### Phase F: Dashboard — Modular Panel (2-3 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| F1 | Create "Agent Operations" modular panel | `packages/ui/src/components/agents/AgentOpsPanel.tsx` | New ModularDashboard panel with compact agent cards |
| F2 | Agent status cards (×3) | `AgentCard.tsx` | Compact cards for Staffing, Researcher, Custodian |
| F3 | Managed employee badges | `EmployeeBadges.tsx` | Compact role badges with health indicators |
| F4 | Wire panel to API | `useAgentOps.ts` | Hook for polling agent status |
| F5 | REST API: agent status endpoints | `api/routers/agents.py` | All endpoints from Section 6.2 |

**Exit criteria:** Dashboard shows the Agent Operations panel with compact cards for all 3 system agents + managed employee badges.

---

### Phase I: Dashboard — Detail Overlay + AI Gateway Agent Models (3-4 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| I1 | Create Agent Ops detail overlay shell | `AgentOpsDetail.tsx` | Reuses `DetailOverlay` from AI Gateway |
| I2 | System Agents tab | `SystemAgentsTab.tsx` | Per-agent config sections with model read-only display + deep-link to AI Gateway |
| I3 | Managed Employees tab | `ManagedEmployeesTab.tsx` | Roster table + per-employee detail drawer (AGENTS.md, SOUL.md, Knowledge Scope, RoleVector bars) |
| I4 | Add "Agent Models" section to AI Gateway Assigned tab | `AssignedModelsPanel.tsx` | 3 new `ModelSlotRow` components for Staffing, Researcher, Custodian |
| I5 | Staffing generate wizard | `GenerateWizard.tsx` | 3-mode selector from Doc 05 wireframes |
| I6 | Custodian cleanup preview | `CleanupPreview.tsx` | File list with dependent counts and archive status |
| I7 | Researcher topic list | `ResearchTopicList.tsx` | Topic cards with push status |

**Exit criteria:** Clicking into Agent Operations opens a full detail overlay with 2 tabs, and the AI Gateway Assigned tab shows agent model slots.

---

### Phase G: CLI Commands (1-2 days)

| # | Task | File(s) | Notes |
|---|------|---------|-------|
| G1 | `codrag hr` subcommand group | `cli.py` | generate, adopt, audit, sync |
| G2 | `codrag research` subcommand group | `cli.py` | run, topics, history |
| G3 | `codrag custodian` subcommand group | `cli.py` | run, archive, restore |

---

## 11. Dependency Management

LangGraph and CrewAI are **optional dependencies**. They are NOT required to use the native Paperclip adapter.

```toml
# pyproject.toml
[project.optional-dependencies]
langgraph = ["langgraph>=0.2.0", "langchain-anthropic>=0.3.0", "langchain-ollama>=0.3.0"]
crewai = ["crewai>=0.80.0", "crewai-tools>=0.14.0"]
agents = ["codrag[langgraph,crewai]"]  # Install both
```

The native adapter uses only CoDRAG's existing dependencies (`LLMClient`, `httpx`). Users who don't want LangGraph or CrewAI never install them.

The `langchain-ollama` package is included in the LangGraph extras so that users running local models can use LangGraph without any cloud API keys.

---

## 12. Total Implementation Estimate

| Phase | Scope | Days |
|-------|-------|------|
| A | Shared Foundation | 3-4 |
| B | Staffing Agent Engine | 4-5 |
| C | Researcher Agent Engine | 3-4 |
| H | Digital Custodian Engine | 3-4 |
| D | LangGraph Adapters (all 3 agents) | 2-3 |
| E | CrewAI Adapters (all 3 agents) | 2-3 |
| F | Dashboard — Modular Panel | 2-3 |
| I | Dashboard — Detail Overlay | 3-4 |
| G | CLI Commands | 1-2 |
| **Total** | | **24-32 days** |

---

## 13. Cross-References

| Document | Relationship |
|----------|-------------|
| [HR-concept-adapter/README.md](../HR-concept-adapter/README.md) | Staffing Agent vision and capability summary |
| [HR 02: Architecture](../HR-concept-adapter/02_HR_Agent_Architecture.md) | Core capabilities, execution modes, output format |
| [HR 03: Integration Reference](../HR-concept-adapter/03_Integration_Reference.md) | CoDRAG internal integration points, Paperclip API surface |
| [HR 04: Orchestrator Adapters](../HR-concept-adapter/04_Orchestrator_Adapters.md) | Universal adapter pattern, RoleSpec dataclass, Paperclip/CrewAI/AutoGen mapping |
| [HR 05: Edge Cases & Modes](../HR-concept-adapter/05_Edge_Cases_and_Modes.md) | 3 generation modes, insufficient data handling, dashboard wireframes |
| [HR 06: Context Pipeline](../HR-concept-adapter/06_Context_Pipeline_and_Knowledge.md) | KNOWLEDGE.md design, complete context delivery pipeline, token budgets |
| [HR 07: Primary vs Agent](../HR-concept-adapter/07_Primary_vs_Agent_Alignment.md) | Architecture audit ensuring MCP use case safety + IDE user benefits |
| [Phase 65: Pushing to Paperclip](../../Phase65_PushingTasksToPaperclip/README.md) | PushEngine, PMAdapter, ActionItem → Paperclip mapping |
| [Phase 66: Pi Agent](../../Phase66_Pi-Agent/README.md) | Pi daemon thread architecture, AgentConcurrencyGate, 7 scenarios |
| [Researcher README](./README.md) | Researcher Agent concept: co-owned identity, scenarios, architecture |
