# HR Agent Architecture — CoDRAG Agent Role Manager

> **Phase 67 Research** | Date: 2026-04-01
> The "HR Agent" concept — a subsystem that generates, manages, and evolves Paperclip agent roles using CoDRAG's epistemic knowledge graph.

---

## 1. System Identity

The **CoDRAG HR Adapter** is an epistemic role management engine. It operates as both:
- A **standalone tool** (CLI / API) that generates and maintains agent role files
- A **Paperclip integration** that programmatically manages agent lifecycle via Paperclip's REST API

It is NOT a runtime orchestrator. It is a **role architect** — it reasons about *what roles should exist* and *what each role should know*, then either produces files or pushes to Paperclip.

---

## 2. Core Capabilities

### 2.1 Role Generation (From Scratch)

**Input:** A CoDRAG project with a completed epistemic pipeline (at least through Stage 7 — Module Clustering)

**Process:**
1. **Analyze codebase structure**: Read module clusters, architecture layer distribution, domain tag frequency, hub files
2. **Infer organizational needs**: Use the Thinking LLM to reason about what roles are needed based on:
   - Module count and diversity (many UI modules → need a UX role)
   - Architecture layer spread (heavy infra → need DevOps)
   - Domain tag clusters (auth, payments, api → need a security role)
   - Codebase size and complexity (large → more specialized roles, small → fewer generalist roles)
3. **Generate role definitions**: For each recommended role, produce:
   - `AGENTS.md` — Behavioral instructions, priorities, knowledge sources
   - `SOUL.md` — Identity, values, communication style, guardrails
   - `KNOWLEDGE.md` — CoDRAG-specific context injection (optional)
4. **Generate org chart**: Reporting lines, collaboration axes, decision authority

**Output:** A complete `agents/` directory with per-role folders, ready for Paperclip or standalone use.

### 2.2 Role Adoption (From Existing Agents)

**Input:** An existing set of Paperclip agents (fetched via API) or existing `AGENTS.md` files

**Process:**
1. **Parse existing role definitions**: Extract role name, responsibilities, relationships, tech stack references
2. **Enrich with CoDRAG intelligence**:
   - Add `codrag(role="<role>")` calls to each agent's instruction set
   - Generate optimal Knowledge Scope file paths using Auto-Populate
   - Add CoDRAG-specific behavioral guidance (e.g., "Use codrag_search before making changes")
3. **Normalize format**: Ensure consistent structure across AGENTS.md + SOUL.md + KNOWLEDGE.md
4. **Sync to Paperclip**: Push updated promptTemplates via Paperclip API

**Output:** Enhanced agent definitions with CoDRAG integration, pushed to Paperclip.

### 2.3 Role Drift Detection (Periodic Analysis)

**Input:** Existing role definitions + current CoDRAG epistemic state (post-pipeline-run)

**Process:**
1. **For each role**, compute a **role fitness score**:
   - Compare the role's stated responsibilities to the current codebase reality
   - Use RoleVector scoring to measure alignment between role's domain affinity and actual codebase composition
   - Detect new modules/domains that no role covers (orphaned domains)
   - Detect roles whose domain has shrunk or been deprecated

2. **Apply thresholds**:
   | Fitness Score | Action |
   |--------------|--------|
   | > 0.8 | ✅ Healthy — no action needed |
   | 0.6 – 0.8 | 🟡 Minor drift — suggest priority reordering, file scope update |
   | 0.4 – 0.6 | 🟠 Significant drift — recommend role description update |
   | < 0.4 | 🔴 Critical — propose elimination, merger, or promotion to new role |

3. **Cross-role analysis**:
   - Detect overlap (two roles covering the same domain → merge or clarify boundaries)
   - Detect gaps (domain with no role coverage → propose new hire)
   - Detect over/under-specialization

4. **Generate report**: Markdown report with specific recommendations per role

**Output:** Drift analysis report + optional auto-apply of recommended changes.

### 2.4 Role Evolution (Triggered by Code Changes)

**Input:** CoDRAG pipeline rebuild event (via watcher or manual trigger)

**Process:**
1. **Diff analysis**: Compare previous and current epistemic state:
   - New modules added
   - Modules removed or deprecated
   - Domain tag distribution shifts
   - Architecture layer balance changes
2. **Impact projection**: For each role, assess whether the changes affect their domain
3. **Propose adjustments**: Generate a structured "HR Report" with:
   - Agents unaffected (no action)
   - Agents needing priority reordering
   - Agents needing scope expansion
   - New role proposals (if new domains emerged)
   - Elimination proposals (if domains were removed)

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CoDRAG HR Adapter                             │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Role        │  │  Drift       │  │  Paperclip           │   │
│  │  Generator   │  │  Detector    │  │  Sync Client         │   │
│  │              │  │              │  │                      │   │
│  │  - analyze   │  │  - fitness   │  │  - GET /agents       │   │
│  │  - infer     │  │  - threshold │  │  - POST /agents      │   │
│  │  - generate  │  │  - cross-    │  │  - PATCH /agents/:id │   │
│  │  - format    │  │    role      │  │  - sync instructions │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │               │
│  ┌──────┴─────────────────┴──────────────────────┴───────────┐  │
│  │                  CoDRAG Knowledge Layer                    │  │
│  │                                                            │  │
│  │  - Epistemic entries (architecture_layer, domain_tags)     │  │
│  │  - Module clusters (subsystem grouping)                    │  │
│  │  - RoleVector scoring engine (Phase 64)                    │  │
│  │  - Auto-Populate vetting (Phase 67)                        │  │
│  │  - Atlas + Sub-Atlas generation                            │  │
│  │  - Graph centrality (hub files, in-degree)                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  LLM Reasoning Layer                       │  │
│  │                                                            │  │
│  │  - Thinking LLM for role inference and drift analysis      │  │
│  │  - Instruct LLM for AGENTS.md/SOUL.md prose generation     │  │
│  │  - Uses existing LLMClient infrastructure                  │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
              │                                ▲
              ▼                                │
┌──────────────────────┐         ┌──────────────────────────┐
│   Paperclip API      │         │   File System            │
│   localhost:3100     │         │   agents/CEO/AGENTS.md   │
│                      │         │   agents/CEO/SOUL.md     │
│   - Companies        │         │   agents/CTO/AGENTS.md   │
│   - Agents           │         │   ...                    │
│   - Instructions     │         │                          │
└──────────────────────┘         └──────────────────────────┘
```

---

## 4. Execution Modes

### Mode 1: Generate (`codrag hr generate`)
```bash
# Analyze the codebase and generate a fresh agent workforce
codrag hr generate --project <id> --output ./agents/

# Generate with business context (optional)
codrag hr generate --project <id> --business-goal "E-commerce platform" --budget 1500
```

### Mode 2: Adopt (`codrag hr adopt`)
```bash
# Import existing Paperclip agents and enhance them with CoDRAG
codrag hr adopt --paperclip-url http://localhost:3100 --company <id>

# Import from existing agent files
codrag hr adopt --from ./existing-agents/ --output ./agents/
```

### Mode 3: Audit (`codrag hr audit`)
```bash
# Run drift detection against current codebase state
codrag hr audit --project <id> --agents ./agents/

# Generate report without auto-applying
codrag hr audit --project <id> --dry-run
```

### Mode 4: Sync (`codrag hr sync`)
```bash
# Push local agent files to Paperclip
codrag hr sync --paperclip-url http://localhost:3100 --company <id> --agents ./agents/
```

---

## 5. Agent File Format (Output)

Each role gets three files in a directory:

### `agents/<RoleName>/AGENTS.md`
```markdown
# <Title> — <RoleName>

<One-paragraph identity statement generated from codebase analysis>

## Priorities
1. <Derived from module importance and domain coverage>
2. ...

## Role-Specific Behavior
- <Behavioral guardrails derived from architecture analysis>
- When using code intelligence, call `codrag(role="<role_slug>")` for scoped context
- When making code changes, call `codrag_impact(file_path="...")` to check blast radius
- ...

## Knowledge Sources
- `<top_relevant_files_from_auto_populate>` — <description>
- ...

## CoDRAG Integration
This agent is managed by CoDRAG's HR Adapter.
- Role Vector: <serialized scoring profile>
- Last Audit: <timestamp>
- Fitness Score: <score>
```

### `agents/<RoleName>/SOUL.md`
```markdown
# <RoleName> Soul

## Identity
<Personality and identity statement, derived from role type>

## Values
1. <Value statement aligned with role domain>
...

## Behavioral Guardrails
- <Boundary definitions based on org chart position>
...

## Communication Style
- <Style guidance based on role type>
...
```

### `agents/<RoleName>/KNOWLEDGE.md` (optional)
```markdown
# <RoleName> Knowledge

## CoDRAG Context
When working on this project, always start by calling:
\`\`\`
codrag(role="<role_slug>")
\`\`\`

## Architecture Overview
<Role-filtered Atlas excerpt>

## Key Modules
<Module summaries relevant to this role>

## Key Files
<Hub files and high-relevance files for this role>
```

---

## 6. Scheduling & Triggers

| Trigger | Action | Frequency |
|---------|--------|-----------|
| Manual CLI invocation | Full generate/adopt/audit | On-demand |
| Post-pipeline-rebuild hook | Lightweight drift check | After every pipeline run |
| Dashboard "HR Audit" button | Full drift analysis with UI report | On-demand |
| Weekly cron (optional) | Comprehensive audit + report generation | Weekly |
| Paperclip webhook (future) | Sync role updates back to Paperclip | On role change |

---

## 7. What Makes This Unique (Competitive Moat)

No other system can do this because:

1. **Epistemic depth**: CoDRAG doesn't just list files — it understands architecture layers, domain tags, module clusters, and epistemic confidence per file
2. **Role projection mathematics**: Phase 64's RoleVector scoring translates roles into weighted queries across CoDRAG's indexed dimensions
3. **Auto-Populate vetting**: The LLM-based file vetting pipeline ensures role scopes are precise, not just keyword-matched
4. **Graph awareness**: Hub files, import chains, and dependency graphs inform which files are *structurally* important to a role
5. **Continuous evolution**: Unlike one-shot generators, the drift detection loop keeps roles aligned with the living codebase
6. **Platform integration**: Direct Paperclip API integration means roles don't just exist as files — they're deployed to a running agent workforce

**This is the "HR department" that reads the entire building's blueprints before deciding who to hire and what to tell them.**
