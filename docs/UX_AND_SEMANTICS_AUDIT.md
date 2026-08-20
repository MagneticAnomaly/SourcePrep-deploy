# SourcePrep UI Semantics & UX Audit Report (Deep Scrutiny & Reverse-Engineered)

**Date:** August 20, 2026  
**Target System:** SourcePrep Dashboard & Component Library (`packages/ui`, `src/config/panelRegistry.ts`, `tools/playwright_smoke.py`, `tools/phase145_uat`)  
**Scope:** Foundational Epistemic Semantics, Panel Registry Audit (Active vs. Sunsetted), Progressive Disclosure Architecture, DOM Contracts, and Playwright UAT Harness Invariants.

---

## 1. Executive Summary & Foundational Principles

SourcePrep is architected around a non-negotiable core principle: **delivering deep, structured epistemic context to AI coding agents before they touch code.** Unlike ungrounded keyword matching (grep) or shallow vector similarity, SourcePrep builds a multi-layered epistemic code graph using native Rust parsers, reference inference, continuous graph deepening, and architectural concept synthesis.

This deep audit scrutinizes every active user-facing UI component, panel title, and microcopy string to ensure:
1. **Epistemic Context is Celebrated & Clear:** Epistemic reasoning, epistemic confidence, and epistemic graph layers are preserved as the core brand and functional USP.
2. **Progressive Disclosure Replaces Cognitive Overload:** Rather than forcing users into overwhelming 15-stage waterfalls or introducing artificial "verbose mode" toggles, the UI uses **clean, native progressive disclosure**: calm, scannable default group summaries that expand inline on click.
3. **Legacy / Sunsetted Panels are Quarantined:** Past experimental panels (*Spaghetti Finder*, *Health Scanner*, *Advisor*, *Goalposts*, *AI Gateway summary card*) are strictly segregated from the 19 active production panels.
4. **Zero Regressions on Playwright UAT Contracts:** All `data-testid`, `data-stage-state`, `data-stage-progress`, and invariant checks ($I_1$ to $I_{15}$) remain 100% backward-compatible.

---

## 2. Reverse-Engineered Panel Inventory (Active vs. Legacy)

A thorough code audit of [`packages/ui/src/config/panelRegistry.ts`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/config/panelRegistry.ts) and [`packages/ui/src/stories/dashboard/FullDashboard.stories.tsx`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/stories/dashboard/FullDashboard.stories.tsx) confirms which panels are actively wired versus sunsetted in past phases.

```
SourcePrep Panel Architecture
├── Active Production Panels (19 Wired Panels)
│   ├── trace-pipeline     → Graph Enrichment Pipeline (15-stage epistemic pipeline)
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
└── Sunsetted / Deprecated Panels (Excluded from Public Dashboard)
    ├── spaghetti          → SUNSET (Phase 65) — Merged into Opportunities
    ├── health_scanner     → SUNSET (Phase 65) — Merged into Opportunities
    ├── advisor            → SUNSET (Phase 65) — Merged into Opportunities / Roadmap
    ├── goalposts          → SUNSET (Phase 65) — Replaced by Roadmap
    ├── llm-status         → SUNSET (Phase 74) — Replaced by Sidebar AI Gateway widget
    └── build              → DEV-ONLY — Manual trigger superseded by watcher & Danger Zone
```

---

## 3. Semantics & Microcopy Audit

### 3.1 Preserving & Clarifying Core Epistemic Terminology
- **Epistemic Reasoning (Stage 6):** Preserved and celebrated. Epistemic scoring provides multi-layer domain and confidence ratings for every symbol in the graph.
- **Epistemic Confidence:** Kept in tooltips and detail views as the measure of structural certainty.

### 3.2 Specific Microcopy & Label Refinements

| Component / Stage | Current Label / String | Reverse-Engineered Finding | Recommended Refinement | Rationale |
|---|---|---|---|---|
| **Stage 3** (`catalogue`) | "Fast Catalogue" | Manifest is `trace_augment_manifest.json`, prop is `augmentationStatus`. "Catalogue" can sound like a shop catalog. | **Symbol & File Catalog** | Accurately describes cataloging all parsed AST declarations and file spans. |
| **Stage 8** (`clustering`) | "Module Synthesis" | Manifest is `trace_modules_manifest.json`. "Synthesis" can be confused with LLM code generation. | **Module Discovery & Synthesis** | Clarifies that the engine is discovering subsystem boundaries and cohesive clusters. |
| **Stage 9** (`deepening`) | "Continuous Deepening" | Manifest is `deepening_manifest.json`. Standalone "Deepening" is abstract. | **Continuous Graph Deepening** | Explains that the engine is iteratively traversing multi-hop references and interface implementations. |
| **Stage 15** (`antibodies`) | "Immune System" | Manifest is `antibodies_manifest.json`. "Immune system" without context can sound like antivirus. | **Anti-Pattern Guards** (sub-label: *Immune System*) | Clarifies that this stage derives invariant rules to protect against code regressions. |
| **Prompt Output** (`context-output`) | "Prompt Buffer" | In `ContextOutput.tsx`, title is hardcoded as "Prompt Buffer". | **Assembled AI Prompt** | "Buffer" is internal plumbing; users want the copy-ready prompt. |
| **Search Settings** (`context-options`) | "Context Assembler" | In `ContextOptionsPanel.tsx`, title is "Context Assembler". | **Prompt & Context Settings** | Plain, intuitive label for configuring token budgets and similarity thresholds. |
| **AI Gateway Telemetry** | `AIMD backoff`, `dynamic capacity`, `ghost locks` | In `SidebarAIGateway.tsx` & `CapacityHealth.tsx`. | **Rate Limit Headroom: Normal / Throttled** | Keeps internal scheduler math in the Settings inspector, displaying clear status in the sidebar. |
| **Agent Roles** | "Managed Employees" / "HR Agent" | In `ManagedEmployeesTab.tsx`. | **Managed Agent Roles** | Fits standard AI coding agent workflows (`AGENTS.md`, `SOUL.md`, `KNOWLEDGE.md`). |

---

## 4. Progressive Disclosure Architecture (No "Verbose Mode")

### 4.1 Reverse-Engineered Implementation in `GraphEnrichmentPipeline.tsx`

Inspection of [`packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx) reveals that the component already contains the foundation for progressive disclosure:
- `fastCollapsed`, `deepCollapsed`, `finalizeCollapsed` props control group visibility.
- When collapsed, `CondensedGroupRow` renders an elegant, compact rollup badge (`computeGroupRollup`).
- When expanded, `StageRow` renders full per-stage telemetry, model badges (`Rust`, `Thinking`, `CPU`), runtime durations, sub-progress bars, and provenance hashes.

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

#### Inline Expansion (Zero Mode Switches)
Clicking the chevron on **Deep Enrichment** smoothly unfolds the 5 underlying stages in place:
```
│  ▼ 2. Deep Enrichment   Complete (Epistemic Reasoning)        ▴ │
│    ├── [✓] Epistemic Reasoning    [Thinking] 4.5s · 82% confidence │
│    ├── [✓] Group Reasoning        [Thinking] 3.1s · 12 groups      │
│    ├── [✓] Module Synthesis       [Thinking] 2.8s · 14 modules     │
│    ├── [✓] Continuous Deepening   [Thinking] 1.9s · 340 hops       │
│    └── [✓] Deep Knowledge Embed   [Fast]     800ms · 128 chunks    │
```

---

## 5. Playwright & UAT Harness Compatibility Audit

### 5.1 Contract Scrutiny: `tools/playwright_smoke.py` & `tools/phase145_uat/invariants.py`
We reverse-engineered the exact invariant checks in [`tools/phase145_uat/invariants.py`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/tools/phase145_uat/invariants.py):
- **$I_1$**: At most one running row per active group (`ACTIVE_PIPELINE_PHASES`).
- **$I_2$**: No running row shows a prior-run timestamp chip (`data-testid="last-run-chip"`).
- **$I_3$**: No row downstream of `current_stage` shows `complete` during an active run (freeze-green safety).
- **$I_{13}$**: Exactly one `data-testid="current-stage-indicator"` per group with an active stage.
  - *Scrutiny finding:* $I_{13}$ explicitly documents: *"Collapsed groups are N/A. The dashboard renders `CondensedGroupRow` instead of per-stage rows when a group is collapsed... we skip rather than fire a guaranteed-zero false positive."*
- **$I_{14}$**: No row says *"Not run"* against an API-completed `stage_results` entry.
- **$I_{15}$**: No percent chip in any pipeline-stage-row exceeds 100%.

### 5.2 Preservation of Public Test Hooks
All DOM test attributes remain untouched:
- `data-testid="pipeline-panel"`
- `data-testid="pipeline-stage-row-{stage_id}"`
- `data-stage-id="{stage_id}"`
- `data-stage-state="{state}"`
- `data-stage-progress="{progress}"`
- `data-testid="current-stage-indicator"`
- `data-testid="last-run-chip"`

Any future invariant additions must be numbered sequentially starting at **$I_{16}$** to avoid colliding with existing $I_1$ through $I_{15}$.

---

## 6. Actionable Implementation Checklist

- [ ] **1. Panel Registry Titles:** Update user-facing titles and descriptions in [`packages/ui/src/config/panelRegistry.ts`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/config/panelRegistry.ts) to match the refined labels in §4.
- [ ] **2. Component Fallback Titles:** Align hardcoded fallback titles in [`ContextOutput.tsx`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/search/ContextOutput.tsx) and [`ContextOptionsPanel.tsx`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/search/ContextOptionsPanel.tsx).
- [ ] **3. Subtitle Refinements in Pipeline:** Update stage sub-labels in [`GraphEnrichmentPipeline.tsx`](file:///Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx) (*Symbol & File Catalog*, *Module Discovery & Synthesis*, *Continuous Graph Deepening*, *Anti-Pattern Guards*).
- [ ] **4. Quarantined Sunset Panels:** Verify that `spaghetti`, `health_scanner`, `advisor`, `goalposts`, and `llm-status` remain flagged with `devOnly: true` or omitted from public builds.
- [ ] **5. Test Suite Verification:** Run `.venv/bin/pytest tests/test_phase145_invariants.py` to confirm zero regression across all active invariant checks.
