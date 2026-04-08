# Phase 73.2 — Prompt Architecture Audit: Every Prompt That Shapes Agent Output

> Date: 2026-04-05 | Deep audit of all LLM prompts and markdown assembly templates

---

## The CoDRAG Prompt Stack

CoDRAG has **three layers** where prompts shape AI output quality:

```
Layer 1: Pipeline Prompts (build-time)
  └─ Generate enriched file data baked into the index
  └─ Affect EVERYTHING downstream — quality compounds here

Layer 2: Atlas Prompts (build-time)  
  └─ Synthesize the codebase orientation document
  └─ Injected into every AI query as system-level context

Layer 3: MCP Response Assembly (runtime)
  └─ Format pipeline data into markdown for AI consumption
  └─ Zero-cost to iterate — changes are immediate
```

---

## Layer 1: Pipeline Prompts (Build-Time Data Generation)

### 1A. SYMBOL_SUMMARY_PROMPT (`augmenter.py:181`)

**Purpose**: Summarize individual code symbols (functions, classes).
**Quality Impact**: These summaries feed into file-level summaries, which feed into module names.

**Current Issues**:
- System message is bare-minimum: "You are a code analyst." No grounding in the PURPOSE of the summary.
- The output schema asks for `"role": "{role_hint}"` which pre-fills with `"utility"` — meaning the LLM often rubber-stamps it.
- **Low-value for search**: Symbol summaries are 1-2 sentences, but they're the primary content indexed for semantic search. A symbol named `_apply_lod_compression` gets a summary like "Applies LOD compression to chunks" — which is essentially a paraphrase of the function name. This adds zero information for retrieval.

**Opportunity**: Add a grounding clause to the system prompt explaining WHY concise summaries matter: "Your summaries will be embedded for semantic search. Include the business purpose, not just the mechanical description. Bad: 'Sends an email'. Good: 'Notifies the team lead when a PR review is overdue — part of the code review automation pipeline.'"

### 1B. FILE_ROLE_PROMPT (`augmenter.py:204`)

**Purpose**: Classify files by role and generate 1-sentence summaries.
**Quality Impact**: These feed directly into module synthesis AND the knowledge index embeddings.

**Current Issues**:
- Only sees the first 30 lines of a file. For a 3248-line `orchestrator.py`, this means the LLM only sees imports and maybe a docstring.
- The `related_files` field asks for "up to 5 files this file most likely relates to (by path)" — but the LLM has no knowledge of other file paths. It must guess them from import statements in those first 30 lines.
- No example of a GOOD vs BAD summary to guide quality.

**Opportunity**: 
- For files >500 lines, include both head AND tail (last 30 lines). The tail often contains the public API or main entry point.
- Add positive/negative examples: "Bad: 'Python utility file.' Good: 'Pipeline stage orchestrator — coordinates the 9-stage indexing pipeline, manages LLM model loading/unloading, and emits progress telemetry via websocket.'"
- Consider including the file's import list as a signal for what the file DOES (imports `asyncio`, `websocket`, `LLMClient` implies async orchestration).

### 1C. DOC_ROLE_PROMPT (`augmenter.py:226`)

**Purpose**: Classify documentation files.
**This prompt is solid.** It asks for doc_type, doc_status, and related_files, which are all useful downstream signals. The schema is clean.

**Minor opportunity**: The `doc_status` field could include "wip" (work-in-progress) as a value — currently many Phase docs get classified as "active" when they're really in-progress research.

### 1D. EPISTEMIC_CODE_PROMPT (`epistemic_enrichment.py:51`)

**Purpose**: Deep analysis of code files — domain tags, architecture layer, subsystem, tech debt.
**Quality Impact**: This is the highest-value prompt in the pipeline. These outputs become the `extended_summary` used in module synthesis.

**Current State**: This prompt is well-structured. It includes:
- Pass 1 summary (from FILE_ROLE_PROMPT)
- Neighbor context (enriched summaries of connected files)
- Source excerpt (150 lines)

**Issues**:
- The `subsystem` field is free-form, leading to inconsistent naming across files. One file gets `"trace-engine"`, another gets `"pipeline-orchestrator"`, and a third gets `"core-pipeline"` — they're all the same subsystem.
- The `design_patterns` field is frequently empty or filled with generic patterns like `["singleton"]` that aren't useful for agents.
- **150 lines is too few for large files.** `orchestrator.py` has 3248 lines. The LLM only sees 4.6% of the code. It can't possibly describe the file's role accurately.

**Opportunities**:
- Add a CANONICAL SUBSYSTEM LIST to the prompt: "Assign each file to exactly one of these subsystems: [trace-engine, pipeline, mcp-server, dashboard, vscode-extension, knowledge-index, atlas, ...]. If the file doesn't fit any, propose a new name."
- Increase excerpt for large files. Consider the `_get_strategic_excerpt` approach already in augmenter.py — send head + most-referenced sections.
- Replace `design_patterns` with something more useful: `"key_behaviors": ["long-running background task", "manages model lifecycle", "emits websocket events"]`. These are more actionable for agents.

### 1E. EPISTEMIC_DOC_PROMPT (`epistemic_enrichment.py:87`)

**Same issues as EPISTEMIC_CODE_PROMPT** re: subsystem naming.
**Specific issue**: `decision_chains` is a powerful field ("key decisions documented here") but the LLM often returns generic entries. Could add examples.

### 1F. MODULE_SYNTHESIS_PROMPT (`cluster.py:113`)

**Purpose**: Name and describe file clusters as subsystem modules.
**Quality Impact**: These names appear in the atlas, architecture context, and module lists.

**Current Issues (post-Fix-5)**:
- The naming rules we added are good but not enforced by the schema. The JSON schema (`batch_prompts.py:501`) only requires `["id", "name", "summary"]` — no validation of naming quality.
- The `component_status` enum uses `"complete|partial|stubbed|deprecated"` but the batched version uses `"active|stable|experimental|deprecated|unknown"` — **inconsistent enums** between individual and batched prompts.
- **Critical problem**: The prompt sees `member_summaries` which are file-level summaries from Pass 1 (FILE_ROLE_PROMPT). If those summaries are generic ("Python source file"), the module synthesis has garbage-in, garbage-out.

**Opportunity**: 
- Prefer Pass 2 `extended_summary` from epistemic enrichment instead of Pass 1 summaries when available. The extended summaries are much richer.
- Add `ANTI-PATTERNS: Never produce these names: "UI Subsystem", "Config Module", "Data Layer", "Testing Framework". Each name must be unique across all modules.`
- Fix the enum inconsistency between individual and batched paths.

### 1G. INFERRED_EDGES_PROMPT (`inferred_edges.py:49`)

**Purpose**: Discover cross-file edges that static analysis misses.
**This prompt is well-designed.** Clear categories, concrete examples, explicit rules about only targeting known files.

**Minor issue**: The `known_files` list is capped at 100 entries. For a 1400-file codebase, the LLM can only suggest edges to 7% of files. Consider prioritizing "likely target" files in the known_files list (e.g., router files, config files, main entry points).

---

## Layer 2: Atlas Prompts (Build-Time Orientation Document)

### 2A. ATLAS_PROMPT (`atlas/prompts.py:17`)

**Purpose**: Generate the codebase orientation document injected into every AI query.
**Quality Impact**: This is arguably the single highest-leverage prompt — it shapes every AI interaction.

**Current Structure**: 9 sections (IDENTITY, STACK, ARCHITECTURE, SUBSYSTEMS, MODULE DEPENDENCIES, FLOW, API SURFACE, DATA MODELS, PATTERNS, RISKS).

**Issues**:
- **Too many sections for a compact atlas.** For a ~2000 char budget, 9 sections means ~220 chars each — barely 2 sentences. Most sections end up as "(insufficient data)" or unhelpfully terse.
- **SUBSYSTEMS duplicates module list.** The atlas SUBSYSTEMS section lists the same modules that appear in the ambient context's `_format_module_tiers()`. This is content triplication (atlas + ambient modules + architecture context).
- **API SURFACE and DATA MODELS** are almost always "(insufficient data)" because the enrichment pipeline doesn't extract this information explicitly.
- **FLOW** is valuable but hard for the LLM to get right from module summaries alone — it often produces a plausible but incorrect data flow.

**Opportunities**:
- **Reduce to 5 sections**: IDENTITY, STACK, WORKSPACE MAP, CROSS-CUTTING, KEY PATTERNS. Drop API SURFACE, DATA MODELS, and RISKS (which are always empty or wrong).
- **Make IDENTITY more actionable**: Instead of "what this project is", say "what an AI agent needs to know to work on this project effectively."
- Add a rule: "SUBSYSTEMS section is unnecessary — modules are listed separately. Focus on HOW modules connect, not listing them again."

### 2B. ROOT_ATLAS_PROMPT (`atlas/prompts.py:57`)

**This is already well-designed.** 4 sections (IDENTITY, STACK, WORKSPACE MAP, CROSS-CUTTING). Lean and purposeful.

The golden atlas on disk (`atlas.json`) is only 1796 chars / 13 lines — this is the good outcome of a well-constrained prompt. **This should be the model for all atlas prompts.**

### 2C. SEGMENT_ATLAS_PROMPT (`atlas/prompts.py:89`)

**Purpose**: Per-segment subsystem orientation (injected when touching files in that segment).

**Well-structured** with 6 sections. The `IMPORTANT: Only reference files that appear in the FILE LISTING above` rule is critical and well-placed.

**Minor opportunity**: Add "KEY ENTRY POINTS" as a section — "Which files should an agent read first to understand this segment?"

---

## Layer 3: MCP Response Assembly (Runtime Formatting)

### 3A. `tool_context` (Ambient Context / `codrag` tool)

**File**: `server.py:863-1019`

**Current assembly**:
```
1. Header: "## CoDRAG Context (N chunks, N chars)"
2. Stats line: "Hubs: N | Modules: N | Neighbors: N"  
3. Context body from _assemble_ambient_context:
   - Module list (tiered — Fix 1)
   - Hub file content (LOD 0 — full source)
   - Neighbor file content (LOD 1 — signatures)
4. Atlas prepend (if no rules file)
5. Role atlas (if role specified)
6. Architecture context (from architecture.py — Fix 6)
7. Concepts stats line
```

**Issues identified**:
- **"## CoDRAG Context" header is wasted tokens.** The AI already knows it called `codrag`. Replace with `## Codebase Structure` or `## Project Context`.
- **Stats line ("Hubs: N | Modules: N") is noise.** The AI doesn't need to know how many chunks were used. Delete this line.
- **Architecture context at line 981 gets 3000 chars.** This is redundant with the module list already in section 3. **Reduce to 1500 chars.**
- **Concepts stats line** ("Concepts: 5 active, 2 seeds — technical: 3, ...") is useful but cryptic. Consider: "[5 codebase concepts documented. Use codrag_concepts to explore.]"

**Opportunities**:
- Add a natural-language preamble explaining what the agent is seeing: "This is the structural context for [project name]. It includes the module hierarchy, hub files (most-connected code), and architecture annotations."
- The module list should show summaries more prominently. Currently it's `**Name** (N files): summary → deps`. Change to `**Name** — summary (N files, depends on: X, Y)`. Lead with the human-readable description.

### 3B. `tool_search` (Code Search / `codrag_search` tool)

**File**: `server.py:745-857`

**Current assembly**:
```
1. [retrieval confidence: high/medium/low | top score: 0.XX | N chunks] (NEW — Fix 7)
2. [Related concepts:] (Phase 74 — if concepts exist)
3. [Subsystem focus: dir/ -- N/M results in this area]
4. Raw context from search.py (LOD-compressed source chunks)
```

**Issues**:
- **Subsystem hint reads from `sources` which doesn't exist in the structured path.** Same bug as the score display — structured path returns `chunks` not `sources`. The subsystem hint at `server.py:805` never fires.
- **No framing for the AI.** The search results dump raw code directly. The AI sees LOD-compressed file skeletons but has no orientation about what it's looking at.
- **Concept augmentation** is a good idea but the implementation fires an extra API call on every search. Consider caching concept embeddings in-process.

**Opportunities**:
- Fix the subsystem hint to read from `chunks` (same pattern as the score fix).
- Add a brief header: "Results for: '{query}' — {N} files matched across {subsystem areas}."
- After the results, add: "[Use codrag_impact to check dependencies before modifying these files.]" — this cross-promotes the impact tool which is underused.

### 3C. Architecture Context (`architecture.py:424-525`)

**Issues already addressed**: Module cap at 30 (Fix 6).

**Remaining**: The architecture context only adds value when there are user annotations (notes, ACRs, linked issues). Without annotations, it's a redundant copy of the module list. Consider: **Skip the architecture section entirely when zero annotations exist.**

---

## Cross-Cutting Prompt Quality Issues

### Issue A: Persona Inconsistency

- Pipeline prompts use "code analyst" (augmenter), "software architect" (epistemic, atlas, cluster), "documentation analyst" (docs).
- MCP layer uses no persona — responses are assembled programmatically.
- **Recommendation**: Standardize on "senior software architect" for all deep-analysis prompts. The "code analyst" persona for augmenter is fine since it's a simpler task.

### Issue B: No Few-Shot Examples Anywhere

Not a single prompt in the entire pipeline includes a concrete example of a GOOD output. Research consistently shows that few-shot examples improve LLM output quality by 15-40%.

**High-impact opportunity**: Add 1-2 examples to the three highest-value prompts:
1. `MODULE_SYNTHESIS_PROMPT` — show a good module name + summary
2. `EPISTEMIC_CODE_PROMPT` — show a good extended_summary + domain tags
3. `ATLAS_PROMPT` — show what a good 200-char IDENTITY section looks like

### Issue C: Inconsistent Enum Values Between Individual and Batched Prompts

| Field | Individual Prompt | Batched Prompt |
|-------|------------------|----------------|
| `component_status` | `complete\|partial\|stubbed\|deprecated` | `active\|stable\|experimental\|deprecated\|unknown` |
| `architecture_layers` | not present | present in batch clustering |

This causes downstream inconsistencies when some modules were synthesized individually vs batched.

### Issue D: Summary Quality Compounds

The pipeline is: File Summary → Extended Summary → Module Name → Atlas → Agent Output.

If `FILE_ROLE_PROMPT` generates "Python source file at src/codrag/core/orchestrator.py" (because it only saw 30 lines of imports), then:
- EPISTEMIC enrichment gets "Pass 1 summary: Python source file" → produces a mediocre extended_summary
- MODULE_SYNTHESIS gets mediocre member summaries → produces "Pipeline Subsystem #3"
- Atlas gets "Pipeline Subsystem #3" → wastes atlas budget on a meaningless name

**Fix**: The FILE_ROLE_PROMPT's input quality is the single highest-leverage improvement. Giving it more context (head + tail lines, or head + most-imported sections) cascades through EVERY downstream prompt.

---

## Priority-Ranked Improvement List

| # | Change | File | Layer | Impact | Effort |
|---|--------|------|-------|--------|--------|
| 1 | Fix subsystem hint to read chunks (same as score fix) | `server.py:805` | 3 | Medium | Tiny |
| 2 | Reduce architecture budget 3000→1500 | `server.py:981` | 3 | Medium | Tiny |
| 3 | Add few-shot example to MODULE_SYNTHESIS_PROMPT | `cluster.py:113` | 1 | High | Small |
| 4 | Add few-shot example to EPISTEMIC_CODE_PROMPT | `epistemic.py:51` | 1 | High | Small |
| 5 | Increase FILE_ROLE_PROMPT input to head+tail | `augmenter.py:204` | 1 | High | Medium |
| 6 | Reduce ATLAS_PROMPT from 9 to 5 sections | `atlas/prompts.py:17` | 2 | High | Medium |
| 7 | Align component_status enums across individual/batch | `cluster.py` + `batch_prompts.py` | 1 | Medium | Small |
| 8 | Add canonical subsystem list to EPISTEMIC_CODE_PROMPT | `epistemic.py:51` | 1 | Medium | Medium |
| 9 | Skip architecture section when zero annotations | `server.py:975` | 3 | Medium | Small |
| 10 | Remove stats line from tool_context header | `server.py:949` | 3 | Low | Tiny |
