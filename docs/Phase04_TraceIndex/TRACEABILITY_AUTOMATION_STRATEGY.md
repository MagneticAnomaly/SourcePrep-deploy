# Traceability Automation Strategy (Prep)

This document proposes how Prep can support **requirements/plan ↔ code ↔ tests** traceability in a way that is:

- Local-first (can run without paid APIs)
- Incremental (can run continuously via Phase 03 Auto-Rebuild)
- Transparent (outputs are inspectable + diffable)
- Optional (users can choose “manual-only”, “local hybrid”, or “heavy LLM validation”)

This complements:
- `README.md` (Phase04) — automated Trace Index (files/symbols/imports)
- `CURATED_TRACEABILITY_FRAMEWORK.md` — curated traceability layer (plans/decisions/research ↔ code)

## Problem we are solving

Prep’s Trace Index (Phase04) answers structural questions:
- what imports what?
- what symbols exist?

But “full traceability” requires linking:
- plans/requirements → implementing code
- plans/requirements → tests
- decisions/ADRs → impacted code

This is harder because:
- requirements are often informal
- code rarely cites requirements explicitly
- even when links exist, they drift over time

## Minimum required (MVP)

If Prep only implements ONE thing for curated traceability, it should be:

1. **Stable identifiers** for “spec artifacts”
   - Examples: `REQ-123`, `ADR-0004`, `PLAN-05`, etc.
   - Stored in the text artifacts themselves (docs-as-code)

2. **Deterministic extraction + linking**
   - Parse the repo for explicit references to those IDs.
   - Create high-confidence edges based on explicit citations.

3. **Validation outputs**
   - Report “orphans” and “missing coverage” (requirements with no code/tests).

This yields immediate value with **zero LLM dependence**.

## Options spectrum (from minimal → ambitious)

### Option 0: Manual curated traceability (no automation)

- Users maintain curated files/links by hand.
- Prep only indexes/searches them.

Pros:
- Simple
- Deterministic

Cons:
- High maintenance

### Option 1: Deterministic link extraction (regex + conventions) (recommended MVP)

Mechanism:
- Support repo conventions:
  - requirement IDs in docs headings
  - requirement IDs in code comments / docstrings
  - ADR IDs in decision files
- Prep scans and generates edges:
  - `documents` / `documented_by`
  - `implements` / `implemented_by`
  - `tests` / `tested_by`

Confidence:
- All edges from explicit citations are `high`.

Pros:
- Runs locally
- Cheap
- Incremental

Cons:
- Requires users to adopt conventions

### Option 2: IR/embedding-based candidate generation (no LLM)

Mechanism:
- Treat each requirement/plan as a query.
- Use Prep’s existing embeddings + BM25/FTS to retrieve top-k code chunks.
- Emit *candidate* links (not authoritative) with `medium/low` confidence.

Pros:
- Still local
- Leverages Prep’s core strengths

Cons:
- Can produce false positives
- Needs a review/approval workflow

Research context:
- Traditional “traceability link recovery” commonly starts with IR-style retrieval and then applies thresholds/reranking.

### Option 3: Hybrid local LLM (small) for link selection + justification

Mechanism:
- Use Option 2 to retrieve candidates.
- Ask a local instruct model (e.g. via Ollama) to:
  - choose the best links among candidates
  - output a short justification
  - assign a confidence level

Pros:
- Local-first UX (no paid tokens)
- Better precision than raw similarity

Cons:
- Model-dependent quality
- Still needs validation

### Option 4: Two-tier pipeline (local model + heavy validation)

Mechanism:
- Local model generates/updates links continuously.
- A larger model is invoked only for:
  - periodic audits
  - PR checks
  - validating low-confidence links

Pros:
- Cost bounded
- High quality where it matters

Cons:
- Requires user BYOK configuration

## Model sizing + context window guidance

A key design goal is to **avoid needing the whole repo in-context**.

Instead:
- Break the problem into small prompts:
  - one requirement at a time
  - with retrieved candidates

Typical context budgets if we design prompts well:
- 2–6k tokens per call (requirement text + 3–10 candidate snippets)

Implications:
- A local 7B–14B instruct model can often do *link selection* and *short justification*.
- You do not need an 80B model for every step.
- Bigger models are most useful for:
  - ambiguous cross-cutting features
  - long-range architectural reasoning
  - global consistency checks

“Reasoning mode” / `<think>`:
- Not required if we demand structured output.
- If a model supports deeper reasoning, it can improve link selection, but Prep should not depend on it.

## How this fits into Prep (data + API)

### Storage

Do not replace Phase04 trace index.

Add a second, optional set of outputs stored alongside `trace_*.jsonl`, e.g.:

- `trace_curated_nodes.jsonl`
- `trace_curated_edges.jsonl`
- `trace_curated_manifest.json`

Curated nodes represent:
- plans/requirements
- decisions/ADRs
- research notes
- tests (optional)

Curated edges represent:
- `implements`, `documents`, `tests`, etc.

### Build integration

Add optional build phases under the existing project build flow:

- `trace_build` (Phase04: files/symbols/imports)
- `traceability_extract` (regex citations)
- `traceability_candidates` (IR retrieval)
- `traceability_llm` (optional)
- `traceability_validate` (reports)

### Query-time usage

Prep can merge both graphs during retrieval:

- Structural expansion: imports/contains
- Intent expansion: implements/documents/decision links

## Phase03 Auto-Rebuild overlap

Auto-rebuild should treat trace + traceability as incremental jobs:

- On code changes:
  - update trace index for changed files
  - update candidate links for requirements affected by changed code chunks

- On docs changes:
  - re-extract IDs and citations
  - regenerate candidate links only for changed requirements/plans

Storm protection:
- LLM validation should be debounced and capped (never run on every keystroke).

## Open-source projects to learn from (with licensing notes)

These are useful references for *patterns*, not code reuse:

- Doorstop (requirements management in git)
  - License: LGPLv3
  - Pattern: each item is a file; explicit links; integrity checks; HTML publish
  - Repo: https://github.com/doorstop-dev/doorstop

- Sphinx-Needs (docs-as-code lifecycle objects)
  - License: MIT
  - Pattern: typed objects + links, automatic inbound links, external sync
  - Site: https://www.sphinx-needs.com/

- TraceLab (traceability research workbench)
  - License: GPL-3.0
  - Repo: https://github.com/CoEST/TraceLab

- Fine-grained Traceability Link Recovery (FTLR)
  - License: GPL-3.0
  - Pattern: precompute similarity matrices + optional call-graph incorporation
  - Repo: https://github.com/tobhey/finegrained-traceability

If Prep wants commercial-friendly dependencies, prefer permissive licenses (MIT/BSD/Apache-2) and treat GPL projects as research references.

## Research references (starting set)

- NASA SWE-072 (bidirectional traceability guidance)
  - https://swehb.nasa.gov/display/SWEHBVB/SWE-072+-+Bidirectional+Traceability+Between+Software+Test+Procedures+and+Software+Requirements

- TraceBERT (pretrained BERT for trace link generation)
  - https://arxiv.org/abs/2102.04411

- LLM-based data augmentation for traceability
  - https://arxiv.org/html/2509.20149v1

- Requirements Traceability Link Recovery via Retrieval-Augmented Generation (KITopen entry)
  - https://publikationen.bibliothek.kit.edu/1000178589

- LiSSA (generic TLR via RAG; KITopen entry)
  - https://publikationen.bibliothek.kit.edu/1000178348

## Recommended Prep path (pragmatic)

### Phase A (minimum viable, local-first)

- Implement Option 1 (deterministic ID extraction)
- Emit curated nodes/edges + `.validation/`-style reports
- Add a minimal UI to browse:
  - requirements/plans
  - linked code
  - orphan/missing coverage lists

### Phase B (improve recall without paid APIs)

- Add Option 2 candidate generation via embeddings + BM25
- Add review workflow:
  - accept/reject links
  - persist accepted links as `high` confidence

### Phase C (optional LLM assist)

- Add Option 3 local LLM “link selection”
- Keep context small by retrieval; never ask the model to read the whole repo.

### Phase D (optional heavy validation)

- Add scheduled “audit” jobs using a user-specified provider/model.
- Focus on:
  - low-confidence links
  - high-impact requirements
  - drift after refactors
