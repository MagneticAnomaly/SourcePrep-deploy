# Phase 96 — MCP Dogfooding Findings from External Project Testing

**Date:** 2026-04-14
**Source:** Live MCP tool testing against PowerMateReborn (24-file Swift project, full pipeline with concepts + antibodies + Tier 2 audit reports). Additional context from prior Haley/LinuxBrain testing.
**Pipeline:** Finalize group completed. Atlas (LLM mode, kimi-k2.5:cloud), concepts (133 created), audit (62 findings, Tier 2 parallel with 5 docs), antibodies (47 derived). Python engine backend. 7.4 minutes.

---

## Finding Index

| ID | Title | Severity | Category | Status |
|----|-------|----------|----------|--------|
| MCP-01 | AntibodyStore not initialized — `codrag_audit(action="antibodies")` returns error | HIGH | MCP Wiring | Related to F-37, may be regression or incomplete fix |
| MCP-02 | Structural audit missing import cycles — reads legacy audit findings instead of trace graph | HIGH | MCP Retrieval | NEW |
| MCP-03 | Impact graph empty for Swift files — Python engine doesn't resolve Swift imports | HIGH | Pipeline/Parser | NEW |
| MCP-04 | Hub-files API field name mismatch (`path` vs `file_path`) may cause empty hub list on some projects | HIGH | MCP Wiring | NEW — needs verification |
| MCP-05 | Symbol search missing signatures/docstrings for non-Python languages | MEDIUM | Pipeline/Parser | NEW |
| MCP-06 | Audit health grade may not account for project scale (24 files gets same rubric as 2700 files) | LOW | Audit Quality | NEW — research question |
| MCP-07 | Concept seeding produces "seed" status concepts that aren't surfaced by default ambient context | LOW | UX/Product | NEW |
| MCP-08 | Audit report flags 11 files as "potentially orphaned" that are actually core source files | MEDIUM | Audit Quality | NEW |
| MCP-09 | "Batch synthesis failed" modules from older clustering runs persist in module summaries | LOW | Pipeline Data | Matches F-32 |
| MCP-10 | Hub count (52) vs impact dependents count (3) discrepancy for same file | LOW | UX Confusion | NEW |

---

## MCP-01: AntibodyStore Not Initialized

**Severity:** HIGH
**Category:** MCP Wiring
**Symptom:**
```
codrag_audit(action="antibodies")
→ Error: AntibodyStore not initialized. Call antibody_store.init(db_path) first.
```

**Context:** The pipeline successfully derived 47 antibodies from the 133 concepts (confirmed in `pipeline_run_metadata.json`: `"derived": 47, "saved": 47`). The antibody data exists on disk. But the MCP server can't access it because the store singleton wasn't initialized for this project.

**Relationship to F-37:** F-37 documented this exact issue — `antibody_store.init()` was never called, causing saves to silently fail at DEBUG level. F-37 was marked ✅ FIXED. However, the error is still occurring on PowerMateReborn as of 2026-04-14.

**Possible causes:**
1. F-37 fix was for the pipeline worker (saves succeed now — confirmed by the metadata), but the MCP server initialization path was not updated. The MCP server needs to call `antibody_store.init(db_path)` during project resolution, which may not be happening for embedded-mode projects.
2. The antibody store DB path for embedded projects (`.prep/antibodies.db` or similar) may not be resolved correctly by the MCP server's project resolver.
3. The fix in F-37 may have been for the daemon's own antibody store instance, but the MCP server runs in a separate process (stdio mode) and needs its own initialization.

**Research tasks:**
- [ ] Grep for `antibody_store.init` in `src/codrag/mcp/server.py` — is it called during `_resolve_project_id()`?
- [ ] Check what DB path the pipeline uses vs what the MCP server would use for embedded-mode projects
- [ ] Verify F-37 fix scope: did it cover the MCP server path or only the pipeline worker path?

**Expected fix:** Add `antibody_store.init(db_path)` in the MCP server's project initialization, similar to how `concept_store` and `observation_store` are initialized. The DB path should be `{project_index_dir}/antibodies.db` for embedded projects.

---

## MCP-02: Structural Audit Missing Import Cycles

**Severity:** HIGH
**Category:** MCP Retrieval
**Symptom:** `codrag_audit(action="scan")` returns coupling hotspots but zero import cycle findings, despite the atlas identifying 71 cycles (Haley) or the pipeline processing import data.

**Root cause:** The structural scanner in `src/codrag/core/audit/structural.py` receives cycles from its `ctx` dict. The MCP handler `tool_audit_structural()` in `server.py:1928-1944` populates cycles by calling:

```python
GET /projects/{project_id}/audit/findings?limit=500
# Then filters: f.get("analyzer") == "circular_deps"
```

This reads from the **legacy AutoAudit findings store** — the Tier 1 analyzer pipeline that runs as `POST /projects/{id}/audit`. For embedded-mode projects (like PowerMateReborn and Haley), the legacy audit may have run during the pipeline finalize stage but stores its findings in a different format or location than what the MCP handler expects.

Meanwhile, the atlas structural analysis detects cycles directly from the trace graph during atlas generation and stores them in `atlas.json`. These two data sources are disconnected.

**Evidence from PowerMateReborn:** The pipeline ran an audit stage that produced 62 findings. But the structural scanner's cycle query reads from `GET /audit/findings` looking for `analyzer == "circular_deps"`. If the finalize-stage audit didn't produce findings with that exact analyzer name, the cycle list is empty.

**Evidence from Haley:** The atlas reported 71 import cycles. `codrag_audit(action="scan")` returned 0 cycle findings. Same pattern.

**Research tasks:**
- [ ] What analyzer names does the finalize-stage audit produce? Are any of them `"circular_deps"`?
- [ ] Does `GET /projects/{id}/audit/findings` return the 62 findings from the finalize stage for PowerMateReborn?
- [ ] Does the atlas store its cycle data in a queryable format (e.g., `atlas.json` cycles field)?
- [ ] Consider: should the structural scanner run its OWN lightweight cycle detection on the trace graph rather than depending on a separate audit run?

**Expected fix:** Either:
1. Have `tool_audit_structural()` read cycles from the atlas data (already computed, stored in `atlas.json`) as a fallback when legacy audit findings are empty
2. Or: add inline cycle detection to `structural.py` that traverses the trace graph directly (similar to what `atlas/generator.py` does)
3. Or: ensure the finalize-stage audit produces findings with `analyzer == "circular_deps"` that the MCP handler can find

---

## MCP-03: Impact Graph Empty for Swift Files

**Severity:** HIGH
**Category:** Pipeline/Parser
**Symptom:** `codrag_impact(file_path="Sources/PowerMateManager.swift", direction="all")` returns 1 node, 0 edges. PowerMateManager is the central orchestrator that imports from both transport files, the gesture engine, and is used by AppDelegate.

**Meanwhile**, `codrag_impact(file_path="Sources/AppDelegate.swift", direction="dependents")` correctly returns 3 dependents. And the structural audit found AppDelegate has 52 incoming dependencies.

**Root cause:** The pipeline ran with `"engine_backend": "python"`. CoDRAG's Rust parser (`codrag-parser`) has tree-sitter grammars for Python and TypeScript. For Swift files, the Python-fallback parser is used, which does text-based import inference (regex matching `import X` statements) rather than AST-based extraction.

Swift uses `import Foundation`, `import IOKit`, `import CoreBluetooth` — all framework imports, not file-to-file imports. The internal file-to-file dependencies (PowerMateManager uses PowerMateUSBTransport, PowerMateGestureEngine, etc.) are established through **type references** (e.g., `class PowerMateManager` has a property of type `PowerMateUSBTransport`), not through `import` statements. Swift files in the same module don't need to import each other.

This means the trace graph for Swift has:
- Framework import edges (import Foundation, import IOKit) → mapped to external nodes
- Some reference edges from text matching (AppDelegate mentioning other file names in code)
- But **no file-to-file import edges** because Swift's module system doesn't require them

AppDelegate has edges because it's referenced by name in many places (text-matching produces reference edges). PowerMateManager has fewer textual references, so its edges are sparse.

**This is a fundamental language limitation, not a bug.** For Swift (and similar languages like Go, Kotlin, Java with packages), file-to-file dependencies are implicit through the type system, not explicit through import statements.

**Research tasks:**
- [ ] Confirm: what edge types exist for PowerMateManager.swift in the trace graph? (Check via `GET /trace/neighbors?node_id=file:Sources/PowerMateManager.swift`)
- [ ] Does the LLM-inferred edges stage (Stage 2) add any edges for Swift files? If so, why are they missing?
- [ ] Consider: for languages without file-level imports, should the indexer use type-reference analysis to infer edges? (e.g., "PowerMateManager has a property of type PowerMateUSBTransport → edge from Manager to USBTransport")

**Possible improvements:**
1. **Short-term:** Use the LLM inferred-edges stage more aggressively for non-Python/TS files — prompt the model to identify type references and delegate patterns
2. **Medium-term:** Add tree-sitter-swift grammar to the Rust parser for actual AST-level type resolution
3. **Long-term:** Implement a type-reference edge inference pass that works across languages (scan for class/protocol names defined in other files)

---

## MCP-04: Hub-Files API Field Name Mismatch

**Severity:** HIGH
**Category:** MCP Wiring
**Symptom:** Structural audit may receive an empty hub file list due to API response key mismatch.

**Evidence:** The trace hub-files API at `src/codrag/api/routers/trace_routes/query.py:624` returns:
```python
{"hub_files": [{"path": p, "in_degree": d} for p, d in hubs]}
```

The MCP handler at `server.py:1921` reads:
```python
fp = hf.get("file_path", "")   # reads "file_path"
deg = hf.get("in_degree", 0)
```

The API returns `"path"`, the handler reads `"file_path"`. If this mismatch is real (not resolved by an intermediate layer), then `fp` is always empty string, and every hub file is silently dropped.

**However:** The structural audit DID find AppDelegate as a coupling hotspot with 52 dependencies on PowerMateReborn. This means hub_files data IS reaching the scanner for at least some cases. Possible explanations:
1. There's a middleware or envelope layer that normalizes `"path"` to `"file_path"` in the response
2. The hub-files API was updated to return `"file_path"` since my last code reading (I was reading from the stale worktree)
3. There's a different code path for embedded-mode projects that returns the correct field name

**Research tasks:**
- [ ] Read the CURRENT `server.py` hub_files parsing code on main (not the worktree copy)
- [ ] Read the CURRENT trace hub-files API endpoint to verify the field name
- [ ] If there IS a mismatch: why does AppDelegate still show up? There may be a secondary data path

---

## MCP-05: Symbol Search Missing Signatures for Non-Python Languages

**Severity:** MEDIUM
**Category:** Pipeline/Parser
**Symptom:** `codrag_search(query="PowerMateTransport", type="symbol")` returns:
```
- `PowerMateTransport` (symbol) @ `Sources/PowerMateManager.swift`:27
- `PowerMateTransportDelegate` (symbol) @ `Sources/PowerMateManager.swift`:19
```

Line numbers and qualified names are present (Phase 83 fix working). But no protocol definition body, no method signatures, no docstrings.

For comparison, Haley's Python symbols now include docstring excerpts:
```
- `PersonaMemoryStore._score_memory_with_relevance` @ store.py:717
    Score memory for retrieval with pre-computed relevance.
    Phase 72 scoring formula (with epistemic):
    combined = 0.35*relevance + 0.25*epistemic + ...
```

**Root cause:** The Phase 83 symbol formatter reads `n.get("signature")` and `n.get("docstring")` from trace node metadata. For Python, the parser (or enrichment stage) populates these fields from the AST. For Swift, the parser is text-based and doesn't extract protocol declarations, method signatures, or documentation comments.

**This is the same language limitation as MCP-03.** The Rust parser handles Python/TypeScript; other languages get text-based fallback that doesn't extract structured metadata.

**Research tasks:**
- [ ] For Haley's Python files: where exactly do `signature` and `docstring` get populated? In the Rust parser? In the Python enrichment? In the deep enrichment LLM stage?
- [ ] Could the LLM deep enrichment stage be enhanced to extract signatures for non-Python languages?
- [ ] Consider: add a `/// Swift doc comment` extraction regex to the Python-fallback parser

---

## MCP-06: Audit Health Grade May Not Account for Project Scale

**Severity:** LOW (research question)
**Category:** Audit Quality
**Symptom:** PowerMateReborn (24 files, well-structured) received a health grade of **C**. The audit report justification:

> "Zero critical defects and a well-defined four-layer architecture are offset by a 1,253-line god class in AppDelegate.swift, heavy reliance on undocumented macOS private APIs in hardware drivers, and 11 files flagged as potentially orphaned."

**Question: Is grade C fair for a 24-file project?**

Arguments that C is too harsh:
- A 1,253-line AppDelegate is normal for a macOS menu-bar app — it's the NSApplicationDelegate which inherently centralizes lifecycle and menu management. Calling it a "god class" applies web-app patterns to a desktop app where a single coordinator is the expected architecture.
- "11 files potentially orphaned" is 11 of 24 files — but these ARE the core source files (BrightnessController, DDCController, MIDIController, etc.). They're not orphaned; they're used via Swift's implicit module system which CoDRAG can't parse. This is a false finding from the parser limitation.
- "Reliance on undocumented private APIs" is a correct observation but it's inherent to the project's purpose — you can't control external monitor brightness on macOS without private APIs. It's a conscious design choice, not technical debt.

Arguments that C is fair:
- A god class is still a maintainability risk regardless of platform conventions
- Private API usage IS a real stability risk (Apple can break it any time)
- The project genuinely does have architectural concerns

**Root cause:** The Tier 2 LLM synthesis prompt likely doesn't receive project context about language conventions. A macOS Swift app has different "normal" than a Python microservice. The grading rubric appears to be language/platform-agnostic.

**Research tasks:**
- [ ] Read the Tier 2 audit synthesis prompts — do they receive language/platform context?
- [ ] Consider: should the audit grade be calibrated by project size? (A 24-file project with 1 large coordinator is fundamentally different from a 1000-file project with 10 large files)
- [ ] Consider: should the "potentially orphaned" finding be suppressed or downgraded for languages where CoDRAG can't resolve imports?
- [ ] The 11 "orphaned" files account for nearly half the total findings. If these are false positives (parser limitation), the grade would likely be B or B+ without them

---

## MCP-07: Seed Concepts Not Surfaced in Ambient Context

**Severity:** LOW
**Category:** UX/Product
**Symptom:** 133 concepts were created, all with status "seed". The `codrag` ambient response shows:
```
[Concepts: 0 active, 133 seeds — architecture: 25, constraint: 22, decision: 22, product: 18, +6 more. Use codrag_concepts to explore.]
```

The concepts are accessible via `codrag_concepts(action="get")` and appear in search results as cross-references. But the ambient context says "0 active" which suggests concepts need to be promoted from "seed" to "active" before they fully participate in all tool responses.

**Question:** Is the seed → active promotion workflow documented? Is it manual (human reviews and promotes) or automatic (seeds become active after N days or N citations)?

**Research tasks:**
- [ ] What is the concept lifecycle: seed → active → archived?
- [ ] How does a seed get promoted to active?
- [ ] Should the ambient context show a summary of seed concepts (even if brief) since they may be the only concepts available?
- [ ] The search tool DOES inject concepts regardless of status — verify this is intentional

---

## MCP-08: Audit Report Flags Core Source Files as Orphaned

**Severity:** MEDIUM
**Category:** Audit Quality
**Symptom:** The AUDIT_SUMMARY report lists 11 files as "potentially orphaned":
```
Sources/BrightnessController.swift, Sources/DDCController.swift, 
Sources/CustomModeEngine.swift, Sources/CustomModeSettingsView.swift, 
Sources/MIDIController.swift, Sources/MenuBarIcon.swift, 
Sources/OSCController.swift, Sources/OSDOverlay.swift, 
Sources/PowerMateBLETransport.swift, Sources/PowerMateUSBTransport.swift, 
Sources/VolumeController.swift
```

These are ALL core application files. They're flagged because the trace graph has no import edges pointing to them (Swift same-module files don't need imports). This is a false positive from MCP-03 (Swift import resolution gap).

**Impact:** This finding inflates the audit severity and likely contributed to the C grade. If removed, the audit would focus on the AppDelegate god-class and private API usage — both legitimate findings — and the grade would likely improve.

**The report does qualify the finding:** "verify whether these files are dead code or simply missing static import edges" — which shows self-awareness. But for an agent acting on the report, the qualification may not be strong enough.

**Research tasks:**
- [ ] Can the orphan detection be suppressed for languages where import resolution is known to be incomplete?
- [ ] Should the finding severity be downgraded from INFO to NOTE for non-Python/TS projects?
- [ ] Consider: check if the file is referenced in the atlas/module descriptions — if CoDRAG describes it as part of the architecture, it's clearly not orphaned

---

## MCP-09: Batch Synthesis Failure Persistence

**Severity:** LOW
**Category:** Pipeline Data
**Matches:** F-32

On Haley, ~15% of modules show "(Batch synthesis failed)" from an older clustering run. These persist because the module summaries aren't regenerated unless the clustering stage reruns.

Not observed on PowerMateReborn (fresh pipeline, no older data to carry forward). But this is a known issue for iteratively-built indexes where older clustering data persists.

---

## MCP-10: Hub Count vs Impact Dependents Discrepancy

**Severity:** LOW
**Category:** UX Confusion
**Symptom:** The structural audit says "AppDelegate.swift has 52 incoming dependencies" but `codrag_impact(direction="dependents")` returns only 3.

**Explanation:** The 52 comes from the trace graph's total in-degree for the node, which includes ALL edge types: imports, references, calls, inferred, contains. The impact tool's dependents mode may only count `[calls]` and `[imports]` edges, filtering out reference and inferred edges.

Both numbers are "correct" but they measure different things. For an agent, seeing "52 dependencies" in the audit and then "3 dependents" in the impact tool is confusing.

**Research tasks:**
- [ ] Confirm: what edge types does each tool count?
- [ ] Consider: should the audit report specify the edge type breakdown? "52 incoming (3 imports/calls, 49 references)"
- [ ] Consider: should the impact tool accept an `edge_types` filter parameter?

---

## Summary

| Priority | ID | Issue | Fix Type |
|----------|-----|-------|----------|
| **P0** | MCP-01 | Antibody store not initialized in MCP | Wiring fix — init store on project resolution |
| **P0** | MCP-02 | Cycles missing from structural audit | Query trace graph directly instead of legacy findings |
| **P1** | MCP-03 | Empty graph for Swift files | Language support — add type-reference edge inference |
| **P1** | MCP-04 | Hub-files field name mismatch (verify) | One-line fix if confirmed |
| **P1** | MCP-08 | Core files flagged as orphaned (false positive) | Suppress orphan detection for non-Python/TS |
| **P2** | MCP-06 | Audit grade not scale-aware | Research — calibrate grading by project size/language |
| **P2** | MCP-05 | No Swift signatures in symbol search | Language support — extract from doc comments |
| **P2** | MCP-07 | Seed concepts vs active workflow | UX — document lifecycle, consider auto-promotion |
| **P3** | MCP-10 | Hub count vs dependents mismatch | UX — add edge type breakdown to audit |
| **P3** | MCP-09 | Stale batch synthesis failures | Known (F-32) |
