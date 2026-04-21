# Curated Traceability Framework (Optional Layer)

This document describes an **optional curated traceability layer** that complements Prep’s automated **Trace Index** (code graph).

- The **Trace Index** (Phase04) is built automatically from code (AST parsing, imports, symbol spans).
- The **Curated Traceability Framework** captures the higher-level “why”: plans, decisions, research, and explicit links to the implementing code.

This layer is **not required** for Prep’s baseline value. It exists to support teams who want stronger traceability and governance.

## Why this exists

Automated code graphs answer structural questions (what imports what, what defines what). They do not reliably answer:

- Why does this code exist?
- Which plan/requirement does this implement?
- Which decision justified this design?
- What tests verify this requirement?

A curated layer is a lightweight way to preserve that intent in a queryable, tool-friendly format.

## Universal patterns (sources)

### Bidirectional traceability (RTM-style)

Key guidance (NASA SWE-072) that maps directly to Prep’s goals:

- Unique identifiers for traced elements (requirements/design/code/tests)
- Maintain traceability throughout the lifecycle
- Bidirectional traversal (forward + backward)
- Use traceability to identify:
  - missing tests for requirements
  - tests that do not map to any requirement

Source:
- https://swehb.nasa.gov/display/SWEHBVB/SWE-072+-+Bidirectional+Traceability+Between+Software+Test+Procedures+and+Software+Requirements

### Decision records (ADR-style)

Useful ADR characteristics:

- Use a consistent template (context/problem, options, decision, consequences)
- Record tradeoffs
- Record confidence level
- Keep records pithy and factual

Sources:
- https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record
- https://adr.github.io/adr-templates/

## Proposed representation (curated graph)

A curated traceability graph can be stored as human-editable entries (e.g. YAML-in-Markdown) plus machine-readable validation outputs.

### Categories

- `plans/` (or requirements)
- `decisions/` (ADRs)
- `research/`
- `code/` (hand-curated metadata about major modules/files)
- `crossrefs/` (optional derived artifacts like coverage stats)

### Link types (examples)

- `implements` / `implemented_by`
- `depends_on` / `depended_by`
- `documents` / `documented_by`
- `tests` / `tested_by`
- `supersedes` / `superseded_by`
- `related` (symmetric)

### Confidence levels

Curated edges should carry a confidence signal:

- `high`: explicit citation in a doc/comment
- `medium`: strong inference
- `low`: speculative

This mirrors how real projects evolve: some links are authoritative, others are best-effort.

## Relationship to Phase04 Trace Index

The curated layer can integrate with the trace index without requiring new infrastructure:

- Curated `code` entries can reference `file_path` and (optionally) symbol `qualname`.
- Prep can offer a query-time expansion mode that uses:
  - automated trace neighbors (imports/contains)
  - curated neighbors (implements/documents/decision links)

This enables retrieval that is both:
- structurally grounded
- intent-aware

## Minimal example

A cleaned, content-agnostic example of this curated framework (schema + AI prompts) lives at:

- `docs/Phase00_Initial-Concept/EXAMPLE-TRACE-STRUCTURE/curated_trace_framework/`
