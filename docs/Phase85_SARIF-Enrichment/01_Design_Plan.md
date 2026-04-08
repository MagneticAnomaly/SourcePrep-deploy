# Phase 85 — SARIF Enrichment: Industry-Standard Finding Ingestion

**Date:** 2026-04-08
**Status:** Design finalized
**Scope:** Add SARIF 2.1.0 ingestion to `codrag_audit` enrichment mode, enabling power users to pipe GitHub Code Scanning, semgrep, SonarQube, and other SARIF-emitting tools through CoDRAG for structural enrichment
**Dependencies:** Phase 83 (enrichment mode must exist first with simple schema)
**Predecessor:** Phase 82 doc 13 (Audit as Knowledge Layer), Phase 83 enrichment mode V1

---

## Executive Summary

Phase 83 ships enrichment mode with a simple JSON schema — good enough to prove the concept and get early feedback. Phase 85 adds the format that power users actually produce: **SARIF 2.1.0** (Static Analysis Results Interchange Format), the OASIS standard used by GitHub Code Scanning, semgrep, SonarQube, Checkmarx, CodeQL, and dozens of other tools.

The insight from [AI-Native SARIF research](https://parsiya.net/blog/ai-native-sarif/) is that SARIF's extensibility model (property bags on rules and results) is purpose-built for exactly what CoDRAG does — adding contextual metadata to findings. CoDRAG can consume standard SARIF, enrich it, and return **valid SARIF** with CoDRAG context injected into property bags. This means:

1. An AI agent can run `semgrep --sarif` → pipe output to `codrag_audit(findings=<sarif>)` → get enriched SARIF back
2. The enriched SARIF is still valid SARIF — it can be uploaded to GitHub Code Scanning, ingested by other tools, or stored for tracking
3. GitHub users (our power users) get the most value: their existing Code Scanning results become structurally intelligent

---

## Design

### SARIF Version Support

**Accept both SARIF 2.0 and 2.1.0, always emit 2.1.0.** Old tools shouldn't be a blocker for users. Auto-detect version from `$schema` or `version` field.

### SARIF Ingestion

**What CoDRAG reads from SARIF input:**

```
runs[].results[]:
  ruleId          → maps to finding type
  level           → error/warning/note → severity
  message.text    → human-readable description
  locations[0]:
    physicalLocation:
      artifactLocation.uri    → file path
      region.startLine        → line number
      region.startColumn      → column (optional)
  partialFingerprints        → dedup key (if present)

runs[].tool.driver:
  name            → source tool (semgrep, ruff, codeql, etc.)
  rules[]:
    id            → rule identifier
    shortDescription → what the rule checks
    properties    → existing metadata
```

**What CoDRAG ignores (passthrough):**
- `runs[].invocations` — tool execution metadata
- `runs[].artifacts` — file listings
- `runs[].taxonomies` — classification schemes
- Any fields not listed above — passed through unchanged

### SARIF Enrichment Output

CoDRAG returns **valid SARIF** with enrichment injected into property bags:

**Per-result enrichment** (in `results[].properties.codrag`):

```json
{
  "ruleId": "C901",
  "level": "warning",
  "message": { "text": "Function too complex (23)" },
  "locations": [{ "physicalLocation": { "artifactLocation": { "uri": "src/codrag/mcp/server.py" }, "region": { "startLine": 142 } } }],
  "properties": {
    "codrag": {
      "dependents": 23,
      "hub_status": "critical",
      "module": "mcp",
      "concepts": [
        {
          "title": "MCP handler dispatch refactoring",
          "assertion": "server.py should dispatch to per-tool handler modules, not inline all logic",
          "status": "active"
        }
      ],
      "observations": [
        "2026-03-15: Complexity growing — each new tool adds another branch to dispatch"
      ],
      "risk_score": 0.87,
      "recommendation": "Critical hub file with planned refactoring. Prioritize this over other complexity warnings."
    }
  }
}
```

**Per-run enrichment** (in `runs[].properties.codrag`):

```json
{
  "properties": {
    "codrag": {
      "enrichment_version": "1.0",
      "project_id": "1d6f0b35-...",
      "index_freshness": "2026-04-07T10:30:00Z",
      "summary": {
        "total_findings": 47,
        "enriched": 42,
        "unenriched": 5,
        "high_risk": 8,
        "concept_violations_detected": 3,
        "key_insights": [
          "8 findings cluster around server.py — a known hub file with planned refactoring",
          "3 findings violate active architectural concepts",
          "17 findings are in low-coupling leaf files — likely low priority"
        ]
      }
    }
  }
}
```

Stale data handling follows Phase 83: if any findings reference un-indexed files, include: "Looks like you have stale data, CoDRAG recommends running enrichment again."

### Enrichment Pipeline

For each SARIF result:

```
1. Extract file path from locations[0].physicalLocation.artifactLocation.uri
2. Normalize path (SARIF uses URI format, CoDRAG uses filesystem paths)
3. Look up file in trace graph → get dependent count, hub status, module
4. Query concepts anchored to this file/module → get relevant concepts
5. Query observations mentioning this file → get observation history
6. Compute risk score (composite of structural + epistemological signals)
7. Generate recommendation (template default, LLM if experimental on)
8. Inject codrag property bag into result
```

### Multi-Run SARIF

A single SARIF file can contain multiple `runs` (from different tools). **V1: enrich each run independently.** No cross-referencing between runs.

**Future (highly recommended):** Cross-run analysis — "ruff and semgrep both flagged server.py, and it's a critical hub with 23 dependents. This file has convergent signals from multiple tools." This is a natural extension that adds significant value and should be prioritized in a Phase 85.1 follow-up.

### Simple Schema → SARIF Output

When `codrag_audit(findings=[simple_schema])` is called, the enriched output can optionally be returned as valid SARIF. This lets agents normalize everything to one format, useful for GitHub upload workflows.

Auto-detect: if input is SARIF, output is SARIF. If input is simple schema, output is simple enriched JSON by default. Add `output_format="sarif"` param to force SARIF output from simple input.

### Deduplication & Grouping

Before enrichment:

1. **Group by file** — all findings for the same file share one trace graph lookup (performance)
2. **Deduplicate by fingerprint** — if `partialFingerprints` is present, skip duplicate results
3. **Cap enrichment** — default limit of 200 findings per call (aligns with Phase 83 cap). Beyond cap: top 200 by risk score, summary notes remaining count. Configurable via `max_findings`.

### Size Limits

**Maximum: 5MB / 1000 results per call.** Documented clearly in tool description and error messages. Larger files should be split or scoped before enrichment.

### Tool Detection & Adaptation

Different SARIF-emitting tools have different characteristics. CoDRAG adapts enrichment based on the source tool:

| Tool | Characteristic | Adaptation |
|------|---------------|------------|
| **semgrep** | Security-focused, high-confidence rules | Emphasize dependent count (blast radius of a vulnerability) |
| **CodeQL** | Deep dataflow analysis, complex findings | Add import chain context (how tainted data flows through modules) |
| **ruff** | Style + complexity, high volume | Emphasize hub status (complexity in a hub matters more than in a leaf) |
| **ESLint** | Frontend-focused, convention checks | Add component tree context if available |
| **SonarQube** | Broad coverage, reliability/security/maintainability | Map SonarQube severity to CoDRAG risk for composite scoring |

Tool detection from `runs[].tool.driver.name`. Unknown tools get default enrichment.

---

## Implementation Plan

### Stage 1: SARIF Parser

**New file:** `src/codrag/core/sarif.py`

**What to build:**
1. SARIF 2.0 + 2.1.0 parser — read and validate SARIF JSON, auto-detect version
2. Result extractor — pull file path, line, message, severity, rule from each result
3. Path normalizer — convert SARIF URI paths (`file:///`, relative paths) to CoDRAG filesystem paths
4. Validation — reject malformed SARIF with clear error messages, accept partial/incomplete SARIF gracefully

### Stage 2: Enrichment Integration

**Files to modify:**
- `src/codrag/core/enrichment.py` (from Phase 83) — Add SARIF input handler alongside simple schema handler
- `src/codrag/mcp/server.py` — Auto-detect SARIF vs simple schema based on input structure
- `src/codrag/mcp_tools.py` — Add `output_format` parameter (values: "auto", "sarif", "simple")

**What to build:**
1. SARIF → internal finding conversion (reuse same enrichment pipeline as simple schema)
2. Internal enriched finding → SARIF output conversion (inject property bags)
3. Auto-detection: if `findings` contains `"$schema"` or `"version"` SARIF markers, treat as SARIF
4. Simple → SARIF output conversion (for `output_format="sarif"` with simple input)
5. Per-run summary generation

### Stage 3: Performance Optimization

**What to build:**
1. Batch trace graph lookups — group findings by file, query once per file
2. Concept/observation batch queries — single query per module, not per finding
3. Finding cap with prioritization — if >200 findings, enrich top 200 by estimated risk, return rest unenriched
4. Size limit enforcement — reject >5MB / >1000 results with actionable error message

### Stage 4: Tool-Specific Adapters

**New file:** `src/codrag/core/sarif_adapters.py`

**What to build:**
1. Tool detection from `runs[].tool.driver.name`
2. Per-tool recommendation templates (security tools emphasize blast radius, style tools emphasize hub status)
3. Per-tool severity mapping (SonarQube BLOCKER ≠ ruff error in structural importance)
4. Fallback default adapter for unknown tools

### Stage 5: GitHub Integration Testing

**What to test:**
1. Export Code Scanning SARIF from a real GitHub repo → enrich → verify output is valid SARIF
2. Round-trip: enriched SARIF can be uploaded back to GitHub Code Scanning via `gh api`
3. Semgrep SARIF output → enrichment → validate
4. CodeQL SARIF output → enrichment → validate
5. Mixed-tool SARIF (multiple runs in one file) → enrichment → validate

---

## Success Criteria

1. **Valid SARIF in, valid SARIF out** — enriched output passes SARIF 2.1.0 validation
2. **Property bags are additive** — CoDRAG never modifies existing SARIF fields, only adds `codrag` property bags
3. **Handles real-world SARIF** — tested against actual semgrep, CodeQL, and ruff SARIF output
4. **Performance** — enriches 200 findings in <5 seconds (single trace graph lookup per file, not per finding)
5. **Graceful degradation** — un-indexed files get stale data message, malformed results are skipped with warnings
6. **GitHub round-trip** — enriched SARIF can be uploaded to GitHub Code Scanning without errors
7. **Both versions accepted** — SARIF 2.0 and 2.1.0 inputs both work

---

## Future Work (Roadmapped)

- **Cross-run analysis (Phase 85.1, highly recommended)** — When multiple tools flag the same file, synthesize: "convergent signals from ruff + semgrep on a critical hub file." This multiplies the value of multi-tool SARIF.
- **GitHub App integration** — Auto-enrich Code Scanning results on push. CoDRAG runs as a GitHub App, watches for new SARIF uploads, enriches them, and posts enriched results back. Out of scope for Phase 85 but a natural extension.
- **SARIF export from structural mode** — `codrag_audit()` (no findings) could optionally export its structural findings as SARIF, making CoDRAG a SARIF producer as well as consumer.

---

## Resolved Questions

1. **SARIF version support** — Accept both 2.0 and 2.1.0, always emit 2.1.0.
2. **Multi-run SARIF** — Independent per run for V1. Cross-referencing is highly recommended future work (Phase 85.1).
3. **SARIF output for simple schema input** — Yes. Auto-detect input format, allow `output_format="sarif"` to force SARIF output.
4. **GitHub App integration** — Out of scope, noted as future direction.
5. **Size limits** — 5MB / 1000 results cap, documented clearly.
