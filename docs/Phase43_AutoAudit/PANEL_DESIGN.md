# AutoAudit Panel Design — Refined Vision

## The Problem With V1

The first panel iteration hides information behind dropdowns and collapsibles.
The findings are raw analyzer output — technically correct but not actionable.
Compare with the refactor2/ docs: 8 flat markdown files, each with clear
headers, tables, code snippets, and concrete next steps. That's the bar.

## The Goal

**Both human-readable AND AI-actionable.** The user reads the audit, checks
the items they want to address, and sends them to the AI with one command.
The AI gets both the audit instructions AND the trace graph context (from
CoDRAG's normal MCP context) in a single call.

## Panel Layout: Flat Tabs

Instead of hiding findings in dropdowns, the panel uses **flat tabs** — one
per audit section, matching the structure of the refactor2 docs:

```
┌─────────────────────────────────────────────────────────────────┐
│  Codebase Audit  [A]   Run Audit ▶   Full Report ▶   Copy MCP  │
├─────────────────────────────────────────────────────────────────┤
│  Summary │ Architecture │ Quality │ Coverage │ Tech Debt │ Reports│
│ ━━━━━━━━━                                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ☐  GAP-1: LLMClient misplaced in augmenter.py                │
│     P0 · Critical · Small effort                                │
│     augmenter.py → 5 modules depend on it                       │
│     Action: Extract to core/llm_client.py                       │
│                                                                 │
│  ☐  GAP-2: Duplicate analyzer dispatch in TraceBuilder          │
│     P1 · Medium · Small effort                                  │
│     trace.py lines 1148-1255                                    │
│     Action: Extract _get_analyzer() + _collect_result()         │
│                                                                 │
│  ☑  GAP-3: Query preprocessing in wrong layer                   │
│     P3 · Low · Small effort                                     │
│     projects.py → core/query.py                                 │
│     Action: Move to core/query.py                               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  2 selected · [Send to AI ▶] codrag_audit_refactor              │
└─────────────────────────────────────────────────────────────────┘
```

### Tab Structure

| Tab | Content | Refactor2 Equivalent |
|-----|---------|---------------------|
| **Summary** | Health grade, severity bar, top 5 findings, module status table | `01_large_files_audit.md` |
| **Architecture** | Import graph issues, circular deps, hub bottlenecks, boundary violations | `02_architectural_optimizations.md` |
| **Quality** | Dead code, duplicate logic, naming, staleness | `06_gap_analysis.md` |
| **Coverage** | Test coverage map, API surface gaps | (new) |
| **Tech Debt** | Per-module debt items from epistemic enrichment | (new) |
| **Reports** | Generated markdown reports (Tier 2 synthesis) | `05_annotated_refactor_plan.md` |

### Finding Card Layout (Flat, Not Collapsed)

Each finding is **always visible** — no click to expand. The card shows:

```
☐  [P0] [Critical] [Small]  Title of the finding
   Files: path/to/file.py, path/to/other.py
   Problem: One-sentence description of what's wrong.
   Action: One-sentence concrete next step.
```

- **Checkbox** — user selects which to send to AI
- **Priority badge** — P0/P1/P2/P3/P4
- **Severity badge** — Critical/Warning/Info/Suggestion  
- **Effort badge** — Small/Medium/Large
- **Always-visible** description + action (no expand/collapse)

### Bottom Action Bar

When ≥1 finding is checked:
```
  3 selected · [Send to AI ▶] codrag_audit_refactor · [Copy List] · [Clear]
```

- **Send to AI** — copies `codrag_audit_refactor` with the selected finding IDs
  as context. The AI calls this MCP tool, gets the findings + trace context,
  and starts implementing.
- **Copy List** — copies selected findings as markdown (for pasting into a chat)
- **Clear** — unchecks all

## MCP Tools: Actionable Commands

### `codrag_audit` (existing — enhanced)
Returns the full findings list with priority/effort/severity.
AI can read and summarize.

### `codrag_audit_refactor` (NEW)
**The key innovation.** When called with finding IDs, returns:
1. The selected findings with full detail (problem + files + action)
2. Trace context for the affected files (via normal CoDRAG context assembly)
3. Structured instructions the AI can follow

```json
{
  "name": "codrag_audit_refactor",
  "description": "Get specific audit findings with trace context for implementation. The user has selected which findings to address. Each finding includes affected files, the problem, and the concrete action. CoDRAG automatically includes relevant code context from the trace graph for the affected files.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "finding_ids": {
        "type": "array",
        "items": { "type": "string" },
        "description": "IDs of the findings to address (from codrag_audit)"
      },
      "instructions": {
        "type": "string",
        "description": "Optional additional instructions from the user"
      }
    }
  }
}
```

**Response shape:**
```
## Audit Findings to Address

### GAP-1: LLMClient misplaced in augmenter.py [P0 · Critical]
**Problem:** LLMClient is a general-purpose HTTP client trapped in augmenter.py...
**Files:** augmenter.py, cluster.py, epistemic_enrichment.py, inferred_edges.py
**Action:** Extract to core/llm_client.py. Update all imports.

### GAP-2: Duplicate analyzer dispatch [P1 · Medium]
**Problem:** TraceBuilder.build() has 4 identical code blocks...
**Files:** trace.py
**Action:** Extract _get_analyzer() and _collect_analyzer_result() methods.

---

## Relevant Code Context
[CoDRAG trace-expanded context for the affected files]
```

### `codrag_audit_check` (NEW)
After the AI makes changes, the user can re-run specific checks:
```json
{
  "name": "codrag_audit_check",
  "description": "Re-run specific audit analyzers to verify fixes. Returns only findings from the specified analyzers, so you can confirm a fix resolved the issue.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "analyzers": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Analyzer names to re-run: large_files, circular_deps, misplaced_imports, etc."
      }
    }
  }
}
```

## Deeper Synthesis (Tier 2 Enhancement)

The current Tier 2 synthesizer produces generic summaries. The enhanced version
should produce **refactor2-quality documents** — each section should have:

1. **Numbered items** (GAP-1, GAP-2) with stable IDs
2. **Priority + effort + severity** on every item
3. **Concrete file paths and line numbers**
4. **Code snippets** showing the before state
5. **Explicit resolution steps** (not vague "consider refactoring")
6. **Priority ranking table** at the bottom

The LLM prompt should reference the refactor2 docs as the style guide.
