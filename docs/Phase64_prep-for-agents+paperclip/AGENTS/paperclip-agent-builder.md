---
description: Paperclip AI agent company for any codebase — from codebase analysis through deployed
---

# Paperclip Agent Builder Pipeline

Universal workflow for analyzing a codebase, designing an agent team, creating instruction files, and deploying to Paperclip. Works with any project that has CoDRAG indexed.

---

## Phase 1: Codebase Discovery

**Goal:** Understand what the project is, what it does, and what work needs to happen.

### Step 1.1 — Structural Scan
// turbo
```
Call codrag() to get the module map, hub files, and focus areas.
```

Read the output carefully. Identify:
- **Languages and frameworks** in use
- **Module boundaries** (frontend, backend, infra, docs, tests)
- **Hub files** (most-connected files = highest blast radius)
- **Focus areas** the user has flagged

### Step 1.2 — Business Context

Read any business/product docs (`README.md`, `docs/`, `Docs/`, `roadmap*`, `concept*`, `overview*`) to understand:
- What the product does and who it's for
- Business model and current state (MVP, alpha, production, broken?)

### Step 1.3 — Architecture Audit
// turbo
```
Call codrag_audit() to get codebase health findings.
```

Note: large files, circular deps, test gaps, naming issues, tech debt hotspots.

### Step 1.4 — Roadmap & Priorities

Read roadmap/phase docs. Identify what's broken vs. missing vs. planned, and the critical path.

**Output:** You can now answer: "What is this project, what state is it in, and what comes next?"

---

## Phase 2: Team Design

**Goal:** Define the minimal agent team that matches this project's actual needs.

### Step 2.1 — Identify Work Domains

Every project has some combination of these. Check which apply:

| Domain | Signals | Typical Role |
|--------|---------|-------------|
| Strategy & Coordination | Complex roadmap, multiple agents | CEO |
| Engineering (code) | Source code to write/maintain | CTO / Engineer |
| Product (specs) | UX maps, feature specs, stories | VP Product / PM |
| Design (UI/UX) | Frontend, design system, CSS | UX Designer |
| Marketing / Brand | Marketing site, copy, GTM | CMO |
| Content / Community | Blog, docs, social, community | VP Content |
| Quality / DevOps | Tests, CI/CD, deploys | QA/DevOps Lead |
| Data / Analytics | Pipelines, dashboards, ML | Data Engineer |
| Security | Auth, permissions, compliance | Security Lead |

**Rule of thumb:** Start with 4-7 agents. Hire more later via Paperclip governance.

### Step 2.2 — Define the Org Chart

Every Paperclip company needs exactly one CEO reporting to Board (human founder). ICs report to their functional lead.

```
Board (human)
  └── CEO
       ├── CTO
       │    └── QA/DevOps Lead
       ├── VP Product
       │    └── UX Designer
       └── CMO
            └── VP Content
```

### Step 2.3 — Collaboration Axes

Document explicit relationships: who sends specs to whom, who validates whose work, who has veto power over what. Don't leave these implied.

---

## Phase 3: Knowledge Mapping

**Goal:** Map codebase files to each agent's domain using CoDRAG's role-scoped context.

### Step 3.1 — Role-Scoped Discovery
// turbo
```
For each agent, call codrag(role="<agent name>") using the agent's role name
(e.g. "ceo", "engineer", "design engineer", "qa").
CoDRAG resolves the name into weighted context — hub files, module summaries,
and focus areas filtered for that role's concerns.

Then supplement with codrag_search() for targeted queries:
  - CTO: "architecture", "state machine", "API routes", "database schema"
  - VP Product: "UX map", "user flow", "feature spec"
  - UX Designer: "design system", "CSS tokens", "component library"
  - CMO: "marketing", "brand", "go-to-market"
  - QA: "test", "CI", "deploy", "monitoring"
```

### Step 3.2 — Assign Primary vs. Extended Sources

For each agent:
- **Primary sources (3-5 files)** → AGENTS.md. Files needed on almost every task.
- **Extended catalog (10-30 files)** → KNOWLEDGE.md (optional). On-demand.

Only create KNOWLEDGE.md for agents with >5 relevant source files.

---

## Phase 4: Write Agent Files

### File Structure Per Agent

```
agents/{AgentName}/
  ├── AGENTS.md      — Identity, priorities, codrag role, sources (~1.5K chars)
  ├── SOUL.md        — Personality, values, guardrails (~2K chars)
  └── KNOWLEDGE.md   — Extended file catalog, on-demand (optional, ~1.5K chars)
```

### Step 4.1 — Write AGENTS.md (for each agent)

Template:
```markdown
# {Title} — {Full Title}

{1-2 sentence identity. What you own. Who you report to. Who you manage.}

## CoDRAG Context

Always call `codrag(role="{agent name}")` at task start for role-scoped context.
{Role-specific hints: codrag_impact before changes, codrag_audit for debt, etc.}

## Priorities

1. {Most urgent thing}
2. {Second priority}
3. {Third priority}
4. {Fourth priority}
5. {Fifth priority}

## Role-Specific Behavior

- {Behavior that Paperclip's heartbeat protocol does NOT cover}
- {Key constraint or guardrail unique to this role}
- {How to handle the most common inter-agent interaction}

## Knowledge Sources

- `{path}` — {1-word description}
- `{path}` — {1-word description}
- `{path}` — {1-word description}

{Optional: See `KNOWLEDGE.md` for full file catalog.}
```

**Size target: 1.2–1.8K chars.** Longer = duplicating Paperclip/Claude built-ins.

### Step 4.2 — Write SOUL.md (for each agent)

Template:
```markdown
# {Agent Name} Soul

## Identity
{2-3 sentences of who this agent IS. Not what they do — who they are.}

## Values
1. **{Value}.** {Why this matters in practice.}
2. **{Value}.** {Concrete guidance, not platitudes.}
3. **{Value}.** {Include tension with other values.}
4. **{Value}.** {How this shapes decisions.}
5. **{Value}.** {What makes this agent different.}

## Behavioral Guardrails
- Never {thing outside this agent's domain}
- Always {positive discipline}
- When {common situation}, {expected response}

## Communication Style
- {How they write — formal, terse, detailed, visual?}
- {Output format — specs, memos, code, mockups?}

## What Success Looks Like
{2-3 sentences. What does the world look like when this agent excels?}
```

**Size target: 2.0–2.8K chars.** The SOUL is the differentiator.

### Step 4.3 — Write KNOWLEDGE.md (CTO and design-heavy agents only)

```markdown
# {Agent Name} Knowledge Catalog

## {Category}
- `{path}`
- `{path}`
```

**Size target: 1.0–2.0K chars.** Just paths organized by category.

---

## Phase 5: What NOT to Write

**DON'T create HEARTBEAT.md** — Paperclip auto-injects its 9-step heartbeat. Duplicating it wastes ~1.5K tokens per agent per heartbeat.

**DON'T create TOOLS.md** — Claude auto-discovers MCP tools. Put role-specific hints in AGENTS.md instead:
- ✅ `codrag(role="ceo")` at task start
- ✅ `codrag_impact` before modifying hub files
- ❌ Documenting generic calling conventions

**DON'T over-explain Paperclip concepts** — The agent already has the Paperclip skill. Don't re-explain tasks, approvals, or the heartbeat lifecycle.

---

## Phase 6: Deploy to Paperclip

### Step 6.1 — Ensure Paperclip Is Running
```bash
cd ~/paperclip && pnpm dev
# Verify: curl -s http://localhost:3100/api/companies | head
```

### Step 6.2 — Create Company (if new)

In Paperclip UI (http://localhost:3100): create company, set goal, note `companyId`.

### Step 6.3 — Create Agents (if new)

For each agent: **Name**, **Role** (`ceo`/`cto`/`manager`/`engineer`/`researcher`/`pm`), **Adapter** (`claude_local`), **Model**, **Working directory** (project root), **Reports to**. Note each UUID.

### Step 6.4 — Copy Instruction Files

```bash
COMPANY_BASE="$HOME/.paperclip/instances/default/companies/{COMPANY_ID}/agents"
SRC="path/to/your/agents"
cp "$SRC/CEO/AGENTS.md" "$COMPANY_BASE/{CEO_AGENT_ID}/instructions/AGENTS.md"
cp "$SRC/CEO/SOUL.md" "$COMPANY_BASE/{CEO_AGENT_ID}/instructions/SOUL.md"
# ... repeat for each agent
```

### Step 6.5 — Create a Sync Script

```bash
#!/usr/bin/env bash
COMPANY_BASE="$HOME/.paperclip/instances/default/companies/{COMPANY_ID}/agents"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../agents" && pwd)"

cat <<'MAP' > /tmp/agent_map.txt
CEO={CEO_UUID}
CTO={CTO_UUID}
MAP

while IFS='=' read -r folder agent_id; do
  dest="$COMPANY_BASE/$agent_id/instructions"
  for f in AGENTS.md SOUL.md KNOWLEDGE.md; do
    [ -f "$SRC/$folder/$f" ] && cp "$SRC/$folder/$f" "$dest/$f"
  done
  rm -f "$dest/HEARTBEAT.md" "$dest/TOOLS.md"
  total=$(cat "$dest"/*.md 2>/dev/null | wc -c | tr -d ' ')
  echo "✓ $folder ($total bytes)"
done < /tmp/agent_map.txt
rm -f /tmp/agent_map.txt
```

### Step 6.6 — Set Environment Variables

In each agent's adapter config:
```json
{ "env": { "CODRAG_PROJECT_ID": "{your_codrag_project_id}" } }
```

### Step 6.7 — Launch

Set budgets per agent, invoke the CEO's heartbeat. The CEO delegates and the company starts operating.

---

## Quick Reference

| File | Target | Purpose |
|------|--------|---------|
| AGENTS.md | 1.2–1.8K chars | Identity, priorities, codrag role, sources |
| SOUL.md | 2.0–2.8K chars | Personality, values, guardrails |
| KNOWLEDGE.md | 1.0–2.0K chars | Extended file catalog (optional) |
| HEARTBEAT.md | ❌ Don't create | Paperclip handles this |
| TOOLS.md | ❌ Don't create | Claude auto-discovers tools |

## `codrag(role=)` — Root-Level Context

Every agent should call `codrag(role="<their role name>")` at task start. CoDRAG resolves the role name into weighted, scoped context automatically — the agent just passes its own name.

| Agent | codrag() Call | What They Get |
|-------|--------------|---------------|
| CEO | `codrag(role="ceo")` | Module summaries, strategy docs, health overview |
| CTO | `codrag(role="cto")` | Architecture, hub files, tech debt, API surface |
| VP Product | `codrag(role="pm")` | UX maps, feature specs, user flows |
| UX Designer | `codrag(role="design engineer")` | Components, design system, CSS tokens |
| CMO | `codrag(role="marketing")` | Brand docs, marketing site, GTM |
| QA/DevOps | `codrag(role="qa")` | Test coverage, CI/CD, deploy configs |
| Intern | `codrag(role="intern")` | Extra context + documentation (training wheels) |

## Additional CoDRAG Tools

| Agent Type | Extra Tools Beyond `codrag(role=)` |
|-----------|-----------------------------------|
| Engineering | `codrag_impact` before changes, `codrag_audit` for tech debt |
| QA/DevOps | `codrag_audit` for test gaps and health |
| Product/Design | `codrag_search` to find implementations that validate specs |
| Strategy/Content | Usually none — `codrag(role=)` gives them everything |