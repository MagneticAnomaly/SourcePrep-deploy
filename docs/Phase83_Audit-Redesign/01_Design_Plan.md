# Phase 83 — Audit Redesign: Structural Intelligence + Enrichment Layer

**Date:** 2026-04-07
**Status:** Design finalized
**Scope:** Redesign `codrag_audit` from a linter-clone into a dual-mode tool: structural intelligence (CoDRAG-unique findings) and external finding enrichment
**Dependencies:** None (can begin immediately)
**Predecessor:** Phase 82 MCP-Dogfooding analysis (all 15 docs)

---

## Executive Summary

Phase 82 dogfooding revealed that `codrag_audit` is the weakest of the 6 MCP tools. It generates 100+ findings that overlap with what ruff, eslint, and semgrep already catch, inflates severity on generated files (package-lock.json flagged as CRITICAL), duplicates the same bottleneck finding 6x, and provides generic remediation text that doesn't account for file type or architectural context.

The core insight: **AI agents that consume CoDRAG already have access to linters.** Claude Code runs ruff. Cursor surfaces ESLint. What these agents *don't* have is structural context — how many files depend on the thing the linter flagged, whether there's a concept saying it's scheduled for refactoring, whether it's been observed as a growing concern across sessions.

CoDRAG should stop competing with linters and instead become the **enrichment layer** that makes linter findings actionable. Simultaneously, CoDRAG should surface the structural insights that *only* it can see — coupling hotspots, hub concentration risk, concept violations, architectural drift.

The dashboard's Audit pane is **downgraded to experimental/dev-only**. The real product surface for audit is the MCP layer — AI agents are the primary consumers.

---

## Global Experimental Toggle

A single project-level setting controls all experimental features:

```
experimental: true/false  (default: false)
```

**When off (default):** Template-based recommendations only. Audit dashboard pane hidden. Stable, predictable behavior.

**When on:** LLM-generated recommendations appear alongside templates. Audit dashboard pane visible (dev/QA tool). Future experimental features activate through this same toggle.

No per-feature flags. One toggle, everything experimental lights up or stays dark.

---

## Design

### Single Tool, Two Modes

`codrag_audit` becomes a dual-mode tool. The mode is determined by the presence or absence of a `findings` parameter:

#### Mode 1: Structural (no `findings` parameter)

```
codrag_audit()
codrag_audit(category="coupling")
codrag_audit(scope="src/codrag/mcp/server.py")
```

Returns CoDRAG-unique structural insights. These are things no linter can detect because they require the trace graph, concepts, and observation history:

| Finding Type | What It Detects | Data Source |
|-------------|-----------------|-------------|
| **Coupling hotspot** | Files with disproportionate inbound dependencies | Trace graph in-degree |
| **Hub concentration risk** | Too much logic concentrated in too few files | Trace graph + file size |
| **Concept violation** | Code diverges from stated architectural intent | Concepts + code analysis |
| **Architectural drift** | Observed patterns diverging from concepts over time | Observations + concepts |
| **Observation-pattern warning** | Recurring concerns flagged across sessions | Observation history |
| **Import cycle risk** | Circular dependency chains that affect maintainability | Trace graph cycle detection |
| **Module boundary violation** | Cross-module coupling that breaks intended isolation | Module map + trace graph |

**What gets dropped from current audit:**
- Complexity metrics (ruff does this)
- Naming/style violations (eslint/ruff do this)
- Generated file findings (package-lock.json, .d.ts, lockfiles)
- Duplicate findings (one bottleneck = one finding, not 6)
- Generic remediation text ("extract into dedicated module" applied to everything)

**Output format:** Markdown, consistent with other CoDRAG tools. Each finding includes:
- What was detected (specific, not generic)
- Why it matters (structural impact: dependent count, concept reference)
- What to consider (context-aware, not template remediation)

#### Mode 2: Enrichment (`findings` parameter provided)

```
codrag_audit(findings=[...])
codrag_audit(findings=[...], format="sarif")
```

Accepts external findings and annotates each one with CoDRAG structural context. The AI agent runs its own linter, gets results, and pipes them through CoDRAG for enrichment.

**Input V1 — Simple schema (Phase 83):**

```json
{
  "findings": [
    {
      "file": "src/codrag/mcp/server.py",
      "line": 142,
      "message": "Function too complex (C901: 23)",
      "severity": "warning",
      "tool": "ruff"
    },
    {
      "file": "src/codrag/dashboard/src/App.tsx",
      "line": 1,
      "message": "File exceeds 500 lines",
      "severity": "info",
      "tool": "custom"
    }
  ]
}
```

**Input V2 — SARIF (Phase 85):**

Full SARIF 2.1.0 ingestion. See Phase 85 plan for details.

**Enrichment output:**

Each finding is returned with a `codrag` context block appended:

```json
{
  "findings": [
    {
      "file": "src/codrag/mcp/server.py",
      "line": 142,
      "message": "Function too complex (C901: 23)",
      "severity": "warning",
      "tool": "ruff",
      "codrag": {
        "dependents": 23,
        "hub_status": "critical",
        "module": "mcp",
        "concepts": [
          "Planned refactor: split handler dispatch into per-tool modules (Phase 3 roadmap)"
        ],
        "observations": [
          "2026-03-15: Flagged as growing concern during MCP server refactoring",
          "2026-04-01: Complexity increased after adding codrag_concepts handler"
        ],
        "risk_score": 0.87,
        "recommendation": "High-impact target for refactoring — 23 dependents means changes here ripple widely. Existing concept confirms this is already planned. Prioritize."
      }
    },
    {
      "file": "src/codrag/dashboard/src/App.tsx",
      "line": 1,
      "message": "File exceeds 500 lines",
      "severity": "info",
      "tool": "custom",
      "codrag": {
        "dependents": 8,
        "hub_status": "moderate",
        "module": "dashboard",
        "concepts": [],
        "observations": [],
        "risk_score": 0.34,
        "recommendation": "Moderate coupling but no architectural concerns flagged. Standard refactoring candidate, not urgent."
      }
    }
  ],
  "summary": {
    "total": 2,
    "enriched": 2,
    "high_risk": 1,
    "key_insight": "server.py complexity finding is structurally critical — it's a hub file with planned refactoring already conceptualized."
  }
}
```

**Enrichment context fields:**

| Field | Source | Description |
|-------|--------|-------------|
| `dependents` | Trace graph | Number of files that import/depend on this file |
| `hub_status` | Trace graph + thresholds | "critical" / "high" / "moderate" / "low" based on dependent count |
| `module` | Module map | Which CoDRAG-identified module this file belongs to |
| `concepts` | Concepts store | Related architectural decisions, design rationale, planned changes |
| `observations` | Observation store | Cross-session notes about this file/area |
| `risk_score` | Composite | 0-1 score combining: dependent count, hub status, concept alignment, observation frequency |
| `recommendation` | Generated | Context-aware sentence synthesizing all signals |

### Risk Score Formula

```
risk_score = (
    0.40 * hub_score          # 0-1 based on dependent count percentile
  + 0.30 * concept_score      # 1.0 if active constraint, 0.5 if architecture, 0.0 if none
  + 0.20 * observation_score  # 0-1 based on recency and frequency of observations
  + 0.10 * churn_score        # 0-1 based on how often this file changes (from git)
)
```

Hub dominates because structural impact is CoDRAG's strongest unique signal. Weights stored in config (not hardcoded) for post-dogfooding tuning.

### Recommendations: Templates + Experimental LLM

**Default (experimental off):** Template-based composable fragments:
- `[hub_status = critical]` → "Critical hub file — changes here ripple to {n} dependents."
- `[has_concept]` → "Existing concept: {concept.title}."
- `[has_observations]` → "Flagged {n} times since {earliest_date}."
- `[hub + concept]` → "Prioritize — high structural impact with planned refactoring already documented."
- `[hub + no_concept]` → "High impact but no architectural plan documented. Consider creating a concept before modifying."

**Experimental on:** LLM-generated recommendations appear alongside template output. The LLM receives the same context (dependents, concepts, observations) and produces a more contextual, nuanced recommendation. Both are returned so the user/agent can compare quality.

### Stale Data Handling

If any findings reference files not in the CoDRAG index, the response includes a single message:

> "Looks like you have stale data, CoDRAG recommends running enrichment again."

No per-file flags, no error metadata. One message, actionable.

### Enrichment Limits

Default cap: **200 findings per call**. Beyond cap: top 200 by estimated risk score, summary notes remaining count. Configurable via `max_findings` parameter.

### P0 Quick Fixes (Bundle With This Phase)

These fixes from Phase 82 doc 07 are small enough to ship alongside the audit redesign and improve the other tools:

1. **Format `codrag_impact` direction="all" as markdown** — currently returns raw JSON while all other tools return markdown. Use the existing `tool_impact` formatter.

2. **Filter stdlib/external nodes from `codrag_impact`** — 75% of impact results are noise (`json`, `os`, `logging`). Filter to project-internal dependencies by default, add `include_external=true` param for when you actually want them.

3. **Add code context to `codrag_search` symbol results** — currently returns bare file paths. Include: qualified name, first-line docstring, line number, and a 3-line code snippet.

4. **Exclude generated/lock files from audit** — `package-lock.json`, `.d.ts` declaration files, and similar generated artifacts should never appear in findings.

---

## Implementation Plan

### Stage 1: Strip Down Current Audit (Structural Mode)

**Files to modify:**
- `src/codrag/mcp_tools.py` — Update `codrag_audit` schema: add `findings` param (optional), add `scope` param, update description
- `src/codrag/mcp/server.py` — Route: if `findings` present → enrichment handler, else → structural handler
- `src/codrag/api/routers/audit.py` (or equivalent) — New structural-only finding generators

**What to build:**
1. New structural finding generators that query the trace graph for coupling, hub concentration, cycles, boundary violations
2. Concept violation checker that compares concept assertions against code state
3. Observation pattern aggregator that surfaces recurring warnings
4. Finding deduplication (one file = one finding, not N findings per consumer)
5. Context-aware recommendation generator (replaces generic "extract into module" text)

### Stage 2: Enrichment Mode

**Files to modify:**
- `src/codrag/mcp/server.py` — New `tool_audit_enrich()` handler
- New: `src/codrag/core/enrichment.py` — Enrichment engine: takes a finding, queries trace graph + concepts + observations, returns annotated finding

**What to build:**
1. Finding parser (V1 simple schema)
2. Per-finding enrichment pipeline: file → trace graph lookup → concept query → observation query → risk score → recommendation
3. Summary generator (aggregate insights across all findings)
4. Output formatter (JSON with codrag blocks)

### Stage 3: P0 Quick Fixes

Parallel with Stages 1-2:
1. Impact markdown formatting
2. Impact stdlib filtering
3. Search symbol context
4. Audit generated file exclusion

### Stage 4: Testing & Dogfooding

- Dogfood structural mode on CoDRAG itself — compare output quality to current audit
- Dogfood enrichment mode by running `ruff check src/ --output-format json`, converting to simple schema, piping through enrichment
- Validate that AI agents (Claude Code, Cursor) can successfully use both modes
- Measure: token efficiency (should be much less noise), actionability (findings should be specific enough to act on)

---

## Success Criteria

1. **Structural mode** returns <20 findings (not 100+), each one unique to CoDRAG's structural knowledge
2. **Enrichment mode** adds measurable value: an AI agent receiving enriched findings makes better prioritization decisions than one receiving raw lint output
3. **No false positives on generated files** — package-lock.json, .d.ts, lockfiles never appear
4. **No duplicate findings** — one bottleneck file = one finding
5. **Token efficiency** — structural mode response fits in <3K tokens (vs current 5K+ with noise)
6. **Format consistency** — both modes produce clean markdown/JSON matching other tool output styles

---

## Competitive Positioning

This redesign positions CoDRAG uniquely in the market:

- **SonarQube MCP** exposes its own findings to agents — a pipe, no enrichment
- **Code Pathfinder** provides call graphs but no semantic/epistemological layer
- **Ruff/ESLint/Semgrep** find problems but can't tell you *why* a problem matters structurally
- **CoDRAG** becomes the only tool that says: "This complexity warning matters because 23 files depend on this, there's already a plan to refactor it, and it was flagged as growing 3 weeks ago"

Nobody else is building the enrichment layer. This is the moat.

---

## Resolved Questions

1. **Risk score formula** — Weighted composite: 0.40 hub + 0.30 concept + 0.20 observation + 0.10 churn. Weights in config for tuning.
2. **Recommendation generation** — Both: templates as default, LLM as experimental (behind global toggle). LLM output appears alongside templates when experimental=true.
3. **Enrichment for files not in the index** — Single message: "Looks like you have stale data, CoDRAG recommends running enrichment again." No per-file metadata.
4. **Streaming** — Batch with 200-finding cap. Top 200 by risk score. Configurable via `max_findings`.
