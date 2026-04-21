# Phase 85: SARIF Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SARIF 2.1.0 ingestion to `prep_audit` enrichment mode so external SARIF findings get enriched with Prep structural context and returned as valid SARIF.

**Architecture:** New `sarif.py` module parses SARIF input, converts to internal finding format (reusing Phase 83's enrichment pipeline), then converts enriched findings back to SARIF with Prep context in property bags. Auto-detection in MCP dispatch determines whether input is SARIF or simple schema. Tool-specific adapters customize enrichment emphasis per source tool.

**Tech Stack:** Python 3.11, JSON parsing, existing enrichment engine.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/prep/core/sarif.py` | **Create** | SARIF parser, validator, converter (SARIF→simple, enriched→SARIF) |
| `src/prep/core/sarif_adapters.py` | **Create** | Tool-specific enrichment adapters (semgrep, ruff, codeql, etc.) |
| `src/prep/core/enrichment.py` | **Modify** | Add `enrich_sarif()` orchestrator that wraps parse→enrich→emit |
| `src/prep/mcp/server.py` | **Modify** | Auto-detect SARIF in `tool_audit_enrich`, add `output_format` param |
| `src/prep/mcp_tools.py` | **Modify** | Add `output_format` param to prep_audit schema |
| `tests/test_sarif.py` | **Create** | Tests for SARIF parsing, enrichment output, round-trip |
| `tests/test_sarif_adapters.py` | **Create** | Tests for tool-specific adapters |

---

### Task 1: SARIF Parser and Converter

**Files:**
- Create: `src/prep/core/sarif.py`
- Create: `tests/test_sarif.py`

Core module with three responsibilities:
1. `parse_sarif(data)` — validate and extract findings from SARIF JSON
2. `sarif_to_simple(sarif_data)` — convert SARIF results to simple schema for enrichment pipeline
3. `enriched_to_sarif(original_sarif, enriched_findings, summary)` — inject Prep property bags into SARIF output

### Task 2: Tool-Specific Adapters

**Files:**
- Create: `src/prep/core/sarif_adapters.py`
- Create: `tests/test_sarif_adapters.py`

Detect source tool from `runs[].tool.driver.name` and customize recommendation emphasis.

### Task 3: Enrich SARIF Orchestrator

**Files:**
- Modify: `src/prep/core/enrichment.py`

Add `enrich_sarif()` that orchestrates: detect SARIF → parse → convert to simple → enrich → convert back to SARIF.

### Task 4: MCP Integration

**Files:**
- Modify: `src/prep/mcp_tools.py`
- Modify: `src/prep/mcp/server.py`

Auto-detect SARIF input and add `output_format` parameter.

### Task 5: Integration Tests

End-to-end test with realistic SARIF input.

---
