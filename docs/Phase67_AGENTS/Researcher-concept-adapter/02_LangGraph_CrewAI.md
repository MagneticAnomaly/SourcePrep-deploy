# LangGraph & CrewAI Integration Blueprint

> **Phase 67 — Adapter Architecture** | Date: 2026-04-01
> This document provides the detailed technical specification for building Prep agent adapters on LangGraph and CrewAI, including the competitive positioning analysis, the LLM provider bridge strategy, and complete code blueprints for each adapter.

---

## 1. Why LangGraph and CrewAI?

### 1.1 The Three-Layer Agent Stack

Prep, Paperclip, LangGraph, and CrewAI are **not competitors**. They occupy three complementary layers:

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
│ │ Prep │ — Module clusters, domain tags, architecture       │
│ └────────┘   layers, impact graphs, audit findings            │
│              The "knowledge" — WHAT the agent knows about     │
└───────────────────────────────────────────────────────────────┘
```

**Prep** is Layer 1 (knowledge). **LangGraph/CrewAI** are Layer 2 (orchestration). **Paperclip** is Layer 3 (workplace management). Each layer is substitutable and complementary — Prep can power any Layer 2 orchestrator, and any orchestrator can push results to any Layer 3 PM tool.

### 1.2 Competitive vs. Complementary

| Relationship | Verdict | Reasoning |
|-------------|---------|-----------|
| Prep vs. LangGraph | **Complementary** | Prep provides codebase knowledge; LangGraph provides the reasoning loop. Neither does the other's job. |
| Prep vs. CrewAI | **Complementary** | Same as above. CrewAI's `role`/`goal`/`backstory` paradigm maps perfectly to Prep-generated `RoleSpec` objects. |
| Prep vs. Paperclip | **Complementary** | Prep provides intelligence; Paperclip provides project management. They don't overlap at all. |
| LangGraph vs. CrewAI | **Competitors** | Both are Layer 2 orchestrators. Users choose one or the other (or both). |
| LangGraph vs. Paperclip | **Complementary** | LangGraph runs the agent logic; Paperclip manages the results. |
| CrewAI vs. Paperclip | **Complementary** | Same relationship — CrewAI also has internal task management, but Paperclip operates at a higher level (org charts, budgets, heartbeats). |

### 1.3 The Marketing Opportunity

Each framework's community is incentivized to amplify projects that showcase their tools doing impressive things. Prep solves the exact problem all three communities struggle with: **how do you give an autonomous agent real, structural codebase knowledge?**

| Platform | Blog Post Title | Target Audience | Community Size |
|----------|----------------|-----------------|---------------|
| **Paperclip** | "How Prep's Staffing Agent Auto-Generates Your Agent Workforce" | Paperclip users wanting smarter agent provisioning | Growing |
| **LangGraph** | "Building an Autonomous Tech Lead with Prep + LangGraph" | LangChain ecosystem | ~500K devs |
| **CrewAI** | "A Self-Healing Codebase: CrewAI Crews Powered by Prep Intelligence" | CrewAI community | ~200K installs |

---

## 2. LLM Provider Strategy

### 2.1 Multi-Provider Support

Both LangGraph and CrewAI are **multi-provider** — they are NOT Anthropic-only:

| Framework | Supported Providers | Connection Method |
|-----------|--------------------|--------------------|
| **LangGraph** | Anthropic, OpenAI, Google, Ollama, Azure, any LangChain-compatible | `ChatAnthropic`, `ChatOpenAI`, `ChatOllama`, etc. |
| **CrewAI** | Anthropic, OpenAI, Google, Ollama, Azure, LiteLLM proxy | `llm` param accepts any LiteLLM-compatible string |

Both can use **local models via Ollama** — the same Ollama endpoint Prep's own `LLMClient` already talks to. This means users running Prep with local models (no cloud API keys) can use LangGraph/CrewAI adapters with those same local models.

### 2.2 The AI Gateway Bridge

All agent model assignments are configured in the **AI Gateway Details → Assigned tab** — the same place users already configure pipeline models and Pi Agent scenarios. The agent model slots are stored in `pipeline_config`:

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

### 2.3 The `_build_llm_from_gateway()` Bridge Function

This is the central translation layer. It reads the AI Gateway config and constructs the correct LLM client object for whichever framework is being used:

```python
# src/prep/agents/shared/llm_bridge.py

from prep.services.settings_store import settings

def build_llm_for_langchain(agent_name: str):
    """Construct a LangChain-compatible LLM from Prep's AI Gateway config.
    
    Used by both LangGraph and CrewAI adapters, since CrewAI supports
    LangChain chat model objects natively.
    
    Args:
        agent_name: One of "staffing", "researcher", "custodian"
    
    Returns:
        A LangChain BaseChatModel instance configured from the AI Gateway.
    """
    config = settings.get("pipeline_config") or {}
    model_key = f"agent_model_{agent_name}"
    model = config.get(model_key, config.get("model_thinking", "claude-sonnet-4-20250514"))
    provider = _detect_provider(model, config)
    
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            api_key=config.get("anthropic_api_key"),
            max_tokens=4096,
        )
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model,
            base_url=config.get("ollama_url", "http://localhost:11434"),
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=config.get("openai_api_key"),
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=config.get("google_api_key"),
        )
    else:
        raise ValueError(f"Unknown LLM provider for model '{model}'. "
                        f"Configure provider in AI Gateway settings.")


def _detect_provider(model: str, config: dict) -> str:
    """Auto-detect the provider from the model name.
    
    Heuristics:
    - Contains "claude" or "anthropic" → anthropic
    - Contains "gpt" or "o1" or "o3" → openai
    - Contains "gemini" or "gemma" → google
    - Contains ":cloud" → look at the base model name
    - Everything else → ollama (local)
    """
    model_lower = model.lower()
    
    if "claude" in model_lower or "anthropic" in model_lower:
        return "anthropic"
    elif any(p in model_lower for p in ("gpt", "o1-", "o3-", "openai")):
        return "openai"
    elif any(p in model_lower for p in ("gemini", "gemma")):
        return "google"
    elif ":cloud" in model_lower:
        # Cloud-hosted model via Ollama → check the base name
        base = model_lower.split(":cloud")[0]
        if "claude" in base:
            return "anthropic"
        return "ollama"
    else:
        # Default to Ollama (local models like qwen3:8b, deepseek-r1:32b)
        return config.get("llm_provider", "ollama")
```

**Key design decision:** The native Paperclip adapter does NOT use this bridge — it uses Prep's `LLMClient` directly (which already reads from the same AI Gateway config). The bridge is only needed for LangGraph and CrewAI, which require LangChain-compatible chat model objects.

---

## 3. LangGraph Adapter — Detailed Blueprint

### 3.1 What Is LangGraph?

LangGraph (by LangChain) is a framework for building stateful, cyclical agent workflows as directed graphs. Each node is a function that transforms state. Edges define the flow (including conditional branching). The key advantage over vanilla LangChain is **explicit state management** — you can inspect, replay, and checkpoint any point in the agent's reasoning.

### 3.2 Why LangGraph Fits Prep

LangGraph's explicit state-machine semantics map perfectly to Prep's research workflow:

```
Ingest Prep data → Select topics → Research each → Formulate plans → Push to Paperclip
```

Each step is a discrete node. The state (`ResearchState`) travels through the graph, accumulating data. If a step fails, you can resume from the last checkpoint. If you want to add web search, you add a conditional edge after the Research node.

### 3.3 Researcher Agent — LangGraph StateGraph

```python
# src/prep/agents/researcher/adapters/langgraph_adapter.py

from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from prep.agents.core import AgentCore
from prep.agents.shared.llm_bridge import build_llm_for_langchain

class ResearchState(TypedDict):
    """State that flows through the LangGraph researcher."""
    findings: list           # Raw Prep audit findings
    selected_topics: list    # Top N findings worth researching
    research_results: list   # LLM-synthesized research per topic
    paperclip_projects: list # Formatted Paperclip project payloads
    push_results: list       # API responses from Paperclip
    errors: list             # Error log for observability


def build_researcher_graph(core: AgentCore) -> StateGraph:
    """Build a LangGraph StateGraph for the Researcher Agent.
    
    Nodes:
        ingest       — Pull audit findings from Prep
        select       — LLM selects top 3 most impactful topics
        research     — LLM researches solutions per topic
        formulate    — Structure research into Paperclip project schemas
        push         — POST to Paperclip via Phase 65 adapter
    
    Edges:
        ingest → select → research → formulate → push → END
        (Future: research → web_search → research for external docs)
    """
    llm = build_llm_for_langchain("researcher")
    graph = StateGraph(ResearchState)
    
    # ── Node: Ingest findings from Prep ──
    def ingest(state: ResearchState) -> ResearchState:
        findings = core.get_audit_findings()
        # Enrich top findings with impact radius
        for f in findings[:20]:
            if f.affected_files:
                f.impact = core.get_impact_radius(f.affected_files[0])
        state["findings"] = findings
        return state
    
    # ── Node: Select top topics ──
    def select(state: ResearchState) -> ResearchState:
        prompt = f"""You are a technical PM reviewing codebase health findings.
        
        Select the top 3 findings that would most benefit from deeper research 
        and a structured implementation plan. Prioritize issues that:
        1. Have high blast radius (many dependent files)
        2. Block other improvements
        3. Can be fixed with a clear, bounded scope
        
        Findings:
        {[f.to_summary() for f in state['findings'][:20]]}
        
        Return a JSON array: [{{"id": "...", "rationale": "..."}}]"""
        
        response = llm.invoke(prompt)
        state["selected_topics"] = _parse_selected(response, state["findings"])
        return state
    
    # ── Node: Research solutions ──
    def research(state: ResearchState) -> ResearchState:
        results = []
        for topic in state["selected_topics"]:
            # Pull deep Prep context for this specific topic
            context = core.search_code(topic.title)
            impact = core.get_impact_radius(topic.affected_files[0]) if topic.affected_files else None
            
            prompt = f"""Research a solution for this codebase issue:
            
            Title: {topic.title}
            Description: {topic.description}
            Affected files: {topic.affected_files}
            Impact radius: {impact}
            Code context: {context}
            
            Produce a detailed implementation plan:
            1. Root cause analysis
            2. Step-by-step fix procedure (with file paths)
            3. Estimated effort: small (< 2h), medium (2-8h), large (> 8h)
            4. Risk assessment
            5. Testing strategy
            6. Dependencies / blockers"""
            
            result = llm.invoke(prompt)
            results.append({"topic": topic, "plan": result.content})
        
        state["research_results"] = results
        return state
    
    # ── Node: Formulate Paperclip projects ──
    def formulate(state: ResearchState) -> ResearchState:
        from prep.agents.shared.models import PMProject
        projects = []
        for r in state["research_results"]:
            project = PMProject(
                name=f"Research: {r['topic'].title}",
                description=r["plan"],
                source="researcher_agent",
                prep_address=f"prep://{core.project_id}/{r['topic'].id}",
                priority=r["topic"].priority,
            )
            projects.append(project)
        state["paperclip_projects"] = projects
        return state
    
    # ── Node: Push to Paperclip ──
    def push(state: ResearchState) -> ResearchState:
        results = []
        for project in state["paperclip_projects"]:
            try:
                result = core.push_project(project)
                results.append(result)
            except Exception as e:
                state.setdefault("errors", []).append(str(e))
        state["push_results"] = results
        return state
    
    # Wire the graph
    graph.add_node("ingest", ingest)
    graph.add_node("select", select)
    graph.add_node("research", research)
    graph.add_node("formulate", formulate)
    graph.add_node("push", push)
    
    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "select")
    graph.add_edge("select", "research")
    graph.add_edge("research", "formulate")
    graph.add_edge("formulate", "push")
    graph.add_edge("push", END)
    
    return graph.compile()
```

### 3.4 Staffing Agent — LangGraph StateGraph

```python
# src/prep/agents/hr/adapters/langgraph_adapter.py

class StaffingState(TypedDict):
    modules: list          # Prep module structure
    atlas: str             # Codebase atlas overview
    findings: list         # Audit findings for domain tagging
    generated_roles: list  # RoleSpec objects
    instruction_files: dict  # {role_slug: {agents_md, soul_md, knowledge_md}}
    push_results: list

def build_staffing_graph(core: AgentCore, mode: str = "auto") -> StateGraph:
    """
    Nodes:
        analyze    — Read codebase structure from Prep
        generate   — LLM generates RoleSpec objects
        write      — Generate AGENTS.md, SOUL.md, KNOWLEDGE.md per role
        push       — Create agents in Paperclip
    """
    # ... (follows same pattern as Researcher)
```

### 3.5 Custodian — LangGraph StateGraph

```python
# src/prep/agents/custodian/adapters/langgraph_adapter.py

class CleanupState(TypedDict):
    candidates: list       # Files flagged as dead/orphaned
    verified: list         # Candidates that passed safety checks
    rejected: list         # Candidates that were kept
    archive_plan: dict     # Git operations needed
    push_results: list

def build_custodian_graph(core: AgentCore) -> StateGraph:
    """
    Nodes:
        scan       — Pull dead code / orphan audit findings
        verify     — LLM reviews each candidate for dynamic usage
        plan       — Build git branch + archive plan
        archive    — Execute git operations (if not dry-run)
        push       — Push cleanup report to Paperclip
    """
    # ... (follows same pattern)
```

---

## 4. CrewAI Adapter — Detailed Blueprint

### 4.1 What Is CrewAI?

CrewAI is a framework for building multi-agent teams where each agent has a `role`, `goal`, `backstory`, and a set of `tools`. Agents collaborate by passing task results to each other. CrewAI provides a higher-level abstraction than LangGraph — you describe *what* each agent should do, and CrewAI manages the orchestration.

### 4.2 Why CrewAI Fits Prep

Prep's HR-generated `RoleSpec` objects map perfectly to CrewAI's `Agent` constructor:

| Prep RoleSpec Field | CrewAI Agent Field | Example |
|----------------------|-------------------|---------|
| `title` | `role` | "Codebase Health Analyst" |
| `description` | `goal` | "Identify the top 3 most impactful codebase issues" |
| `soul_md` → identity | `backstory` | "You have deep knowledge of this codebase's architecture..." |
| `knowledge_scope` | `tools` | Prep MCP tools filtered by role |

This means Prep can auto-generate CrewAI agent definitions from its knowledge graph — a powerful selling point.

### 4.3 Researcher Agent — CrewAI Crew

```python
# src/prep/agents/researcher/adapters/crewai_adapter.py

from crewai import Agent, Task, Crew, Process
from prep.agents.core import AgentCore
from prep.agents.shared.llm_bridge import build_llm_for_langchain

def build_researcher_crew(core: AgentCore) -> Crew:
    """Build a CrewAI Crew for the Researcher Agent.
    
    Agents:
        analyst    — Equipped with Prep MCP tools. Finds issues.
        architect  — Reads analyst's findings, designs solutions.
        pm         — Formats plans and pushes to Paperclip.
    """
    llm = build_llm_for_langchain("researcher")
    atlas = core.get_atlas()
    
    # ── Agent 1: Codebase Analyst ──
    analyst = Agent(
        role="Codebase Health Analyst",
        goal="Identify the top 3 most impactful codebase issues worth fixing",
        backstory=f"""You have deep knowledge of this codebase's architecture. 
        The codebase has {len(core.get_module_structure())} modules. 
        You use Prep's epistemic analysis to find issues that matter.
        
        Architecture overview:
        {atlas[:2000]}""",
        tools=[prep_search_tool, prep_audit_tool, prep_impact_tool],
        llm=llm,
        verbose=True,
    )
    
    # ── Agent 2: Solutions Architect ──
    architect = Agent(
        role="Solutions Architect",
        goal="Research and design implementation plans for codebase issues",
        backstory="""You are an expert software architect. Given a codebase 
        issue identified by the Analyst, you research best practices, 
        design a step-by-step fix, and estimate effort and risk.
        
        For each issue, produce:
        1. Root cause analysis
        2. Step-by-step fix procedure with file paths
        3. Effort estimate (small/medium/large)
        4. Risk assessment
        5. Testing strategy""",
        tools=[prep_search_tool],
        llm=llm,
        verbose=True,
    )
    
    # ── Agent 3: Technical PM ──
    pm = Agent(
        role="Technical Project Manager",
        goal="Structure research findings into actionable Paperclip projects",
        backstory="""You transform technical research into structured project 
        plans. You create projects with clear goals, subtasks, and 
        assignments that can be pushed to Paperclip's task board.
        
        Each project must include:
        - A clear title and description
        - Priority (P0-P3)
        - Effort estimate
        - Affected files
        - Prep address for traceability""",
        tools=[paperclip_push_tool],
        llm=llm,
        verbose=True,
    )
    
    # ── Tasks ──
    analyze_task = Task(
        description="Pull the latest Prep audit findings and select the top 3 most impactful issues.",
        expected_output="A JSON list of 3 findings with ID, title, affected files, and impact summary.",
        agent=analyst,
    )
    
    research_task = Task(
        description="For each of the top 3 issues, research a solution and create an implementation plan.",
        expected_output="3 implementation plans with root cause, fix steps, effort, risk, and testing strategy.",
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

### 4.4 CrewAI Tools from Prep MCP

CrewAI agents need `Tool` objects. We wrap Prep's internal APIs:

```python
from crewai_tools import BaseTool

class PrepSearchTool(BaseTool):
    name: str = "Prep Code Search"
    description: str = "Search the codebase using natural language. Returns relevant code with structural context."
    
    def _run(self, query: str) -> str:
        return core.search_code(query)

class PrepAuditTool(BaseTool):
    name: str = "Prep Audit"
    description: str = "Get the latest codebase health audit findings."
    
    def _run(self) -> str:
        findings = core.get_audit_findings()
        return json.dumps([f.to_export_json() for f in findings[:20]])

class PrepImpactTool(BaseTool):
    name: str = "Prep Impact Analysis"
    description: str = "Analyze what depends on a file. Returns dependents and blast radius."
    
    def _run(self, file_path: str) -> str:
        result = core.get_impact_radius(file_path)
        return str(result)

class PaperclipPushTool(BaseTool):
    name: str = "Push to Paperclip"
    description: str = "Create a project in Paperclip's task board."
    
    def _run(self, name: str, description: str, priority: str = "P2") -> str:
        project = PMProject(name=name, description=description, priority=priority)
        result = core.push_project(project)
        return f"Created project: {result.project_id}"
```

---

## 5. Dependency Management

LangGraph and CrewAI are **optional dependencies**. The native Paperclip adapter works with zero external packages beyond Prep's existing `LLMClient` and `httpx`.

```toml
# pyproject.toml
[project.optional-dependencies]
langgraph = [
    "langgraph>=0.2.0",
    "langchain-anthropic>=0.3.0",
    "langchain-ollama>=0.3.0",
    "langchain-openai>=0.3.0",
]
crewai = [
    "crewai>=0.80.0",
    "crewai-tools>=0.14.0",
]
agents = ["prep[langgraph,crewai]"]  # Install both
```

**Install scenarios:**
- `pip install prep` → No agent framework dependencies. Native adapter only.
- `pip install prep[langgraph]` → LangGraph + LangChain provider packages installed.
- `pip install prep[crewai]` → CrewAI + tools installed.
- `pip install prep[agents]` → Everything installed.

The adapters use lazy imports — if you run `prep research run --adapter langgraph` without `langgraph` installed, you get a clear error message telling you to run `pip install prep[langgraph]`.

---

## 6. Running the Adapters

### 6.1 CLI

```bash
# Native adapter (default) — runs inside Prep daemon
prep research run --project <id>

# LangGraph adapter — runs as external process
prep research run --project <id> --adapter langgraph

# CrewAI adapter — runs as external process
prep research run --project <id> --adapter crewai

# Dry-run mode (any adapter)
prep research run --project <id> --dry-run

# Same pattern for HR/Staffing
prep hr generate --project <id> --adapter langgraph

# Same pattern for Custodian
prep custodian run --project <id> --adapter crewai
```

### 6.2 Programmatic Usage

```python
from prep.agents.core import AgentCore
from prep.agents.researcher.adapters.langgraph_adapter import build_researcher_graph

core = AgentCore(project_id="1d6f0b35-...")
graph = build_researcher_graph(core)
result = graph.invoke({"findings": [], "selected_topics": [], "research_results": [],
                        "paperclip_projects": [], "push_results": [], "errors": []})
print(f"Pushed {len(result['push_results'])} projects to Paperclip")
```

---

## 7. Testing Strategy

| Test Level | What | How |
|-----------|------|-----|
| **Unit tests** | LLM bridge provider detection | Mock `settings`, verify correct LangChain class returned |
| **Unit tests** | State graph node functions | Mock `AgentCore`, verify state transformations |
| **Integration test** | LangGraph dry-run | Real Prep data, mock Paperclip push, verify 3 projects generated |
| **Integration test** | CrewAI dry-run | Real Prep data, mock Paperclip push, verify crew completes |
| **E2E test** | Full push | Run adapter against live Prep + Paperclip, verify projects appear in UI |
