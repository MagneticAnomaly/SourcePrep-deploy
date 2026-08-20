# SourcePrep UI Semantics & UX Audit Report (Revised)

**Date:** August 20, 2026  
**Target System:** SourcePrep Dashboard & Component Library (`packages/ui`, `src/config/panelRegistry.ts`, `tools/playwright_smoke.py`, `tools/phase145_uat`)  
**Scope:** Brand-Aligned Semantics, Panel Headlines & Descriptions, Active vs. Legacy Inventory, Progressive Disclosure (Clean vs. Expanded States), and Playwright QA Harness Verification.

---

## 1. Executive Summary & Foundational Principles

SourcePrep is built on a clear, core premise: **giving AI agents and developers deep, structured epistemic context before they make changes.** Unlike shallow keyword matching (grep) or ungrounded vector search, SourcePrep constructs a multi-layered epistemic code graph using Rust parsers, inference passes, continuous graph deepening, and architectural concept synthesis.

This audit addresses two interrelated UX challenges:
1. **Surfacing Deep Intelligence Without Cognitive Overload:** The dashboard must communicate instantly to a user: **"Is my project indexed, healthy, and ready for my AI assistant?"** Power users and builders still need rapid access to stage timings, provenance hashes, and concurrency telemetry, but this must be delivered via **clean progressive disclosure**, not through overwhelming default screens or clunky "mode switches."
2. **Clarifying Panel Headlines & Retiring Legacy Surfaces:** The codebase has evolved across multiple phases. Several legacy panels (*Spaghetti Finder*, *Health Scanner*, *Advisor*, *Goalposts*, *AI Gateway summary card*) have been sunset or merged into unified components (*Opportunities*, *Roadmap*, *Sidebar AI Gateway*). We must ensure all active panel headlines and descriptions are crisp, purposeful, and free of outdated artifacts.

---

## 2. Active vs. Legacy Panel Inventory

A key priority of this audit is separating **active production panels** from **deprecated/sunsetted experimental panels** that linger in older documentation or dev-only flags.

### 2.1 Panel Status Breakdown

```
SourcePrep Panel Architecture
├── Active Production Panels (Core Workflow)
│   ├── trace-pipeline     → Graph Enrichment (15-stage epistemic pipeline)
│   ├── status             → Knowledge Status (index health, freshness, stats)
│   ├── search             → Semantic Search
│   ├── results            → Retrieved Context (code chunks & score preview)
│   ├── context-options    → Context Assembler (prompt limits & structure)
│   ├── context-output     → Prompt Buffer (assembled prompt ready for LLM)
│   ├── file-tree          → Knowledge Scope (file inclusion/exclusion tree)
│   ├── trace              → Code Graph Explorer (symbol relationship web)
│   ├── graph-structure    → Graph Scope (queue of pending files & patterns)
│   ├── index-health       → Knowledge Health (staleness, coverage metrics)
│   ├── atlas              → Codebase Atlas (sub-atlas tree & role lens)
│   ├── audit              → Codebase Audit (structural analysis reports)
│   ├── opportunities      → Opportunities (actionable issues & AI prompt export)
│   ├── roadmap            → Roadmap (milestones, timeline & TODO scanning)
│   ├── agent-ops          → Agent Operations (roles, AGENTS.md, Paperclip bridge)
│   ├── architecture       → Architecture (interactive module diagram)
│   ├── concepts           → Concepts (design decisions & domain rationale)
│   ├── usage-guide        → Quick Start (MCP tool reference & copy badges)
│   ├── mcp-snippet        → MCP Setup Snippet (IDE configuration generator)
│   └── log-console        → Process Logs (real-time daemon log stream)
│
└── Deprecated / Sunsetted Panels (Do NOT Surface in Public UI)
    ├── spaghetti          → SUNSET (Phase 65) — Merged into Opportunities
    ├── health_scanner     → SUNSET (Phase 65) — Merged into Opportunities
    ├── advisor            → SUNSET (Phase 65) — Merged into Opportunities / Roadmap
    ├── goalposts          → SUNSET (Phase 65) — Replaced by Roadmap
    ├── llm-status         → SUNSET (Phase 74) — Replaced by Sidebar AI Gateway widget
    └── build              → DEV-ONLY — Manual trigger superseded by watcher & Danger Zone
```

---

## 3. Semantics & Terminology Refinement

### 3.1 Brand Alignment: Celebrating Epistemic Intelligence
- **"Epistemic Context" & "Epistemic Reasoning":** Keep and celebrate. This is SourcePrep's defining identity (*"Give your AI access to the epistemic context it needs to understand your codebase"*). It clearly articulates that the system understands code truth, boundaries, and confidence, rather than just strings.
- **Stage Descriptions:** Clarify what each stage produces in plain English while preserving its technical name in detailed tooltips.

### 3.2 Terminology & Microcopy Improvements

| Surface / Stage | Current Label / Copy | UX Friction / Ambiguity | Recommended Clean Label | Refined Description / Microcopy |
|---|---|---|---|---|
| **Stage 3** | Fast Catalogue | Sounds like an external package directory or store catalog. | **Symbol & File Catalog** (or *Fast Catalog*) | Maps and catalogs all symbols, declarations, and file metadata into the trace graph. |
| **Stage 8** | Module Synthesis | "Synthesis" often implies generative AI code generation rather than clustering files into subsystems. | **Module Discovery & Synthesis** | Clusters files into cohesive architectural modules and dependency boundaries. |
| **Stage 9** | Continuous Deepening | "Deepening" by itself is abstract; users aren't sure what is happening. | **Continuous Graph Deepening** | Iteratively resolves transitive call chains, indirect dependencies, and interface implementations. |
| **Stage 15** | Immune System (`antibodies`) | Biological metaphor without context can sound like a malware scanner. | **Anti-Pattern Guards** (sub-titled *Immune System*) | Generates and checks codebase invariants to prevent architectural drift and regressions. |
| **Search Output** | Prompt Buffer (`context-output`) | "Buffer" is an implementation detail (memory buffer). | **Generated Context Prompt** | The final assembled epistemic context, formatted and ready to paste to your AI. |
| **Search Settings** | Context Assembler (`context-options`) | Mechanical phrasing for prompt options. | **Prompt & Context Settings** | Configure token budget, similarity thresholds, and structured citation output. |
| **AI Gateway Telemetry** | `AIMD backoff`, `ghost locks`, `dynamic capacity` | Internal scheduler plumbing shown in standard sidebar view. | **Rate Limit Headroom: Normal / Throttled** | Keep detailed AIMD graphs and manual reset triggers in the AI Gateway Settings drawer. |
| **Agent Roles** | Managed Employees (`ManagedEmployeesTab`) | "Employees" metaphor clashes with developer mental models for AI subagents. | **Managed Agent Roles** | AI agent definitions (`AGENTS.md`, `SOUL.md`, `KNOWLEDGE.md`) tailored to codebase subsystems. |

---

## 4. Panel Headlines & Microcopy Audit

Below is the verified audit of active panel headlines in [`packages/ui/src/config/panelRegistry.ts`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/config/panelRegistry.ts):

| Panel ID | Current Title | Current Description | Refined Title | Refined Description (Actionable & Clear) |
|---|---|---|---|---|
| `trace-pipeline` | Graph Enrichment | The 15-stage enrichment pipeline... Hover each stage for its epistemological role. | **Graph Enrichment Pipeline** | 15-stage epistemic analysis pipeline: Sync, Deep Reasoning, and Finalize. Maps imports, modules, rules, and concepts. |
| `status` | Knowledge Status | Health and freshness of your codebase knowledge... | **Index Status** | Real-time status and freshness of your codebase index — indexed symbols, embedding model, and file sync state. |
| `search` | Search | Semantic search across your codebase knowledge... | **Codebase Search** | Semantic and structural search — find symbols, logic, and design decisions across your codebase. |
| `context-options` | Context Assembler | Configure and assemble the context prompt from search results. | **Prompt Settings** | Fine-tune context window limits, relevance score thresholds, and structured citations. |
| `results` | Retrieved Context | Chunks of code and text retrieved from your codebase knowledge. | **Retrieved Context** | Code snippets and symbol references retrieved by semantic relevance. |
| `context-output` | Prompt Buffer | The final assembled context, ready to be copied to your LLM. | **Assembled AI Prompt** | Copy-ready context prompt with verified file paths, symbol spans, and epistemic citations. |
| `file-tree` | Knowledge Scope | Pick which files belong in your codebase knowledge... | **File Scope & Filters** | Configure which directories and files are indexed. Boost key folders or exclude vendor code. |
| `trace` | Code Graph Explorer | Navigate the complete web of relationships... | **Code Graph Explorer** | Explore symbol hierarchies, function calls, and import dependencies across modules. |
| `audit` | Codebase Audit | Autonomous health analysis: architecture findings... | **Architecture & Quality Audit** | In-depth structural audit reports: architectural boundaries, quality gaps, and test coverage. |
| `opportunities` | Opportunities | Unified codebase improvement opportunities... | **Codebase Opportunities** | Actionable improvements, refactoring candidates, and tech debt with 1-click AI prompts. |
| `roadmap` | Roadmap | Visual project timeline: track completed, active... | **Project Roadmap** | Interactive milestone timeline tracking completed work, active tasks, and AI-suggested milestones. |
| `agent-ops` | Agent Operations | Configure SourcePrep agent engines... | **Agent Operations** | Configure and export specialized agent roles (`AGENTS.md`) and connect to MCP clients. |
| `architecture` | Architecture | Interactive architecture diagram... | **System Architecture** | High-level interactive diagram of modules, boundaries, and dependencies. |
| `concepts` | Concepts | High-level codebase understanding: business rationale... | **Design Concepts & Rationale** | Documented architectural decisions, business rules, and domain models extracted from code. |

---

## 5. Clean Progressive Disclosure (Showing More Without Clutter)

Instead of a binary "Simplified vs Verbose Mode" switch (which adds artificial cognitive overhead), SourcePrep should use **consistent progressive disclosure**:
- **Default State:** Calm, high-signal, scannable. Displays high-level health, group completion, and key metrics.
- **Interactive Disclosure ("Show Details" / Accordion):** Clicking into any section, stage, or panel expands rich sub-metrics, model tags, and debug logs inline.

### 5.1 Case Study: Graph Enrichment Pipeline (`GraphEnrichmentPipeline.tsx`)

#### Default Compact State (Calm & Clear)
When the pipeline is idle or complete, groups collapse into clean status summaries:
```
┌─────────────────────────────────────────────────────────────────┐
│ Graph Enrichment Pipeline                          [Rebuild ▾] │
├─────────────────────────────────────────────────────────────────┤
│ ● Index Status: Up to Date · Ready for AI                       │
│                                                                 │
│  [✓] 1. Fast Sync         Complete (1,240 symbols, 89 files)  ▾ │
│  [✓] 2. Deep Enrichment   Complete (Epistemic Reasoning)      ▾ │
│  [✓] 3. Finalize          Complete (Atlas, Concepts & Rules)  ▾ │
│                                                                 │
│ Last full run: 12m ago · 15/15 stages verified                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Expanded Stage Detail (Revealed on Click)
Clicking on **Deep Enrichment** smoothly unfolds the 5 underlying stages with full technical depth:
```
│  ▼ 2. Deep Enrichment   Complete (Epistemic Reasoning)        ▴ │
│    ├── [✓] Deep Code Reasoning    [Thinking] 4.5s · 82% confidence │
│    ├── [✓] Group Reasoning        [Thinking] 3.1s · 12 groups      │
│    ├── [✓] Module Synthesis       [Thinking] 2.8s · 14 modules     │
│    ├── [✓] Continuous Deepening   [Thinking] 1.9s · 340 hops       │
│    └── [✓] Deep Knowledge Embed   [Fast]     800ms · 128 chunks    │
```

---

### 5.2 Case Study: Search & Prompt Generation

#### Default Scannable State
- Query bar at the top: *"Search codebase or ask an architecture question..."*
- Clean result list showing matched files, symbols, and relevance score badges.
- Prominent **"Copy Context for AI"** button in the header.

#### Expanded Prompt Settings (Gear Icon)
- Clicking the settings gear slides open a compact popover/drawer for:
  - Max token/character budget slider ($2,000 - 32,000$ chars)
  - Number of chunks ($k = 5 - 50$)
  - Minimum similarity threshold ($0.0 - 1.0$)
  - Include Atlas summary toggle
  - Include structured JSON metadata toggle

---

## 6. Playwright & QA Harness Validation Strategy

The existing test harness in [`tools/playwright_smoke.py`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/tools/playwright_smoke.py) and [`tools/phase145_uat/invariants.py`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/tools/phase145_uat/invariants.py) ensures that UI refinements do not introduce regressions or break automation contracts:

1. **Test Attribute Contract:**
   - Keep `data-testid="pipeline-stage-row-{stage_id}"`, `data-stage-id`, `data-stage-state`, and `data-stage-progress` intact on both collapsed group rows and expanded stage rows.
   - The DOM scraper in `playwright_smoke.py` continues to evaluate stage states without error.
2. **Automated UX Invariant Assertions:**
   - $I_{\text{clean}}$: When all stages in a group are `complete`, the group header displays a valid green rollup status.
   - $I_{\text{a11y}}$: Every interactive collapse chevron, pause button, and copy action carries an explicit `aria-label` and `title`.
   - $I_{\text{legacy}}$: Assert that sunsetted panels (`spaghetti`, `health_scanner`, `advisor`, `goalposts`) never mount in the default dashboard grid.

---

## 7. Actionable Next Steps

1. **Update Panel Registry:** Apply the refined titles and descriptions in [`packages/ui/src/config/panelRegistry.ts`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/config/panelRegistry.ts).
2. **Refine Stage Sub-Labels:** Add the updated descriptive subtitles to `GraphEnrichmentPipeline.tsx` (e.g., *Symbol & File Catalog*, *Anti-Pattern Guards*).
3. **Default to Group Rollups:** Ensure `GraphEnrichmentPipeline.tsx` defaults `fastCollapsed`, `deepCollapsed`, and `finalizeCollapsed` to `true` when all stages are complete, providing a clean, calm default experience with 1-click drilldown.
