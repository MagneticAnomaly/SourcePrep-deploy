# HR Agent Adapter — README

> **Phase 67: Agent Role Manager** | CoDRAG Subsystem
> Date: 2026-04-01

---

## What Is This?

The **HR Agent Adapter** is a CoDRAG subsystem that generates, manages, and evolves AI agent role definitions using CoDRAG's epistemic knowledge graph. It acts as an automated "HR department" for Paperclip agent workforces (with a universal adapter pattern for future orchestrators).

**The core insight:** CoDRAG already understands the codebase at an epistemic level — architecture layers, domain tags, module clusters, file importance scores. The HR Adapter uses this knowledge to reason about *what agent roles a project needs* and *keep those roles aligned as the codebase evolves*.

---

## Research Summary

### Does a tool like this already exist?

**No.** Three adjacent categories exist, but none combine what we need:

| Category | Examples | Gap |
|----------|---------|-----|
| AGENTS.md generators | Smithery agents-md-generator | One-shot, no epistemic awareness, no lifecycle management |
| Agent orchestrators | Paperclip, CrewAI, AutoGen | Runtime orchestration, no codebase intelligence |
| Code intelligence | CoDRAG, Copilot | Knowledge delivery, no role generation/management |

**CoDRAG uniquely has:** Per-file epistemic metadata + RoleVector scoring + module clustering + graph centrality. No other system has this combination. See [01_Landscape_Research.md](01_Landscape_Research.md).

---

## Documents

| # | Document | Purpose |
|---|----------|---------|
| 01 | [Landscape Research](01_Landscape_Research.md) | Market analysis confirming no existing tool does what we need |
| 02 | [HR Agent Architecture](02_HR_Agent_Architecture.md) | System architecture, capabilities, execution modes, output format |
| 03 | [Integration Reference](03_Integration_Reference.md) | How it connects to CoDRAG internals and Paperclip's API |
| 04 | [Orchestrator Adapters](04_Orchestrator_Adapters.md) | Universal adapter pattern: Paperclip (primary), CrewAI, AutoGen (future) |
| 05 | [Edge Cases & Generation Modes](05_Edge_Cases_and_Modes.md) | The three generation modes, insufficient data handling, first-run UX, dashboard design |

---

## Key Capabilities

1. **Generate** — Three modes:
   - `list`: User provides exact role titles → generates exactly those
   - `auto`: System analyzes codebase → generates best-guess workforce
   - `auto+list`: Auto analysis → includes user-specified roles
2. **Adopt** — Import existing Paperclip agents and enhance with CoDRAG intelligence
3. **Audit** — Detect role drift when the codebase evolves; propose realignments, eliminations, or new hires
4. **Sync** — Push role definitions to Paperclip via REST API

---

## Architecture

```
CoDRAG (epistemic knowledge) → HR Adapter (role reasoning) → Paperclip (runtime orchestration)
                                      │
                              ┌───────┼──────────┐
                              │       │           │
                        Paperclip  CrewAI    AutoGen
                        (primary) (future)  (future)
```

CoDRAG provides the **knowledge**. The HR Adapter performs the **reasoning** via a platform-neutral `RoleSpec`. Orchestrator-specific **adapters** emit the correct output format. Paperclip performs the **execution**.

---

## Dashboard Integration

The HR panel is a new `ModularDashboard` panel (`agent-workforce`) that shows:
- Empty state with "Get Started" wizard when no agents exist
- Generation wizard with three-mode selector
- Agent roster table with fitness scores and health indicators
- Audit controls and drift history
- Sync-to-Paperclip buttons

---

## Edge Case Highlights

| Edge Case | Behavior |
|-----------|----------|
| **Insufficient data** | Blocks auto mode, shows readiness checklist, recommends running pipeline first |
| **Single-domain codebase** | Generates fewer, more generalist roles |
| **Massive monorepo** | Generates specialized domain-owner roles |
| **Re-generation** | Detect existing agents, offer Regenerate/Merge/Cancel |
| **Role elimination** | NEVER auto-deletes — presents proposals for human approval |
| **Pipeline rebuilding** | Uses snapshot of data at audit start time |

---

## Reference: DebateHaus Precedent

The DebateHaus project (`Phase05_agent-workers`) demonstrates the manual version of this workflow:
- 6 agents with AGENTS.md + SOUL.md per role
- `bootstrap-agents.sh` — Creates agents via Paperclip REST API
- `sync-instructions.sh` — Copies instruction files to Paperclip directories
- Detailed org chart with collaboration axes and conflict resolution protocols

The HR Adapter automates and enhances this entire workflow using CoDRAG's epistemic intelligence.
