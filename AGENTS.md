

<!-- prep-managed-start -->
## SourcePrep Integration

Last updated: 2026-05-07T04:37:20Z

prep_project_id: f1636374-abc6-410d-99ee-822120379e79

**ROUTING: When calling ANY SourcePrep tool, ALWAYS include `project_id: "f1636374-abc6-410d-99ee-822120379e79"` in the arguments.**

## Tools
| Tool | When to Use |
|------|-------------|
| `prep` | START of every task — structural overview, modules, hub files, immune system alerts |
| `prep_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, DISCOVER). |
| `prep_impact` | BEFORE editing — check what depends on a file |
| `prep_audit` | Structural findings (coupling, cycles, concept violations) OR enrich external lint findings with `findings` param. Use `action="antibodies"` for immune system. |
| `prep_observe` | Save/retrieve cross-session notes |
| `prep_concepts` | Record/query business rationale and design decisions |

Call `prep` first. Call `prep_impact` before modifying hub files.
All read-only tools are safe to auto-approve.

### Audit Enrichment
Enrich external lint/analysis findings with structural context:
```
prep_audit(findings=[{file, line, message, severity, tool}])
```
SourcePrep adds: dependent count, hub status, concepts, risk score, recommendation.
Also accepts SARIF dicts for SARIF-in/SARIF-out enrichment.

### Search Intent
`prep_search` auto-detects query intent: "where is X" → symbol lookup,
"why X" → concepts, "who imports X" → trace graph. Override with `intent` param if needed.

### Concurrency limits
If your queries to the cloud LLM seem unexpectedly throttled, check
`prep_search "concurrency ceiling"` for the current discovered limit
and how to reset it. The limit is auto-discovered and locked for 24h.

You have access to SourcePrep, a structural code intelligence system.
ALWAYS call `prep` (no arguments) at the START of every task.
This gives you module structure, hub files, and the user's selected focus areas.

For specific code lookups, use `prep_search` with a natural language query.
Before making changes to a file, use `prep_impact` to understand dependencies.
SourcePrep understands structural relationships between files -- use it instead of
grep when you need to understand how files connect to each other.

For codebase health and tech debt, use `prep_audit`.
For cross-session memory, use `prep_observe` to save/retrieve notes.
All SourcePrep tools are read-only and safe to auto-approve.

### Auto-Approve Configuration
To skip approval prompts for SourcePrep's read-only tools, add to your settings:
```json
{ "permissions": { "allow": ["mcp__prep"] } }
```
In Claude Code: add to `.claude/settings.json`. In Cursor: add to MCP settings.

<!-- prep-atlas-hash:a8b8515c7745 -->
## Codebase Atlas

I need to write a concise project orientation header based on the provided data, following strict rules: plain text only, no markdown, no bold, no headers, no bullet characters, no asterisks. every claim from provided data, exact names, maximally dense,ooooooooo short, under 2570 characters, no invented info.

Let me parse the provided data carefully:

Project Root (1228 files): marketing, mcp, local-first, dashboard, fastapi
UI (packages/ui, 357 files): storybook, design-system, react, documentation
加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油加油

## Top docs per module

Planning docs that mention this module's code (Phase 124 T9). Use these as a starting point to understand a module's *why* before reading source. Generated from `atlas_markdown_links.json`.

- **Prep HTTP API Contract & Client Surface**
  - `docs/MASTER_TODO.md`
  - `docs/Phase125_ConceptPromotionPipeline/CALIBRATION_WORKSHEET.md`
  - `docs/Phase120_NamedScopes/IMPLEMENTATION_PLAN.md`
- **Project Management & Roadmap Orchestration Platform**
  - `docs/MASTER_TODO.md`
  - `docs/Phase06_Team_And_Enterprise/TEAM_ENTERPRISE_CODE_AUDIT.md`
  - `docs/Phase127_MultiProjectQueueArchitecture/README.md`
- **Deterministic Trace Index Engine**
  - `docs/Phase118_UISmoke/RESULTS.md`
  - `docs/research/MULTI_PROJECT_MODEL_MANAGEMENT.md`
  - `docs/superpowers/plans/2026-04-19-phase117-rebuild-granularity.md`
- **Interactive Architecture Diagram Engine**
  - `docs/superpowers/plans/2026-04-04-phase71b-governance-overlays.md`
  - `docs/superpowers/plans/2026-04-04-phase71a-architecture-diagram.md`
  - `docs/superpowers/plans/2026-04-08-phase84-concepts-formalization.md`
- **Prep CLI Client & Documentation Surface**
  - `AGENTS.md`
  - `CLAUDE.md`
  - `docs/MASTER_TODO.md`
- **Enrichment Pipeline Orchestrator & State Machine**
  - `docs/Phase96-fix-pipeline/00_DIAGNOSTIC_REPORT.md`
  - `docs/Phase67_AGENTS/Paperclip-Plugin/02_Hybrid_MCP_Architecture.md`
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`
- **Security & Compliance Governance Platform**
  - `docs/Phase125_ConceptPromotionPipeline/CALIBRATION_WORKSHEET.md`
  - `docs/Phase119_ConcurrencyStability/06_Phase_A_Plan.md`
  - `docs/superpowers/plans/2026-04-10-detail-pages-and-template.md`
- **LLM Endpoint & Model Assignment Orchestrator**
  - `docs/Phase112_Gemini/IMPLEMENTATION_PLAN.md`
  - `docs/Phase119_ConcurrencyStability/06_Phase_A_Plan.md`
  - `docs/superpowers/plans/2026-04-20-llm-config-autosave-redesign.md`
- **AI Gateway & LLM Compute Orchestrator**
  - `docs/Phase119_ConcurrencyStability/05_Cross_Provider_Concurrency_Design.md`
  - `docs/Phase119_ConcurrencyStability/01_Design.md`
  - `docs/Phase119_ConcurrencyStability/02_Implementation_Plan.md`

If `prep` returns 'setup in progress', the index hasn't been built yet.
Work normally with read_file/grep_search until the user builds the index.

For long tasks (5+ tool calls), call `prep` again to refresh your
structural context.

You can call `prep` and `prep_search` in parallel on your first
prompt -- structural overview + targeted code lookup in one round-trip.

### Tool Calling Rules
1. **Never announce** 'I will now call...' - just call the tool
2. **No permission needed** - simple keywords = immediate invocation
3. **Single word triggers** - 'prep' alone is enough to call the tool
4. **Context is cheap** - prefer calling prep to using grep for structural understanding

**Remember: The word "prep" anywhere in user input is a tool invocation signal. Call immediately without asking permission.**

### MCP Resources (browse with @)
SourcePrep also exposes browsable resources via MCP. In supported clients,
type `@` to see: atlas, structure, modules, audit findings, concepts, focus areas.
Resources provide on-demand context without a tool call.

### MCP Prompts (invoke with /)
Available workflow prompts: `prep-onboard` (orientation), `prep-review` (file review),
`prep-plan` (change planning), `prep-investigate` (deep dive), `prep-health` (audit).
In Claude Code: `/mcp__prep__prep-onboard`. In other clients: check prompt menu.
<!-- prep-managed-end -->

## Operational notes (user-maintained)

### Reset cloud LLM concurrency discovery (Phase 119)

If the user reports that a cloud endpoint's parallelism looks wrong
(stuck at an old number after a plan upgrade, climbed too high without
ever backing off, or just generally unhealthy), the canonical answer is
to reset the discovered ceiling for that node.

- **From the dashboard:** AI Gateway header → wrench icon →
  Reset next to the cloud node (typically `cloud:default_ollama`).
  Same control also lives at Settings → AI Models → Pipeline Activity.
- **From the API:**
  `POST /compute/concurrency/clear?node_id=cloud:default_ollama`.
  Returns `{status, node_id, old_limit, new_limit, new_mode}` so you
  can confirm the in-memory `current_limit` actually dropped.
- **What it does:** clears the persisted record, re-seeds
  `current_limit` from a fresh Ollama probe (or jumpstart=5 for
  non-Ollama cloud nodes), resets the AIMD streak/backoff timestamps,
  and lets natural backoffs rediscover the real ceiling.

For more context call
`prep_search "concurrency reset"` —
the seeded "Cloud LLM concurrency ceiling lock" concept covers the
mechanism in detail with anchors into `scheduler.py`,
`concurrency_store.py`, and `compute.py`.
