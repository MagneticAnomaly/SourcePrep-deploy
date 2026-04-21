# Agentic Integration Guide

How to connect Prep to multi-agent frameworks — Paperclip, CrewAI, AutoGen, LangGraph, or any system that runs multiple AI workers against a codebase.

---

## The Problem

When you run multiple AI agents in parallel — a security reviewer, a UI generator, an API scaffolder — each agent gets the **same** raw codebase dump. A security agent wastes tokens reading component styles. A UI agent wastes tokens reading deployment configs. Every agent gets noise from every other agent's domain.

## The Solution

Prep's `role` parameter gives each agent a context view shaped for its job. Same index, no extra setup:

```
prep(role="security")          → auth, data access, infra, config
prep(role="ux designer")       → components, design tokens, layouts
prep(role="backend engineer")  → business logic, data models, API surface
prep(role="ceo")               → module summaries, health metrics, strategy
```

---

## Setup: One Instruction Per Agent

### For Paperclip

Each Paperclip agent has an `AGENTS.md` file. Add one line to each agent's instructions:

```markdown
## Context
At the start of every task, call `prep(role="<agent name>")` for codebase context.
```

That's it. Prep resolves the agent name automatically — `"SecurityReviewer"`, `"UXDesigner"`, `"QADevOpsLead"`, `"ContentStrategist"` all resolve correctly thanks to built-in CamelCase splitting and keyword decomposition.

#### Example: CTO Agent

**AGENTS.md:**
```markdown
# CTO Agent

You are the CTO. You make technical architecture decisions and evaluate engineering trade-offs.

## Context
At the start of every task, call `prep(role="cto")` for codebase context.
This gives you architecture-level module summaries, hub files, cross-cutting concerns,
and technical debt signals — without implementation-level noise.
```

#### Example: Security Reviewer Agent

**AGENTS.md:**
```markdown
# Security Reviewer

You review code changes for security vulnerabilities, auth issues, and data exposure risks.

## Context
At the start of every task, call `prep(role="security")` for codebase context.
This gives you authentication code, data access patterns, infrastructure configuration,
and compliance-relevant files — filtered for your security focus.
```

#### Example: UX Designer Agent

**AGENTS.md:**
```markdown
# UX Designer

You review and propose UI/UX improvements based on design system principles.

## Context
At the start of every task, call `prep(role="ux designer")` for codebase context.
This gives you components, design tokens, layout patterns, and Storybook documentation —
without backend infrastructure noise.
```

---

### For CrewAI

Each CrewAI agent has a `role` field. Pass it directly:

```python
from crewai import Agent, Task, Crew

security_agent = Agent(
    role="Security Reviewer",
    goal="Review code for vulnerabilities",
    backstory="You are a senior security engineer...",
    tools=[prep_tool],  # MCP tool
)

# In the agent's task, the tool call uses role=
security_task = Task(
    description="""
    First, call prep(role="security reviewer") to get security-focused 
    codebase context. Then review the recent changes for vulnerabilities.
    """,
    agent=security_agent,
)
```

### For AutoGen / LangGraph

Pass the role in the system prompt or tool invocation:

```python
# AutoGen agent config
security_config = {
    "name": "SecurityReviewer",
    "system_message": """You are a security reviewer.
    At the start of each task, call prep(role="security") for context.""",
}

# LangGraph node
def security_node(state):
    context = prep_tool.invoke({"role": "security"})
    return {"context": context, **state}
```

### For Any Framework

The pattern is always the same:

1. **Name your agent** with a descriptive role title
2. **Add one instruction** to call `prep(role="<role name>")` at task start
3. **Prep resolves** the role name automatically — no mapping file needed

---

## What Each Role Sees

### Executive Roles (CEO, CFO, VP)
- **Module-level summaries** (no file paths, no code)
- **Health metrics** (opportunities, confidence scores)
- **Cross-cutting domain tags** (architecture, strategy)
- **Budget:** ~1500 chars — scannable in 30 seconds

### Manager Roles (Tech Lead, Engineering Manager, Product Manager)
- **Module summaries** + **key file highlights**
- **Hub files** (most-connected code in the project)
- **Technical debt signals** and architecture patterns
- **Budget:** ~2500 chars

### Practitioner Roles (Engineer, Designer, Security, QA)
- **File-level detail** for domain-relevant files
- **API surfaces** and component interfaces
- **Design patterns** within their scope
- **Budget:** ~3500 chars

### Onboarding Roles (Intern, Junior)
- **Everything a senior sees** + documentation, readmes, onboarding guides
- **Higher detail level** (more hand-holding)
- **Bigger budget:** ~4000+ chars (they need more context, not less)

---

## How Resolution Works

Prep decomposes any role string into recognizable keywords:

```
Input: "QADevOpsLead"
  ↓ CamelCase split → "qa dev ops lead"
  ↓ Keyword match   → qa (base), devops (base), lead (modifier)
  ↓ Blend           → blend(qa=50%, devops=50%) + lead modifier
  ↓ Output          → Infrastructure + testing + data focus,
                       higher centrality, quality-aware
```

### Coverage

The keyword map covers **160+ keywords** across every business department:

- Engineering, Design, Security, QA, DevOps, Data/AI/ML
- Product, Marketing, Sales, Finance, Legal, HR
- Support, DevRel, Architecture, Documentation
- Executive titles (CxO, VP, Director, President, Founder)
- Seniority modifiers (Senior, Junior, Staff, Principal, Lead)

**Unknown role names** (like `"Bob"`) fall back to the broadest engineering view. No agent ever gets empty context.

---

## Advanced: Custom Role Vectors

For teams with highly specialized roles not covered by keyword decomposition, you can define custom role vectors in the project configuration:

```json
// .runprep/config.json
{
  "custom_roles": {
    "regulatory_affairs": {
      "layer_weights": {
        "documentation": 0.9,
        "configuration": 0.7,
        "business_logic": 0.5,
        "testing": 0.4
      },
      "domain_affinity": ["compliance", "legal", "policy", "audit", "regulatory"],
      "centrality_weight": 0.4,
      "detail_level": 0.5,
      "max_chars": 2500
    }
  }
}
```

Custom roles take precedence over keyword decomposition during resolution.

---

## Performance

| Operation | Latency |
|-----------|---------|
| Cache read (pre-generated role) | ~0.1ms |
| Live generation (novel compound role) | ~200ms |
| Pre-caching all 13 built-in roles | ~3.2s (at index build time) |

Role projection adds negligible overhead to MCP tool calls.

---

## FAQ

### Does each agent need Prep installed separately?
No. All agents connect to the **same Prep daemon** (one instance, one index). The `role` parameter is just a filter applied at read time.

### Can agents share context across roles?
Yes — an orchestrator agent can call `prep()` without a role to get the full atlas, then delegate to specialized agents who each call `prep(role="...")` for their focused view.

### What if my agent framework doesn't support MCP?
Use the HTTP API directly: `GET /projects/{project_id}/atlas?role=security`. Any framework that can make HTTP requests works.

### Can I use this without an agentic framework?
Absolutely. The `role` parameter works in any MCP client (Cursor, Windsurf, Claude Desktop, Antigravity). Just say `"prep role=security"` in your prompt and the AI will pass the parameter.

### Does role context replace the normal atlas?
No — role context is **appended** to the standard atlas response. The agent gets both the structural overview and the role-filtered deep dive.

---

## Related Documentation

- [Role-Aware Context Reference](./ROLE_AWARE_CONTEXT.md) — Full role resolution reference with every supported title
- [MCP Onboarding](./MCP_ONBOARDING.md) — Setting up Prep with AI editors
- [CLI Reference](./CLI.md) — `prep context --role` usage
- [API Reference](./API.md) — HTTP API documentation
