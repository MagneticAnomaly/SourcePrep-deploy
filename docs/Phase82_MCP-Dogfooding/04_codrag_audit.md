# 04 — `codrag_audit` Tool (Codebase Health)

**Grade: B-**
**Calls tested:** 2 (scan, report ARCHITECTURE_ANALYSIS)

## What Works Well

### Real architectural issues surfaced
The scan correctly identified:
- **Circular dependency** between `queue.py` and `events.py` — a genuine code smell
- **High cross-module coupling** between LLM orchestration and UI (17 imports) — real architectural concern
- **Dependency bottlenecks** on `utils.ts` and `api/react.tsx` — these are actual pain points

### Report system provides depth
The 5 available reports (ARCHITECTURE_ANALYSIS, AUDIT_SUMMARY, COMPONENT_INVENTORY, GAP_ANALYSIS, TECH_DEBT_REPORT) offer drill-down beyond the scan summary. Having structured reports for different audiences is good product design.

### Finding format is consistent
Every finding has severity, description, file paths, and suggested action. The structured format makes it parseable by agents.

---

## Issues Found

### ISSUE 1: Severity inflation — lock files flagged as "critical" (HIGH)

**Scan result:** 32 "critical" findings. The top 3 by size:
1. `package-lock.json` (~17,177 lines) — CRITICAL
2. `packages/ui/package-lock.json` (~15,353 lines) — CRITICAL
3. `docs/Phase13_Storybook/theme-examples/tremor-preview/package-lock.json` (~2,919 lines) — CRITICAL

Also flagged: `logs/overnight_2026-02-21.json` (a log file) as CRITICAL.

**Remediation advice for all:** "Consider splitting into a subpackage with focused modules."

You cannot split a `package-lock.json` into subpackages. It's an auto-generated dependency manifest. Flagging it as "critical" and suggesting architectural remediation is actively misleading.

**Root cause:** `src/codrag/core/audit/analyzers/large_files.py`

The `LargeFileAnalyzer` uses byte thresholds (lines 12-13):
- CRITICAL_BYTES = 80,000 (~2000 lines)
- WARNING_BYTES = 40,000 (~1000 lines)

There IS an exclusion list (`EXPECTED_LARGE_BASENAMES`, lines 20-35) that includes `package-lock.json`, `yarn.lock`, etc. But the exclusion may not be working correctly for all paths, or the scan is running before the exclusion filter is applied.

**Suggested fix:**
1. Verify the `EXPECTED_LARGE_BASENAMES` exclusion is actually applied before severity assignment
2. Add exclusions for: log files (`*.log`, `logs/*.json`), generated `.d.ts` bundles, vendor directories
3. Consider a separate "informational" category for files that are large by design (lock files, generated code)
4. The remediation text should be context-aware: large lock files get "This is expected — consider adding to .gitignore if not tracked" instead of "split into subpackages"

**Code pointers:**
- `src/codrag/core/audit/analyzers/large_files.py:12-13` — threshold constants
- `src/codrag/core/audit/analyzers/large_files.py:20-35` — EXPECTED_LARGE_BASENAMES list
- `src/codrag/core/audit/analyzers/large_files.py:62-71` — exclusion logic
- `src/codrag/core/audit/analyzers/large_files.py:76-81` — severity assignment
- `src/codrag/core/audit/analyzers/large_files.py:91-99` — remediation text templates

---

### ISSUE 2: Duplicate bottleneck findings inflate critical count (HIGH)

**Scan result:** `packages/ui/src/api/react.tsx` appears in 6 separate critical findings:
1. "imported by module:ui:684"
2. "imported by module:react:555"
3. "imported by module:search:2221"
4. "imported by module:ui:685"
5. "imported by module:ui:678:build-artifact:210"
6. "imported by module:architecture-visualization:3959"

Each has the same remediation: "Extract shared code from packages/ui/src/api/react.tsx into a dedicated module."

This is one issue (react.tsx is a bottleneck) reported 6 times (once per consuming module). It inflates the "32 critical" count and makes the audit feel noisy.

**Root cause:** `src/codrag/core/audit/analyzers/misplaced_imports.py`

The analyzer (lines 58-105) groups cross-module import edges by pair key `f"{src_module}->{tgt_module}"` (line 51). When a single file accounts for >60% of imports in a pair, it creates one finding per pair. Since 6 different modules import `react.tsx`, you get 6 findings.

The dedup unit is "module pair relationship," not "bottleneck file." This is architecturally reasonable (each module has an independent coupling problem) but produces terrible UX when 6 findings all say the same thing.

**Suggested fix:**
1. Group findings by bottleneck file in the output: "react.tsx is a bottleneck for 6 modules: [list]" → 1 finding instead of 6
2. Keep the per-module findings in the raw data but show the grouped version in the MCP response
3. Add a dedup pass in the MCP tool handler that merges findings with identical `suggested_action` text and overlapping file paths

**Code pointers:**
- `src/codrag/core/audit/analyzers/misplaced_imports.py:51` — pair key generation
- `src/codrag/core/audit/analyzers/misplaced_imports.py:82-105` — per-pair finding creation
- `src/codrag/mcp/server.py:1754-1841` — tool_audit MCP handler (where dedup could be added)

---

### ISSUE 3: Generic remediation text provides no real guidance (MEDIUM)

Every bottleneck finding gets: "Extract shared code from {file} into a dedicated module that both '{module_a}' and '{module_b}' can depend on cleanly."

This is unhelpful because:
- For `utils.ts` → extracting shared utilities is reasonable advice
- For `Button.tsx` → "extract Button into a dedicated module" makes no sense; it IS a dedicated component
- For `react.tsx` (API client hooks) → the fix is likely "import specific hooks, not the whole module" or "code-split the API layer," not "extract into a module"

**Root cause:** `src/codrag/core/audit/analyzers/misplaced_imports.py:101-104`

The `suggested_action` is a single f-string template applied to all bottleneck findings regardless of file type or purpose.

**Suggested fix:**
1. Add file-type-aware remediation templates:
   - Utility files (`utils.*`): "Consider splitting utility functions into domain-specific modules"
   - API clients (`api/*`): "Consider importing specific functions instead of the barrel export"
   - Components (`components/*`): "This component has high fan-in; verify it's correctly scoped"
2. Or: use the LLM synthesizer to generate context-aware remediation (the infrastructure exists in `synthesizer.py`)

---

### ISSUE 4: 100 findings with no grouping or prioritization (MEDIUM)

The scan returned "100 findings" with severity counts: critical: 32, info: 66, warning: 2. The MCP response showed 15 of these. How were the 15 selected? What about the other 85?

There's no grouping (by file, by module, by issue type), no prioritization ("fix these 3 first for maximum impact"), and no way to paginate or filter within the MCP response.

**Suggested fix:**
1. Group findings by category in the MCP response: "Size (8 findings) | Architecture (12 findings) | Quality (4 findings)"
2. Show only the top 10 most impactful findings by default, with a note: "85 more findings available — use `category` parameter to filter"
3. Add a `top_n` parameter to the scan action
4. Consider a single "executive summary" line: "The biggest issue is coupling between LLM orchestration and UI (17 cross-module imports). The 2 circular dependencies should be fixed first."

---

### ISSUE 5: ARCHITECTURE_ANALYSIS report is purely structural (LOW)

The report returned "Generated structurally (LLM unavailable)" — 977 findings dominated by large file warnings. When the LLM is unavailable, the fallback is just a sorted list of file sizes. This provides almost no architectural insight.

**Root cause:** `src/codrag/core/audit/synthesizer.py:266-301` — `_structural_fallback()` creates a plain text document from raw findings when LLM generation fails.

**Suggested fix:**
1. The structural fallback should at least group findings by type and provide summary statistics, not just list them
2. Consider caching LLM-generated reports and serving the cache when LLM is unavailable
3. Add a note to the MCP response: "This report was generated without LLM analysis — results are limited to structural metrics"

---

## Opportunities

### OPPORTUNITY 1: "What should I fix first?" action
A `codrag_audit(action="prioritize")` that returns the top 3 highest-impact, lowest-effort fixes would be immediately actionable. The data exists — circular deps are low-effort/high-impact, bottleneck dedup is medium-effort/high-impact, large lock files are no-effort/no-impact.

### OPPORTUNITY 2: Audit diff between runs
"What got worse since last audit?" would help agents track whether their changes improved or degraded codebase health. Store audit snapshots and compare.

### OPPORTUNITY 3: Module-scoped auditing
`codrag_audit(scope="src/codrag/mcp/")` — audit only the MCP module. Currently the scan is global, which produces findings across the entire codebase when the agent only cares about their working area.
