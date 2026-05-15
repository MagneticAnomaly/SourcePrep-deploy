# Phase 132 — Findings Memo

> **One-page summary of the top behavioral-vs-docs gaps found during the
> 2026-05-14 desk audit.** Audience: the team. Intent: share the patterns
> so they don't keep happening.

## TL;DR

Six tiers of docs (24+ pages) audited against `src/prep/` source-of-truth.
**About 17 substantive drift fixes landed.** None of the drift was malicious
or even surprising — every gap had a plausible origin story (a renamed
class, a Phase-50 consolidation, a feature that was planned but never
shipped, an analyzer that was the third draft of its name). The fixes are
in. The recurring *patterns* are what's worth carrying forward.

## Top three findings

### 1. Three different "intent classifiers" got conflated into one

Docs about `prep_search` confidently referenced an intent classifier with
buckets `docs / tests / code / default`. **That classifier doesn't exist.**
What does exist:

| Where | Buckets | Role |
|---|---|---|
| `core/intent.py` | 7 (LOCATE / EXPLAIN / RATIONALE / TRACE / EXAMPLE / COMPARE / DISCOVER) | User-facing — routes `prep_search` to per-intent retrieval pipelines |
| `core/index.py:41-67` `_detect_intent` | 5 (debug / refactor / add_feature / understand / general) | Internal — tunes trace direction, hops, edge-kind filter |
| `core/index.py:1104, 1110` weights | 4 (docs / code / tests / other) | **Scoring multipliers based on file kind — not a query classifier at all** |

The original `/concepts/context` text appears to have been a half-remembered
description of the third one (file-type weights) reframed as a query
classifier. Fixed by listing the canonical 7-intent taxonomy + the
file-type weights as separate scoring inputs.

**Lesson:** when a doc claims a classifier with N buckets, find the actual
N-tuple in code before paraphrasing. We have three similarly-shaped data
structures here that look alike from a distance.

### 2. Ghost APIs — confidently documented, doesn't exist

Three separate cases where docs referenced something real-looking that
isn't wired:

- **`prep audit` CLI command** — referenced in `/guides/codebase-audit`
  Quick Start with three example invocations. Doesn't exist. Only
  `prep hr-audit` (HR-agent feature) exists. Audits are triggered via the
  MCP `prep_audit` tool, REST API, or the dashboard. `prep opportunities`
  is the real CLI for reading audit findings.
- **`PREP_LOG_LEVEL` environment variable** — documented in `/cli/config`
  env-var table and `/cli/commands` `prep serve` notes. Zero references in
  `src/`; `cli.py:1399` and `server.py:56` hardcode `logging.INFO`.
- **LanceDB / Qdrant / Chroma vector storage** — `/concepts/indexing`
  claimed vectors land in "a local LanceDB instance (or Qdrant/Chroma if
  configured)". Zero references to any vector DB in the codebase; vectors
  are plain `embeddings.npy` (numpy) + JSON metadata.

All three are now corrected. Pattern: each one was a plausible-sounding
implementation detail that *could* have been true at some point or in some
proposal doc, but never made it (or didn't survive) in shipping code.

**Lesson:** when a doc references a specific runtime mechanism (CLI flag,
env var, dependency), grep for it before trusting it.

### 3. LEGACY_TOOLS leaking into user-facing surfaces

`/guides/codebase-audit` documented "four MCP tools" for audit work:
`prep_audit`, `prep_audit_report`, `prep_audit_refactor`, `prep_audit_check`.
Reality (from `mcp_tools.py:25` comment "Phase 50: Consolidated from 16 tools
to 5 + 1 dev alias"):

- `_CORE_TOOLS` (what production MCP clients see) has exactly **one** audit
  tool: `prep_audit`
- `LEGACY_TOOLS` (line 554+) contains the three `prep_audit_*` names as
  routing aliases — they dispatch to the same handler with different
  `action` parameters

This is a clean Phase-50 consolidation in code that didn't propagate to
docs. Fix landed: one tool, action-mode table.

A similar pattern showed up for the audit analyzer registry — the file is
`naming.py` but the registered name is `"naming_consistency"`. The docs
happened to use the registered name (correct), but it's the same kind of
"the file-level name and the runtime-registered name diverged" hazard.

**Lesson:** when a code module is consolidated or renamed, sweep docs for
the pre-consolidation surface as part of the consolidation PR. Bonus
points for adding the kind of CI test described in P132-CI.

## Honorable mentions (smaller drift, same shape)

- `prep serve --debug` — documented in two places, doesn't exist (serve
  only has `--host/--port/--reload`; debug lives on `prep mcp`)
- `prep config set <key> <value>` — actual signature is two positional
  args (`prep config <key> <value>`)
- `nomic-embed-code` dimension claimed as "4 096"; real value is **3 584**
  with Matryoshka truncation to 768
- "Three relationship types" framing on `/concepts/code-graph` collapses
  the actual 5-kind `TraceEdge` enum; defensible as user-facing
  simplification, flagged for product decision
- "Graph Status → Build" panel reference on `/getting-started`; the panel
  was renamed to "Graph Scope" in a prior phase
- `prep.dev` brand reference on `/mcp/paperclip`; should be
  `sourceprep.io` per the SourcePrep / prep brand split

## Closing thoughts

The audit was worth doing — **none of the drift would have been caught by
existing tests**. The drift accumulated across multiple phases of
consolidation, renames, and feature reshuffles. The three CI fidelity
tests proposed under P132-CI (sidebar resolution, panel-registry anchor
resolution, StoryEmbed storyId resolution) would catch the most common
shapes mechanically, but the deeper pattern — "behavioral claim in docs
diverges from current code" — remains a human-review job. A periodic
audit cadence (every quarter? every major phase consolidation?) plus the
three CI tests should keep this manageable.

For now, the docs are honest. Ship-readiness install verification still
needs to happen on a real machine before public launch (parked under
"Ship-readiness checks" in MASTER_TODO).
