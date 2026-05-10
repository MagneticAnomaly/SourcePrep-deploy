

<!-- prep-managed-start -->
## SourcePrep Integration

Last updated: 2026-05-10T04:56:12Z | Full analysis in progress

prep_project_id: f1636374-abc6-410d-99ee-822120379e79

**ROUTING: When calling ANY SourcePrep tool, ALWAYS include `project_id: "f1636374-abc6-410d-99ee-822120379e79"` in the arguments.**

## Tools
| Tool | When to Use |
|------|-------------|
| `prep` | START of every task — structural overview, modules, hub files, immune system alerts |
| `prep_search` | Find code by meaning, not just string match. Auto-classifies intent (LOCATE, EXPLAIN, RATIONALE, TRACE, EXAMPLE, COMPARE, DISCOVER). |
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

<!-- prep-atlas-hash:928556b49a03 -->
## Codebase Atlas

IDENTITY: SourcePrep
STACK: .md 46%, .tsx 22%, .py 17%, .ts 8%, .json 6%, .js 1%
STRUCTURE: 1920 files, 8062 nodes, 12842 edges
EDGE TYPES: contains: 5737, imports: 4970, implements: 1271, configures: 736, listens_to: 64
CIRCULAR DEPS (61): docs/Phase00_Initial-Concept/EXAMPLE-TRACE-STRUCTURE/sample_repo/app.py <-> docs/Phase00_Initial-Concept/EXAMPLE-TRACE-STRUCTURE/sample_repo/utils.py; docs/Phase00_Initial-Concept/EXAMPLE-TRACE-STRUCTURE/sample_repo/app.py <-> docs/Phase00_Initial-Concept/EXAMPLE-TRACE-STRUCTURE/sample_repo/pkg/math_ops.py; docs/Phase00_Initial-Concept/EXAMPLE-TRACE-STRUCTURE/sample_repo/app.py <-> docs/Phase00_Initial-Concept/EXAMPLE-TRACE-STRUCTURE/sample_repo/pkg/__init__.py
ENTRY POINTS: packages/ui/src/components/context/index.ts, packages/ui/src/components/trace/index.ts, packages/ui/src/components/docs/index.ts, packages/ui/src/components/console/index.ts, src/prep/__main__.py
SUBSYSTEMS:
  MCP Protocol Server & Client Integration (47 files) -- Implements the Model Context Protocol server that exposes Prep's codebase intell
  Project Lifecycle & Build Orchestrator (42 files) -- Manages project creation, configuration, and incremental index rebuilding with t
  Roadmap & Sprint Planning Orchestrator (40 files) -- Generates AI-powered project roadmaps with visual timeline nodes, sprint burndow
  LLM Provider & Model Configuration Console (39 files) -- Configures multi-provider LLM endpoints, assigns models to pipeline slots (embed
  SourcePrep Design System Primitives (22 files) -- Renders accessible, composable UI primitives for the SourcePrep platform using R
  AutoAudit Static Analysis Engine (20 files) -- Executes 11 deterministic static analyzers over code import graphs to detect dea
  Agent Ecosystem Integration & Protocol Strategy (19 files) -- Coordinates multi-protocol agent integrations across MCP, A2A, REST, and SARIF s
  Prep CLI Thin-Client & Documentation Surface (17 files) -- Proxies user commands to a background daemon via HTTP REST, handling project CRU
  Dashboard State & Component Refactoring Tracker (16 files) -- Tracks and coordinates frontend technical debt remediation across the CoDRAG das
  Guerilla Marketing Copy Engine (15 files) -- Produces channel-specific organic marketing copy for Reddit, LinkedIn, Lobsters,
TESTS: __tests__/ (19 files), specs/ (18 files), TEST_PLAN.md/ (1 files)
LAYERS: documentation: 868, presentation: 528, business_logic: 176, infrastructure: 103, configuration: 84
HUB FILES: docs/ARCHITECTURE.md (evolving), ext:__future__, ext:typing, ext:react, ext:logging
Active zones: `packages/ui/src/`, `tests/`, `websites/apps/marketing/`, `websites/apps/docs/`, `src/prep/core/`
CALL CHAINS:
  packages/ui/src/components/docs/index.ts -> packages/ui/src/components/docs/DocsLayout.tsx -> packages/ui/src/components/docs/MobileDocsDrawer.tsx -> packages/ui/src/components/docs/DocsSidebarNav.tsx -> sym:DocsSidebarNav@packages/ui/src/components/docs/DocsSidebarNav.tsx:17
  packages/ui/src/components/context/index.ts -> packages/ui/src/components/context/ContextViewer.tsx -> packages/ui/src/components/context/CitationBlock.tsx -> docs/Phase04_TraceIndex/CURATED_TRACEABILITY_FRAMEWORK.md
  packages/ui/src/components/trace/index.ts -> packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx -> packages/ui/src/components/trace/RecoverStagePanel.tsx -> sym:handleOpenToggle@packages/ui/src/components/trace/RecoverStagePanel.tsx:125
CONFIDENCE: 0.84 avg across 1887 files
DOMAINS: marketing, mcp, react, design-system, storybook, nextjs, dashboard, documentation

## Top docs per module

Planning docs that mention this module's code (Phase 124 T9). Use these as a starting point to understand a module's *why* before reading source. Generated from `atlas_markdown_links.json`.

- **MCP Protocol Server & Client Integration**
  - `docs/Phase120_NamedScopes/IMPLEMENTATION_PLAN.md`
  - `docs/Phase120_NamedScopes/README.md`
  - `docs/Phase50_MCP-interfacing/README.md`
- **Project Lifecycle & Build Orchestrator**
  - `docs/Phase25_crashprotection/README.md`
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`
  - `docs/Phase73_Quality-Reccommendations/13_agent_collaboration_infrastructure/feature_documentation.md`
- **Roadmap & Sprint Planning Orchestrator**
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`
  - `docs/Phase67_AGENTS/Paperclip-Plugin/02_Hybrid_MCP_Architecture.md`
  - `docs/Phase125_ConceptPromotionPipeline/CALIBRATION_WORKSHEET.md`
- **LLM Provider & Model Configuration Console**
  - `docs/Phase119_ConcurrencyStability/06_Phase_A_Plan.md`
  - `docs/Phase119_ConcurrencyStability/03_Validation_Report.md`
  - `docs/Phase67_AGENTS/Researcher-concept-adapter/IMPLEMENTATION_STRATEGY.md`
- **SourcePrep Design System Primitives**
  - `docs/Phase81_UI-bugfixes/07_Stage3_Loading_States.md`
  - `.agents/content_marketing_strategist/KNOWLEDGE.md`
  - `.agents/content_marketing_strategist/SOUL.md`
- **AutoAudit Static Analysis Engine**
  - `docs/Phase99_Content/blogs/00_feasibility_audit.md`
  - `docs/Phase116_strategic-oversight/03_CANDIDATE_CHECKPOINTS.md`
  - `docs/Phase116_strategic-oversight/04_EXISTING_ABSTRACTIONS.md`
- **Prep CLI Thin-Client & Documentation Surface**
  - `AGENTS.md`
  - `CLAUDE.md`
  - `docs/Phase06_Team_And_Enterprise/TEAM_ENTERPRISE_CODE_AUDIT.md`
- **Dashboard State & Component Refactoring Tracker**
  - `docs/superpowers/plans/2026-04-19-phase117-rebuild-granularity.md`
- **Enrichment Pipeline State Machine & Resource Scheduler**
  - `docs/Phase96-fix-pipeline/00_DIAGNOSTIC_REPORT.md`
  - `docs/Phase96-fix-pipeline/UI+tweaks/PLAN.md`
  - `docs/refactor2/05_annotated_refactor_plan.md`

## Focus Areas
- docs/MASTER_ROADMAP.md
Call `prep` for detailed content from these areas.

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
