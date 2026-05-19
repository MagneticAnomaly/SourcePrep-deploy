# Prompt site inventory

Master table of every LLM prompt site in SourcePrep, grouped by family. Each row links to its research page under [`prompts/`](./prompts/).

Status legend: `baseline` (catalogued, no iterations yet) · `iterating` (active work) · `stable` (one or more `kept` iterations, no open hypotheses).

## Atlas (3 sites)

Generate plain-text architectural orientation docs for the codebase. Single-doc covers small projects; root + segment cover multi-segment monorepos.

| Site | File | Symbols | Page | Status |
|---|---|---|---|---|
| Single-doc atlas | `src/prep/core/atlas/prompts.py:9-43` | `ATLAS_SYSTEM`, `ATLAS_PROMPT` | [atlas-single-doc.md](./prompts/atlas-single-doc.md) | analyzed (A1 #1 — 5 sections required, only 3 emitted on PowerMate; silent-skip under budget pressure; proposes all-sections-present clause) |
| Root atlas | `src/prep/core/atlas/prompts.py:44-74` | `ROOT_ATLAS_SYSTEM`, `ROOT_ATLAS_PROMPT` | [atlas-root.md](./prompts/atlas-root.md) | analyzed (A1 #1 — structural review; same budget-vs-coverage risk as single-doc; needs multi-segment baseline) |
| Segment atlas | `src/prep/core/atlas/prompts.py:75-117` | `SEGMENT_ATLAS_SYSTEM`, `SEGMENT_ATLAS_PROMPT` | [atlas-segment.md](./prompts/atlas-segment.md) | analyzed (A1 #1 — corrects page stub schema (6 sections not 4); double-stated anti-fabrication discipline; STATUS fallback pattern is well-designed) |

## Concept pipeline (4 sites)

Two-pass concept extraction: Generate (swarm) → Validate (per-concept critique) → T3 Refine (tier-rubric scoring) → Synthesize (cross-cutting concepts). Phase 125c.

| Site | File | Symbols | Page | Status |
|---|---|---|---|---|
| Synthesize | `src/prep/core/concept_synthesizer.py:292-527` | `SYNTH_SYSTEM_PROMPT`, `build_synthesis_prompt` | [concept-synthesize.md](./prompts/concept-synthesize.md) | analyzed (B1 #1 — well-engineered, grounding-gap same as Validate, no edit) |
| Validate | `src/prep/core/concept_validate_prompt.py:49-227` | `VALIDATE_SYSTEM_PROMPT`, `build_validate_user_prompt` | [concept-validate.md](./prompts/concept-validate.md) | analyzed (B1 #2 — Iter #1 finding reverified, no edit) |
| T3 Refine | `src/prep/core/concept_t3_refine.py:119-260` | `T3_SYSTEM_PROMPT`, `_FEW_SHOT_EXAMPLES`, `make_t3_*` | [concept-t3-refine.md](./prompts/concept-t3-refine.md) | analyzed (B1 #1 — **unwired in production pipeline**, no prompt edit possible) |
| Generate (swarm) | `src/prep/core/concept_generate_prompt.py:96-237` | `_GENERATE_SYSTEM_HEADER`, `build_worker_prompt` | [concept-generate.md](./prompts/concept-generate.md) | analyzed (B2 #2 — audit_findings scope-tighten precedent, 60% inter-worker dedup overhead) |

## Batched catalogue (8 sites)

Batched LLM prompts for catalogue augmentation, clustering, and epistemic enrichment. All defined in `src/prep/core/batch_prompts.py`.

| Site | File | Symbols | Page | Status |
|---|---|---|---|---|
| Symbol summaries | `batch_prompts.py:22-54` | `BATCHED_SYMBOL_SYSTEM`, `build_batched_symbol_prompt` | [batch-symbol.md](./prompts/batch-symbol.md) | analyzed (A3 #1 — 64% of records are fallback stubs (LLM not called); role taxonomy too narrow for Swift; confidence clumping 0.9-0.95; iteration deferred until full-coverage capture) |
| File roles | `batch_prompts.py:59-97` | `BATCHED_FILE_SYSTEM`, `build_batched_file_prompt` | [batch-file.md](./prompts/batch-file.md) | analyzed (A4 #1 — 100% LLM coverage on 18 file records; role taxonomy fits well; related_files has ~25-40% questionable cases; confidence clumps 0.9-0.95) |
| Doc type/status | `batch_prompts.py:102-136` | `BATCHED_DOC_SYSTEM`, `build_batched_doc_prompt` | [batch-doc.md](./prompts/batch-doc.md) | analyzed (A4 #1 — doc_status 100% "active" on 6 records (clumping); doc_type taxonomy under-utilized (research files classified as "overview"); shared snapshot conflated with batch-narrative) |
| Doc narrative | `batch_prompts.py:141-176` | `BATCHED_NARRATIVE_SYSTEM`, `build_batched_narrative_prompt` | [batch-narrative.md](./prompts/batch-narrative.md) | analyzed (A4 #1 — page stub schema corrected (7 fields not 2); cannot separately audit from batch-doc without per-prompt capture or routing-signal in output) |
| Inferred edges | `batch_prompts.py:181-216` | `BATCHED_INFERRED_EDGES_SYSTEM`, `build_batched_inferred_edges_prompt` | [batch-edges.md](./prompts/batch-edges.md) | **kept** (B2 #2 — 0% hedge / 0% pkg.swift-configures / verbatim source quotes / 31 edges down from 51) |
| Epistemic code | `batch_prompts.py:221-259` | `BATCHED_EPISTEMIC_CODE_SYSTEM`, `build_batched_epistemic_code_prompt` | [batch-epi-code.md](./prompts/batch-epi-code.md) | iterating (B3 #1 analysis + B3-followup `partial` shipped guidance port + structured schema; BYOK rerun still pending — sequential sibling kept) |
| Epistemic doc | `batch_prompts.py:264-308` | `BATCHED_EPISTEMIC_DOC_SYSTEM`, `build_batched_epistemic_doc_prompt` | [batch-epi-doc.md](./prompts/batch-epi-doc.md) | iterating (B3 #1 analysis + B3-followup `partial` shipped guidance port + structured schema + doc_status reconciliation; BYOK rerun still pending — sequential sibling kept) |
| Cluster summary | `batch_prompts.py:313-358` | `BATCHED_CLUSTER_SYSTEM`, `build_batched_cluster_prompt` | [batch-cluster.md](./prompts/batch-cluster.md) | analyzed (B2 #1 — snapshot at wrong layer; structural review only until per-cluster outputs captured) |

## Audit synthesis (5 sites)

Audit-report document generators. All defined in `src/prep/core/audit/prompts.py`, invoked by `audit/synthesizer.py` (parallel since Phase 96F).

| Site | File | Symbols | Page | Status |
|---|---|---|---|---|
| Summary | `audit/prompts.py:9-42` | `AUDIT_SUMMARY_SYSTEM`, `AUDIT_SUMMARY_PROMPT` | [audit-summary.md](./prompts/audit-summary.md) | analyzed (A2 #1 — well-engineered; Module Status truncates to 8 of 20 modules — instruction ambiguous; page hypothesis corrected on grade format) |
| Architecture | `audit/prompts.py:44-78` | `ARCHITECTURE_ANALYSIS_SYSTEM`, `ARCHITECTURE_ANALYSIS_PROMPT` | [audit-architecture.md](./prompts/audit-architecture.md) | analyzed (A2 #1 — well-engineered; module-identifier casing mixed in output — minor normalization opportunity) |
| Gap analysis | `audit/prompts.py:80-110` | `GAP_ANALYSIS_SYSTEM`, `GAP_ANALYSIS_PROMPT` | [audit-gaps.md](./prompts/audit-gaps.md) | analyzed (A2 #1 — GAP-1 false-positive dead-code finding; grounding-shape issue; proposes prompt softening as fallback while upstream fix is preferred) |
| Component inventory | `audit/prompts.py:112-130` | `COMPONENT_INVENTORY_SYSTEM`, `COMPONENT_INVENTORY_PROMPT` | [audit-inventory.md](./prompts/audit-inventory.md) | iterating (A3 #1 partial — 57% preamble + 3× regeneration; shipped anti-preamble + emit-once clauses; awaiting rerun) |
| Tech debt | `audit/prompts.py:132-165` | `TECH_DEBT_REPORT_SYSTEM`, `TECH_DEBT_REPORT_PROMPT` | [audit-tech-debt.md](./prompts/audit-tech-debt.md) | iterating (A3 #1 partial — 80% preamble; shipped anti-preamble clause; awaiting rerun) |

## Epistemic enrichment (2 sites)

Deep per-file enrichment for the trace graph (Phase 22 Pass 2). Reverse-topological order, leaf files first.

| Site | File | Symbols | Page | Status |
|---|---|---|---|---|
| Epistemic code | `src/prep/core/epistemic_enrichment.py:49-87` | `EPISTEMIC_SYSTEM`, `EPISTEMIC_CODE_PROMPT` | [epistemic-code.md](./prompts/epistemic-code.md) | **kept** (B3 #2 — 18/18 code records carry dict-shaped cross_references + tech_debt with severity tags; consumer-side join sites fixed in a2004c02) |
| Epistemic doc | `src/prep/core/epistemic_enrichment.py:89-140` | `EPISTEMIC_SYSTEM`, `EPISTEMIC_DOC_PROMPT` | [epistemic-doc.md](./prompts/epistemic-doc.md) | **kept** (B4 #2 — 6/6 doc records carry dict-shaped decision_chains + cross_references; doc_status reconciliation working; quotes verbatim doc content) |

## HR / Custodian / Researcher agents (7 sites)

Per-agent prompts for the role / archival / research automation surface.

| Site | File | Symbols | Page | Status |
|---|---|---|---|---|
| HR — AGENTS.md per role | `agents/hr/prompts.py:11-77` (SYSTEM @72) | `AGENTS_MD_SYSTEM`, `render_agents_md_prompt` | [hr-agents-md.md](./prompts/hr-agents-md.md) | analyzed (B4 #1 — corrects page hypothesis on managed markers; edit-preservation fidelity; tool list hardcoded; token target asked of model not enforced; output capture needed for verdicts) |
| HR — SOUL.md per role | `agents/hr/prompts.py:79-126` (SYSTEM @120) | `SOUL_MD_SYSTEM`, `render_soul_md_prompt` | [hr-soul-md.md](./prompts/hr-soul-md.md) | analyzed (B4 #1 — corrects page hypothesis on voice; per-section voice drift is the real risk; SOUL.md consumption at runtime needs verification) |
| HR — auto-roles | `agents/hr/prompts.py:185-268` (SYSTEM @267) | `AUTO_ROLES_SYSTEM`, `render_auto_roles_prompt` | [hr-auto-roles.md](./prompts/hr-auto-roles.md) | analyzed (B5 #1 — corrects page schema (5 fields, no mcp_tools); audit_findings integration is strong; recommends hard-constraint role-count band + display_name NAMING RULES + anti-padding clause) |
| Custodian — safety check | `agents/custodian/prompts.py:5-44` (SYSTEM @41) | `SAFETY_VERIFICATION_SYSTEM`, `render_safety_verification_prompt` | [custodian-safety.md](./prompts/custodian-safety.md) | analyzed (B5 #1 — corrects page schema (SAFE_TO_DELETE|NEEDS_REVIEW|KEEP, no 'archive'); conservatism is engineered via 6-question structure; KEEP path is unspecified; recommends REASON RULES) |
| Researcher — topic select | `agents/researcher/prompts.py:10-53` (SYSTEM @50) | `TOPIC_SELECTION_SYSTEM`, `render_topic_selection_prompt` | [researcher-topic.md](./prompts/researcher-topic.md) | analyzed (A5 #1 — corrects page schema (2 fields not 4); JSON output discipline good; Actionability criterion may bias toward narrow topics; needs PowerMate capture) |
| Researcher — research | `agents/researcher/prompts.py:54-101` (SYSTEM @97) | `RESEARCH_SYSTEM`, `render_research_prompt` | [researcher-research.md](./prompts/researcher-research.md) | analyzed (A5 #1 — corrects page schema (Markdown not JSON; 5 sections; effort with time ranges); HIGH preamble-leakage risk — same shape as audit prompts before A3 fix; needs PowerMate capture) |
| Researcher — plan | `agents/researcher/prompts.py:102-134` (SYSTEM @133) | `PLAN_FORMULATION_SYSTEM`, `render_plan_formulation_prompt` | [researcher-plan.md](./prompts/researcher-plan.md) | analyzed (A5 #1 — corrects page schema (5 flat fields not nested steps); effort/risk enums need passing-test definitions; fix_steps granularity undefined; needs PowerMate capture) |

## Rules generator (1 site)

AGENTS.md content shipped to client projects. Not a runtime LLM call — but the *content* is a prompt-to-downstream-agents, and changes there alter how every IDE-side agent (Claude Code, Cursor, Windsurf, Copilot, etc.) interacts with SourcePrep. Treated as a prompt for audit purposes.

| Site | File | Symbols | Page | Status |
|---|---|---|---|---|
| AGENTS.md managed block | `src/prep/core/rules_generator.py:_build_managed_content` | `_build_managed_content`, `_write_agents_md` | [rules-agents-md.md](./prompts/rules-agents-md.md) | iterating (double-block cleanup #1) |

## Totals

- **30 prompt sites** across 12 source files
- **Atlas:** 3 · **Concept:** 4 · **Batched:** 8 · **Audit:** 5 · **Epistemic:** 2 · **Agents:** 7 · **Rules:** 1
- **Status:** 30 baseline, 0 iterating, 0 stable

## How to add a new site

1. Add a row to the appropriate family table (or open a new family if needed).
2. Create the page under `prompts/<slug>.md` using the template in [`prompts/README.md`](./prompts/README.md).
3. Add an `outputs/<slug>/` subdirectory to the relevant snapshot.
4. Bump the totals.
